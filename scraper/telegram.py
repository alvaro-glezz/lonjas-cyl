"""Canal de Telegram de Lonjas CyL: publica un resumen cada vez que una lonja tiene sesión nueva.

  python scraper/telegram.py                 publica las sesiones nuevas (lo hace la tarea «Actualizar precios»)
  python scraper/telegram.py --configurar    conecta el robot que responde a los mensajes (tarea «Configurar Telegram»)

Necesita estos secretos (GitHub -> Settings -> Secrets and variables -> Actions). Sin ellos no hace nada:
  TELEGRAM_TOKEN    el token que da @BotFather al crear el robot
  TELEGRAM_CANAL    el canal, p. ej. @lonjascyl (el robot tiene que ser administrador del canal)
  TELEGRAM_SECRETO  (solo --configurar) clave que Telegram manda en cada mensaje al robot de Vercel; la misma
                    tiene que estar en Vercel como variable de entorno TELEGRAM_SECRETO
  TELEGRAM_URL      (solo --configurar) dirección de la app en Vercel, p. ej. https://lonjas-cyl-khaki.vercel.app

Guarda en data/telegram.json qué sesión de cada lonja se publicó ya, para no repetir.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, timedelta
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paginas import WEB, fecha_corta, num  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "precios.json"
ESTADO = RAIZ / "data" / "telegram.json"
API = "https://api.telegram.org/bot{token}/{metodo}"
DIAS_PRIMERA_VEZ = 3     # la primera vez solo se publican sesiones de los últimos 3 días
PRINCIPALES = ["trigo", "cebada", "maiz", "avena", "centeno", "triticale", "girasol", "alfalfa", "paja",
               "cerdo-normal", "cerdo-selecto", "lechones", "lechazo"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def flecha(p: dict) -> str:
    act, ant = p.get("act"), p.get("ant")
    if act is None or ant is None:
        return ""
    d = round(act - ant, 5)
    return "=" if d == 0 else ("▲ +" if d > 0 else "▼ −") + num(abs(d))


def linea(p: dict) -> str:
    return f"{escape(p['producto'], quote=False)}: <b>{num(p['act'])}</b> {escape(p.get('unidad', ''), quote=False)} {flecha(p)}".rstrip()


def mensaje_sesion(l: dict, web: str = WEB) -> str:
    """Resumen de una sesión: productos principales, lo que más se mueve, balance y enlaces."""
    con = [p for p in l.get("precios", []) if p.get("act") is not None]
    principales = sorted((p for p in con if p.get("clave") in PRINCIPALES), key=lambda p: PRINCIPALES.index(p["clave"]))[:8]
    vistos = {p["id"] for p in principales}
    movidos = sorted((p for p in con if p["id"] not in vistos and p.get("ant") not in (None, 0) and p["act"] != p["ant"]),
                     key=lambda p: -abs((p["act"] - p["ant"]) / p["ant"]))[:3]
    suben = sum(1 for p in con if p.get("ant") is not None and p["act"] > p["ant"])
    bajan = sum(1 for p in con if p.get("ant") is not None and p["act"] < p["ant"])
    iguales = sum(1 for p in con if p.get("ant") is not None and p["act"] == p["ant"])
    f = l.get("fecha") or ""
    dia = DIAS[date.fromisoformat(f).weekday()] if f else ""
    partes = [f"📊 <b>{escape(l.get('nombre', l['id']), quote=False)}</b> · sesión del {dia} {fecha_corta(f)}", ""]
    partes += [linea(p) for p in principales]
    if movidos:
        partes += ["", "<i>Lo que más se mueve</i>"] + [linea(p) for p in movidos]
    partes += ["", f"▲ {suben} suben · ▼ {bajan} bajan · = {iguales} repiten",
               f"Todos los precios: {web}lonja/{l['id']}/",
               f"Fuente: {escape(l.get('nota') or l.get('nombre', ''), quote=False)} · precios orientativos"]
    return "\n".join(partes)[:4000]


def pendientes(datos: dict, estado: dict, hoy: date) -> list[dict]:
    """Lonjas con una sesión que aún no se ha publicado en el canal."""
    pub = estado.get("publicado", {})
    limite = (hoy - timedelta(days=DIAS_PRIMERA_VEZ)).isoformat()
    out = []
    for l in datos.get("lonjas", []):
        f = l.get("fecha")
        if l.get("estado") == "suspendida" or not f or not any(p.get("act") is not None for p in l.get("precios", [])):
            continue
        if (l["id"] in pub and f > pub[l["id"]]) or (l["id"] not in pub and f >= limite):
            out.append(l)
    return sorted(out, key=lambda l: l["fecha"])


def llamar(token: str, metodo: str, cuerpo: dict) -> dict:
    import requests
    r = requests.post(API.format(token=token, metodo=metodo), json=cuerpo, timeout=20)
    j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not j.get("ok"):
        # Nunca se imprime el token: solo el método y la descripción del error de Telegram
        raise RuntimeError(f"Telegram {metodo}: {j.get('description') or r.status_code}")
    return j.get("result") or {}


def publicar(datos: dict, estado: dict, token: str, canal: str, hoy: date, llamar=llamar) -> list[str]:
    hechas = []
    for l in pendientes(datos, estado, hoy):
        llamar(token, "sendMessage", {"chat_id": canal, "text": mensaje_sesion(l), "parse_mode": "HTML",
                                      "disable_web_page_preview": True})
        estado.setdefault("publicado", {})[l["id"]] = l["fecha"]
        hechas.append(l["id"])
    return hechas


COMANDOS = [
    {"command": "trigo", "description": "Precio del trigo en cada lonja"},
    {"command": "cebada", "description": "Precio de la cebada en cada lonja"},
    {"command": "maiz", "description": "Precio del maíz en cada lonja"},
    {"command": "lechazo", "description": "Precio del lechazo en cada lonja"},
    {"command": "lonjas", "description": "Última sesión de cada lonja"},
    {"command": "ayuda", "description": "Qué puedo preguntar"},
]


def configurar(token: str, url: str, secreto: str, llamar=llamar) -> dict:
    if not re.fullmatch(r"https://[a-z0-9.-]+(:\d+)?/?", url or ""):
        raise ValueError("TELEGRAM_URL tiene que ser la dirección https de la app en Vercel, sin nada detrás")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", secreto or ""):
        raise ValueError("TELEGRAM_SECRETO: entre 16 y 256 letras, números, «_» o «-»")
    llamar(token, "setWebhook", {"url": url.rstrip("/") + "/api/telegram", "secret_token": secreto,
                                 "allowed_updates": ["message"], "drop_pending_updates": True})
    llamar(token, "setMyCommands", {"commands": COMANDOS})
    llamar(token, "setMyDescription", {"description": "Precios de las lonjas agropecuarias de Castilla y León (Salamanca, León, "
                                       "Segovia y Lerma). Escribe un producto (trigo, cebada, lechazo…) o una lonja."})
    llamar(token, "setMyShortDescription", {"short_description": "Precios de las lonjas de Castilla y León"})
    return llamar(token, "getWebhookInfo", {})


def main(argv: list[str]) -> int:
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if not token:
        print("[telegram] Sin configurar (falta el secreto TELEGRAM_TOKEN): no se publica nada.")
        return 1 if "--configurar" in argv else 0
    if "--configurar" in argv:
        info = configurar(token, os.environ.get("TELEGRAM_URL", "").strip(), os.environ.get("TELEGRAM_SECRETO", "").strip())
        print(f"[telegram] Robot conectado a {info.get('url')} · mensajes pendientes: {info.get('pending_update_count', 0)}"
              + (f" · último error: {info['last_error_message']}" if info.get("last_error_message") else ""))
        return 0
    canal = os.environ.get("TELEGRAM_CANAL", "").strip()
    if not canal:
        print("[telegram] Falta el secreto TELEGRAM_CANAL: no se publica nada.")
        return 0
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    estado = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.is_file() else {}
    try:
        hechas = publicar(datos, estado, token, canal, date.today())
    finally:
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[telegram] Publicadas: {', '.join(hechas) or 'ninguna sesión nueva'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

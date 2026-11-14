"""Avisos personales por Telegram: después de leer las lonjas, avisa a quien lo pidió al robot («/aviso trigo 240»).

Los avisos los guarda el robot de Telegram (api/telegram.js) en Upstash Redis:
  avisos:chats        conjunto con los chats que tienen avisos
  avisos:<chat>       lista JSON [{clave, lonja, dir, umbral, unidad, armado, creado}]
Un aviso suena cuando el precio CRUZA el umbral (armado -> sin armar) y se vuelve a armar cuando deja de cumplirse,
igual que los avisos de la app. Si alguien bloquea el robot, se borran sus avisos.

Secretos (GitHub -> Settings -> Secrets and variables -> Actions). Sin ellos no hace nada:
  TELEGRAM_TOKEN, UPSTASH_REDIS_REST_URL y UPSTASH_REDIS_REST_TOKEN (los mismos valores que Vercel)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paginas import fecha_corta, num  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "precios.json"
API = "https://api.telegram.org/bot{token}/{metodo}"
DIAS_RECIENTE = 21
NOMBRES = {"trigo": "Trigo", "cebada": "Cebada", "maiz": "Maíz", "avena": "Avena", "centeno": "Centeno",
           "triticale": "Triticale", "girasol": "Girasol", "alfalfa": "Alfalfa", "paja": "Paja", "cerdo-normal": "Cerdo normal",
           "cerdo-selecto": "Cerdo selecto", "cerdo-graso": "Cerdo graso", "cerda-extra": "Cerda extra",
           "lechones": "Lechones", "cochinillo": "Cochinillo sin hierro", "lechazo": "Lechazo"}


class Redis:
    """Cliente mínimo de la API REST de Upstash (un comando por petición)."""

    def __init__(self, url: str, token: str):
        import requests
        self.url, self.s = url.rstrip("/"), requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}"})

    def __call__(self, *args):
        r = self.s.post(self.url, json=list(args), timeout=20)
        j = r.json()
        if r.status_code != 200 or "error" in j:
            raise RuntimeError(f"Upstash {args[0]}: {j.get('error') or r.status_code}")
        return j.get("result")


def evaluar(a: dict, datos: dict, hoy: date) -> dict | None:
    """Precio que decide el aviso: la lonja elegida o, si no hay, la que más paga (sube) o la que menos (baja)."""
    filas = []
    for l in datos.get("lonjas", []):
        if l.get("estado") == "suspendida" or (a.get("lonja") and l["id"] != a["lonja"]) or not l.get("fecha"):
            continue
        if (hoy - date.fromisoformat(l["fecha"])).days > DIAS_RECIENTE:
            continue
        filas += [dict(p, lonja=l) for p in l.get("precios", [])
                  if p.get("clave") == a["clave"] and p.get("act") is not None and p.get("unidad") == a.get("unidad")]
    if not filas:
        return None
    f = (max if a["dir"] == "sube" else min)(filas, key=lambda p: p["act"])
    return {"fila": f, "cumple": f["act"] >= a["umbral"] if a["dir"] == "sube" else f["act"] <= a["umbral"]}


def mensaje(a: dict, n: int, e: dict) -> str:
    f, l = e["fila"], e["fila"]["lonja"]
    cond = f"{'subía a' if a['dir'] == 'sube' else 'bajaba a'} {num(a['umbral'])} {escape(a['unidad'], quote=False)}"
    return "\n".join([
        "🔔 <b>Aviso cumplido</b>",
        f"{escape(NOMBRES.get(a['clave'], a['clave']), quote=False)} en {escape(l.get('nombre', l['id']), quote=False)}: "
        f"<b>{num(f['act'])} {escape(f.get('unidad', ''), quote=False)}</b> (sesión del {fecha_corta(l['fecha'])}).",
        f"Pediste que te avisara si {cond}.",
        f"Te volveré a avisar si vuelve a cruzar ese precio. Borrarlo: /borrar {n}",
    ])


def revisar(datos: dict, avisos_por_chat: dict, hoy: date) -> tuple[list[tuple[str, str]], dict]:
    """Devuelve (mensajes [(chat, texto)], cambios {chat: {índice: armado}}). No toca nada fuera."""
    mensajes, cambios = [], {}
    for chat, lista in avisos_por_chat.items():
        for i, a in enumerate(lista):
            if not isinstance(a, dict) or a.get("dir") not in ("sube", "baja") or not isinstance(a.get("umbral"), (int, float)):
                continue
            e = evaluar(a, datos, hoy)
            if not e:
                continue
            armado = a.get("armado", True)
            if e["cumple"] and armado:
                mensajes.append((chat, mensaje(a, i + 1, e)))
                cambios.setdefault(chat, {})[i] = False
            elif not e["cumple"] and not armado:
                cambios.setdefault(chat, {})[i] = True        # vuelve a armarse para la próxima vez
    return mensajes, cambios


def audiencia(r, token: str, con_avisos: int) -> None:
    """Para el panel de estadísticas: miembros del canal y personas con avisos, una vez al día (el último valor manda)."""
    from zoneinfo import ZoneInfo
    from datetime import datetime
    from telegram import llamar
    dia = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    campos = ["tg:avisos", con_avisos]
    canal = os.environ.get("TELEGRAM_CANAL", "").strip()
    if canal:
        try:
            campos += ["tg:canal", int(llamar(token, "getChatMemberCount", {"chat_id": canal}))]
        except Exception as e:  # noqa: BLE001 - sin el número de miembros el resto sigue
            print(f"[avisos] no se pudo leer el número de miembros del canal: {type(e).__name__}")
    r("HSET", f"uso:d:{dia}", *campos)
    r("EXPIRE", f"uso:d:{dia}", 400 * 86400)


def bloqueado(error: Exception) -> bool:
    t = str(error).lower()
    return "blocked" in t or "chat not found" in t or "user is deactivated" in t


def main() -> int:
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    url = (os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL") or "").strip()
    clave = (os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or "").strip()
    if not (token and url.startswith("https://") and clave):
        print("[avisos] Sin configurar (faltan TELEGRAM_TOKEN o los secretos de Upstash): no se revisa nada.")
        return 0
    import requests
    from telegram import llamar
    r = Redis(url, clave)
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    chats = sorted(r("SMEMBERS", "avisos:chats") or [])
    avisos = {}
    for c in chats:
        try:
            l = json.loads(r("GET", f"avisos:{c}") or "[]")
            avisos[c] = l if isinstance(l, list) else []
        except json.JSONDecodeError:
            avisos[c] = []
    mensajes, cambios = revisar(datos, avisos, date.today())
    audiencia(r, token, len(chats))
    enviados = fallidos = 0
    for chat, texto in mensajes:
        try:
            llamar(token, "sendMessage", {"chat_id": int(chat), "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True})
            enviados += 1
        except (RuntimeError, requests.RequestException) as e:
            fallidos += 1
            cambios.pop(chat, None)                 # si no llegó, no se marca: se reintenta en la próxima pasada
            if bloqueado(e):
                r("DEL", f"avisos:{chat}")
                r("SREM", "avisos:chats", chat)
                print(f"[avisos] un usuario bloqueó el robot: se borran sus avisos")
    for chat, idx in cambios.items():
        # Se vuelve a leer justo antes de guardar por si el usuario ha cambiado sus avisos mientras tanto
        actual = json.loads(r("GET", f"avisos:{chat}") or "[]")
        for i, armado in idx.items():
            a = avisos[chat][i]
            for b in actual:
                if all(b.get(k) == a.get(k) for k in ("clave", "lonja", "dir", "umbral", "unidad", "creado")):
                    b["armado"] = armado
        r("SET", f"avisos:{chat}", json.dumps(actual, ensure_ascii=False))
    total = sum(len(v) for v in avisos.values())
    print(f"[avisos] {total} avisos de {len(chats)} personas · enviados {enviados}" + (f" · fallidos {fallidos}" if fallidos else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Recordatorios de plazos (data/plazos.json: PAC y seguros agrarios) en el canal de Telegram @lonjas_cyl.

Cada mañana mira los plazos y avisa cuando:
  · empieza hoy un plazo,
  · quedan 7 días o 1 día para que termine.
Sin estado guardado: si un día no se ejecuta, ese aviso se pierde (no se duplica nunca).

  python scraper/recordatorios.py [--fecha AAAA-MM-DD] [--todos] [--enviar canal|yo]
     --todos [--solo seguro]: aviso de prueba de cada plazo en curso, con su cuenta atrás real (aunque hoy no toque)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLAZOS = RAIZ / "data" / "plazos.json"
WEB = "https://lonjas-cyl-khaki.vercel.app/"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def larga(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def toca(p: dict, hoy: date) -> str | None:
    """Motivo del aviso de hoy para el plazo p, o None."""
    ini, fin = date.fromisoformat(p["inicio"]), date.fromisoformat(p["fin"])
    if hoy == ini and ini != fin:
        return "empieza"
    falta = (fin - hoy).days
    if ini <= hoy and falta in (7, 1):
        return f"quedan {falta}"
    return None


def mensaje(p: dict, motivo: str) -> str:
    seguro = p.get("tipo") == "seguro"
    tipo = "Seguro agrario" if seguro else "PAC"
    if motivo == "empieza":
        cab = f"🗓️ <b>Empieza hoy</b> · {tipo}"
        cuando = f"Hasta el {larga(p['fin'])}."
    else:
        n = int(motivo.split()[1])
        cab = f"⏳ <b>{'Mañana es el último día' if n == 1 else f'Quedan {n} días'}</b> · {tipo}"
        cuando = f"El plazo termina el {larga(p['fin'])}."
    lineas = [cab, "", f"<b>{escape(p['titulo'])}</b>", cuando]
    if p.get("detalle"):
        lineas += ["", escape(p["detalle"][:500])]
    if seguro:
        lineas += ["", "Confirma la fecha con tu tomador o mediador de seguros."]
    lineas += ["", f"Fuente: {escape(p.get('fuente_nombre') or 'documento oficial')}", f"Todos los plazos: {WEB}#plazos"]
    return "\n".join(lineas)


def avisos(plazos: dict, hoy: date, todos: bool = False, solo: str | None = None, con_tipo: bool = False) -> list:
    """Mensajes de hoy. Con con_tipo=True devuelve (tipo, mensaje) para mandar los de seguros también a los suscritos."""
    out = []
    for p in plazos.get("plazos", []):
        m = toca(p, hoy)
        if todos and (solo is None or p.get("tipo") == solo) and p["fin"] >= hoy.isoformat() and p["inicio"] <= hoy.isoformat():
            m = f"quedan {(date.fromisoformat(p['fin']) - hoy).days}"          # prueba: la cuenta atrás real de hoy
        elif todos:
            m = None
        if m:
            out.append((p.get("tipo"), mensaje(p, m)) if con_tipo else mensaje(p, m))
    return out


def enviar(texto: str, chat: str) -> int:
    import requests
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/sendMessage",
                      data={"chat_id": chat, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": "true"}, timeout=30)
    if not r.ok and r.status_code not in (400, 403):
        raise RuntimeError(f"Telegram respondió {r.status_code}: {r.text[:200]}")
    return r.status_code


def suscritos() -> tuple[object, list[str]]:
    """Chats que pidieron «avísame de los seguros» (api/telegram.js, conjunto «seguros:chats» de Upstash)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ordenes
    r = ordenes.conectar()
    if r is None:
        return None, []
    try:
        return r, [c for c in (r("SMEMBERS", "seguros:chats") or []) if str(c).lstrip("-").isdigit()]
    except (RuntimeError, OSError, ValueError) as e:
        print(f"[recordatorios] No se pudo leer la lista de suscritos ({e}).")
        return None, []


if __name__ == "__main__":
    args = sys.argv[1:]
    hoy = date.fromisoformat(args[args.index("--fecha") + 1]) if "--fecha" in args else date.today()
    destino = args[args.index("--enviar") + 1] if "--enviar" in args else ""
    solo = args[args.index("--solo") + 1] if "--solo" in args else None
    lista = avisos(json.loads(PLAZOS.read_text(encoding="utf-8")), hoy, todos="--todos" in args, solo=solo, con_tipo=True)
    print(f"[recordatorios] {len(lista)} aviso(s) para el {hoy}.")
    r, chats = suscritos() if destino == "canal" and any(tipo == "seguro" for tipo, _ in lista) else (None, [])
    if chats:
        print(f"[recordatorios] {len(chats)} persona(s) apuntada(s) a los avisos de seguros.")
    for tipo, t in lista:
        print("—" * 30 + "\n" + t)
        if destino:
            chat = "@lonjas_cyl" if destino == "canal" else os.environ.get("TELEGRAM_ADMIN_CHAT", "")
            if not chat or not os.environ.get("TELEGRAM_TOKEN"):
                sys.exit("Falta TELEGRAM_TOKEN o TELEGRAM_ADMIN_CHAT")
            enviar(("🧪 <i>Prueba (solo te llega a ti)</i>\n\n" if destino == "yo" else "") + t, chat)
            if tipo == "seguro":
                pie = "\n\n<i>Te llega porque pediste «avísame de los seguros». Para dejar de recibirlo: baja seguros.</i>"
                for c in chats:
                    if enviar(t + pie, c) == 403 and r is not None:      # bloqueó el robot: se le quita de la lista
                        r("SREM", "seguros:chats", c)

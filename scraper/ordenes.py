"""Órdenes que el dueño da al robot de Telegram (api/telegram.js las guarda en Upstash; aquí las lee GitHub).

  redes:pausa:AAAA-MM-DD   lista JSON de franjas que NO se publican ese día («todo» = ninguna)
  redes:preparar           si existe: mandar las vistas previas de «La semana en las lonjas»
  redes:previa_ficha       id de una ficha del Estudio: mandar su vista previa (la pide api/estudio.js)
  admin:chat_sha           huella SHA-256 del chat del dueño (TELEGRAM_ADMIN_CHAT): así Vercel sabe quién manda
                           sin guardar el número en Vercel ni en el código

  python scraper/ordenes.py --revisar     (tarea «Órdenes de Telegram»): guarda la huella y, si hay que preparar,
                                          escribe preparar=si en $GITHUB_OUTPUT
Sin UPSTASH_REDIS_REST_URL / _TOKEN no hace nada (y nada se pausa).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FRANJAS = ("manana", "reel", "hortalizas", "legumbres", "historia", "tarde", "diario")


def conectar():
    url = (os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL") or "").strip()
    token = (os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or "").strip()
    if not url.startswith("https://") or not token:
        return None
    from avisos_telegram import Redis
    return Redis(url, token)


def pausadas(r, hoy: date) -> list[str]:
    try:
        lista = json.loads(r("GET", f"redes:pausa:{hoy.isoformat()}") or "[]")
    except (RuntimeError, ValueError, OSError) as e:
        print(f"[ordenes] No se pudo leer la pausa ({e}): se publica con normalidad.")
        return []
    return [x for x in lista if x == "todo" or x in FRANJAS] if isinstance(lista, list) else []


def pausada(franja: str, hoy: date, r=None) -> bool:
    r = r if r is not None else conectar()
    if r is None:
        return False
    p = pausadas(r, hoy)
    return "todo" in p or franja in p


def huella(chat: str) -> str:
    return hashlib.sha256(str(chat).strip().encode()).hexdigest()


def revisar(r, admin: str) -> bool:
    """Guarda la huella del dueño y dice si hay que preparar las vistas previas (y borra la orden)."""
    if admin.strip():
        r("SET", "admin:chat_sha", huella(admin))
    orden = r("GET", "redes:preparar")
    if orden:
        r("DEL", "redes:preparar")
    return bool(orden)


def ficha_pedida(r) -> str:
    """Id de la ficha del Estudio cuya vista previa se ha pedido (y borra la petición); "" si no hay."""
    import re
    fid = r("GET", "redes:previa_ficha") or ""
    if fid:
        r("DEL", "redes:previa_ficha")
    return fid if re.fullmatch(r"[a-z0-9]{8,24}", fid) else ""


if __name__ == "__main__":
    if "--revisar" in sys.argv:
        r = conectar()
        if r is None:
            print("[ordenes] Sin almacén (Upstash): nada que revisar.")
            sys.exit(0)
        preparar = revisar(r, os.environ.get("TELEGRAM_ADMIN_CHAT", ""))
        ficha = ficha_pedida(r)
        print("[ordenes] " + ("Orden: preparar las vistas previas de la semana. " if preparar else "")
              + (f"Vista previa de la ficha {ficha}." if ficha else "" if preparar else "Sin órdenes nuevas."))
        salida = os.environ.get("GITHUB_OUTPUT")
        if salida:
            with open(salida, "a", encoding="utf-8") as f:
                f.write(f"preparar={'si' if preparar else 'no'}\nficha={ficha}\n")

"""Copia privada por Telegram de lo que publica el robot de redes (Instagram y Facebook).

  python scraper/redes_telegram.py --previa      tras crear la publicación: te manda la imagen, el carrusel o el reel
                                                 con su texto, antes de que salga en las redes
  python scraper/redes_telegram.py --resultado   tras publicar: si ha salido bien o el error

Lo llama la tarea «Redes sociales». Necesita los secretos TELEGRAM_TOKEN (el del robot @lonjascyl_bot) y
TELEGRAM_ADMIN_CHAT (tu número de chat: escribe /miid al robot y te lo dice). Sin ellos no hace nada.
Si Telegram falla, la publicación en las redes sigue igual: este aviso nunca la bloquea.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "salida"
ESTADO = RAIZ / "data" / "instagram.json"
API = "https://api.telegram.org/bot{token}/{metodo}"
LIMITE_PIE = 1024          # Telegram: texto máximo bajo una foto o un vídeo
LIMITE_MENSAJE = 4096
FRANJAS = {"manana": "Publicación de las 8:00", "reel": "Reel de las 13:30", "tarde": "Publicación de las 19:00",
           "historia": "Reel con historia de las 19:00", "historias-todas": "Ensayo: los cinco reels con historia"}
IMAGEN = (".jpg", ".jpeg", ".png")


def llamar(token: str, metodo: str, datos: dict, archivos: dict | None = None) -> dict:
    import requests
    abiertos = {k: (Path(v).name, open(v, "rb")) for k, v in (archivos or {}).items()}
    try:
        r = requests.post(API.format(token=token, metodo=metodo), data=datos, files=abiertos or None, timeout=120)
    finally:
        for _, f in abiertos.values():
            f.close()
    j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not j.get("ok"):
        raise RuntimeError(f"Telegram {metodo}: {j.get('description') or r.status_code}")   # nunca se imprime el token
    return j.get("result") or {}


def cabecera(franja: str, probar: bool) -> str:
    nombre = f"Reel especial «{franja.split(':', 1)[1]}»" if franja.startswith("especial:") else FRANJAS.get(franja, franja)
    t = f"📅 {nombre} · Instagram y Facebook"
    return ("🧪 PRUEBA (no se publicará)\n" if probar else "") + t


def enviar_archivos(token: str, chat: str, archivos: list[Path], pie: str, llamar=llamar) -> None:
    """Una imagen o un vídeo: con su pie. Varias imágenes: en un carrusel (álbum) de hasta 10."""
    corto = pie if len(pie) <= LIMITE_PIE else pie[:LIMITE_PIE - 40].rsplit("\n", 1)[0] + "\n\n(texto completo abajo ↓)"
    if len(archivos) == 1:
        f = archivos[0]
        if f.suffix.lower() in IMAGEN:
            llamar(token, "sendPhoto", {"chat_id": chat, "caption": corto}, {"photo": f})
        else:
            llamar(token, "sendVideo", {"chat_id": chat, "caption": corto, "supports_streaming": "true"}, {"video": f})
    else:
        media = [{"type": "photo", "media": f"attach://f{i}"} | ({"caption": corto} if i == 0 else {}) for i, _ in enumerate(archivos[:10])]
        llamar(token, "sendMediaGroup", {"chat_id": chat, "media": json.dumps(media, ensure_ascii=False)},
               {f"f{i}": f for i, f in enumerate(archivos[:10])})
    if corto != pie:
        llamar(token, "sendMessage", {"chat_id": chat, "text": pie[-LIMITE_MENSAJE:], "disable_web_page_preview": "true"})


def previa(estado: dict, carpeta: Path, token: str, chat: str, probar: bool, llamar=llamar) -> int:
    """Manda lo creado en esta franja. Devuelve cuántos envíos hizo."""
    franja = estado.get("franja", "?")
    enviados = 0
    if franja == "historias-todas":            # ensayo: cada vídeo con su .txt al lado
        for v in sorted(carpeta.glob("*.mp4")):
            t = v.with_suffix(".txt")
            pie = cabecera(franja, True) + "\n\n" + (t.read_text(encoding="utf-8") if t.is_file() else v.name)
            enviar_archivos(token, chat, [v], pie, llamar)
            enviados += 1
        return enviados
    for item in estado.get("preparado") or []:
        nombres = [item["video"]] if item.get("video") else item.get("imagenes", [])
        archivos = [carpeta / Path(n).name for n in nombres if (carpeta / Path(n).name).is_file()]
        pie = cabecera(franja, probar) + "\n\n" + (item.get("texto") or "")
        if archivos:
            enviar_archivos(token, chat, archivos, pie, llamar)
        else:
            llamar(token, "sendMessage", {"chat_id": chat, "text": pie[:LIMITE_MENSAJE] + "\n\n⚠️ No encuentro los archivos de esta publicación."})
        enviados += 1
    return enviados


def resultado(estado: dict, hoy: date, probar: bool) -> str | None:
    """Texto del aviso tras publicar. La tarea solo lo pide cuando esta franja creó algo (al publicar con éxito,
    instagram.publicar vacía estado['preparado'] y marcar() apunta la franja del día)."""
    franja = estado.get("franja", "?")
    if franja == "historias-todas":
        return None
    nombre = f"Reel especial «{franja.split(':', 1)[1]}»" if franja.startswith("especial:") else FRANJAS.get(franja, franja)
    if probar:
        return f"🧪 {nombre}: era una prueba, no se ha publicado."
    e = estado.get("error")
    if e and e.get("fecha") == hoy.isoformat():
        return f"❌ {nombre}: no se ha podido publicar en Instagram.\n{e.get('detalle', '')[:500]}\nTe llegará también un correo de GitHub."
    if franja in estado.get("franjas", {}).get(hoy.isoformat(), []):
        fb = estado.get("error_facebook")
        if fb and fb.get("fecha", hoy.isoformat()) == hoy.isoformat():
            return f"✅ {nombre}: publicado en Instagram.\n⚠️ Facebook falló: {str(fb.get('detalle', ''))[:300]}"
        return f"✅ {nombre}: publicado en Instagram y Facebook."
    return f"⚠️ {nombre}: no consta como publicada. Mira la tarea «Redes sociales» en GitHub."


def main(argv: list[str]) -> int:
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_ADMIN_CHAT", "").strip()
    if not token or not chat.lstrip("-").isdigit():
        print("[redes→telegram] Sin configurar (faltan TELEGRAM_TOKEN o TELEGRAM_ADMIN_CHAT): no se envía nada.")
        return 0
    estado = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.is_file() else {}
    probar = os.environ.get("PROBAR", "") == "si"
    try:
        if "--previa" in argv:
            n = previa(estado, SALIDA, token, chat, probar)
            print(f"[redes→telegram] Enviadas {n} publicaciones a tu chat" if n else "[redes→telegram] Nada creado en esta franja.")
        elif "--resultado" in argv:
            t = resultado(estado, date.today(), probar)
            if t:
                llamar(token, "sendMessage", {"chat_id": chat, "text": t})
                print("[redes→telegram] Resultado enviado.")
    except Exception as e:  # noqa: BLE001 - el aviso nunca debe parar la publicación
        print(f"[redes→telegram] No se pudo enviar a Telegram: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Reels hechos a mano en el Estudio (fichas guardadas por api/estudio.js en Upstash, hash «estudio:reels»).
Una ficha «programada» para hoy ocupa la franja de las 18:37 (en lugar de «La semana en las lonjas»).
Vídeo: portada (título), una pantalla por escena y el cierre de siempre; la voz lee el guion (o, si está vacío,
el título y los textos de las escenas).

  python scraper/fichas.py ID [carpeta]      crea el reel de esa ficha, sin publicar
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import redes  # noqa: E402
from instagram import etiquetas, pie_texto  # noqa: E402
from paginas import WEB  # noqa: E402

CLAVE_HASH = "estudio:reels"


def leer(r=None) -> list[dict]:
    """Todas las fichas (lista vacía si no hay almacén o no responde: el robot sigue con lo de siempre)."""
    if r is None:
        import ordenes
        r = ordenes.conectar()
    if r is None:
        return []
    try:
        plano = r("HGETALL", CLAVE_HASH) or []
    except (RuntimeError, OSError, ValueError) as e:
        print(f"[fichas] No se pudieron leer las fichas ({e}).")
        return []
    out = []
    for i in range(1, len(plano), 2):
        try:
            f = json.loads(plano[i])
        except ValueError:
            continue
        if isinstance(f, dict) and f.get("id") and f.get("titulo") and f.get("escenas"):
            out.append(f)
    return out


def de_hoy(fichas: list[dict], hoy: date, estado: dict | None = None) -> dict | None:
    ya = {x.get("id") for x in (estado or {}).get("registro", [])}
    for f in sorted(fichas, key=lambda f: f.get("cambiado", "")):
        if f.get("estado") == "programado" and f.get("fecha") == hoy.isoformat() and f"{hoy}-ficha-{f['id']}" not in ya:
            return f
    return None


def guion(f: dict) -> str:
    if f.get("guion", "").strip():
        return f["guion"].strip()
    partes = [f["titulo"]] + [" ".join(x for x in (e.get("titulo"), e.get("texto")) if x) for e in f["escenas"]]
    return ". ".join(p.rstrip(".") for p in partes if p) + ". Todos los precios, gratis, en Lonjas CyL."


def texto(f: dict, web: str = WEB) -> str:
    cuerpo = f.get("copy", "").strip() or "\n".join([f"🎬 {f['titulo']}", ""] + [f"• {e.get('titulo') or ''} {e.get('texto') or ''}".strip()
                                                                              for e in f["escenas"]])
    extra = [x for x in f.get("etiquetas", "").split() if x.startswith("#")]
    return "\n".join([cuerpo, "", pie_texto(web), redes.aviso_voz(), "", etiquetas(*extra, "#reels")])[:2150]


def item(f: dict, hoy: date) -> dict:
    base = f"{hoy}-ficha-{f['id']}"
    return {"tipo": "ficha", "id": base, "ficha": f, "texto": texto(f), "video": base + ".mp4"}


def _escena(n: int, total: int, e: dict):
    """Pantalla de una escena: banda verde con la marca y el título, texto grande en la zona segura."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (redes.VW, redes.VH), redes.FONDO)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, redes.VW, 520], fill=redes.PINO)
    ico = Image.open(redes.ICONO).convert("RGB").resize((64, 64))
    img.paste(ico, (70, 200))
    d.text((150, 232), "Lonjas CyL", font=redes._cifra(54), fill=redes.HOJA, anchor="lm")
    d.text((redes.VW - 70, 232), f"{n}/{total}", font=redes._texto(36, 600), fill=redes.CLARO, anchor="rm")
    y = 340
    for linea in redes._partir(d, e.get("titulo") or "", redes._cifra(92), redes.VW - 140)[:2]:
        d.text((70, y), linea, font=redes._cifra(92), fill=redes.HOJA, anchor="lm")
        y += 96
    y = 640
    for linea in redes._partir(d, e.get("texto") or "", redes._texto(60, 600), redes.VW - 220)[:8]:   # deja libre la derecha
        d.text((70, y), linea, font=redes._texto(60, 600), fill=redes.TINTA, anchor="lm")
        y += 80
    return img


def reel(f: dict, destino: Path, web: str = WEB) -> Path:
    portada = redes._fondo_marca(f["titulo"], f.get("subtitulo") or "Lonjas CyL · Castilla y León")
    pantallas = [_escena(i + 1, len(f["escenas"]), e) for i, e in enumerate(f["escenas"])]
    habla = redes.voz(guion(f), destino.with_name(destino.stem + "-voz.wav"))
    minimo = redes.PORTADA + redes.CIERRE + 3 * len(pantallas)
    total = max(minimo, round(redes.duracion_wav(habla) + 1.0, 1)) if habla else max(minimo, redes.SEGUNDOS)
    cada = (total - redes.PORTADA - redes.CIERRE) / len(pantallas)
    sonido = redes.musica(destino.with_suffix(".wav"), total)
    try:
        return redes._render([(redes.PORTADA, portada)] + [(cada, p) for p in pantallas] + [(redes.CIERRE, redes._cierre(web))],
                             destino, sonido, habla)
    finally:
        sonido.unlink(missing_ok=True)
        if habla:
            habla.unlink(missing_ok=True)


if __name__ == "__main__":
    fs = {f["id"]: f for f in leer()}
    if len(sys.argv) < 2 or sys.argv[1] not in fs:
        sys.exit("Uso: python scraper/fichas.py ID [carpeta] (ID de una ficha guardada)")
    f = fs[sys.argv[1]]
    carpeta = Path(sys.argv[2]) if len(sys.argv) > 2 else redes.SALIDA / "fichas"
    it = item(f, date.today())
    print(reel(f, carpeta / it["video"]))
    print(it["texto"])

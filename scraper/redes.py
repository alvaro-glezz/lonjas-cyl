"""Calendario de redes sociales de Lonjas CyL (Instagram + página de Facebook), de lunes a sábado.

  08:00  «mañana»  1 publicación: la sesión nueva de una lonja; si no hay, el «producto del día» (carrusel:
                   dónde se paga más + evolución de 8 semanas).
  13:30  «reel»    1 reel de ~12 s: «¿Dónde se paga más el …?» (lun, mié, vie) o «Lo que más se mueve esta
                   semana» (mar, jue, sáb).
  19:00  «tarde»   solo si hay otra sesión nueva por publicar o, viernes y sábado, la comparativa de la semana.

Todo sale de data/precios.json (nunca se inventa una cifra). Lo lanza la tarea «Redes sociales»:
  python scraper/redes.py --crear       crea imágenes o vídeo en salida/ y lo anota en data/instagram.json
  python scraper/redes.py --publicar    publica lo creado (los archivos ya subidos a la rama «medios»)
  python scraper/redes.py --muestra     crea en salida/muestra/ un ejemplo de cada cosa, sin publicar
La franja sale de la variable FRANJA o, si no está, de la hora (UTC). Cada franja se hace una vez al día.
"""
from __future__ import annotations

import json
import math
import os
import struct
import subprocess
import sys
import wave
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import instagram as ig  # noqa: E402
from instagram import (ALTO, ANCHO, BAJA, CLARO, FONDO, HOJA, ICONO, LINEA, NOMBRES, PAJA, PINO, SUBE, TENUE,  # noqa: E402
                       TINTA, _ajustar, _cabecera, _cifra, _flecha, _pie, _texto, corto, etiquetas, nombre_corto, pie_texto)
from paginas import PRODUCTOS, WEB, num  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "salida"
REPO = "alvaro-glezz/lonjas-cyl"
CDN = "https://cdn.jsdelivr.net/gh/" + REPO + "@{sha}/"
RAW = "https://raw.githubusercontent.com/" + REPO + "/{sha}/"
PRODUCTO_DIA = ["trigo", "cebada", "maiz", "centeno", "girasol", "lechazo"]          # lunes..sábado
PRODUCTO_REEL = ["cebada", "maiz", "trigo", "cerdo-normal", "centeno", "lechazo"]    # lunes..sábado
ARTICULO = {k: v[0] for k, v in PRODUCTOS.items()}                                  # «del trigo», «de la cebada»…
VW, VH, FPS, SEGUNDOS = 1080, 1920, 30, 12


# ---------- datos ----------

def ranking(datos: dict, clave: str, hoy: date, dias: int = 14) -> dict | None:
    """Última sesión de cada lonja (de los últimos `dias`) para un producto, de mayor a menor (misma unidad)."""
    desde = (hoy - timedelta(days=dias)).isoformat()
    filas = [(l, p) for l in datos.get("lonjas", []) if l.get("estado") != "suspendida" and (l.get("fecha") or "") >= desde
             for p in l.get("precios", []) if p.get("clave") == clave and p.get("act") is not None]
    if len(filas) < 2:
        return None
    unidad = max({p["unidad"] for _, p in filas}, key=lambda u: sum(p["unidad"] == u for _, p in filas))
    filas = sorted(((l, p) for l, p in filas if p["unidad"] == unidad), key=lambda x: -x[1]["act"])
    return {"clave": clave, "unidad": unidad, "filas": filas} if len(filas) >= 2 else None


def evolucion(datos: dict, clave: str, hoy: date, semanas: int = 8) -> dict | None:
    """Serie de las últimas `semanas` de cada lonja para un producto (historial de la app)."""
    desde = (hoy - timedelta(weeks=semanas)).isoformat()
    r = ranking(datos, clave, hoy, dias=21)
    if not r:
        return None
    series = []
    for l, p in r["filas"]:
        pts = [(f, v) for f, v in datos.get("historial", {}).get(p["id"], []) if f >= desde and v is not None]
        if len(pts) >= 2:
            series.append((nombre_corto(l), pts))
    return {"clave": clave, "unidad": r["unidad"], "series": series} if any(len(p) >= 4 for _, p in series) else None


def movimientos(datos: dict, hoy: date, n: int = 3) -> dict | None:
    """Mayores subidas y bajadas (en %) de las sesiones de los últimos 8 días."""
    desde = (hoy - timedelta(days=8)).isoformat()
    cambios = []
    for l in datos.get("lonjas", []):
        if l.get("estado") == "suspendida" or (l.get("fecha") or "") < desde:
            continue
        for p in l.get("precios", []):
            if p.get("act") is not None and p.get("ant") not in (None, 0) and p["act"] != p["ant"]:
                cambios.append({"lonja": nombre_corto(l), "producto": p["producto"], "unidad": p["unidad"], "act": p["act"],
                                "dif": p["act"] - p["ant"], "pct": (p["act"] - p["ant"]) / p["ant"] * 100})
    suben = sorted((c for c in cambios if c["dif"] > 0), key=lambda c: -c["pct"])[:n]
    bajan = sorted((c for c in cambios if c["dif"] < 0), key=lambda c: c["pct"])[:n]
    return {"suben": suben, "bajan": bajan} if suben or bajan else None


def signo(v: float, dec: int | None = None) -> str:
    return ("+" if v > 0 else "−") + num(abs(v), dec)


# ---------- imagen: evolución de 8 semanas ----------

def imagen_evolucion(e: dict, destino: Path, web: str = WEB) -> Path:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    _cabecera(img, d, f"{NOMBRES[e['clave']]}: últimas 8 semanas", f"Precio de cada sesión · {e['unidad']}")
    x0, x1, y0, y1 = 120, 800, 400, 1080
    d.rounded_rectangle([50, 360, ANCHO - 50, 1120], radius=28, fill=HOJA)
    fechas = sorted({f for _, pts in e["series"] for f, _ in pts})
    vals = [v for _, pts in e["series"] for _, v in pts]
    lo, hi = min(vals), max(vals)
    marg = (hi - lo) * 0.15 or max(abs(hi) * 0.02, 1)
    lo, hi = lo - marg, hi + marg
    f0, f1 = date.fromisoformat(fechas[0]), date.fromisoformat(fechas[-1])
    dx = (f1 - f0).days or 1
    X = lambda f: x0 + (date.fromisoformat(f) - f0).days / dx * (x1 - x0)
    Y = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)
    dec = 0 if hi - lo > 15 else 2 if hi - lo > 0.15 else 3
    for i in range(5):
        v = lo + (hi - lo) * (i + 0.5) / 5
        d.line([x0, Y(v), x1, Y(v)], fill=LINEA, width=2)
        d.text((x0 - 12, Y(v)), num(v, dec), font=_texto(24), fill=TENUE, anchor="rm")
    d.text((x0, y1 + 24), corto(fechas[0]), font=_texto(24), fill=TENUE)
    d.text((x1, y1 + 24), corto(fechas[-1]), font=_texto(24), fill=TENUE, anchor="ra")
    colores = [PINO, PAJA, "#2f6db5", "#c0365f", "#8a4fb0"]
    etiquetas_ = []
    for i, (nombre, pts) in enumerate(e["series"]):
        c = colores[i % len(colores)]
        d.line([(X(f), Y(v)) for f, v in pts], fill=c, width=7, joint="curve")
        fx, fv = pts[-1]
        d.ellipse([X(fx) - 10, Y(fv) - 10, X(fx) + 10, Y(fv) + 10], fill=c)
        etiquetas_.append([Y(fv), c, f"{nombre} {num(fv)}"])
    etiquetas_.sort()
    for i in range(1, len(etiquetas_)):
        etiquetas_[i][0] = max(etiquetas_[i][0], etiquetas_[i - 1][0] + 40)
    for y, c, t in etiquetas_:
        d.text((x1 + 22, y), _ajustar(d, t, _texto(28, 700), ANCHO - x1 - 90), font=_texto(28, 700), fill=c, anchor="lm")
    resumen = " · ".join(f"{n} {'repite' if abs(p[-1][1] - p[0][1]) < 1e-9 else signo(p[-1][1] - p[0][1])}" for n, p in e["series"][:4])
    d.text((70, 1150), _ajustar(d, "Cambio en el periodo: " + resumen, _texto(28, 600), ANCHO - 140), font=_texto(28, 600), fill=TINTA)
    _pie(d, "historial de sesiones de cada lonja (Lonjas CyL)", web)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=90, optimize=True)
    return destino


def texto_dia(r: dict, e: dict | None, web: str = WEB) -> str:
    art = ARTICULO.get(r["clave"], "del " + r["clave"])
    lineas = [f"📈 Precio {art}: ¿dónde se paga más?", ""]
    lineas += [f"{i}. {nombre_corto(l)}: {num(p['act'])} {r['unidad']} ({p['producto']}, {corto(l['fecha'])})"
               for i, (l, p) in enumerate(r["filas"], 1)]
    dif = r["filas"][0][1]["act"] - r["filas"][-1][1]["act"]
    lineas += ["", f"Diferencia entre la que más y la que menos: {num(dif, 0 if dif >= 10 else 2)} {r['unidad']}."]
    if e:
        partes = []
        for nombre, pts in e["series"]:
            dd = pts[-1][1] - pts[0][1]
            partes.append(f"{nombre} {'repite' if abs(dd) < 1e-9 else signo(dd)}")
        lineas.append(f"En las últimas semanas: {', '.join(partes)} (desliza para ver el gráfico).")
    lineas += ["", "Cada lonja cotiza su propia calidad. Precios orientativos.", "", pie_texto(web), "",
               etiquetas("#" + NOMBRES[r["clave"]].replace(" ", "").replace("í", "i"), "#precios", "#lonjas")]
    return "\n".join(lineas)[:2150]


# ---------- reel ----------

def _suave(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def musica(destino: Path, segundos: float = SEGUNDOS, tasa: int = 48000) -> Path:
    """Acordes suaves (la menor – fa – do – sol), sin derechos de autor: generados aquí mismo."""
    acordes = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)]
    dur = segundos / len(acordes)
    n = int(segundos * tasa)
    datos = bytearray()
    for i in range(n):
        t = i / tasa
        k = min(int(t / dur), len(acordes) - 1)
        tl = t - k * dur
        env = min(1.0, tl / 0.4) * min(1.0, (dur - tl) / 0.6 + 0.15)
        glob = min(1.0, t / 0.5) * min(1.0, (segundos - t) / 1.0)
        v = sum(math.sin(2 * math.pi * f * t) + 0.3 * math.sin(2 * math.pi * f * 2.001 * t) for f in acordes[k])
        datos += struct.pack("<h", int(max(-1, min(1, v / 6 * env * glob * 0.55)) * 32767))
    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(tasa)
        w.writeframes(bytes(datos))
    return destino


def _fondo_marca(titulo: str, sub: str):
    """Fotograma de portada y de cierre (verde, centrado)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (VW, VH), PINO)
    d = ImageDraw.Draw(img)
    ico = Image.open(ICONO).convert("RGB").resize((96, 96))
    img.paste(ico, (VW // 2 - 150, 300))
    d.text((VW // 2 - 36, 348), "Lonjas CyL", font=_cifra(70), fill=HOJA, anchor="lm")
    y = 640
    for linea in _partir(d, titulo, _cifra(128), VW - 160):
        d.text((VW // 2, y), linea, font=_cifra(128), fill=HOJA, anchor="mm")
        y += 140
    y += 30
    for linea in _partir(d, sub, _texto(44, 600), VW - 200):
        d.text((VW // 2, y), linea, font=_texto(44, 600), fill=PAJA, anchor="mm")
        y += 60
    return img


def _partir(d, texto: str, letra, ancho: int) -> list[str]:
    out, actual = [], ""
    for pal in texto.split():
        prueba = (actual + " " + pal).strip()
        if d.textlength(prueba, font=letra) <= ancho or not actual:
            actual = prueba
        else:
            out.append(actual)
            actual = pal
    return out + ([actual] if actual else [])


def _cierre(web: str):
    from PIL import ImageDraw
    img = _fondo_marca("Todos los precios, gratis", "Sin registro · funciona sin conexión")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([140, 1130, VW - 140, 1250], radius=60, fill=PAJA)
    d.text((VW // 2, 1190), web.split("//")[1].rstrip("/"), font=_cifra(58), fill=TINTA, anchor="mm")
    d.text((VW // 2, 1330), "Avisos en Telegram: t.me/lonjas_cyl", font=_texto(40, 600), fill=CLARO, anchor="mm")
    return img


def _filas_reel(cab: str, sub: str, filas: list[dict], nota: str):
    """Devuelve una función t -> fotograma para la parte central (filas que entran una a una)."""
    from PIL import Image, ImageDraw
    base = Image.new("RGB", (VW, VH), FONDO)
    d = ImageDraw.Draw(base)
    d.rectangle([0, 0, VW, 520], fill=PINO)
    ico = Image.open(ICONO).convert("RGB").resize((64, 64))
    base.paste(ico, (70, 200))
    d.text((150, 232), "Lonjas CyL", font=_cifra(54), fill=HOJA, anchor="lm")
    y = 330
    for linea in _partir(d, cab, _cifra(92), VW - 140)[:2]:
        d.text((70, y), linea, font=_cifra(92), fill=HOJA, anchor="lm")
        y += 96
    d.text((72, 488), _ajustar(d, sub, _texto(34), VW - 140), font=_texto(34), fill=CLARO, anchor="lm")
    # Zona segura de los reels: Instagram tapa la parte de abajo (texto, cuenta) y la derecha (botones).
    alto = 186 if len(filas) <= 4 else 150
    total = len(filas) * (alto + 20) + (130 if nota else 0)
    y0 = 590 + max(0, (900 - total) // 2)
    ancho = VW - 230                                   # las tarjetas acaban en x = 910

    def fotograma(t: float):
        img = base.copy()
        dd = ImageDraw.Draw(img)
        for i, f in enumerate(filas):
            a = _suave((t - 0.35 * i) / 0.5)
            if a <= 0:
                continue
            x = int(60 + (1 - a) * 260)
            yy = y0 + i * (alto + 20)
            capa = Image.new("RGB", (ancho, alto), f.get("fondo", HOJA))
            cd = ImageDraw.Draw(capa)
            xt = 120 if f["n"] else 40
            if f["n"]:
                cd.text((38, alto // 2), f["n"], font=_cifra(80), fill=f.get("tinta_n", TENUE), anchor="lm")
            vf = _cifra(100 if alto > 160 else 86)
            wv = cd.textlength(f["valor"], font=vf) + (46 if f.get("flecha") is not None else 0)
            ancho_txt = ancho - xt - wv - 60
            cd.text((xt, alto * 0.34), _ajustar(cd, f["titulo"], _texto(40, 700), ancho_txt), font=_texto(40, 700), fill=TINTA, anchor="lm")
            cd.text((xt, alto * 0.70), _ajustar(cd, f["sub"], _texto(30), ancho_txt), font=_texto(30), fill=TENUE if f.get("fondo", HOJA) == HOJA else TINTA, anchor="lm")
            cd.text((ancho - 36, alto // 2 + 6), f["valor"], font=vf, fill=f.get("color", TINTA), anchor="rm")
            if f.get("flecha") is not None:
                w = cd.textlength(f["valor"], font=vf)
                _flecha(cd, int(ancho - 36 - w - 44), alto // 2 - 14, f["flecha"], f["color"], 30)
            mascara = Image.new("L", capa.size, 0)
            ImageDraw.Draw(mascara).rounded_rectangle([0, 0, capa.size[0] - 1, alto - 1], radius=32, fill=int(255 * a))
            img.paste(capa, (x, yy), mascara)
        an = _suave((t - 0.35 * len(filas) - 0.4) / 0.6)
        if an > 0 and nota:
            dd.text((60 + ancho // 2, y0 + len(filas) * (alto + 20) + 70), nota, font=_cifra(74), fill=PINO, anchor="mm")
        return img
    return fotograma


def _render(escenas: list[tuple[float, object]], destino: Path, sonido: Path) -> Path:
    """escenas = [(segundos, fotograma o función t -> fotograma)]. Escribe MP4 H.264 + AAC (formato de reels)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}", "-r", str(FPS),
           "-i", "-", "-i", str(sonido), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(destino)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for dur, esc in escenas:
            fijo = None if callable(esc) else esc.tobytes()
            for k in range(int(dur * FPS)):
                proc.stdin.write(fijo if fijo is not None else esc(k / FPS).tobytes())
    finally:
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg no pudo crear el vídeo")
    return destino


def reel_ranking(r: dict, destino: Path, web: str = WEB) -> Path:
    art = ARTICULO.get(r["clave"], "del " + r["clave"])
    fechas = sorted(l["fecha"] for l, _ in r["filas"])
    filas = []
    for i, (l, p) in enumerate(r["filas"][:5]):
        primero = i == 0
        filas.append({"n": str(i + 1), "titulo": nombre_corto(l), "sub": f"{p['producto']} · {corto(l['fecha'])}",
                      "valor": num(p["act"]), "fondo": PAJA if primero else HOJA, "tinta_n": TINTA if primero else TENUE})
    dif = r["filas"][0][1]["act"] - r["filas"][-1][1]["act"]
    medio = _filas_reel(f"Precio {art}", f"Últimas sesiones ({corto(fechas[0])} – {corto(fechas[-1])}) · {r['unidad']}",
                        filas, f"Diferencia: {num(dif, 0 if dif >= 10 else 2)} {r['unidad']}")
    escenas = [(2.4, _fondo_marca(titulo_ranking(r["clave"]), "Últimas sesiones de las lonjas de Castilla y León")),
               (7.0, medio), (SEGUNDOS - 9.4, _cierre(web))]
    sonido = musica(destino.with_suffix(".wav"))
    try:
        return _render(escenas, destino, sonido)
    finally:
        sonido.unlink(missing_ok=True)


def titulo_ranking(clave: str) -> str:
    art = ARTICULO.get(clave, "del " + clave)            # «del trigo» -> «el trigo»; «de la cebada» -> «la cebada»
    nombre = art[3:] if art.startswith("de ") else ("el " + art[4:] if art.startswith("del ") else art)
    return f"¿Dónde se paga más {nombre}?"


def reel_movimientos(m: dict, destino: Path, web: str = WEB) -> Path:
    filas = []
    for c in m["suben"]:
        filas.append({"n": "", "titulo": c["producto"], "sub": c["lonja"], "valor": signo(c["pct"], 1) + " %", "color": SUBE, "flecha": True})
    for c in m["bajan"]:
        filas.append({"n": "", "titulo": c["producto"], "sub": c["lonja"], "valor": signo(c["pct"], 1) + " %", "color": BAJA, "flecha": False})
    medio = _filas_reel("Lo que más se mueve", "Sesiones de los últimos 8 días · cambio frente a la anterior", filas[:6], "")
    escenas = [(2.4, _fondo_marca("Lo que más se ha movido esta semana", "Lonjas de Castilla y León")), (7.0, medio),
               (SEGUNDOS - 9.4, _cierre(web))]
    sonido = musica(destino.with_suffix(".wav"))
    try:
        return _render(escenas, destino, sonido)
    finally:
        sonido.unlink(missing_ok=True)


def texto_reel_ranking(r: dict, web: str = WEB) -> str:
    lineas = [titulo_ranking(r["clave"]) + " 👇", ""]
    lineas += [f"{i}. {nombre_corto(l)}: {num(p['act'])} {r['unidad']} ({p['producto']})" for i, (l, p) in enumerate(r["filas"], 1)]
    lineas += ["", f"Diferencia: {num(r['filas'][0][1]['act'] - r['filas'][-1][1]['act'], 2)} {r['unidad']}. Cada lonja cotiza su propia calidad.",
               "", pie_texto(web), "Precios orientativos.", "",
               etiquetas("#reels", "#" + NOMBRES[r["clave"]].replace(" ", "").replace("í", "i"), "#precios")]
    return "\n".join(lineas)[:2150]


def texto_reel_movimientos(m: dict, web: str = WEB) -> str:
    lineas = ["📊 Lo que más se ha movido esta semana en las lonjas de Castilla y León", ""]
    lineas += [f"▲ {c['producto']} ({c['lonja']}): {signo(c['pct'], 1)} % · {num(c['act'])} {c['unidad']}" for c in m["suben"]]
    lineas += [f"▼ {c['producto']} ({c['lonja']}): {signo(c['pct'], 1)} % · {num(c['act'])} {c['unidad']}" for c in m["bajan"]]
    lineas += ["", "Cambio frente a la sesión anterior de cada lonja.", "", pie_texto(web), "Precios orientativos.", "",
               etiquetas("#reels", "#mercadoagrario", "#precios")]
    return "\n".join(lineas)[:2150]


# ---------- calendario ----------

def franja_por_hora(ahora: datetime) -> str:
    """Hora UTC de la tarea -> franja (las tareas se programan a las 7:00, 12:30 y 18:00 UTC)."""
    return "manana" if ahora.hour < 10 else "reel" if ahora.hour < 15 else "tarde"


def _sesion(datos: dict, estado: dict, hoy: date) -> dict | None:
    for item in ig.pendientes(datos, estado, hoy):
        if item["tipo"] == "sesion":
            return item
    return None


def elegir(franja: str, datos: dict, estado: dict, hoy: date) -> dict | None:
    """Qué toca publicar en esa franja (o None). No crea archivos."""
    dia = hoy.weekday()
    if dia == 6:
        return None
    if franja in ("manana", "tarde"):
        s = _sesion(datos, estado, hoy)
        if s:
            return s
        if franja == "tarde":
            comp = [x for x in ig.pendientes(datos, estado, hoy) if x["tipo"] == "comparativa"]
            return comp[0] if comp else None
        for k in PRODUCTO_DIA[dia:] + PRODUCTO_DIA[:dia]:
            r = ranking(datos, k, hoy)
            if r:
                return {"tipo": "dia", "id": f"{hoy}-dia-{k}", "clave": k, "texto": texto_dia(r, evolucion(datos, k, hoy)),
                        "imagenes": [f"{hoy}-dia-{k}-1.jpg"] + ([f"{hoy}-dia-{k}-2.jpg"] if evolucion(datos, k, hoy) else [])}
        return None
    if franja == "reel":
        orden = ["ranking", "movimientos"] if dia % 2 == 0 else ["movimientos", "ranking"]
        for tipo in orden:
            if tipo == "movimientos":
                m = movimientos(datos, hoy)
                if m:
                    return {"tipo": "reel", "id": f"{hoy}-reel-movimientos", "reel": "movimientos", "texto": texto_reel_movimientos(m),
                            "video": f"{hoy}-reel-movimientos.mp4"}
            else:
                for k in PRODUCTO_REEL[dia:] + PRODUCTO_REEL[:dia]:
                    r = ranking(datos, k, hoy)
                    if r:
                        return {"tipo": "reel", "id": f"{hoy}-reel-{k}", "reel": "ranking", "clave": k, "texto": texto_reel_ranking(r),
                                "video": f"{hoy}-reel-{k}.mp4"}
    return None


def crear_archivos(item: dict, datos: dict, hoy: date, carpeta: Path) -> None:
    lonjas = {l["id"]: l for l in datos.get("lonjas", [])}
    if item["tipo"] == "sesion":
        nombre = Path(item["imagenes"][0]).name
        ig.imagen_sesion(lonjas[item["lonja"]], carpeta / nombre)
        item["imagenes"] = [nombre]
    elif item["tipo"] == "comparativa":
        comps = {c["clave"]: c for c in ig.comparativas(datos, hoy)}
        nombres = []
        for ruta in item["imagenes"]:
            nombre = Path(ruta).name
            ig.imagen_comparativa(comps[nombre.rsplit("-", 1)[1][:-4]], carpeta / nombre)
            nombres.append(nombre)
        item["imagenes"] = nombres
    elif item["tipo"] == "dia":
        k = item["clave"]
        ig.imagen_comparativa(ranking(datos, k, hoy), carpeta / item["imagenes"][0])
        if len(item["imagenes"]) > 1:
            imagen_evolucion(evolucion(datos, k, hoy), carpeta / item["imagenes"][1])
    elif item["tipo"] == "reel":
        if item["reel"] == "ranking":
            reel_ranking(ranking(datos, item["clave"], hoy), carpeta / item["video"])
        else:
            reel_movimientos(movimientos(datos, hoy), carpeta / item["video"])


def hecha(estado: dict, franja: str, hoy: date) -> bool:
    return franja in estado.get("franjas", {}).get(hoy.isoformat(), [])


def marcar(estado: dict, franja: str, hoy: date) -> None:
    f = estado.setdefault("franjas", {})
    f.setdefault(hoy.isoformat(), []).append(franja)
    for viejo in sorted(f)[:-10]:
        del f[viejo]


def crear(datos: dict, estado: dict, franja: str, hoy: date, carpeta: Path = SALIDA, forzar: bool = False) -> dict | None:
    estado["preparado"] = []
    estado["franja"] = franja
    if hecha(estado, franja, hoy) and not forzar:
        return None
    item = elegir(franja, datos, estado, hoy)
    if not item:
        return None
    crear_archivos(item, datos, hoy, carpeta)
    estado["preparado"] = [item]
    return item


def main(argv: list[str]) -> int:
    datos = json.loads(ig.DATOS.read_text(encoding="utf-8"))
    hoy = date.today()
    if "--muestra" in argv:
        dest = SALIDA / "muestra"
        for franja, dia in (("manana", hoy), ("reel", hoy), ("reel", hoy + timedelta(days=1))):
            item = elegir(franja, datos, {"publicado": {l["id"]: l.get("fecha") for l in datos["lonjas"]}, "comparativa": "x"},
                          dia if dia.weekday() != 6 else dia + timedelta(days=1))
            if item:
                crear_archivos(item, datos, hoy, dest)
                (dest / f"{item['id']}.txt").write_text(item["texto"], encoding="utf-8")
                print(f"[redes] Muestra: {item['id']}")
        return 0
    token = os.environ.get("INSTAGRAM_TOKEN", "").strip()
    if not token:
        print("[redes] Sin configurar (falta el secreto INSTAGRAM_TOKEN): no se crea ni se publica nada.")
        return 0
    estado = json.loads(ig.ESTADO.read_text(encoding="utf-8")) if ig.ESTADO.is_file() else {}
    try:
        if "--crear" in argv:
            franja = os.environ.get("FRANJA", "").strip() or franja_por_hora(datetime.utcnow())
            item = crear(datos, estado, franja, hoy, forzar=os.environ.get("FORZAR") == "si")
            print(f"[redes] Franja «{franja}»: " + (f"creado {item['id']}" if item else "nada que publicar"))
        elif "--publicar" in argv:
            if not estado.get("preparado"):
                print("[redes] Nada que publicar.")
                return 0
            sha = os.environ.get("MEDIOS_SHA", "").strip()
            item = estado["preparado"][0]
            primero = item.get("video") or item["imagenes"][0]
            base = next((b for b in (CDN.format(sha=sha), RAW.format(sha=sha)) if ig.en_internet(b + primero, intentos=12)), None)
            if not base:
                print("[redes] Los archivos no están en internet: no se publica.")
                return 0
            cuenta, tk, _ = ig.cuenta(token)
            fb = ig.pagina_fb(token) if os.environ.get("PUBLICAR_FACEBOOK", "si") != "no" else None
            try:
                hechas = ig.publicar(estado, tk, base, hoy, ig=cuenta, fb=fb)
                estado.pop("error", None)
            except ig.ErrorInstagram as e:
                estado["error"] = {"fecha": hoy.isoformat(), "detalle": str(e)}
                raise
            marcar(estado, estado.get("franja", "?"), hoy)
            print(f"[redes] Publicado: {', '.join(hechas)}" + (" (también en Facebook)" if fb and "error_facebook" not in estado else ""))
            if estado.get("error_facebook"):
                print(f"[facebook] No se pudo publicar: {estado['error_facebook']['detalle']}")
    finally:
        ig.guardar(estado)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Calendario de redes sociales de Lonjas CyL (Instagram + página de Facebook), de lunes a sábado.

  08:00  «mañana»  1 publicación: la sesión nueva de una lonja; si no hay, el «producto del día» (carrusel:
                   dónde se paga más + evolución de 8 semanas).
  13:30  «reel»    1 reel de ~12 s: «¿Dónde se paga más el …?» (lun, mié, vie) o «Lo que más se mueve esta
                   semana» (mar, jue, sáb).
  19:00  «tarde»   solo si hay otra sesión nueva por publicar o, viernes y sábado, la comparativa de la semana.
  19:00  «historia» (tarea de las 17:55 UTC, lun–vie) los 5 reels con historia de historias.py, uno por día laborable
                   desde el 9 nov 2026 hasta publicar los cinco. FRANJA=historias-todas crea los cinco sin publicar.

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
import re
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
PORTADA, CIERRE = 2.4, 2.6          # segundos de la portada y del cierre del reel
# Voz: Piper con la voz española «sharvard», hablante de mujer (1). Licencia CC BY 3.0 (corpus Sharvard): hay que citarla,
# y va en AVISO_VOZ. La tarea la descarga y pone su ruta en PIPER_MODELO (y PIPER_HABLANTE=1).
AVISO_VOZ = "🔊 Voz generada por ordenador (voz «sharvard» de Piper, corpus Sharvard, licencia CC BY 3.0)."


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


# ---------- voz ----------

_UNI = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "trece",
        "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós",
        "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_DEC = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_CEN = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos", 6: "seiscientos",
        7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def en_palabras(n: int) -> str:
    """Número entero (0–999.999) en palabras, en español."""
    if n < 30:
        return _UNI[n]
    if n < 100:
        d, u = divmod(n, 10)
        return _DEC[d] + ("" if u == 0 else " y " + _UNI[u])
    if n < 1000:
        c, r = divmod(n, 100)
        if n == 100:
            return "cien"
        return _CEN[c] + ("" if r == 0 else " " + en_palabras(r))
    m, r = divmod(n, 1000)
    return ("mil" if m == 1 else en_palabras(m).replace("uno", "un") + " mil") + ("" if r == 0 else " " + en_palabras(r))


def decir(v: float, dec: int | None = None, sep: str = "con") -> str:
    """236 -> «doscientos treinta y seis»; 9,45 -> «nueve con cuarenta y cinco»; 1,155 -> «uno con ciento cincuenta y cinco»."""
    txt = num(abs(v), dec).replace(".", "")
    ent, _, fr = txt.partition(",")
    out = en_palabras(int(ent))
    if fr and int(fr):
        out += f" {sep} " + (("cero " * (len(fr) - len(fr.lstrip("0")))) + en_palabras(int(fr))).strip()
    return out


UNIDADES_HABLADAS = {"€/t": "euros la tonelada", "€/kg vivo": "euros el kilo vivo", "€/kg canal": "euros el kilo canal",
                     "€/kg": "euros el kilo", "€/ud": "euros la unidad", "€/cabeza": "euros por cabeza", "€/l": "euros el litro"}


def unidad_hablada(u: str, por: bool = False) -> str:
    t = UNIDADES_HABLADAS.get(u, "euros" if u.startswith("€") else u)
    return t.replace(" la ", " por ").replace(" el ", " por ") if por else t


def _euros(n: int) -> str:
    """Entero delante de «euros»: uno -> un, veintiuno -> veintiún, treinta y uno -> treinta y un."""
    return re.sub(r"(veinti)?uno$", lambda m: "veintiún" if m.group(1) else "un", en_palabras(n))


def precio_hablado(v: float, unidad: str, dec: int | None = None, por: bool = False) -> str:
    """236 €/t -> «doscientos treinta y seis euros la tonelada»; 9,90 €/kg vivo -> «nueve euros con noventa céntimos
    el kilo vivo»; 0,45 -> «cuarenta y cinco céntimos por kilo vivo»; 1,155 -> «uno coma ciento cincuenta y cinco euros…»."""
    u = unidad_hablada(unidad, por)
    resto = u[len("euros"):] if u.startswith("euros") else " " + u
    v = round(abs(v), 3 if dec is None else dec)
    if round(v, 2) != v:
        return f"{decir(v, sep='coma')} {u}"
    e, c = divmod(int(round(v * 100)), 100)
    if e == 0:
        return f"{en_palabras(c)} céntimos{resto}"
    if c == 0:
        return f"{_euros(e)} {u}"
    return f"{_euros(e)} {'euro' if e == 1 else 'euros'} con {en_palabras(c)} céntimos{resto}"


def producto_hablado(p: str) -> str:
    """«Oveja desvieje 2ª» -> «oveja desvieje segunda»; «Cebada 62 kg/hl» -> «cebada»; «Girasol 9-2-44» -> «girasol»."""
    p = p.replace("1ª", "primera").replace("2ª", "segunda").replace("3ª", "tercera").replace("<", "menos de ")
    p = re.split(r"\s\d", p)[0]
    return p.strip(" -·").lower()


def _lista(cosas: list[str]) -> str:
    return cosas[0] if len(cosas) == 1 else ", ".join(cosas[:-1]) + " y " + cosas[-1]


def guion_ranking(r: dict) -> str:
    """Pocas frases y bien enlazadas (así la voz no va a trompicones). Las lonjas con el mismo precio, juntas."""
    grupos: list[tuple[float, list[str]]] = []
    for l, p in r["filas"][:5]:
        if grupos and abs(grupos[-1][0] - p["act"]) < 1e-9:
            grupos[-1][1].append(nombre_corto(l))
        else:
            grupos.append((p["act"], [nombre_corto(l)]))
    (p0, l0), resto = grupos[0], grupos[1:]
    txt = f"{titulo_ranking(r['clave'])[:-1]} esta semana? Paga más {_lista(l0)}, con {precio_hablado(p0, r['unidad'])}"
    if resto:
        partes = [f"{_lista(ls)}, con {decir(v, sep='coma')}" for v, ls in resto]
        txt += "; le " + ("sigue " if len(resto[0][1]) == 1 and len(resto) == 1 else "siguen ") + (
            partes[0] if len(partes) == 1 else "; ".join(partes[:-1]) + "; y " + partes[-1])
    dif = r["filas"][0][1]["act"] - r["filas"][-1][1]["act"]
    txt += f". Entre la que más paga y la que menos hay {precio_hablado(dif, r['unidad'], 0 if dif >= 10 else 2, por=True)} de diferencia."
    return txt + " Tienes todos los precios, gratis, en Lonjas CyL."


def guion_movimientos(m: dict) -> str:
    def item(c):
        return f"{producto_hablado(c['producto'])} en {c['lonja']}, un {decir(abs(c['pct']), 1, 'coma')} por ciento"
    txt = "Esto es lo que más se ha movido esta semana en las lonjas de Castilla y León."
    def serie(cs):
        xs = [item(c) for c in cs]
        return xs[0] if len(xs) == 1 else "; ".join(xs[:-1]) + "; y " + xs[-1]
    if m["suben"]:
        txt += " Las mayores subidas: " + serie(m["suben"]) + "."
    if m["bajan"]:
        txt += (" En cambio, las mayores bajadas: " if m["suben"] else " Las mayores bajadas: ") + serie(m["bajan"]) + "."
    return txt + " Tienes todos los precios, gratis, en Lonjas CyL."


def para_leer(texto: str) -> str:
    """Lo que la voz no debe leer letra a letra. Con PIPER_COMAS=si, «;» pasa a «,» (pausas más cortas, más fluido)."""
    texto = texto.replace("Lonjas CyL", "Lonjas Castilla y León").replace("CyL", "Castilla y León")
    texto = texto.replace(" › ", ", ").replace("km/h", "kilómetros por hora").replace("…", ",")
    return texto.replace(";", ",") if os.environ.get("PIPER_COMAS", "si") == "si" else texto


_KOKORO = None


def _voz_kokoro(texto: str, destino: Path) -> Path | None:
    """Narración con Kokoro (modelo abierto, licencia Apache 2.0), más natural que Piper. VOZ_MOTOR=kokoro y KOKORO_VOZ."""
    global _KOKORO
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
        if _KOKORO is None:
            _KOKORO = KPipeline(lang_code="e")
        trozos = [a for _, _, a in _KOKORO(para_leer(texto), voice=os.environ.get("KOKORO_VOZ", "ef_dora"),
                                            speed=float(os.environ.get("KOKORO_RITMO", "1.0")))]
        audio = np.concatenate([np.asarray(a, dtype="float32") for a in trozos])
        destino.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(destino), audio, 24000, subtype="PCM_16")
        return destino
    except Exception as e:  # sin Kokoro, el reel sale solo con música
        print(f"[redes] Sin voz (Kokoro falló): {e!r}"[:300])
        return None


def voz(texto: str, destino: Path) -> Path | None:
    """Narración con Piper (si está instalada y hay modelo), o con Kokoro si VOZ_MOTOR=kokoro.
    Sin voz, el reel sale solo con música."""
    if os.environ.get("VOZ_MOTOR") == "kokoro":
        return _voz_kokoro(texto, destino)
    modelo = os.environ.get("PIPER_MODELO", "").strip()
    if not modelo or not Path(modelo).is_file():
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Ritmo natural (1.0), poca pausa entre frases y algo más de variación en la entonación (noise-w).
    e = os.environ.get
    # Ajuste «C3 · viva», elegido por el dueño el 7 nov: más ágil, sin pausas entre frases, entonación más variada.
    opciones = ["--length-scale", e("PIPER_RITMO", "0.90"), "--sentence-silence", e("PIPER_PAUSA", "0.0"),
                "--noise-scale", e("PIPER_RUIDO", "0.75"), "--noise-w-scale", e("PIPER_RUIDO_W", "1.2")]
    if os.environ.get("PIPER_HABLANTE"):
        opciones += ["-s", os.environ["PIPER_HABLANTE"]]
    r = subprocess.run([sys.executable, "-m", "piper", "-m", modelo, "-f", str(destino), *opciones],
                       input=para_leer(texto), text=True, capture_output=True)
    if r.returncode != 0 or not destino.is_file():
        print(f"[redes] Sin voz (Piper falló): {r.stderr[-300:]}")
        return None
    return destino


def duracion_wav(f: Path) -> float:
    with wave.open(str(f)) as w:
        return w.getnframes() / w.getframerate()


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


def guitarra(destino: Path, segundos: float = SEGUNDOS, tasa: int = 22050) -> Path:
    """Guitarra punteada (arpegios la menor – fa – do – sol), sin derechos de autor: cuerdas sintetizadas aquí mismo
    con el método Karplus-Strong (ruido que se va suavizando en un bucle del largo de la nota)."""
    import random
    rnd = random.Random(7)
    nota = {"A2": 110.0, "C3": 130.81, "E3": 164.81, "F2": 87.31, "G2": 98.0, "A3": 220.0, "C4": 261.63, "E4": 329.63,
            "F3": 174.61, "G3": 196.0, "B3": 246.94, "D4": 293.66}
    acordes = [("A2", "E3", "A3", "C4", "E4", "C4", "A3", "E3"), ("F2", "C3", "F3", "A3", "C4", "A3", "F3", "C3"),
               ("C3", "G3", "C4", "E4", "G3", "E4", "C4", "G3"), ("G2", "D4", "G3", "B3", "D4", "B3", "G3", "D4")]
    largo = int(2.2 * tasa)
    cache: dict = {}

    def pulsar(f: float) -> list:
        if f not in cache:
            n = max(2, int(tasa / f))
            buf = [rnd.uniform(-1, 1) for _ in range(n)]
            out = [0.0] * largo
            i = 0
            for k in range(largo):
                a = buf[i]
                b = buf[(i + 1) % n]
                buf[i] = 0.4985 * (a + b)            # promedio con pérdida: la cuerda se apaga poco a poco
                out[k] = a
                i = (i + 1) % n
            cache[f] = out
        return cache[f]

    total = int(segundos * tasa) + 1
    mezcla = [0.0] * total
    paso = 0.36                                      # corcheas a unos 83 pulsos por minuto
    t, j = 0.0, 0
    while t < segundos:
        acorde = acordes[(j // 8) % len(acordes)]
        nombre = acorde[j % 8]
        golpe = pulsar(nota[nombre])
        vol = 0.42 if j % 8 == 0 else 0.26
        i0 = int(t * tasa)
        for k in range(min(largo, total - i0)):
            mezcla[i0 + k] += golpe[k] * vol
        t += paso
        j += 1
    datos = bytearray()
    for i, v in enumerate(mezcla):
        tt = i / tasa
        glob = min(1.0, tt / 0.3) * min(1.0, (segundos - tt) / 1.5) if tt < segundos else 0.0
        datos += struct.pack("<h", int(max(-1.0, min(1.0, v * 0.9 * max(0.0, glob))) * 32767))
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


def _render(escenas: list[tuple[float, object]], destino: Path, sonido: Path, habla: Path | None = None) -> Path:
    """escenas = [(segundos, fotograma o función t -> fotograma)]. Escribe MP4 H.264 + AAC (formato de reels).
    Con `habla`, la voz va encima de la música (la música, más baja)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    entrada = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}", "-r", str(FPS),
               "-i", "-", "-i", str(sonido)]
    if habla:
        audio = ["-i", str(habla), "-filter_complex",
                 "[1:a]volume=0.45[m];[2:a]aresample=48000,adelay=350|350,volume=1.2[v];[m][v]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89:level=false[a]",
                 "-map", "0:v", "-map", "[a]"]
    else:
        audio = ["-map", "0:v", "-map", "1:a"]
    cmd = entrada + audio + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
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
    return _montar(guion_ranking(r), _fondo_marca(titulo_ranking(r["clave"]), "Últimas sesiones de las lonjas de Castilla y León"),
                   medio, _cierre(web), destino)


def _montar(guion: str, portada, medio, cierre, destino: Path) -> Path:
    """Une portada, parte central y cierre; si hay voz, el reel dura lo que la narración (mínimo 12 s)."""
    habla = voz(guion, destino.with_name(destino.stem + "-voz.wav"))
    total = max(SEGUNDOS, round(duracion_wav(habla) + 1.0, 1)) if habla else SEGUNDOS
    sonido = musica(destino.with_suffix(".wav"), total)
    try:
        return _render([(PORTADA, portada), (total - PORTADA - CIERRE, medio), (CIERRE, cierre)], destino, sonido, habla)
    finally:
        sonido.unlink(missing_ok=True)
        if habla:
            habla.unlink(missing_ok=True)


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
    return _montar(guion_movimientos(m), _fondo_marca("Lo que más se ha movido esta semana", "Lonjas de Castilla y León"),
                   medio, _cierre(web), destino)


def texto_reel_ranking(r: dict, web: str = WEB) -> str:
    lineas = [titulo_ranking(r["clave"]) + " 👇", ""]
    lineas += [f"{i}. {nombre_corto(l)}: {num(p['act'])} {r['unidad']} ({p['producto']})" for i, (l, p) in enumerate(r["filas"], 1)]
    lineas += ["", f"Diferencia: {num(r['filas'][0][1]['act'] - r['filas'][-1][1]['act'], 2)} {r['unidad']}. Cada lonja cotiza su propia calidad.",
               "", pie_texto(web), "Precios orientativos.", AVISO_VOZ, "",
               etiquetas("#reels", "#" + NOMBRES[r["clave"]].replace(" ", "").replace("í", "i"), "#precios")]
    return "\n".join(lineas)[:2150]


def texto_reel_movimientos(m: dict, web: str = WEB) -> str:
    lineas = ["📊 Lo que más se ha movido esta semana en las lonjas de Castilla y León", ""]
    lineas += [f"▲ {c['producto']} ({c['lonja']}): {signo(c['pct'], 1)} % · {num(c['act'])} {c['unidad']}" for c in m["suben"]]
    lineas += [f"▼ {c['producto']} ({c['lonja']}): {signo(c['pct'], 1)} % · {num(c['act'])} {c['unidad']}" for c in m["bajan"]]
    lineas += ["", "Cambio frente a la sesión anterior de cada lonja.", "", pie_texto(web), "Precios orientativos.", AVISO_VOZ, "",
               etiquetas("#reels", "#mercadoagrario", "#precios")]
    return "\n".join(lineas)[:2150]


# ---------- calendario ----------

def franja_por_hora(ahora: datetime) -> str:
    """Hora UTC de la tarea -> franja (las tareas se programan a las 7:00, 12:30 y 18:00 UTC)."""
    return "manana" if ahora.hour < 10 else "reel" if ahora.hour < 15 else "tarde"


# Cada franja: desde qué hora UTC se publica y hasta cuándo se puede recuperar si GitHub se retrasa o se salta la
# tarea (GitHub retrasa las tareas programadas hasta ~1 h en horas de mucho uso, y a veces no las lanza).
VENTANAS = (("manana", (6, 40), (11, 30), range(0, 6)),
            ("reel", (12, 10), (17, 0), range(0, 6)),
            ("historia", (17, 30), (21, 30), range(0, 5)),      # lunes a viernes
            ("tarde", (17, 40), (21, 30), range(0, 6)))


def franja_pendiente(ahora: datetime, estado: dict, hoy: date) -> str | None:
    """La primera franja de hoy que ya toca y aún no se ha publicado (None si no queda ninguna)."""
    hm = (ahora.hour, ahora.minute)
    for franja, desde, hasta, dias in VENTANAS:
        if hoy.weekday() in dias and desde <= hm <= hasta and not hecha(estado, franja, hoy):
            return franja
    return None


def _sesion(datos: dict, estado: dict, hoy: date) -> dict | None:
    for item in ig.pendientes(datos, estado, hoy):
        if item["tipo"] == "sesion":
            return item
    return None


def elegir(franja: str, datos: dict, estado: dict, hoy: date) -> dict | None:
    """Qué toca publicar en esa franja (o None). No crea archivos."""
    dia = hoy.weekday()
    if franja == "historia":
        import historias
        n = historias.siguiente(estado, hoy)
        return historias.item(n, hoy) if n else None
    if franja.startswith("especial:"):              # reels especiales (especiales.py): se lanzan a mano, cualquier día
        import especiales
        return especiales.item(franja.split(":", 1)[1], hoy)
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
    elif item["tipo"] == "historia":
        import historias
        historias.reel(item["n"], carpeta / item["video"], datos, hoy)
    elif item["tipo"] == "guia":
        import especiales
        especiales.imagen_guia(item["so"], carpeta / item["imagenes"][0])
    elif item["tipo"] == "especial":
        import especiales
        especiales.reel(item["nombre"], carpeta / item["video"], datos, hoy)
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
    if franja == "historias-todas":              # ensayo: los cinco reels con historia, sin publicar nada
        import historias
        for n in sorted(historias.HISTORIAS):
            it = historias.item(n, hoy)
            crear_archivos(it, datos, hoy, carpeta)
            (carpeta / it["video"]).with_suffix(".txt").write_text(it["texto"], encoding="utf-8")
        return {"id": "historias-todas"}
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
            franja = os.environ.get("FRANJA", "").strip() or franja_pendiente(datetime.utcnow(), estado, hoy)
            if not franja:
                print("[redes] Todo lo de esta hora ya está publicado: nada que hacer.")
                estado["preparado"] = []
                return 0
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

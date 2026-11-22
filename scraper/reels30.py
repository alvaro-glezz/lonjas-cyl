"""Los 30 reels diarios en 3D (data/reels-30.json, del 22 nov al 21 dic de 2026), a las 21:00 de Madrid, SIN VOZ
(el dueño entregará su voz; hasta entonces, solo música). Las cifras salen de los datos reales del día; si faltan,
ese día no se publica nada (nunca se inventa un precio).

  python scraper/reels30.py N [carpeta]          crea el reel N (1-30) con los datos de hoy, sin publicar
  python scraper/reels30.py --spec N             muestra las escenas (JSON) del reel N
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import redes  # noqa: E402
from instagram import NOMBRES, corto, etiquetas, nombre_corto, pie_texto  # noqa: E402
from paginas import WEB, num  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
GUIONES = RAIZ / "data" / "reels-30.json"
GAS_HIST = RAIZ / "data" / "gasoleo-historial.json"
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
RESUMEN = ["trigo", "cebada", "maiz", "centeno", "girasol", "cerdo-normal", "lechazo", "lechones"]


def guiones() -> list[dict]:
    return json.loads(GUIONES.read_text(encoding="utf-8"))["reels"]


def de_hoy(hoy: date) -> dict | None:
    return next((r for r in guiones() if r["fecha"] == hoy.isoformat()), None)


def _leer(ruta: Path):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _n(k: str) -> str:
    return NOMBRES.get(k, k).capitalize()


def _dir(p: dict) -> int:
    a, b = p.get("ant"), p.get("act")
    return 0 if a is None or b is None or abs(b - a) < 1e-9 else (1 if b > a else -1)


def _cambio(p: dict) -> str:
    a, b = p.get("ant"), p.get("act")
    if a is None or b is None:
        return "sin referencia"
    return "repite" if abs(b - a) < 1e-9 else f"{redes.signo(b - a, 2 if abs(b - a) < 1 else 0)} {p.get('unidad', '')}".strip()


# ---------- escenas con datos ----------

def barras_producto(datos, hoy, clave, forma="silo", color="paja", titulo=None, sub=None):
    r = redes.ranking(datos, clave, hoy)
    if not r:
        return None
    items = [{"etiqueta": nombre_corto(l), "valor": p["act"], "texto": num(p["act"]), "destacar": i == 0} for i, (l, p) in enumerate(r["filas"])]
    fechas = sorted({l["fecha"] for l, _ in r["filas"]})
    esc = {"tipo": "barras", "dur": 8, "forma": forma, "color": color, "titulo": titulo or f"{_n(clave)}: ¿dónde se paga más?",
           "sub": sub or f"{r['unidad']} · sesiones del {corto(fechas[0])} al {corto(fechas[-1])}" if len(fechas) > 1 else f"{r['unidad']} · sesión del {corto(fechas[0])}",
           "items": items, "nota": f"Diferencia: {num(r['filas'][0][1]['act'] - r['filas'][-1][1]['act'])} {r['unidad']}"}
    lineas = [f"• {nombre_corto(l)}: {num(p['act'])} {r['unidad']} ({_cambio(p)}, {corto(l['fecha'])})" for l, p in r["filas"]]
    return esc, lineas


def producto_y_evolucion(datos, hoy, clave, forma, color):
    """Ranking de lonjas (si hay al menos dos) y evolución de 8 semanas en la lonja con más historial."""
    escenas, lineas = [], []
    out = barras_producto(datos, hoy, clave, forma, color)
    if out:
        escenas.append(out[0]); lineas += out[1]
    s = serie(datos, clave, hoy)
    if s and len(s[2]) >= 4:
        nombre, u, pts = s
        v0, v1 = pts[0][1], pts[-1][1]
        escenas.append({"tipo": "curva", "dur": 7, "titulo": f"{_n(clave)} en {nombre}", "sub": f"Últimas 8 semanas · {u}",
                        "series": [{"nombre": _n(clave), "valores": [v for _, v in pts], "inicio": num(v0), "fin": f"{num(v1)} {u}",
                                    "color": "paja" if color in ("paja", "baja") else "pino"}]})
        lineas += ["", f"En {nombre}, del {corto(pts[0][0])} al {corto(pts[-1][0])}: {num(v0)} → {num(v1)} {u} ({redes.signo((v1 - v0) / v0 * 100, 1)} %)."]
    return (escenas, lineas) if escenas else None


def flechas_lonja(filas, titulo, sub=""):
    items = [{"etiqueta": p["producto"][:22], "dir": _dir(p), "texto": _cambio(p)} for p in filas[:8]]
    return {"tipo": "flechas", "dur": 6, "titulo": titulo, "sub": sub, "items": items}


def resumen_semana(datos, hoy):
    items, lineas = [], []
    for k in RESUMEN:
        r = redes.ranking(datos, k, hoy, dias=8)
        if not r:
            continue
        l, p = max(r["filas"], key=lambda x: abs((x[1].get("act") or 0) - (x[1].get("ant") or x[1].get("act") or 0)))
        items.append({"etiqueta": _n(k), "dir": _dir(p), "texto": f"{_cambio(p)} · {nombre_corto(l)}"})
        lineas.append(f"• {_n(k)}: {_cambio(p)} en {nombre_corto(l)} ({num(p['act'])} {p['unidad']})")
    if len(items) < 3:
        return None
    sube = [i["etiqueta"] for i in items if i["dir"] > 0]
    baja = [i["etiqueta"] for i in items if i["dir"] < 0]
    esc = [{"tipo": "flechas", "dur": 8, "titulo": "La semana en las lonjas", "sub": "El mayor cambio de cada producto, últimos 8 días", "items": items[:8]}]
    return esc, lineas + ["", f"Suben: {', '.join(sube) or 'ninguno'}. Bajan: {', '.join(baja) or 'ninguno'}."]


def serie(datos, clave, hoy, semanas=8):
    ev = redes.evolucion(datos, clave, hoy, semanas)
    if not ev:
        return None
    nombre, pts = max(ev["series"], key=lambda s: len(s[1]))
    return nombre, ev["unidad"], pts


def curva_trigo_cebada(datos, hoy):
    series, lineas = [], []
    for k, color in (("trigo", "paja"), ("cebada", "pino")):
        s = serie(datos, k, hoy)
        if not s or len(s[2]) < 4:
            continue
        nombre, u, pts = s
        v0, v1 = pts[0][1], pts[-1][1]
        series.append({"nombre": f"{_n(k)} · {nombre}", "valores": [v for _, v in pts], "inicio": num(v0), "fin": f"{num(v1)} {u}", "color": color})
        lineas.append(f"• {_n(k)} ({nombre}): {num(v0)} → {num(v1)} {u} ({redes.signo((v1 - v0) / v0 * 100, 1)} %), del {corto(pts[0][0])} al {corto(pts[-1][0])}")
    if not series:
        return None
    return [{"tipo": "curva", "dur": 9, "titulo": "Ocho semanas de mercado", "sub": "Lonja con más historial de cada producto", "series": series}], lineas


def gas_provincias():
    import semana
    g = semana.datos_gasoleo(_leer(RAIZ / "data" / "gasoleo.json"))
    if not g:
        return None
    items = [{"etiqueta": p["nombre"], "valor": p["media"], "texto": num(p["media"], 3), "destacar": i == 0} for i, p in enumerate(g["provincias"])]
    esc = [{"tipo": "barras", "dur": 9, "forma": "gota", "color": "pino", "titulo": "Gasóleo B por provincia",
            "sub": f"Precio medio · €/l · {corto(g['fecha'][:10])}", "items": items,
            "nota": f"Media de Castilla y León: {num(g['cyl'], 3)} €/l" if g.get("cyl") else ""}]
    lineas = [f"{i}. {p['nombre']}: {num(p['media'], 3)} €/l de media" for i, p in enumerate(g["provincias"], 1)]
    return esc, lineas + ["", f"Precios del Ministerio para la Transición Ecológica ({g['fecha'][:10]})."]


def gas_baratas():
    g = _leer(RAIZ / "data" / "gasoleo.json")
    if not g:
        return None
    todas = sorted(((b, p["nombre"]) for p in g.get("provincias", []) if p.get("cyl") for b in p.get("baratas", [])), key=lambda x: x[0]["precio"])[:5]
    if len(todas) < 3:
        return None
    items = [{"etiqueta": (b.get("municipio") or b.get("localidad") or "")[:18], "valor": b["precio"], "texto": num(b["precio"], 3), "destacar": i == 0}
             for i, (b, _) in enumerate(todas)]
    esc = [{"tipo": "barras", "dur": 9, "forma": "gota", "color": "pino", "titulo": "Las 5 más baratas", "sub": f"Gasóleo B en Castilla y León · €/l · {corto(g['fecha'][:10])}",
            "items": items, "nota": "Precio en cada gasolinera según el Ministerio"}]
    lineas = [f"{i}. {b.get('nombre', '')}, {b.get('municipio', '')} ({prov}): {num(b['precio'], 3)} €/l" for i, (b, prov) in enumerate(todas, 1)]
    return esc, lineas + ["", f"Precios del Ministerio para la Transición Ecológica ({g['fecha'][:10]}). Confírmalo antes de ir."]


def gas_mes(hoy):
    g, h = _leer(RAIZ / "data" / "gasoleo.json"), _leer(GAS_HIST)
    if not g or not h:
        return None
    ids = [p["id"] for p in g.get("provincias", []) if p.get("cyl")]
    desde = (hoy - timedelta(days=28)).isoformat()
    por_dia: dict[str, list[float]] = {}
    for i in ids:
        for f, media, *_ in h.get(i, []):
            if f >= desde and media:
                por_dia.setdefault(f, []).append(media)
    dias = sorted(f for f, v in por_dia.items() if len(v) == len(ids))
    if len(dias) < 7:
        return None
    vals = [sum(por_dia[f]) / len(ids) for f in dias]
    esc = [{"tipo": "curva", "dur": 9, "titulo": "El gasóleo B en un mes", "sub": "Media de las 9 provincias de Castilla y León · €/l",
            "series": [{"nombre": "Media CyL", "valores": vals, "inicio": num(vals[0], 3), "fin": f"{num(vals[-1], 3)} €/l", "color": "pino"}]}]
    return esc, [f"Del {corto(dias[0])} al {corto(dias[-1])}: de {num(vals[0], 3)} a {num(vals[-1], 3)} €/l ({redes.signo(vals[-1] - vals[0], 3)} €/l).",
                 "Media de las nueve provincias. Precios del Ministerio para la Transición Ecológica."]


def leon(datos, hoy, mesa, forma, color):
    import hortalizas
    r = hortalizas.patatas(datos, hoy, mesa)
    if not r:
        return None
    l, filas = r
    top = sorted(filas, key=lambda p: -p["act"])
    dec = 2 if any(not float(p["act"]).is_integer() for p in filas) else None
    items = [{"etiqueta": p["producto"][:14], "valor": p["act"], "texto": num(p["act"], dec), "destacar": i == 0} for i, p in enumerate(top[:7])]
    nombre = "Patatas" if mesa == "hortalizas" else "Alubias"
    esc = [{"tipo": "barras", "dur": 9, "forma": forma, "color": color, "titulo": f"{nombre} · Lonja de León",
            "sub": f"{filas[0]['unidad']} · sesión del {corto(l['fecha'])}", "items": items},
           flechas_lonja(filas, "Frente a la semana anterior", f"Sesión del {corto(l['fecha'])}")]
    return esc, [f"• {p['producto']}: {num(p['act'], dec)} {p['unidad']} ({_cambio(p)})" for p in filas] + ["", "Fuente: Lonja de León."]


def diferencias(datos, hoy):
    import semana
    filas = semana.datos_diferencias(datos, hoy)[:6]
    if len(filas) < 3:
        return None
    items = [{"etiqueta": _n(f["clave"]), "valor": f["dif"] / max(1e-9, f["alto"] if "alto" in f else 1), "texto": f"{num(f['dif'])} {f['unidad'].replace('€/', '€/')}"}
             for f in filas]
    # La altura es la diferencia en porcentaje del precio más bajo: así se comparan productos con unidades distintas.
    for it, f in zip(items, filas):
        r = redes.ranking(datos, f["clave"], hoy)
        it["valor"] = f["dif"] / r["filas"][-1][1]["act"] * 100
    items[max(range(len(items)), key=lambda i: items[i]["valor"])]["destacar"] = True
    esc = [{"tipo": "barras", "dur": 9, "forma": "columna", "color": "pino", "titulo": "¿Cuánto cambia según la lonja?",
            "sub": "De la que más paga a la que menos · altura = diferencia en %", "items": items}]
    return esc, [f"• {_n(f['clave'])}: {num(f['dif'])} {f['unidad']} ({f['alta']} › {f['baja']})" for f in filas] + ["", "Cada lonja cotiza su propia calidad."]


def camion(datos, hoy):
    r = redes.ranking(datos, "trigo", hoy)
    if not r or r["unidad"] != "€/t":
        return None
    (la, pa), (lb, pb) = r["filas"][0], r["filas"][-1]
    items = [{"etiqueta": nombre_corto(la), "valor": pa["act"] * 25, "texto": f"{num(pa['act'] * 25, 0)} €", "destacar": True},
             {"etiqueta": nombre_corto(lb), "valor": pb["act"] * 25, "texto": f"{num(pb['act'] * 25, 0)} €"}]
    esc = [{"tipo": "barras", "dur": 8, "forma": "columna", "color": "paja", "titulo": "Un camión de 25 t de trigo",
            "sub": f"Al precio de la lonja que más paga y de la que menos ({num(pa['act'])} y {num(pb['act'])} €/t)", "items": items,
            "nota": f"Diferencia: {num((pa['act'] - pb['act']) * 25, 0)} € por camión"}]
    return esc, [f"• {nombre_corto(la)}: 25 t × {num(pa['act'])} €/t = {num(pa['act'] * 25, 0)} €",
                 f"• {nombre_corto(lb)}: 25 t × {num(pb['act'])} €/t = {num(pb['act'] * 25, 0)} €",
                 "", "Cálculo con el precio publicado por cada lonja; no incluye portes ni calidad."]


def termometro(datos, hoy, clave="trigo"):
    s = serie(datos, clave, hoy, semanas=12)
    if not s or len(s[2]) < 6:
        return None
    nombre, u, pts = s
    vals = [v for _, v in pts]
    hoyv, lo, hi = vals[-1], min(vals), max(vals)
    pos = 0.5 if hi == lo else (hoyv - lo) / (hi - lo)
    donde = "en la parte alta" if pos >= 0.67 else "en la parte baja" if pos <= 0.33 else "en la zona media"
    items = [{"etiqueta": "Mínimo", "valor": lo, "texto": num(lo)}, {"etiqueta": "Hoy", "valor": hoyv, "texto": num(hoyv), "destacar": True},
             {"etiqueta": "Máximo", "valor": hi, "texto": num(hi)}]
    esc = [{"tipo": "barras", "dur": 8, "forma": "gota", "color": "baja" if pos >= 0.67 else "pino", "titulo": f"Termómetro del {NOMBRES.get(clave, clave)}",
            "sub": f"{nombre} · {u} · últimas 12 semanas", "items": items, "nota": f"Hoy está {donde} de su rango"}]
    return esc, [f"{_n(clave)} en {nombre}: hoy {num(hoyv)} {u}; en 12 semanas, mínimo {num(lo)} y máximo {num(hi)}. Está {donde}."]


def lechones(datos, hoy):
    out = barras_producto(datos, hoy, "lechones", forma="columna", color="pino2", titulo="Lechones por lonja")
    if not out:
        return None
    esc, lineas = out
    seg = next((l for l in datos.get("lonjas", []) if l["id"] == "segovia"), None)
    coch = next((p for p in (seg or {}).get("precios", []) if p.get("clave") == "cochinillo" and p.get("act") is not None), None)
    escenas = [esc]
    if coch and seg["fecha"] >= (hoy - timedelta(days=14)).isoformat():
        escenas.append({"tipo": "tarjetas", "dur": 4, "titulo": "Cochinillo de Segovia", "items": [
            {"titulo": f"{num(coch['act'])} {coch['unidad']}", "texto": f"{coch['producto']} · sesión del {corto(seg['fecha'])} · {_cambio(coch)}"}]})
        lineas.append(f"• Cochinillo (Segovia): {num(coch['act'])} {coch['unidad']} ({_cambio(coch)})")
    return escenas, lineas


def centeno_avena(datos, hoy):
    escenas, lineas = [], []
    for k, color in (("centeno", "pino2"), ("avena", "paja")):
        out = barras_producto(datos, hoy, k, forma="silo", color=color)
        if out:
            out[0]["dur"] = 6
            escenas.append(out[0]); lineas += [f"{_n(k)}:"] + out[1]
    return (escenas, lineas) if escenas else None


def calendario(datos):
    activas = [l for l in datos.get("lonjas", []) if l.get("estado") != "suspendida" and l.get("dia")]
    if not activas:
        return None
    orden = sorted(activas, key=lambda l: DIAS.index(l["dia"]) if l["dia"] in DIAS else 9)
    items = [{"titulo": l["dia"], "texto": f"{l.get('nombre', l['id'])} ({l.get('provincia', '')})"} for l in orden]
    return [{"tipo": "tarjetas", "dur": 2.6 * len(items), "titulo": "¿Qué lonja cotiza cada día?", "items": items}], \
        [f"• {l['dia']}: {l.get('nombre', l['id'])}" for l in orden]


# ---------- reels sin datos ----------

FIJOS = {
    1: ([{"tipo": "mesa", "dur": 8, "titulo": "Una mesa, dos partes", "sub": "Compradores y vendedores acuerdan un precio de referencia", "pizarra": "Precio de referencia"},
         {"tipo": "tarjetas", "dur": 8, "titulo": "¿Qué es una lonja?", "items": [
             {"titulo": "No es una subasta", "texto": "Es un acuerdo semanal que sirve de guía a todo el sector."},
             {"titulo": "Cada lonja, su día", "texto": "En Castilla y León cotizan en días distintos de la semana."},
             {"titulo": "Todas juntas", "texto": "Las ves en Lonjas CyL, gratis y en cuanto salen."}]}],
        ["En una lonja, compradores y vendedores se sientan a la misma mesa y acuerdan un precio de referencia.",
         "No es una subasta: es un acuerdo que sirve de guía a todo el sector. Cada lonja cotiza un día distinto."]),
    4: ([{"tipo": "tarjetas", "dur": 12, "titulo": "Tonelada, kilo vivo, kilo canal", "items": [
            {"titulo": "€/t", "texto": "Los cereales y las oleaginosas se cotizan por tonelada (1.000 kg)."},
            {"titulo": "€/kg vivo", "texto": "El ganado en vivo: por cada kilo que pesa el animal."},
            {"titulo": "€/kg canal", "texto": "Por cada kilo de canal, tras el sacrificio. Por eso es más alto que en vivo."},
            {"titulo": "Antes de comparar", "texto": "Mira siempre la unidad: si no coincide, no se puede comparar."}]}],
        ["€/t: cereales y oleaginosas, por tonelada.", "€/kg vivo: por cada kilo del animal.",
         "€/kg canal: por cada kilo de canal tras el sacrificio; por eso es más alto.", "Compara siempre con la misma unidad."]),
    10: ([{"tipo": "flechas", "dur": 6, "titulo": "Cómo leer una lonja", "sub": "Frente a la sesión anterior", "items": [
             {"etiqueta": "Sube", "dir": 1, "texto": "más que la semana pasada"}, {"etiqueta": "Baja", "dir": -1, "texto": "menos que la semana pasada"},
             {"etiqueta": "Repite", "dir": 0, "texto": "el mismo precio"}]},
          {"tipo": "tarjetas", "dur": 4, "titulo": "¿Y «s/c»?", "items": [{"titulo": "Sin cotización", "texto": "Ese día no hubo acuerdo de precio para ese producto, o no hubo operaciones."}]}],
         ["Sube / baja: frente a la sesión anterior.", "Repite: el mismo precio que la semana pasada.", "s/c: sin cotización ese día."]),
    12: ([{"tipo": "movil", "dur": 10, "titulo": "Avisos de precio por Telegram", "sub": "Gratis, en el robot @lonjascyl_bot", "items": [
             {"titulo": "Abre el robot", "texto": "Busca @lonjascyl_bot en Telegram y pulsa Iniciar."},
             {"titulo": "Escribe tu aviso", "texto": "Por ejemplo: «aviso trigo salamanca más de 240»."},
             {"titulo": "Te avisa solo", "texto": "Cuando la lonja pase de ese precio, te llega un mensaje."},
             {"titulo": "Tus avisos", "texto": "Escribe «avisos» para verlos y «borrar» para quitarlos."}]}],
         ["Abre @lonjascyl_bot en Telegram y escribe, por ejemplo: «aviso trigo salamanca más de 240».",
          "Cuando la lonja pase de ese precio, te llega un aviso. Gratis."]),
    15: ([{"tipo": "tarjetas", "dur": 12, "titulo": "El precio de la lonja no es el que cobras", "items": [
             {"titulo": "Calidad", "texto": "Peso específico, humedad, proteína… cambian el precio final."},
             {"titulo": "Portes", "texto": "Quién pone el transporte y hasta dónde."},
             {"titulo": "Pago", "texto": "Al contado o a plazo: no vale lo mismo."},
             {"titulo": "Úsalo para negociar", "texto": "La lonja es tu referencia para hablar con datos."}]}],
         ["El precio de la lonja es una referencia: al final cuentan la calidad, los portes, la forma y el plazo de pago y la cantidad.",
          "Úsalo para negociar con datos."]),
    19: ([{"tipo": "movil", "dur": 10, "titulo": "Mi pizarra", "sub": "Tus productos de un vistazo", "items": [
             {"titulo": "Toca la estrella", "texto": "En cada producto que te interese."},
             {"titulo": "Mi pizarra", "texto": "Al abrir Lonjas CyL los verás juntos, con su último precio."},
             {"titulo": "Sin registrarte", "texto": "Se guarda en tu móvil. Gratis."}]}],
         ["Toca la estrella en los productos que te interesan y aparecerán juntos en «Mi pizarra» al abrir Lonjas CyL.", "Sin registrarte y gratis."]),
    24: ([{"tipo": "movil", "dur": 10, "titulo": "Compara lonjas", "sub": "En la app, gratis", "items": [
             {"titulo": "Elige el producto", "texto": "Por ejemplo, trigo o lechazo."},
             {"titulo": "Pulsa comparar", "texto": "Verás todas las lonjas ordenadas de mayor a menor precio."},
             {"titulo": "Con su fecha", "texto": "Cada precio indica de qué sesión es."}]}],
         ["Elige el producto y pulsa comparar: todas las lonjas ordenadas, con la fecha de cada sesión."]),
    30: ([{"tipo": "tarjetas", "dur": 12, "titulo": "Todo Lonjas CyL", "items": [
             {"titulo": "Precios", "texto": "Todas las lonjas de Castilla y León, en cuanto salen."},
             {"titulo": "Comparar", "texto": "Qué lonja paga más por tu producto."},
             {"titulo": "Gasóleo B", "texto": "La gasolinera más barata de tu municipio."},
             {"titulo": "Avisos y comentario", "texto": "Avisos por Telegram y un comentario cada sábado."}]}],
         ["Precios de todas las lonjas de Castilla y León, comparador, gasóleo agrícola, avisos por Telegram y un comentario cada sábado. Gratis."]),
}


def contenido(n: int, datos: dict, hoy: date):
    """(escenas, líneas del texto) del reel n con los datos de hoy, o None si faltan datos."""
    if n in FIJOS:
        return FIJOS[n]
    if n == 8:
        return calendario(datos)
    if n in (2,):
        return gas_provincias()
    if n == 16:
        return gas_baratas()
    if n == 29:
        return gas_mes(hoy)
    producto = {3: ("trigo", "silo", "paja"), 9: ("cebada", "silo", "pino2"), 11: ("cerdo-normal", "columna", "baja"),
                13: ("maiz", "silo", "paja"), 17: ("lechazo", "columna", "pino"), 23: ("girasol", "silo", "paja")}
    if n in producto:
        return producto_y_evolucion(datos, hoy, *producto[n])
    if n == 5:
        return leon(datos, hoy, "hortalizas", "saco", "paja")
    if n == 6:
        return leon(datos, hoy, "legumbres", "tarro", "baja")
    if n in (7, 14, 21, 28):
        return resumen_semana(datos, hoy)
    if n == 18:
        return curva_trigo_cebada(datos, hoy)
    if n == 20:
        return diferencias(datos, hoy)
    if n == 22:
        return camion(datos, hoy)
    if n == 25:
        return centeno_avena(datos, hoy)
    if n == 26:
        return termometro(datos, hoy)
    if n == 27:
        return lechones(datos, hoy)
    return None


def spec(n: int, datos: dict, hoy: date, web: str = WEB) -> tuple[dict, list[str]] | None:
    g = next(r for r in guiones() if r["n"] == n)
    c = contenido(n, datos, hoy)
    if not c:
        return None
    escenas, lineas = c
    portada = {"tipo": "portada", "dur": 3, "titulo": g["titulo"], "sub": f"Lonjas CyL · {DIAS[hoy.weekday()].lower()} {corto(hoy.isoformat())}"}
    cierre = {"tipo": "cierre", "dur": 3.5, "web": web.replace("https://", "").rstrip("/")}
    return {"escenas": [portada, *escenas, cierre]}, lineas


def texto(n: int, lineas: list[str], web: str = WEB) -> str:
    g = next(r for r in guiones() if r["n"] == n)
    fuente = g.get("fuente") or ""
    cuerpo = [f"🎬 {g['titulo']}", "", *lineas, ""]
    if fuente and fuente != "—":
        cuerpo.append(f"Fuente: {fuente}.")
    cuerpo += [pie_texto(web), "Precios orientativos.", "", etiquetas("#reels", "#lonjas", "#agricultura")]
    return "\n".join(cuerpo)[:2150]


def item(datos: dict, hoy: date, n: int | None = None, con_voz: bool = False) -> dict | None:
    g = de_hoy(hoy) if n is None else next((r for r in guiones() if r["n"] == n), None)
    if not g:
        return None
    s = spec(g["n"], datos, hoy)
    if not s:
        print(f"[reels30] Reel {g['n']} («{g['titulo']}»): faltan datos hoy, no se publica.")
        return None
    base = f"{hoy}-diario-{g['n']:02d}" + ("-voz" if con_voz else "")
    t = texto(g["n"], s[1])
    if con_voz:
        if not guion_lleno(g["n"]):
            print(f"[reels30] Reel {g['n']}: su guion lleva datos del día y aún no tiene voz.")
            return None
        t = t.replace(pie_texto(WEB), pie_texto(WEB) + "\n" + redes.aviso_voz(), 1)
    return {"tipo": "tres", "n": g["n"], "id": base, "texto": t, "video": base + ".mp4", "spec": s[0], "voz": con_voz}


def guion_lleno(n: int) -> str | None:
    """Lo que lee la voz. Solo los guiones sin huecos {…} (aprender y app); los de datos aún no llevan voz."""
    g = next(r for r in guiones() if r["n"] == n)
    return None if "{" in g["guion"] else g["guion"]


def ajustar(spec: dict, segundos: float) -> dict:
    """Alarga las escenas centrales (no la portada ni el cierre) para que la voz quepa entera."""
    total = sum(e["dur"] for e in spec["escenas"])
    falta = segundos - total
    medio = spec["escenas"][1:-1]
    if falta <= 0 or not medio:
        return spec
    base = sum(e["dur"] for e in medio)
    return {**spec, "escenas": [spec["escenas"][0], *[{**e, "dur": round(e["dur"] * (base + falta) / base, 2)} for e in medio], spec["escenas"][-1]]}


def reel(it: dict, destino: Path) -> Path:
    import tres3d
    spec, habla = it["spec"], None
    if it.get("voz"):
        texto_voz = guion_lleno(it["n"])
        habla = redes.voz(texto_voz, destino.with_name(destino.stem + "-voz.wav")) if texto_voz else None
        if habla:
            spec = ajustar(spec, redes.duracion_wav(habla) + 0.6 + 1.5)       # 0,6 s de entrada y 1,5 s de margen
    try:
        return tres3d.render(spec, destino, voz=habla)
    finally:
        if habla:
            habla.unlink(missing_ok=True)


if __name__ == "__main__":
    datos = json.loads(redes.ig.DATOS.read_text(encoding="utf-8"))
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0])
    g = next(r for r in guiones() if r["n"] == n)
    hoy = date.today()
    s = spec(n, datos, hoy)
    if not s:
        sys.exit(f"Reel {n}: faltan datos hoy.")
    if "--spec" in sys.argv:
        print(json.dumps(s[0], ensure_ascii=False, indent=1))
        print(texto(n, s[1]))
        sys.exit(0)
    carpeta = Path(args[1]) if len(args) > 1 else redes.SALIDA / "diario"
    print(reel({"spec": s[0]}, carpeta / f"{hoy}-diario-{n:02d}.mp4"))

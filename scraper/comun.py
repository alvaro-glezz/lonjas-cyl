"""Utilidades compartidas por los lectores de cada lonja.

Todo lo que es "conocimiento del sector" (cómo se llama cada producto en
cada lonja, qué unidad usa, qué productos son comparables entre lonjas)
vive aquí, para que los lectores de cada lonja sean pequeños.
"""
from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Texto y números
# ---------------------------------------------------------------------------

def sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def slug(t: str) -> str:
    t = sin_acentos(t).lower().replace("ª", "a").replace("º", "o")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


NUM = r"-?\d{1,3}(?:\.\d{3})*(?:,\d+)?|-?\d+(?:[.,]\d+)?"
SIN_COTIZACION = re.compile(r"\b(s\s*/?\s*c|sin\s+cotiz\w*|sin\s+acuerdo)\b", re.I)


def numero(t: str | None) -> float | None:
    """'1.234,56' -> 1234.56 ; '228,00' -> 228.0 ; 'S/C' -> None."""
    if t is None:
        return None
    t = str(t).strip().replace("€", "").replace(" ", "")
    if not t or SIN_COTIZACION.search(t):
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Productos comparables entre lonjas
# ---------------------------------------------------------------------------
# clave -> lista de patrones (sobre el nombre en minúsculas y sin acentos).
# El primer patrón que encaje gana; el orden importa.
CLAVES: list[tuple[str, str]] = [
    ("trigo", r"^trigo\b"),
    ("cebada", r"^cebada\b"),
    ("maiz", r"^maiz\b"),
    ("avena", r"^avena\b"),
    ("centeno", r"^centeno\b"),
    ("triticale", r"^triticale\b"),
    ("girasol", r"^girasol(?!.*alto)"),
    ("alfalfa", r"^alfalfa (empacada|paquete rama)"),
    ("paja", r"^paja\b"),
    ("cerdo-selecto", r"^cerdo selecto"),
    ("cerdo-normal", r"^cerdo (blanco )?normal"),
    ("lechones", r"^lechon(es)? (base|20|tipo)"),
    ("lechazo", r"^lechazo (hasta 1[12]|10-12)"),
]


def clave_de(producto: str) -> str | None:
    p = sin_acentos(producto).lower()
    for clave, patron in CLAVES:
        if re.search(patron, p):
            return clave
    return None


# ---------------------------------------------------------------------------
# Lectura de líneas de boletín: "Trigo Blando 238,00 -2,00 236,00 € / t ="
# ---------------------------------------------------------------------------
UNIDAD = re.compile(r"(€|eur\w*)\s*/\s*(t\b|tm|kg\.?\s*(vivo|canal)?|kg|ud\w*|unidad|l\w*|e\.?q\.?)", re.I)


def unidad_de(linea: str, por_defecto: str = "") -> str:
    m = UNIDAD.search(linea)
    if not m:
        return por_defecto
    u = sin_acentos(m.group(2)).lower().replace(".", "").strip()
    if u in ("t", "tm"):
        return "€/t"
    if u.startswith("kg"):
        return "€/kg " + m.group(3).lower() if m.group(3) else "€/kg"
    if u.startswith("ud") or u.startswith("unidad"):
        return "€/ud"
    if u.startswith("eq") or u.startswith("e q"):
        return "€/E.Q."
    if u.startswith("l"):
        return "€/l"
    return por_defecto


def es_titulo(linea: str) -> bool:
    """Una línea en mayúsculas sin números se toma como cabecera de mesa."""
    l = linea.strip()
    return bool(l) and not re.search(r"\d", l) and l.upper() == l and len(l) >= 4 and re.search(r"[A-ZÁÉÍÓÚÑ]", l) is not None


CABECERA_RUIDO = re.compile(r"cotizaci[oó]n|anterior|actual|diferencia|tendencia|precio|www\.|http", re.I)


ROMANOS = {"i", "ii", "iii", "iv", "igp", "ib", "u", "r", "o"}


def bonito(nombre: str) -> str:
    """'……… PRIMERA' -> 'Primera'; 'TRIGO TIPO III' -> 'Trigo tipo III'."""
    nombre = re.sub(r"^[\s.…·:*-]+", "", nombre).strip()
    if nombre.upper() != nombre:
        return nombre[:1].upper() + nombre[1:]
    palabras = []
    for i, w in enumerate(nombre.lower().split()):
        palabras.append(w.upper() if w.strip("().") in ROMANOS else (w.capitalize() if i == 0 else w))
    return " ".join(palabras)


def _inicio_precios(linea: str) -> int | None:
    """Posición donde empiezan los precios: el primer número (o S/C) que no
    forma parte del nombre del producto. Se ignoran los números entre
    paréntesis y los que describen el producto ("15,1-19 kg", "9-2-44",
    "72 kg/hl", "dos carreras")."""
    prof = 0
    for m in re.finditer(rf"[()]|s\s*[/.]\s*c\b|sin\s+(cotiz|acuerdo)|{NUM}", linea, re.I):
        g = m.group(0)
        if g == "(":
            prof += 1
            continue
        if g == ")":
            prof = max(0, prof - 1)
            continue
        if prof or m.start() == 0:
            continue
        if g.startswith("-") and linea[m.start() - 1].isdigit():  # "9-2-44"
            continue
        despues = linea[m.end():m.end() + 8].lower()
        if re.match(r"^(\s*(kg|kgs|º|%|meses|m\b|a \d|cm)|-\d|/\d+\s*kg|º)", despues):
            continue
        antes = linea[:m.start()]
        if re.search(r"(\d\s*a|-|/)\s*$", antes):  # segunda mitad de "4 a 6 kg"
            continue
        return m.start()
    return None


def leer_linea(linea: str, con_diferencia: bool | None = None) -> dict | None:
    """Convierte una línea de boletín en {producto, ant, act, rango?}.

    Admite los formatos de los boletines de CyL:
      'Trigo Pienso 230,00 228,00 ▼'                     (anterior, actual)
      'Trigo Blando 238,00 -2,00 236,00 € / t'          (anterior, diferencia, actual)
      'Maíz 250,00 S/C'                                  (actual sin cotización)
      'Cerdo Selecto 1,20 / 1,21 ='                     (horquilla)
    """
    linea = re.sub(r"\s+", " ", linea.replace(" ", " ")).strip()
    if not linea or CABECERA_RUIDO.search(linea[:25]) or re.match(r"(?i)(lonja|semana|sesi[oó]n|fecha)\b", linea):
        return None
    if re.search(r"(?i)\d{1,2}\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)", linea):
        return None
    inicio = _inicio_precios(linea)
    if inicio is None:
        return None
    producto = linea[:inicio].strip(" .,:*-")
    resto = linea[inicio:]
    producto = bonito(re.sub(r"\*+$", "", producto).strip(" ,"))
    if len(producto) < 3 or producto.lower() in ("total", "media"):
        return None
    resto_sin_unidad = UNIDAD.sub(" ", resto)
    # Tokens: números o S/C, en orden
    tokens = re.findall(rf"s\s*[/.]\s*c\b|sin cotiz\w*|sin acuerdo|{NUM}", resto_sin_unidad, re.I)
    tokens = [t for t in tokens if t.strip()]
    vals = [numero(t) if not re.match(r"s\s*[/.]\s*c", t, re.I) else None for t in tokens]
    if not tokens:
        return None
    rango = None
    # Formato de Lerma: "231 €/TONELADA (232)" = actual y, entre paréntesis, anterior
    lerma = re.match(rf"\s*({NUM}|s\s*/\s*c)\s*(€|eur)[^()]*\(\s*({NUM}|s\s*/\s*c)\s*\)", resto, re.I)
    if lerma:
        out = {"producto": producto, "ant": numero(lerma.group(3)), "act": numero(lerma.group(1))}
        return out
    barra = re.search(rf"({NUM})\s*/\s*({NUM})", resto_sin_unidad)
    if len(vals) == 1:
        ant, act = None, vals[0]
    elif len(vals) == 2 and barra and None not in vals:
        # Formato "mín / máx" de Salamanca; "34,00 / 0,00" significa precio único
        if vals[1] == 0:
            ant, act = None, vals[0]
        else:
            ant, act = None, round((vals[0] + vals[1]) / 2, 4)
            rango = f"{tokens[0]}–{tokens[1]}"
    elif len(vals) == 2:
        ant, act = vals
    else:
        a, b, c = vals[0], vals[1], vals[2]
        if con_diferencia is not False and a is not None and b is not None and c is not None and abs(round(a + b, 4) - c) < 0.0051:
            ant, act = a, c
        elif con_diferencia is not False and a is not None and c is None:
            ant, act = a, None
        else:
            ant, act = a, b
    if act is None and ant is None:
        return {"producto": producto, "ant": None, "act": None}
    out = {"producto": producto, "ant": ant, "act": act}
    if rango:
        out["rango"] = rango
    return out


def leer_texto(texto: str, unidad_defecto: str = "") -> list[dict]:
    """Lee un boletín completo en texto plano, detectando las mesas por sus cabeceras."""
    filas, cat, unidad_mesa = [], "General", unidad_defecto
    for bruta in texto.splitlines():
        linea = bruta.strip()
        if not linea:
            continue
        if es_titulo(linea):
            t = re.sub(r"^MESA (DE|DEL) ", "", linea.strip()).strip()
            if not CABECERA_RUIDO.search(t) and len(t) < 40:
                cat = t.capitalize()
            continue
        u = unidad_de(linea)
        if u and not re.search(r"\d", UNIDAD.sub("", linea)):
            unidad_mesa = u  # línea que solo declara la unidad de la mesa
            continue
        f = leer_linea(linea)
        if f:
            f["cat"] = cat
            f["unidad"] = u or unidad_mesa
            filas.append(f)
    return filas

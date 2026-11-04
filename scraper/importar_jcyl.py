"""Importa el histórico semanal de lonjas que publica la Junta de Castilla y León.

Fuente: https://agriculturaganaderia.jcyl.es/web/es/estadistica-informacion-agraria/lonjas-2026.html
(y la página equivalente de 2025). Cada semana la Junta publica un Excel con cinco hojas
(Bovino, Ovino-Caprino, Porcino, Avícola y Granos y henos). En cada hoja, cada lonja ocupa un
bloque de columnas: precio y diferencia, o mínimo / máximo y diferencia.

Uso:
    python scraper/importar_jcyl.py              # importa los Excel guardados en data/fuentes/jcyl/
    python scraper/importar_jcyl.py --descargar  # además baja los Excel nuevos de la web de la Junta

Resultado (la app solo lee estos archivos):
    data/historico/indice.json   lonjas, series (producto + unidad + lonja) y archivos importados
    data/historico/<año>.json    puntos de cada serie: [fecha de celebración, semana ISO, precio o mínimo, máximo]

Reglas: no se corrige ni se inventa ningún valor. Se guardan tal cual el precio, la unidad, el nombre del
producto y la fecha de celebración que publica la Junta. Una misma sesión repetida en dos Excel seguidos
se guarda una sola vez. Si una lonja no indica fecha de celebración, el punto queda sin fecha y se
identifica por la semana del Excel.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from comun import numero, sin_acentos, slug  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "data" / "fuentes" / "jcyl"
SALIDA = RAIZ / "data" / "historico"
PAGINA = "https://agriculturaganaderia.jcyl.es/web/es/estadistica-informacion-agraria/lonjas-{anio}.html"
ANIOS = (2025, 2026)
MAX_ARCHIVO = 30_000_000

SECTORES = {
    "Bovino": "Vacuno",
    "Ovino-Caprino": "Ovino y caprino",
    "Porcino": "Porcino",
    "Sector Avícola y cunícola": "Aves y conejos",
    "Granos y henos": "Cereales y forrajes",
}

# Nombre en el Excel (en minúsculas y sin acentos ni asteriscos) -> (id, nombre, ámbito, id en la app)
_L = [
    ("salamanca", "Lonja de Salamanca", "cyl", "salamanca", ["salamanca", "lonja de salamanca"]),
    ("leon", "Lonja de León", "cyl", "leon", ["leon", "lonja de leon"]),
    ("segovia", "Lonja de Segovia", "cyl", "segovia", ["segovia", "lonja de segovia"]),
    ("lerma", "Lonja de Lerma", "cyl", "lerma", ["lerma", "lonja de lerma"]),
    ("zamora", "Lonja de Zamora", "cyl", "zamora", ["zamora", "lonja de zamora"]),
    ("valladolid", "Lonja de Valladolid", "cyl", None, ["valladolid"]),
    ("palencia", "Lonja de Palencia", "cyl", None, ["palencia"]),
    ("medina-del-campo", "Mercado de Medina del Campo", "cyl", None, ["mercado de medina del campo"]),
    ("mercado-salamanca", "Mercado de Salamanca", "cyl", None, ["mercado de salamanca"]),
    ("mercado-ganados-salamanca", "Mercado Regional de Ganados de Salamanca", "cyl", None,
     ["mercado regional de ganados de salamanca"]),
    ("mercado-ganados-leon", "Mercado Regional de Ganados de León", "cyl", None, ["mercado regional de ganados de leon"]),
    ("mesa-lechazo", "Asociación Mesa del Lechazo de Castilla y León", "cyl", None,
     ["asociacion mesa del lechazo de castilla y leon"]),
    ("ebro", "Lonja del Ebro", "nacional", None, ["ebro", "lonja de ebro", "lonja del ebro"]),
    ("binefar", "Lonja de Binéfar", "nacional", None, ["binefar", "lonja de binefar"]),
    ("lerida", "Lonja de Lérida", "nacional", None, ["lerida"]),
    ("mercolleida", "Mercolleida", "nacional", None, ["mercolleida", "mercolerida"]),
    ("albacete", "Lonja de Albacete", "nacional", None, ["albacete"]),
    ("ciudad-real", "Lonja de Ciudad Real", "nacional", None, ["ciudad real", "lonja de ciudad real"]),
    ("extremadura", "Lonja de Extremadura", "nacional", None, ["extremadura", "lonja de extremadura"]),
    ("murcia", "Lonja de Murcia", "nacional", None, ["lonja de murcia"]),
    ("mercamurcia", "MercaMurcia", "nacional", None, ["mercamurcia"]),
    ("reus", "Lonja de Reus", "nacional", None, ["reus", "lonja de reus"]),
    ("silleda", "Silleda", "nacional", None, ["silleda"]),
    ("vich", "Lonja de Vich", "nacional", None, ["lonja de vich"]),
    ("santiago", "Lonja de Santiago", "nacional", None, ["lonja de santiago"]),
    ("madrid", "Madrid", "nacional", None, ["madrid"]),
    ("bellpuig", "Bellpuig", "nacional", None, ["bellpuig"]),
    ("talavera-reina", "Talavera de la Reina", "nacional", None, ["talavera de la reina"]),
    ("mercado-talavera", "Mercado de Talavera", "nacional", None, ["mercado de talavera"]),
    ("torrelavega", "Torrelavega", "nacional", None, ["torrelavega"]),
    ("pola-siero", "Pola de Siero", "nacional", None, ["pola de siero"]),
]
PROVINCIAS = {"salamanca": "Salamanca", "leon": "León", "segovia": "Segovia", "lerma": "Burgos", "zamora": "Zamora", "valladolid": "Valladolid", "palencia": "Palencia", "medina-del-campo": "Valladolid", "mercado-salamanca": "Salamanca", "mercado-ganados-salamanca": "Salamanca", "mercado-ganados-leon": "León", "mesa-lechazo": "Castilla y León", "ebro": "Zaragoza", "binefar": "Huesca", "lerida": "Lleida", "mercolleida": "Lleida", "albacete": "Albacete", "ciudad-real": "Ciudad Real", "extremadura": "Badajoz", "murcia": "Murcia", "mercamurcia": "Murcia", "reus": "Tarragona", "silleda": "Pontevedra", "vich": "Barcelona", "santiago": "A Coruña", "madrid": "Madrid", "bellpuig": "Lleida", "talavera-reina": "Toledo", "mercado-talavera": "Toledo", "torrelavega": "Cantabria", "pola-siero": "Asturias"}
LONJAS = {i: {"nombre": n, "ambito": a, "provincia": PROVINCIAS[i], **({"app": app} if app else {})}
          for i, n, a, app, _ in _L}
NOMBRES = {alias: i for i, _, _, _, alias_ in _L for alias in alias_}

IGNORAR = re.compile(r"^(fecha de celebraci|documentaci|\*|nota\b|semana\b|diferencia de cotizaci|datos no disponibles|lonjas (nacionales|regionales)|m[ií]n$|m[aá]x$|id$|precio$|diferencia$)", re.I)


def norm(t: str) -> str:
    t = sin_acentos(str(t)).lower().replace("*", " ")
    return re.sub(r"\s+", " ", t).strip()


def limpio(t: str) -> str:
    return re.sub(r"\s+", " ", str(t).replace("\xa0", " ")).strip()


def unidad(t: str) -> str:
    """'(€/Kg. vivo)' -> '€/kg vivo'; '(€/100Kg)' -> '€/100 kg'. Solo se normaliza la escritura."""
    u = norm(t).strip("() ").replace("eur", "€").replace(" / ", "/")
    u = re.sub(r"\bkgs?\.?", "kg", u).replace("100kg", "100 kg").replace("kg.", "kg")
    u = re.sub(r"kg\.?(vivo|canal)", r"kg \1", u)
    u = u.replace("€/ud.", "€/unidad").replace("€/ud", "€/unidad")
    return re.sub(r"\s+", " ", u).strip(" .")


# ---------------------------------------------------------------------------
# Lectura de la hoja como cuadrícula (igual para .xlsx y .xls)
# ---------------------------------------------------------------------------
class Hoja:
    def __init__(self, nombre, celdas, combinadas, max_col):
        self.nombre, self.celdas, self.combinadas, self.max_col = nombre, celdas, combinadas, max_col

    def fila(self, r):
        return sorted((c, v) for (rr, c), v in self.celdas.items() if rr == r)


def abrir(ruta: Path) -> list[Hoja]:
    if ruta.stat().st_size > MAX_ARCHIVO:
        raise ValueError("archivo demasiado grande")
    hojas = []
    if ruta.suffix == ".xlsx":
        import openpyxl, warnings  # noqa: E401
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = openpyxl.load_workbook(ruta, data_only=True)
        for ws in wb.worksheets:
            celdas = {}
            for row in ws.iter_rows():
                for c in row:
                    if c.value is not None and not (isinstance(c.value, str) and not c.value.strip()):
                        celdas[(c.row, c.column)] = c.value
            comb = [(m.min_row, m.min_col, m.max_row, m.max_col) for m in ws.merged_cells.ranges]
            hojas.append(Hoja(ws.title, celdas, comb, ws.max_column))
    else:
        import xlrd
        wb = xlrd.open_workbook(str(ruta), formatting_info=True)
        for ws in wb.sheets():
            celdas = {}
            for r in range(ws.nrows):
                for c in range(ws.ncols):
                    cel = ws.cell(r, c)
                    if cel.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        continue
                    v = cel.value
                    if cel.ctype == xlrd.XL_CELL_DATE:
                        v = xlrd.xldate_as_datetime(v, wb.datemode)
                    if isinstance(v, str) and not v.strip():
                        continue
                    celdas[(r + 1, c + 1)] = v
            comb = [(r0 + 1, c0 + 1, r1, c1) for r0, r1, c0, c1 in ws.merged_cells]
            hojas.append(Hoja(ws.name, celdas, comb, ws.ncols))
    return hojas


# ---------------------------------------------------------------------------
# Interpretación de una hoja
# ---------------------------------------------------------------------------
def es_fecha(v) -> bool:
    return isinstance(v, (dt.datetime, dt.date)) and v.year >= 2000


def token(v):
    """Clasifica el contenido de una celda de datos. Devuelve None si es texto (etiqueta)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return ("n", round(float(v), 6))
    if es_fecha(v) or isinstance(v, (dt.datetime, dt.date, dt.time)):
        return ("x", None)
    t = limpio(v)
    if t in ("/", "-"):
        return ("/", None)
    if t in ("=", ",", ".", "º", "*"):
        return ("=", None)
    if re.fullmatch(r"(?i)s\s*/\s*c\.?|sin cotiz\w*|n\.?\s*c\.?", t):
        return ("sc", None)
    m = re.fullmatch(r"'?(-?\d+(?:[.,]\d+)?)\s*/\s*(-?\d+(?:[.,]\d+)?)", t)
    if m:
        return ("r", (numero(m.group(1)), numero(m.group(2))))
    if re.fullmatch(r"'?[-+]?\d+(?:[.,]\d+)?", t):
        return ("n", numero(t.lstrip("'")))
    return None


IDEM = {'"', "”", "“", "''", "id", "id.", "idem", "ídem"}


def es_unidad(v) -> bool:
    return isinstance(v, str) and ("€" in v and len(v) < 40 or limpio(v).lower() in IDEM)


def leer_hoja(h: Hoja):
    """Devuelve una lista de (lonja, fecha, sección + producto, unidad, mínimo, máximo, diferencia, celda)."""
    cab = []  # (fila, col_ini, col_fin, id_lonja)
    comb_por_celda = {(r0, c0): (r1, c1) for r0, c0, r1, c1 in h.combinadas}
    filas = sorted({r for r, _ in h.celdas})
    for r in filas:
        fila = h.fila(r)
        cols_cab = [(c, NOMBRES[norm(v)]) for c, v in fila if isinstance(v, str) and norm(v) in NOMBRES]
        for i, (c, lid) in enumerate(cols_cab):
            if (r, c) in comb_por_celda:
                fin = comb_por_celda[(r, c)][1]
            elif i + 1 < len(cols_cab):
                fin = cols_cab[i + 1][0] - 1
            else:
                fin = h.max_col
            cab.append((r, c, fin, lid))
    filas_cab = {r for r, *_ in cab}

    def lonja_de(r, c):
        mejor = None
        for rr, c0, c1, lid in cab:
            if rr < r and c0 <= c <= c1 and (mejor is None or rr > mejor[0]):
                mejor = (rr, c0, c1, lid)
        if mejor is None:
            return None
        # Subcolumnas dentro del bloque de una lonja (p. ej. León: «Frisona» y otra sin rótulo).
        # Se reconocen por celdas combinadas con texto entre la cabecera y la fila de datos.
        rr0, c0, c1, lid = mejor
        for fr in range(rr0 + 1, r):
            en_fila = [(m0, m1) for (a, m0, b, m1) in h.combinadas if a == fr and c0 <= m0 and m1 <= c1 and m1 > m0]
            rotulos = {m0: limpio(h.celdas[(fr, m0)]) for m0, _ in en_fila
                       if isinstance(h.celdas.get((fr, m0)), str) and not IGNORAR.search(norm(h.celdas[(fr, m0)]))
                       and re.search(r"[a-zA-Z]", h.celdas[(fr, m0)])}
            if rotulos:
                for m0, m1 in en_fila:
                    if m0 <= c <= m1 and not es_fecha(h.celdas.get((fr, m0))):
                        return (rr0, c0, c1, lid, rotulos.get(m0, ""), m0)
        return (*mejor, "", c0)

    def fecha_de(r, bloque):
        rr0, c0, c1 = bloque[:3]
        for rr in range(r - 1, rr0 - 1, -1):
            fechas = [v for c, v in h.fila(rr) if c0 <= c <= c1 and es_fecha(v)]
            if fechas:
                return fechas[0].date().isoformat()
        return None

    secciones, niveles, salida, avisos, ult_unidad = {}, {}, [], [], {}
    for r in filas:
        if r in filas_cab:
            continue
        fila = h.fila(r)
        # Partir la fila en tramos: [etiquetas] [unidad] [datos...]; un tramo nuevo empieza con otra etiqueta
        tramos, actual = [], None
        for c, v in fila:
            t = token(v)
            if t is None and not es_unidad(v):
                txt = limpio(v)
                if IGNORAR.search(norm(txt)) or txt.startswith("*") or not re.search(r"[a-zA-Záéíóúñ]", txt):
                    actual = None
                    continue
                if (actual is None or actual["unidad"] is not None or actual["datos"]
                        or (actual["etiquetas"] and c - actual["etiquetas"][-1][0] > 3)):
                    actual = {"etiquetas": [], "unidad": None, "datos": []}
                    tramos.append(actual)
                actual["etiquetas"].append((c, txt))
            elif es_unidad(v) and (t is None or limpio(v).lower() in IDEM):
                if limpio(v).lower() in IDEM:
                    if c not in ult_unidad:
                        actual = None
                        continue
                    v = ult_unidad[c]  # «"» = la misma unidad que la fila de arriba
                ult_unidad[c] = v
                if actual is None:
                    actual = {"etiquetas": [], "unidad": None, "datos": []}
                    tramos.append(actual)
                actual["unidad"] = (c, v)
            elif actual is not None and t[0] != "x":
                actual["datos"].append((c, t))
        for tr in tramos:
            if not tr["etiquetas"]:
                continue
            col0 = tr["etiquetas"][0][0]
            valores = [t for _, t in tr["datos"] if t[0] in ("n", "r", "sc")]
            hay_valores = bool(valores) and not (len(valores) == 1 and valores[0] == ("n", 0.0))
            if tr["unidad"] is None and not hay_valores:
                # Cabecera de sección ("Añojos", "Lechazos", "Cebo")
                secciones[col0] = (r, " ".join(t for _, t in tr["etiquetas"]))
                for k in [k for k in niveles if k >= col0]:
                    del niveles[k]
                continue
            if tr["unidad"] is None:
                continue
            # Etiquetas en varias columnas ("Huevos | Blancos | XL"): las que faltan se heredan de la fila anterior
            for k in [k for k in niveles if k >= col0]:
                del niveles[k]
            for c, t in tr["etiquetas"]:
                niveles[c] = t
            partes = [niveles[k] for k in sorted(niveles) if col0 - 3 <= k < tr["unidad"][0]]
            # Una sección solo vale dentro del bloque de lonjas en el que aparece (debajo de su cabecera)
            cab_encima = max((rr for rr, *_ in cab if rr < r), default=0)
            sec = next((secciones[k][1] for k in sorted(secciones, reverse=True)
                        if k <= col0 and secciones[k][0] > cab_encima), None)
            if sec and norm(sec) not in norm(partes[0]):
                partes = [sec] + partes
            producto = " · ".join(partes)
            u = unidad(tr["unidad"][1])
            # Agrupar los datos por lonja
            por_lonja = collections.OrderedDict()
            for c, t in tr["datos"]:
                b = lonja_de(r, c)
                if b is None:
                    if t[0] in ("n", "r"):
                        avisos.append(f"{h.nombre}!{r},{c}: valor sin lonja")
                    continue
                por_lonja.setdefault(b, []).append((c, t))
            for b, toks in por_lonja.items():
                lid, sub = b[3], b[4]
                tipos = [t[0] for _, t in toks]
                vals = [t for _, t in toks if t[0] in ("n", "sc", "r")]
                mn = mx = dif = None
                if any(t[0] == "r" for t in vals):
                    i = next(i for i, t in enumerate(vals) if t[0] == "r")
                    mn, mx = vals[i][1]
                    resto = vals[i + 1:]
                    dif = resto[0][1] if resto and resto[0][0] == "n" else None
                elif "/" in tipos:
                    i = tipos.index("/")
                    antes = [t for _, t in toks[:i] if t[0] in ("n", "sc")]
                    despues = [t for _, t in toks[i + 1:] if t[0] in ("n", "sc")]
                    a = antes[-1] if antes else None
                    z = despues[0] if despues else None
                    mn = a[1] if a and a[0] == "n" else None
                    mx = z[1] if z and z[0] == "n" else None
                    if a is None and z is not None and len(despues) >= 1:
                        # "/ 9,35 0" sin mínimo: precio único
                        mn, mx = mx, None
                    if mn is None and mx is not None:
                        mn, mx = mx, None
                    d = despues[1:] if z is not None else despues
                    dif = d[0][1] if d and d[0][0] == "n" else None
                elif len(vals) == 1:
                    mn = vals[0][1] if vals[0][0] == "n" else None
                elif len(vals) == 2:
                    mn = vals[0][1] if vals[0][0] == "n" else None
                    dif = vals[1][1] if vals[1][0] == "n" else None
                elif len(vals) == 3:
                    mn = vals[0][1] if vals[0][0] == "n" else None
                    mx = vals[1][1] if vals[1][0] == "n" else None
                    dif = vals[2][1] if vals[2][0] == "n" else None
                elif not vals:
                    continue
                else:
                    avisos.append(f"{h.nombre}!{r}: {len(vals)} valores para {lid} en «{producto}»; fila ambigua, no se importa")
                    continue
                if mn is None and mx is not None:
                    mn, mx = mx, None
                if mx is not None and mx == mn:
                    mx = None
                if mn is None:
                    continue  # S/C o sin dato
                if mx is not None and mx < mn:
                    avisos.append(f"{h.nombre}!{r}: mínimo {mn} mayor que máximo {mx} ({lid}, «{producto}»); no se importa")
                    continue
                nombre = f"{producto} · {sub}" if sub and norm(sub) not in norm(producto) else producto
                salida.append((lid, fecha_de(r, b), nombre, u, mn, mx, dif, f"{h.nombre}!{r}"))
    return salida, avisos


# ---------------------------------------------------------------------------
# Semana de cada Excel
# ---------------------------------------------------------------------------
def semana_iso(fecha: str) -> str:
    a, s, _ = dt.date.fromisoformat(fecha).isocalendar()
    return f"{a}-W{s:02d}"


def fecha_plausible(fecha: str, anio: int, num: int) -> bool:
    """Una sesión publicada en el Excel de la semana N es de esa semana o de alguna de las cinco anteriores
    (fiestas, lonjas que no cotizan todas las semanas). Lo demás es una errata de la fuente."""
    lunes_ = dt.date.fromisocalendar(anio, min(num, 52), 1)
    f = dt.date.fromisoformat(fecha)
    return lunes_ - dt.timedelta(days=42) <= f <= lunes_ + dt.timedelta(days=7)


def semana_archivo(anio: int, num: int, filas) -> tuple[str, str | None]:
    """La semana del Excel es la de la mayoría de las fechas de celebración publicadas en él.
    Devuelve (semana, aviso). Si no coincide con el título del enlace, se avisa."""
    rotulo = f"{anio}-W{num:02d}"
    sem = collections.Counter(semana_iso(f) for _, f, *_ in filas if f)
    if not sem:
        return rotulo, f"sin fechas de celebración; se usa la semana del título ({rotulo})"
    if rotulo in sem:
        return rotulo, None
    mayoria, n = sem.most_common(1)[0]
    if n * 2 >= sum(sem.values()):
        return mayoria, f"el título dice semana {num} pero ninguna fecha de celebración es de esa semana; se usa {mayoria}"
    return rotulo, f"ninguna fecha de celebración es de la semana {num}; se mantiene la del título"



# ---------------------------------------------------------------------------
# Descarga (opcional) de los Excel publicados
# ---------------------------------------------------------------------------
DOMINIO_JCYL = "jcyl.es"
MAX_REDIRECCIONES = 5


def bajar(url: str):
    """Descarga segura, con las mismas reglas que scraper/actualizar.py: solo https y solo la web de la Junta
    (jcyl.es y sus subdominios), redirecciones revisadas una a una y tamaño limitado."""
    import requests
    for _ in range(MAX_REDIRECCIONES + 1):
        p = urllib.parse.urlparse(url)
        h = (p.hostname or "").lower()
        if p.scheme != "https" or not (h == DOMINIO_JCYL or h.endswith("." + DOMINIO_JCYL)):
            raise RuntimeError(f"Dirección no permitida ({h})")
        r = requests.get(url, headers={"User-Agent": "lonjas-cyl (app de cotizaciones agrarias)"},
                         timeout=(10, 60), stream=True, allow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
            url = urllib.parse.urljoin(url, r.headers["Location"])
            r.close()
            continue
        r.raise_for_status()
        buf = bytearray()
        for trozo in r.iter_content(65536):
            buf += trozo
            if len(buf) > MAX_ARCHIVO:
                r.close()
                raise RuntimeError("Respuesta demasiado grande")
        r._content, r._content_consumed = bytes(buf), True
        return r
    raise RuntimeError("Demasiadas redirecciones")


def descargar() -> list[str]:
    import requests

    avisos = []
    manifiesto = FUENTES / "enlaces.tsv"
    previos = {}
    if manifiesto.exists():
        for linea in manifiesto.read_text("utf-8").splitlines():
            p = linea.split("\t")
            if len(p) == 3:
                previos[(p[0], p[1])] = p[2]
    for anio in ANIOS:
        try:
            html = bajar(PAGINA.format(anio=anio)).text
        except (requests.RequestException, RuntimeError) as exc:
            avisos.append(f"No se pudo leer la página de {anio}: {type(exc).__name__}")
            continue
        for m in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
            href = urllib.parse.urljoin(PAGINA.format(anio=anio), m.group(1).replace("&amp;", "&"))
            texto = re.sub(r"\s*\(\d+\s*kbytes\)", "", limpio(re.sub(r"<[^>]+>", " ", m.group(2))), flags=re.I).strip()
            ruta = urllib.parse.unquote(urllib.parse.urlparse(href).path)
            s = re.search(r"Semana\s+(\d{1,2})\b", texto)
            if not s or not re.search(r"\.xlsx?$", ruta, re.I):
                continue
            destino = FUENTES / str(anio) / f"semana-{int(s.group(1)):02d}{Path(ruta).suffix.lower()}"
            if destino.exists() or destino.with_suffix(".xls").exists() or destino.with_suffix(".xlsx").exists():
                continue
            if any(k[1] == href.split("?")[0] and k[0] != str(anio) for k in previos):
                avisos.append(f"{anio} semana {s.group(1)}: el enlace apunta a un Excel de otro año; no se descarga")
                continue
            try:
                r = bajar(href)
            except (requests.RequestException, RuntimeError) as exc:
                avisos.append(f"{anio} semana {s.group(1)}: descarga fallida ({type(exc).__name__})")
                continue
            if not r.content.startswith((b"PK", b"\xd0\xcf\x11\xe0")):
                avisos.append(f"{anio} semana {s.group(1)}: no es un Excel; no se guarda")
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(r.content)
            previos[(str(anio), href.split("?")[0])] = texto
            print(f"Descargado {destino.relative_to(RAIZ)}")
    manifiesto.write_text("".join(f"{a}\t{u}\t{t}\n" for (a, u), t in sorted(previos.items())), "utf-8")
    return avisos


# ---------------------------------------------------------------------------
# Proceso completo
# ---------------------------------------------------------------------------
def importar() -> dict:
    series, puntos, archivos, avisos, vistos = {}, collections.defaultdict(dict), [], [], set()
    total_leidos = repetidos = 0
    for anio in ANIOS:
        for ruta in sorted((FUENTES / str(anio)).glob("semana-*.xls*")):
            num = int(re.search(r"semana-(\d+)", ruta.name).group(1))
            try:
                hojas = abrir(ruta)
            except Exception as exc:  # noqa: BLE001
                avisos.append(f"{ruta.name} ({anio}): no se pudo abrir ({type(exc).__name__})")
                continue
            if not any(hj.nombre in SECTORES for hj in hojas):
                avisos.append(f"{anio} semana {num}: formato distinto (hojas {[hj.nombre for hj in hojas]}); "
                              "no son cotizaciones de lonja y no se importa")
                archivos.append({"anio": anio, "semana": num, "archivo": f"{anio}/{ruta.name}", "importado": False,
                                 "motivo": "Publicación distinta (precios medios provinciales), no cotizaciones de lonja"})
                continue
            filas = []
            for hj in hojas:
                if hj.nombre not in SECTORES:
                    continue
                f, av = leer_hoja(hj)
                filas += [(SECTORES[hj.nombre], *x) for x in f]
                avisos += [f"{anio} s{num} {a}" for a in av]
            erratas = collections.Counter()
            for i, x in enumerate(filas):
                if x[2] and not fecha_plausible(x[2], anio, num):
                    erratas[(x[1], x[2])] += 1
                    filas[i] = (*x[:2], None, *x[3:])
            for (lid, f), n in sorted(erratas.items()):
                avisos.append(f"{anio} semana {num}: {lid} publica la fecha {f}, imposible para este Excel "
                              f"({n} precios); se guardan sin fecha, identificados por la semana")
            sem, aviso = semana_archivo(anio, num, [(x[1], x[2]) for x in filas])
            if aviso:
                avisos.append(f"{anio} semana {num}: {aviso}")
            if sem in vistos:
                avisos.append(f"{anio} semana {num}: la semana {sem} ya estaba en otro Excel; se omite")
                continue
            vistos.add(sem)
            nuevos = 0
            for sector, lid, fecha, producto, u, mn, mx, dif, celda in filas:
                sid = f"{lid}--{slug(sector)}--{slug(producto)}--{slug(u)}"[:100].strip("-")
                sid = re.sub(r"-{3,}", "--", sid)
                series.setdefault(sid, {"l": lid, "s": sector, "p": producto, "u": u})
                clave = fecha or sem
                total_leidos += 1
                if clave in puntos[sid]:
                    repetidos += 1  # misma sesión publicada de nuevo en el Excel siguiente
                    continue
                puntos[sid][clave] = {"f": fecha, "w": sem, "a": mn, "b": mx, "d": dif, "o": f"{anio}/{ruta.name}"}
                nuevos += 1
            archivos.append({"anio": anio, "semana": num, "semana_iso": sem, "archivo": f"{anio}/{ruta.name}",
                             "importado": True, "registros": nuevos,
                             "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest()})
    return {"series": series, "puntos": puntos, "archivos": archivos, "avisos": avisos,
            "leidos": total_leidos, "repetidos": repetidos}


def puntos_dudosos(pts: list[dict]) -> set[int]:
    """Índices de los puntos que se alejan más de un 45 % de la mediana de la serie (o de la mediana de sus
    ocho vecinos). Suelen ser filas desplazadas en el Excel de origen. No se borran: se marcan para que
    los gráficos y los indicadores no los usen, y la app los enseña aparte."""
    if len(pts) < 5:
        return set()
    v = [(p["a"] + p["b"]) / 2 if p["b"] is not None else p["a"] for p in pts]
    med = sorted(v)[len(v) // 2]
    out = set()
    for i, x in enumerate(v):
        vec = sorted(v[max(0, i - 4):i] + v[i + 1:i + 5])
        local = vec[len(vec) // 2]
        if med > 0 and local > 0 and abs(x / med - 1) > 0.45 and abs(x / local - 1) > 0.45:
            out.add(i)
    return out


def lunes(semana: str) -> str:
    a, s = semana.split("-W")
    return dt.date.fromisocalendar(int(a), int(s), 1).isoformat()


def escribir(res: dict) -> dict:
    SALIDA.mkdir(parents=True, exist_ok=True)
    por_anio = collections.defaultdict(dict)
    indice_series = {}
    for sid, meta in sorted(res["series"].items()):
        pts = sorted(res["puntos"][sid].values(), key=lambda p: (p["f"] or lunes(p["w"]), p["w"]))
        if not pts:
            continue
        anios = sorted({int(p["w"][:4]) for p in pts})
        indice_series[sid] = {**meta, "n": len(pts), "anios": anios}
        dudosos = puntos_dudosos(pts)
        if dudosos:
            indice_series[sid]["dudosos"] = len(dudosos)
        for i, p in enumerate(pts):
            fila = [p["f"], p["w"], p["a"], p["b"]]
            if i in dudosos:
                fila.append(1)
            elif p["b"] is None:
                fila.pop()
            por_anio[int(p["w"][:4])].setdefault(sid, []).append(fila)
    usadas = {m["l"] for m in indice_series.values()}
    indice = {
        "fuente": PAGINA.format(anio=2026),
        "nota": "Cotizaciones semanales publicadas por la Junta de Castilla y León (Servicio de Estudios, "
                "Estadística y Planificación Agraria). Valores tal como se publican.",
        "generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "formato_punto": ["fecha de celebración (o null)", "semana ISO", "precio o mínimo",
                          "máximo (si hay horquilla; null si no)", "1 si el valor es dudoso"],
        "anios": sorted(por_anio),
        "lonjas": {k: v for k, v in LONJAS.items() if k in usadas},
        "series": indice_series,
        "archivos": res["archivos"],
    }
    # Si los datos no han cambiado se conserva la fecha de generación: así el robot no publica commits vacíos
    previo = SALIDA / "indice.json"
    if previo.exists():
        try:
            viejo = json.loads(previo.read_text("utf-8"))
            if {**viejo, "generado": None} == json.loads(json.dumps({**indice, "generado": None})):
                indice["generado"] = viejo.get("generado", indice["generado"])
        except ValueError:
            pass
    escribir_si_cambia(SALIDA / "indice.json", indice)
    for anio, datos in por_anio.items():
        escribir_si_cambia(SALIDA / f"{anio}.json", {"anio": anio, "series": datos})
    return indice


def escribir_si_cambia(ruta: Path, datos) -> None:
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    if not ruta.exists() or ruta.read_text("utf-8") != texto:
        ruta.write_text(texto, "utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--descargar", action="store_true", help="bajar antes los Excel nuevos de la Junta")
    args = ap.parse_args()
    avisos = descargar() if args.descargar else []
    res = importar()
    indice = escribir(res)
    puntos = sum(m["n"] for m in indice["series"].values())
    print(f"Archivos importados: {sum(a['importado'] for a in res['archivos'])} de {len(res['archivos'])}")
    print(f"Series: {len(indice['series'])} · registros: {puntos} · sesiones repetidas omitidas: {res['repetidos']}")
    for a in avisos + res["avisos"]:
        print("AVISO:", a)
    return 0


if __name__ == "__main__":
    sys.exit(main())

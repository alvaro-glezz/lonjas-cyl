"""Actualiza data/precios.json con las últimas cotizaciones de las lonjas de CyL.

Uso:  python scraper/actualizar.py            (todas las lonjas)
      python scraper/actualizar.py leon       (solo una, para probar)

Reglas de seguridad para no publicar datos malos:
  * Si un lector falla o lee menos filas de las esperadas, se conservan los
    precios anteriores de esa lonja y se anota el error (la app lo muestra).
  * Solo se reemplaza una sesión por otra con fecha más reciente.
  * Un CSV en data/manual/<lonja>.csv con fecha más reciente gana siempre:
    es la vía para corregir o cargar a mano una semana.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from comun import bonito, clave_de, es_titulo, leer_linea, leer_texto, numero, slug  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "precios.json"
MANUAL = RAIZ / "data" / "manual"
CABECERAS = {"User-Agent": "AppLonjasCyL/1.0 (lector semanal de cotizaciones publicas)"}
MESES = {m: i + 1 for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"])}
MINIMO_FILAS = 4
FALLOS_TOPE = 3        # «3 o más» lecturas fallidas seguidas
AÑOS_HISTORIAL = 3
# Un producto que deja de salir en la sesión se sigue mostrando como «sin cotizar» con su último precio
# durante este tiempo (cubre productos de temporada y mesas que se publican otro día, como en León).
DIAS_SIN_COTIZAR = 180

# --- Límites de seguridad -------------------------------------------------
# Solo se descargan páginas y PDF de estos dominios (y sus subdominios), siempre por https. Los enlaces a
# PDF salen del HTML de webs ajenas: sin esta lista, una web comprometida podría hacer que el robot
# descargue cualquier otra dirección. Si una lonja cambia de dominio, añádelo aquí.
DOMINIOS_PERMITIDOS = ("lasalina.es", "lonjadeleon.es", "fessegovia.es", "lerma.burgos.es", "datosabiertossalamanca.es")
MAX_BYTES = 15 * 1024 * 1024   # tamaño máximo de cada descarga
MAX_PAGINAS_PDF = 30           # solo se leen las primeras páginas: un boletín real tiene 1-5
MAX_PAGINAS_TOTAL = 400        # un PDF más grande que esto ni se abre
MAX_REDIRECCIONES = 5
PRECIO_MAX = 100_000           # €/t, €/kg, €/ud... nada real se acerca a esto


# ---------------------------------------------------------------------------
# Utilidades de red y de fechas
# ---------------------------------------------------------------------------
def dominio_permitido(url: str) -> bool:
    p = urlparse(url)
    h = (p.hostname or "").lower()
    return p.scheme == "https" and any(h == d or h.endswith("." + d) for d in DOMINIOS_PERMITIDOS)


def bajar(url: str, parcial: int | None = None) -> requests.Response:
    """Descarga segura: solo https y dominios conocidos, redirecciones revisadas una a una, tamaño limitado.
    Con `parcial`, se leen solo los primeros bytes indicados (sin error): útil para archivos que crecen cada
    semana y traen lo más reciente al principio (datos abiertos de Salamanca)."""
    for _ in range(MAX_REDIRECCIONES + 1):
        if not dominio_permitido(url):
            raise ValueError(f"Dirección no permitida ({urlparse(url).hostname}). "
                             "Si es legítima, añade su dominio a DOMINIOS_PERMITIDOS.")
        r = requests.get(url, headers=CABECERAS, timeout=(10, 40), stream=True, allow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
            url = urljoin(url, r.headers["Location"])
            r.close()
            continue
        r.raise_for_status()
        buf = bytearray()
        for trozo in r.iter_content(65536):
            buf += trozo
            if parcial and len(buf) >= parcial:
                r.close()
                break
            if len(buf) > MAX_BYTES:
                r.close()
                raise ValueError("Respuesta demasiado grande")
        r._content, r._content_consumed = bytes(buf), True  # para que .text/.json/.content sigan funcionando
        return r
    raise ValueError("Demasiadas redirecciones")


def fecha_plausible(iso: str | None) -> bool:
    """Una sesión real es de los últimos 2 años y no es futura. Evita que una fecha mal leída
    (p. ej. 2099) bloquee para siempre las actualizaciones, ya que solo se aceptan sesiones más nuevas."""
    try:
        d = date.fromisoformat(iso or "")
    except ValueError:
        return False
    hoy = date.today()
    return hoy - timedelta(days=730) <= d <= hoy + timedelta(days=1)


def fecha_en(texto: str) -> str | None:
    """Primera fecha que aparezca: '3 de noviembre de 2026', '29-10-2026', '29.10.2026'."""
    t = texto.lower()
    try:
        m = re.search(r"(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")\s+(?:de\s+)?(\d{4})", t)
        if m:
            return date(int(m.group(3)), MESES[m.group(2)], int(m.group(1))).isoformat()
        m = re.search(r"(\d{4})[-_ ](" + "|".join(MESES) + r")[-_ ](\d{1,2})", t)  # lonja-2026-Noviembre-3
        if m:
            return date(int(m.group(1)), MESES[m.group(2)], int(m.group(3))).isoformat()
    except ValueError:
        return None
    m = re.search(r"\b(\d{1,2})[-./](\d{1,2})[-./](\d{4}|\d{2})\b", t)
    if m:
        a = int(m.group(3)); a += 2000 if a < 100 else 0
        try:
            return date(a, int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def texto_pdf(contenido: bytes) -> str:
    """Texto de las primeras MAX_PAGINAS_PDF páginas (un PDF largo no se rechaza: se lee solo el principio)."""
    import pdfplumber
    if not contenido.startswith(b"%PDF-"):
        raise ValueError("El archivo descargado no es un PDF")
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        n = len(pdf.pages)
        if n > MAX_PAGINAS_TOTAL:
            raise ValueError(f"PDF con demasiadas páginas ({n})")
        if n > MAX_PAGINAS_PDF:
            print(f"    aviso: el PDF tiene {n} páginas; se leen solo las {MAX_PAGINAS_PDF} primeras")
        # Solo el texto horizontal: algunos boletines (Segovia) llevan rótulos en vertical o reflejados
        # ('SELAEREC' = CEREALES) que se mezclarían con los nombres de los productos.
        horizontal = lambda o: o.get("object_type") != "char" or (o.get("upright", True) and o["matrix"][0] > 0)
        return "\n".join((p.filter(horizontal).extract_text() or "") for p in pdf.pages[:MAX_PAGINAS_PDF])


def fecha_de_enlace(url: str, texto: str) -> str | None:
    """Fecha en el nombre del archivo o en el texto del enlace ('lonja-2026-Noviembre-3.pdf', 'Lonja 31.10.2026')."""
    nombre = url.rsplit("/", 1)[-1]
    for trozo in (texto, nombre.replace("-", " ").replace("_", " "), url.replace("-", " ").replace("_", " ")):
        f = fecha_en(trozo or "")
        if f and fecha_plausible(f):
            return f
    return None


def elegir_pdf(lid: str, pdfs: list[tuple[str, str]], patron: str) -> tuple[str, str | None]:
    """Elige el boletín más reciente entre los PDF enlazados en una página.
    1) se quedan los que parecen de cotizaciones (patron) si hay alguno;
    2) de los que llevan fecha válida, el más nuevo;
    3) si ninguno lleva fecha, el primero de la página (estas webs ponen arriba el último).
    Deja en el registro de Actions qué candidatos vio y cuál eligió, para poder revisarlo."""
    vistos, unicos = set(), []
    for u, t in pdfs:
        if u not in vistos:
            vistos.add(u); unicos.append((u, t))
    utiles = [p for p in unicos if not re.search(NO_BOLETIN, p[0] + " " + p[1], re.I)]
    if not utiles:
        for u, t in unicos[:8]:
            print(f"[{lid}] PDF descartado (no es un boletín): {t[:60]!r} | {u[:140]}")
        raise RuntimeError("La página no enlaza ningún boletín de cotizaciones")
    candidatos = [p for p in utiles if re.search(patron, p[0] + " " + p[1], re.I)] or utiles
    con_fecha = [(fecha_de_enlace(u, t), u, t) for u, t in candidatos]
    for f, u, t in con_fecha[:20]:
        print(f"[{lid}] PDF visto: {f or 'sin fecha'} | {t[:60]!r} | {u[:140]}")
    fechados = [c for c in con_fecha if c[0]]
    elegido = max(fechados) if fechados else con_fecha[0]
    print(f"[{lid}] PDF elegido: {elegido[1][:160]}")
    return elegido[1], elegido[0]


def diagnostico(lid: str, texto: str, filas: list, fecha: str | None) -> None:
    """Si la lectura sale floja, deja en el registro el principio del documento para ver su formato."""
    if fecha and len(filas) >= 8:
        return
    lineas = [l.strip() for l in texto.splitlines() if l.strip()][:15]
    print(f"[{lid}] lectura floja ({len(filas)} filas, fecha {fecha!r}). Principio del documento:")
    for l in lineas:
        print(f"    | {l[:110]}")


UNIDADES_LEON = ((r"€\s*/\s*t\b|euros?\s*/\s*t(on)?", "€/t"), (r"kg\.?\s*vivo", "€/kg vivo"), (r"kg\.?\s*canal", "€/kg canal"),
                 (r"unidad", "€/ud"), (r"litro", "€/litro"), (r"e\.?\s*q", "€/e.q."), (r"€\s*/\s*kg|euros?\s*/\s*kg", "€/kg"))


def unidad_leon(txt: str) -> str:
    for patron, u in UNIDADES_LEON:
        if re.search(patron, txt or "", re.I):
            return u
    return ""


def precio_leon(txt: str):
    """'1.100,00' -> 1100; '0,475*' -> 0.475; '3,60/4,60' -> (3.6, 4.6); 'S/C' o vacío -> None."""
    txt = (txt or "").replace("*", "").strip()
    if not txt or re.fullmatch(r"(?i)s\s*/\s*c\.?", txt):
        return None
    partes = re.findall(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?", txt)
    vals = [numero(p) for p in partes][:2]
    if not vals or any(v is None for v in vals):
        return None
    return (vals[0], vals[1]) if len(vals) == 2 and "/" in txt else vals[0]


def filas_de_tablas_html(html: str, cat_defecto: str, unidad_defecto: str = "") -> list[dict]:
    """Tablas de la Lonja de León: 'NOMBRE | COTIZACIÓN ANTERIOR | COTIZACIÓN ACTUAL | DIF.'.
    Fila de cabecera -> mesa ('PATATAS'); fila con unidades ('€/t', '€/Kg. Canal') -> unidad (y, si trae nombre,
    sección: 'GANADO VIDA'); fila sin precios ('Hembras 180-200 kg.') -> prefijo de las siguientes ('U', 'R', 'O').
    Horquillas '3,60/4,60' -> centro + rango. Comprobado con las entradas reales de oct.–nov. 2026."""
    sopa = BeautifulSoup(html, "html.parser")
    filas, cat, unidad, prefijo = [], cat_defecto, unidad_defecto, ""
    for tr in sopa.select("tr"):
        celdas = [re.sub(r"\s+", " ", c.get_text(" ", strip=True).replace("\xa0", " ")).strip() for c in tr.find_all(["td", "th"])]
        if not any(celdas):
            continue
        nombre, resto = celdas[0], celdas[1:]
        texto_resto = " ".join(resto)
        if re.search(r"(?i)cotizaci|anterior|actual", texto_resto):          # cabecera de la tabla
            if nombre:
                cat = bonito(nombre).capitalize()
            prefijo = ""
            continue
        if resto and unidad_leon(texto_resto) and not re.search(r"\d", texto_resto):   # fila de unidades
            unidad = unidad_leon(texto_resto)
            if nombre:
                cat = bonito(nombre).capitalize()
            prefijo = ""
            continue
        valores = [precio_leon(c) for c in resto[:2]]
        if nombre and not any(v is not None for v in valores) and not re.search(r"(?i)s\s*/\s*c", texto_resto):
            prefijo = re.sub(r"[.\s]+$", "", nombre)                         # subtítulo: 'Hembras 180-200 kg'
            continue
        if not nombre:
            continue
        limpio = re.sub(r"[*\s]+$", "", nombre).strip()
        if prefijo and len(limpio) <= 3:
            limpio = f"{prefijo} {limpio}"
        ant, act = (valores + [None, None])[:2]
        f = {"producto": limpio, "cat": cat, "unidad": unidad or unidad_defecto}
        if isinstance(act, tuple):
            f["rango"] = "–".join(f"{v:.2f}".replace(".", ",") for v in act)
            act = round(sum(act) / 2, 4)
        if isinstance(ant, tuple):
            ant = round(sum(ant) / 2, 4)
        f.update(ant=ant, act=act)
        filas.append(f)
    if not filas:  # sin tablas: probar como texto
        filas = leer_texto(sopa.get_text("\n"), unidad_defecto)
        for f in filas:
            if f["cat"] == "General":
                f["cat"] = cat_defecto
    return filas


def enlaces_pdf(html: str, base: str) -> list[tuple[str, str]]:
    """PDF enlazados en la página: enlaces <a>, marcos/visores (iframe, embed, object) y, por si los pinta
    un script, cualquier ruta terminada en .pdf escrita en el HTML. En orden de aparición, sin repetir."""
    sopa = BeautifulSoup(html, "html.parser")
    out, vistos = [], set()
    def poner(href, texto):
        u = urljoin(base, href.strip())
        if ".pdf" in u.lower() and u not in vistos:
            vistos.add(u); out.append((u, texto))
    for a in sopa.find_all("a", href=True):
        poner(a["href"], a.get_text(" ", strip=True))
    for tag, attr in (("iframe", "src"), ("embed", "src"), ("object", "data")):
        for el in sopa.find_all(tag):
            if el.get(attr):
                poner(el[attr], f"({tag})")
    for m in re.finditer(r"""["'(=]\s*((?:https?:)?/?/?[^"'()<>\s]{1,300}?\.pdf)\b""", html[:2_000_000], re.I):
        poner(m.group(1), "")
    return out


NO_BOLETIN = r"estatut|normativ|reglament|ordenanz|acuerdo|bases|convocatoria|acta"


# ---------------------------------------------------------------------------
# Lectores, uno por lonja. Cada uno devuelve (fecha_iso, filas, url_origen)
# ---------------------------------------------------------------------------
def leer_leon():
    """Web WordPress de la Lonja: una entrada por mesa ('Lonja cereal 29-10-2026')."""
    url = "https://www.lonjadeleon.es/wp-json/wp/v2/posts?per_page=40&_fields=date,title,link,content"
    fecha, filas, enlace, usadas = interpretar_leon(bajar(url).json())
    MATERIAL["leon"] = {"entradas": usadas}
    return fecha, filas, enlace


def mesa_leon(titulo: str) -> str:
    """'Lonja carne de vacuno 29-10-2026' y 'Lonja carne vacuno 30-09-2026' -> 'carne vacuno' (misma mesa)."""
    t = re.sub(r"(?i)\blonja\b|\d{1,2}-\d{1,2}-\d{2,4}", " ", titulo).lower()
    palabras = [re.sub(r"s$", "", p) for p in re.findall(r"[a-záéíóúñ]+", t) if p not in ("de", "y", "del", "la", "el")]
    return " ".join(palabras) or "general"


def interpretar_leon(entradas: list):
    """La Lonja de León publica cada mesa en su día (cereal, girasol, patata y alubia los miércoles; vacuno, ovino,
    leche y forraje los jueves). Se toma la última entrada de cada mesa publicada en los 10 días anteriores a la
    más reciente, y la sesión de la lonja es la fecha más reciente. Devuelve también las entradas usadas, que se
    guardan como caso de prueba."""
    ultimas: dict[str, tuple] = {}
    for e in entradas:
        titulo = BeautifulSoup(e["title"]["rendered"], "html.parser").get_text()
        if not re.match(r"(?i)\s*lonja\b", titulo):
            continue  # noticias del blog
        f = fecha_en(titulo) or e["date"][:10]
        if not fecha_plausible(f):
            continue
        clave = mesa_leon(titulo)
        if clave not in ultimas or f > ultimas[clave][0]:
            ultimas[clave] = (f, titulo, e)
    if not ultimas:
        raise RuntimeError("No hay entradas de cotizaciones en la web de la Lonja de León")
    fecha = max(f for f, _, _ in ultimas.values())
    limite = (date.fromisoformat(fecha) - timedelta(days=10)).isoformat()
    elegidas = sorted((v for v in ultimas.values() if v[0] >= limite), key=lambda v: (v[0], v[1]), reverse=True)
    filas = []
    for f, titulo, e in elegidas:
        mesa = re.sub(r"(?i)lonja( de)?|\d{1,2}-\d{1,2}-\d{2,4}", "", titulo).strip(" -") or "General"
        unidad = "€/t" if re.search(r"cereal|forraj|patat|girasol", mesa, re.I) else ""
        filas += filas_de_tablas_html(e["content"]["rendered"], mesa.capitalize(), unidad)
    usadas = [{"date": e["date"], "link": e["link"], "title": {"rendered": e["title"]["rendered"]},
               "content": {"rendered": e["content"]["rendered"]}} for _, _, e in elegidas]
    principal = next(e for f, _, e in elegidas if f == fecha)
    return fecha, filas, principal["link"], usadas


def leer_segovia():
    """La FES publica cada jueves una entrada con el PDF 'LONJA CEREALES OVINO Y PORCINO dd.mm.aaaa'."""
    api = "https://www.fessegovia.es/wp-json/wp/v2/posts?search=precios%20lonja&per_page=5&_fields=date,title,link,content"
    entradas = bajar(api).json()
    if not entradas:
        raise RuntimeError("No se encuentra la última entrada 'Precios Lonja' en fessegovia.es")
    e = max(entradas, key=lambda x: x["date"])
    pdfs = enlaces_pdf(e["content"]["rendered"], e["link"])
    if not pdfs:
        raise RuntimeError(f"La entrada {e['link']} no tiene PDF")
    url_pdf = pdfs[0][0]
    material = {"texto": texto_pdf(bajar(url_pdf).content), "url_pdf": url_pdf, "titulo": e["title"]["rendered"], "fecha_entrada": e["date"]}
    MATERIAL["segovia"] = material
    fecha, filas = interpretar_segovia(material)
    return fecha, filas, url_pdf


# Productos del boletín de Segovia -> (mesa, nombre en la app, unidad). Los nombres son los que ya usaba la app,
# para conservar su histórico. Un producto nuevo que no esté aquí no se publica y queda anotado en el registro.
SEGOVIA_PRODUCTOS = [
    (r"^cebada", ("Cereales", "Cebada 62 kg/hl", "€/t")),
    (r"^trigo pienso", ("Cereales", "Trigo pienso 72 kg/hl", "€/t")),
    (r"^trigo", ("Cereales", "Trigo", "€/t")),
    (r"^avena", ("Cereales", "Avena", "€/t")),
    (r"^centeno", ("Cereales", "Centeno", "€/t")),
    (r"^triticale", ("Cereales", "Triticale", "€/t")),
    (r"^ma[ií]z", ("Cereales", "Maíz", "€/t")),
    (r"^girasol", ("Oleaginosas", "Girasol 9-2-44", "€/t")),
    (r"^colza", ("Oleaginosas", "Colza 9-2-42", "€/t")),
    (r"^(alfalfa|paquete empacada)", ("Forrajes", "Alfalfa empacada", "€/t")),
    (r"^paja", ("Forrajes", "Paja empacada", "€/t")),
    (r"^forraje veza", ("Forrajes", "Forraje veza mezcla", "€/t")),
    (r"^forraje$", ("Forrajes", "Forraje", "€/t")),
    (r"extra igp", ("Ovino", "Cordero Extra IGP", "€/kg vivo")),
    (r"segolechal", ("Ovino", "Cordero Segolechal", "€/kg vivo")),
    (r"lechal 10-12", ("Ovino", "Lechazo 10-12 kg", "€/kg vivo")),
    (r"nodriza", ("Ovino", "Cordero nodriza y 2ª", "€/kg vivo")),
    (r"lechal 12,1-15", ("Ovino", "Lechal 12,1-15 kg", "€/kg vivo")),
    (r"recental", ("Ovino", "Recental 15,1-19 kg", "€/kg vivo")),
    (r"pascual 19,1", ("Ovino", "Pascual 19,1-23 kg", "€/kg vivo")),
    (r"pascual 23,1", ("Ovino", "Pascual 23,1-25,5 kg", "€/kg vivo")),
    (r"pascual 25,5", ("Ovino", "Pascual 25,5-28 kg", "€/kg vivo")),
    (r"(grande )?28,1-34", ("Ovino", "Cordero 28,1-34 kg", "€/kg vivo")),
    (r"ovejas? desvieje primera", ("Ovino", "Oveja desvieje 1ª", "€/kg vivo")),
    (r"ovejas? desvieje segunda", ("Ovino", "Oveja desvieje 2ª", "€/kg vivo")),
    (r"^selecto", ("Porcino", "Cerdo selecto", "€/kg vivo")),
    (r"^normal", ("Porcino", "Cerdo normal", "€/kg vivo")),
    (r"^cerdo graso", ("Porcino", "Cerdo graso", "€/kg vivo")),
    (r"^cerdas? desvieje extra", ("Porcino", "Cerda desvieje extra", "€/kg vivo")),
    (r"^cerdas? desvieje primera", ("Porcino", "Cerda desvieje primera", "€/kg vivo")),
    (r"^lechones de 20", ("Porcino", "Lechones 20 kg", "€/ud")),
    (r"con hierro", ("Porcino", "Cochinillos con hierro", "€/ud")),
    (r"sin hierro", ("Porcino", "Cochinillos sin hierro", "€/ud")),
]
_PRECIO_SG = r"(S/C|-?\d+,\d+)"


def leer_segovia_texto(texto: str) -> list[dict]:
    """Líneas 'Nombre  anterior  diferencia  actual [otras columnas]'. Si el nombre ocupa dos líneas
    ('Cordero lechal 10-12 Kg. para' + '9,35 0,10 9,45 104'), se une con la anterior."""
    filas, pendiente, vistos = [], "", set()
    for linea in texto.splitlines():
        linea = re.sub(r"\s+", " ", linea).strip()
        if not linea or len(linea) > MAX_LINEA_SG:
            continue
        m = re.search(rf"{_PRECIO_SG} {_PRECIO_SG} {_PRECIO_SG}", linea) or re.search(rf"{_PRECIO_SG} {_PRECIO_SG}(?!\S)", linea)
        if not m:
            if re.search(r"[a-zá-ú]{3}", linea, re.I) and not re.search(r"(?i)precio|semana|anterior|medida|origen|agricultor|granja|lonja|cotizaciones|euros|sacrificio|€", linea):
                pendiente = linea
            continue
        nombre = linea[:m.start()].strip(" .*") or pendiente
        pendiente = ""
        clave = re.sub(r"\s+", " ", nombre.replace("*", "")).strip(" .").lower()
        destino = next((d for patron, d in SEGOVIA_PRODUCTOS if re.search(patron, clave)), None)
        if not destino:
            if clave:
                print(f"[segovia] producto no reconocido (no se publica): {nombre!r}")
            continue
        if destino in vistos:
            continue
        vistos.add(destino)
        vals = [None if g == "S/C" else numero(g) for g in m.groups()]
        ant, act = (vals[0], vals[2]) if len(vals) == 3 else (vals[0], vals[1])
        filas.append({"cat": destino[0], "producto": destino[1], "unidad": destino[2], "ant": ant, "act": act})
    return filas


MAX_LINEA_SG = 200


def interpretar_segovia(m: dict):
    fecha = fecha_en(m["url_pdf"].replace("-", " ")) or fecha_en(m["titulo"]) or m["fecha_entrada"][:10]
    return fecha, leer_segovia_texto(m["texto"])


SALAMANCA_CKAN = "https://datosabiertossalamanca.es/api/3/action/package_show?id=cotizaciones-semanales-de-la-lonja-de-salamanca"
SALAMANCA_DATASET = "https://datosabiertossalamanca.es/dataset/cotizaciones-semanales-de-la-lonja-de-salamanca"
SALAMANCA_NOTA = "Datos abiertos de la Diputación de Salamanca (licencia CC BY 4.0)"
# (MESA, PRODUCTO, CATEGORÍA) del CSV -> (mesa en la app, nombre, unidad). Los nombres de los productos que la app
# ya tenía se conservan tal cual para no cortar su histórico (p. ej. «Terneras +12 meses, menos de 270 kg» es la
# categoría Especial, la que se tomaba de referencia). Lo que no está aquí no se publica (p. ej. el despiece de ibérico).
SALAMANCA_PRODUCTOS = {
    ("CEREALES", "Cereales", "Trigo Blando p.e. > 72 kg/Hl"): ("Cereales", "Trigo blando", "€/t"),
    ("CEREALES", "Cereales", "Cebada"): ("Cereales", "Cebada", "€/t"),
    ("CEREALES", "Cereales", "Avena"): ("Cereales", "Avena", "€/t"),
    ("CEREALES", "Cereales", "Centeno"): ("Cereales", "Centeno", "€/t"),
    ("CEREALES", "Cereales", "Triticale"): ("Cereales", "Triticale", "€/t"),
    ("CEREALES", "Cereales", "Maíz"): ("Cereales", "Maíz", "€/t"),
    ("CEREALES", "Leguminosas", "Guisantes"): ("Leguminosas", "Guisantes", "€/t"),
    ("CEREALES", "Leguminosas", "Garbanzo pedrosillano"): ("Leguminosas", "Garbanzo pedrosillano", "€/t"),
    ("CEREALES", "Leguminosas", "Lenteja armuña D.O."): ("Leguminosas", "Lenteja de La Armuña IGP", "€/t"),
    ("CEREALES", "Oleaginosas", "Girasol"): ("Oleaginosas", "Girasol", "€/t"),
    ("CEREALES", "Oleaginosas", "Girasol A.O."): ("Oleaginosas", "Girasol alto oleico", "€/t"),
    ("CEREALES", "Oleaginosas", "Colza"): ("Oleaginosas", "Colza", "€/t"),
    ("CEREALES", "Forrajes", "Forraje Extra"): ("Forrajes", "Forraje extra", "€/t"),
    ("CEREALES", "Forrajes", "Forraje de Primera"): ("Forrajes", "Forraje de primera", "€/t"),
    ("CEREALES", "Forrajes", "Alfalfa empacada"): ("Forrajes", "Alfalfa empacada", "€/t"),
    ("CEREALES", "Forrajes", "Veza henificada"): ("Forrajes", "Veza henificada", "€/t"),
    ("CEREALES", "Forrajes", "Paja paquete pequeño"): ("Forrajes", "Paja paquete pequeño", "€/t"),
    ("CEREALES", "Forrajes", "Paja paquete grande"): ("Forrajes", "Paja", "€/t"),
    ("OVINO", "Lechazo", "Extra"): ("Ovino", "Lechazo extra", "€/kg vivo"),
    ("OVINO", "Lechazo", "Hasta 11 Kg"): ("Ovino", "Lechazo hasta 11 kg", "€/kg vivo"),
    ("OVINO", "Lechazo", "11,01 a 13 KG."): ("Ovino", "Lechazo 11-13 kg", "€/kg vivo"),
    ("OVINO", "Lechazo", "13,01 a 15 KG."): ("Ovino", "Lechazo 13-15 kg", "€/kg vivo"),
    ("OVINO", "Cordero", "15,01 a 19 KG."): ("Ovino", "Cordero 15-19 kg", "€/kg vivo"),
    ("OVINO", "Cordero", "19,01 a 23 KG."): ("Ovino", "Cordero 19-23 kg", "€/kg vivo"),
    ("OVINO", "Cordero", "23,01 a 25,49 KG."): ("Ovino", "Cordero 23-25,5 kg", "€/kg vivo"),
    ("OVINO", "Cordero", "25,5 a 28 KG."): ("Ovino", "Cordero 25,5-28 kg", "€/kg vivo"),
    ("OVINO", "Cordero", "28,01 a 34 KG."): ("Ovino", "Cordero 28-34 kg", "€/kg vivo"),
    ("OVINO", "Cordero", "+ de 34 KG."): ("Ovino", "Cordero más de 34 kg", "€/kg vivo"),
    ("OVINO", "Oveja", "Sacrificio"): ("Ovino", "Oveja de sacrificio", "€/kg vivo"),
    ("OVINO", "Oveja", "Vida"): ("Ovino", "Oveja de vida", "€/ud"),
    ("PORCINO BLANCO E IBÉRICO", "Porcino blanco", "Selecto"): ("Porcino blanco", "Cerdo selecto", "€/kg vivo"),
    ("PORCINO BLANCO E IBÉRICO", "Porcino blanco", "Normal"): ("Porcino blanco", "Cerdo normal", "€/kg vivo"),
    ("PORCINO BLANCO E IBÉRICO", "Porcino blanco", "Graso"): ("Porcino blanco", "Cerdo graso", "€/kg vivo"),
    ("PORCINO BLANCO E IBÉRICO", "Porcino blanco", "Cerdas"): ("Porcino blanco", "Cerdas de desvieje", "€/kg vivo"),
    ("PORCINO BLANCO E IBÉRICO", "Lechón", "Selecto"): ("Porcino blanco", "Lechones base 20 kg", "€/ud"),
    ("PORCINO BLANCO E IBÉRICO", "Tostón", "4 a 6 Kg"): ("Porcino blanco", "Tostones 4-6 kg", "€/ud"),
    ("PORCINO BLANCO E IBÉRICO", "Tostón", "6,01 a 8 Kg"): ("Porcino blanco", "Tostones 6-8 kg", "€/ud"),
    ("PORCINO BLANCO E IBÉRICO", "Porcino Ibérico", "Bellota 100% IB"): ("Porcino ibérico", "Ibérico bellota 100 %", "€/kg vivo"),
    ("PORCINO BLANCO E IBÉRICO", "Porcino Ibérico", "Cebo de campo"): ("Porcino ibérico", "Ibérico cebo de campo", "€/kg vivo"),
    ("PORCINO BLANCO E IBÉRICO", "Porcino Ibérico", "Cebo"): ("Porcino ibérico", "Ibérico cebo", "€/kg vivo"),
    ("PORCINO BLANCO E IBÉRICO", "Porcino Ibérico", "Lechones hasta 23 Kg (Gran partida)"): ("Porcino ibérico", "Lechones ibéricos", "€/kg vivo"),
    ("PORCINO BLANCO E IBÉRICO", "Porcino Ibérico", "Primales ibérico puro"): ("Porcino ibérico", "Primales ibérico puro", "€/kg vivo"),
    ("PORCINO BLANCO E IBÉRICO", "Porcino Ibérico", "Primales ibérico cruzado"): ("Porcino ibérico", "Primales ibérico cruzado", "€/kg vivo"),
    ("BOVINO DE VIDA", "Ternero", "Extra macho"): ("Vacuno de vida", "Terneros", "€/kg vivo"),
    ("BOVINO DE VIDA", "Ternero", "Extra hembra"): ("Vacuno de vida", "Terneras", "€/kg vivo"),
    ("BOVINO DE VIDA", "Ternero del país", "Macho"): ("Vacuno de vida", "Terneros del país", "€/kg vivo"),
    ("BOVINO DE CARNE", "Ternera mayor 12 meses", "Especial menor 270 Kg"): ("Vacuno de carne", "Terneras +12 meses, menos de 270 kg", "€/kg canal"),
    ("BOVINO DE CARNE", "Ternera mayor 12 meses", "Especial mayor 270 Kg"): ("Vacuno de carne", "Terneras +12 meses, más de 270 kg", "€/kg canal"),
    ("BOVINO DE CARNE", "Añojos", "Especial menor 350 Kg"): ("Vacuno de carne", "Añojos menos de 350 kg", "€/kg canal"),
    ("BOVINO DE CARNE", "Añojos", "Especial mayor 350 Kg"): ("Vacuno de carne", "Añojos más de 350 kg", "€/kg canal"),
    ("BOVINO DE CARNE", "Erales", "Extra"): ("Vacuno de carne", "Erales", "€/kg canal"),
    ("BOVINO DE CARNE", "Novillos", "Extra"): ("Vacuno de carne", "Novillos", "€/kg canal"),
    ("BOVINO DE CARNE", "Toros", "Extra"): ("Vacuno de carne", "Toros", "€/kg canal"),
    ("BOVINO DE CARNE", "Vacas", "Extra"): ("Vacuno de carne", "Vacas", "€/kg canal"),
}


def _clave_csv(*partes: str) -> tuple:
    """Clave tolerante: sin espacios repetidos ni diferencias de mayúsculas o de punto final."""
    return tuple(re.sub(r"\s+", " ", p or "").strip().rstrip(".").lower() for p in partes)


_SALAMANCA_CLAVES = {_clave_csv(*k): v for k, v in SALAMANCA_PRODUCTOS.items()}


def leer_salamanca_csv(texto: str):
    """CSV de datos abiertos: "ID";"FECHA";"MESA";"PRODUCTO";"CATEGORIA";"VALOR1";"VALOR2" (sesiones más nuevas
    primero). VALOR2 es el máximo de la horquilla (0 o -1 si no hay); 0 en los dos = esa semana no cotizó."""
    def num(v):
        v = (v or "").strip().replace(".", "").replace(",", ".") if "," in (v or "") else (v or "").strip()
        try:
            x = float(v)
        except ValueError:
            return None
        return x if x > 0 else None
    sesiones: dict[str, dict] = {}
    for fila in csv.reader(io.StringIO(texto), delimiter=";"):
        if len(fila) < 7 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fila[1].strip()):
            continue  # cabecera o última línea cortada (lectura parcial)
        destino = _SALAMANCA_CLAVES.get(_clave_csv(fila[2], fila[3], fila[4]))
        if not destino:
            continue
        a, b = num(fila[5]), num(fila[6])
        if a is None:
            continue
        sesiones.setdefault(fila[1].strip(), {})[destino] = (a, b if b and b > a else None)
    if not sesiones:
        return None, []
    fechas = sorted(sesiones, reverse=True)
    actual, previa = sesiones[fechas[0]], (sesiones[fechas[1]] if len(fechas) > 1 else {})
    medio = lambda a, b: round((a + b) / 2, 4) if b else a
    filas = []
    for (cat, nombre, unidad), (a, b) in actual.items():
        f = {"cat": cat, "producto": nombre, "unidad": unidad, "act": medio(a, b),
             "ant": medio(*previa[(cat, nombre, unidad)]) if (cat, nombre, unidad) in previa else None}
        if b:
            f["rango"] = f"{a:.3f}".rstrip("0").rstrip(".").replace(".", ",") + "–" + f"{b:.3f}".rstrip("0").rstrip(".").replace(".", ",")
        filas.append(f)
    orden = list(dict.fromkeys(v for v in SALAMANCA_PRODUCTOS.values()))
    filas.sort(key=lambda f: orden.index((f["cat"], f["producto"], f["unidad"])))
    return fechas[0], filas


def leer_salamanca():
    """Cotizaciones de la Lonja de Salamanca: datos abiertos de la Diputación (cada lunes, desde 2005; CC BY 4.0).
    El CSV pesa más de 10 MB pero trae lo más reciente al principio: basta con leer su comienzo."""
    try:
        recursos = bajar(SALAMANCA_CKAN).json()["result"]["resources"]
        url = next(r["url"] for r in recursos if (r.get("format") or "").upper() == "CSV")
        crudo = bajar(url, parcial=512 * 1024).content
        try:
            texto = crudo.decode("utf-8")
        except UnicodeDecodeError:
            texto = crudo.decode("latin-1")
        fecha, filas = leer_salamanca_csv(texto)
        if fecha:
            fechas = sorted({m.group(1) for m in re.finditer(r'^"\d+";"(\d{4}-\d{2}-\d{2})"', texto, re.M)}, reverse=True)[:2]
            MATERIAL["salamanca"] = {"csv": "\n".join([texto.splitlines()[0]] + [l for l in texto.splitlines() if any(f'"{x}"' in l[:30] for x in fechas)])}
        if fecha and len(filas) >= MINIMO_FILAS:
            print(f"[salamanca] datos abiertos: sesión {fecha}, {len(filas)} filas")
            return fecha, filas, SALAMANCA_DATASET
        print(f"[salamanca] los datos abiertos no traen una sesión válida ({len(filas)} filas, fecha {fecha!r})")
    except Exception as exc:  # noqa: BLE001
        print(f"[salamanca] datos abiertos no disponibles ({type(exc).__name__}: {exc}); se prueba la web de la Lonja")
    return leer_salamanca_pdf()


def leer_salamanca_pdf():
    """Respaldo: boletín en PDF enlazado desde la web de la Lonja (en nov. 2026 la web no enlaza ninguno)."""
    pagina = "https://www.lasalina.es/economiayhacienda/agriculturayganaderia/mercado/lonja/"
    html = bajar(pagina).text
    pdfs = enlaces_pdf(html, pagina)
    if not any(re.search(r"/pdfs/lonja|cotiz", u, re.I) for u, _ in pdfs):
        # El boletín no está en la portada de la Lonja: se mira en sus subpáginas (cotizaciones, boletines...)
        sopa = BeautifulSoup(html, "html.parser")
        sub = []
        for a in sopa.find_all("a", href=True):
            u = urljoin(pagina, a["href"]).split("#")[0]
            txt = a.get_text(" ", strip=True)
            if (dominio_permitido(u) and ".pdf" not in u.lower() and u.rstrip("/") != pagina.rstrip("/")
                    and re.search(r"cotiza|bolet|precio|sesion|sesión|mesa", u + " " + txt, re.I) and u not in sub):
                sub.append(u)
        for u in sub[:4]:
            print(f"[salamanca] buscando el boletín en la subpágina {u[:140]}")
            try:
                pdfs += enlaces_pdf(bajar(u).text, u)
            except Exception as exc:  # noqa: BLE001
                print(f"[salamanca] no se pudo abrir la subpágina: {type(exc).__name__}")
    if not pdfs:
        raise RuntimeError("No hay PDF en la página de La Salina")
    url_pdf, fecha_nombre = elegir_pdf("salamanca", pdfs, r"/pdfs/lonja|lonja-20\d\d|cotiz")
    texto = texto_pdf(bajar(url_pdf).content)
    fecha = fecha_en(texto[:1500]) or fecha_nombre or fecha_en(texto)
    filas = leer_texto(texto)
    diagnostico("salamanca", texto, filas, fecha)
    return fecha, filas, url_pdf


LERMA_UNIDADES = {"tonelada": "€/t", "kg": "€/kg", "unidad": "€/ud"}
LERMA_MESAS = (("cereal", "Cereales"), ("porcino", "Porcino"), ("lech", "Porcino"), ("vacuno", "Vacuno"), ("ovino", "Ovino"))
LERMA_LINEA = re.compile(r"^(?P<nombre>.+?)[\s.…]*?\s(?P<precio>\d{1,5}(?:[.,]\d{1,3})?)\s*(?P<unidad>euros?\s*/\s*[a-záéíóú.]+|[“”\"]+)?\s*$", re.I)


def nombre_lerma(crudo: str, anterior: str, mesa_original: str) -> str:
    """'“ “ rosada' tras 'Terneras carne blanca' -> 'Terneras carne rosada'; 'Normal' (porcino) -> 'Cerdo normal'."""
    crudo = re.sub(r"[()]", " ", crudo)
    if re.match(r"^[“”\"]", crudo):
        resto = re.sub(r"^([“”\"]\s*)+", "", crudo).strip()
        base = anterior.rsplit(" ", 1)[0] if " " in anterior else anterior
        crudo = f"{base} {resto}"
    n = re.sub(r"\s+", " ", crudo).strip().lower()
    if "porcino" in mesa_original.lower() and n in ("selecto", "normal", "graso"):
        n = "cerdo " + n
    n = n.replace("cerdas desvieje", "cerdas de desvieje")
    n = n[:1].upper() + n[1:]
    return re.sub(r"\biii\b", "III", re.sub(r"\blerma\b", "Lerma", n))


def leer_sesion_lerma(bloque: str):
    """Lee una sesión: 'FECHA DE CELEBRACIÓN: 30 de Octubre de 2026' y líneas 'Trigo (Tipo III).... 230 Euros/Tonelada'."""
    from comun import numero
    m = re.search(r"celebraci[oó]n\s*:?\s*(.{0,60})", bloque, re.I)
    fecha = fecha_en(m.group(1)) if m else fecha_en(bloque[:400])
    filas, mesa, mesa_original, unidad, anterior = [], "General", "", "", ""
    for linea in bloque.splitlines():
        linea = linea.strip()
        if not linea or len(linea) > 200:
            continue
        if re.match(r"(?i)comentario", linea):
            break
        if not re.search(r"\d", linea) and linea.upper() == linea and len(linea) < 40:
            for clave, nombre in LERMA_MESAS:
                if clave in linea.lower():
                    mesa, mesa_original, unidad = nombre, linea, ""
            continue
        if mesa == "General":
            continue  # cabecera del boletín (fechas, títulos)
        m = LERMA_LINEA.match(linea)
        if not m:
            continue
        u = (m.group("unidad") or "").lower()
        if u.startswith("euro"):
            unidad = next((v for k, v in LERMA_UNIDADES.items() if k in u), unidad)
        nombre = nombre_lerma(m.group("nombre").strip(" .…"), anterior, mesa_original)
        anterior = nombre
        und = unidad + (" vivo" if unidad == "€/kg" and mesa == "Porcino" else "")
        filas.append({"cat": mesa, "producto": nombre, "unidad": und, "ant": None, "act": numero(m.group("precio"))})
    return fecha, filas


LERMA_UNIDAD_HTML = (("tonelada", "€/t"), ("unidad", "€/ud"), ("kg", "€/kg"))


def leer_lerma_html(html: str):
    """Sesión actual de Lerma, publicada como tabla en la propia página (comprobado el 5 nov 2026):
    filas 'TRIGO TIPO III | 231 €/TONELADA | 232 €/TONELADA'; títulos de mesa ('CEREALES', 'PORCINO CEBADO'…);
    en ganado, '........... PRIMERA' repite la primera parte del nombre anterior ('Añojos primera');
    '-' es sin cotización."""
    sopa = BeautifulSoup(html, "html.parser")
    fecha, filas, mesa, mesa_original, anterior = None, [], "General", "", ""
    for tabla in sopa.find_all("table"):
        texto_tabla = tabla.get_text(" ", strip=True)
        if not re.search(r"(?i)cotizaciones|celebraci", texto_tabla):
            continue
        m = re.search(r"(?i)celebraci[oó]n\s*(.{0,60})", texto_tabla)
        fecha = fecha_en(m.group(1)) if m else fecha_en(texto_tabla)
        for tr in tabla.find_all("tr"):
            celdas = [re.sub(r"\s+", " ", td.get_text(" ", strip=True).replace("\xa0", " ")).strip() for td in tr.find_all(["td", "th"])]
            celdas = [c for c in celdas if c]
            if not celdas:
                continue
            if re.match(r"(?i)comentario", celdas[0]):
                break
            if len(celdas) == 1 or re.fullmatch(r"(?i)actual|anterior", " ".join(celdas[1:2])):
                for clave, nombre in LERMA_MESAS:
                    if clave in celdas[0].lower():
                        mesa, mesa_original = nombre, celdas[0]
                continue
            if mesa == "General" or len(celdas) < 2 or not re.search(r"\d|-", " ".join(celdas[1:])):
                continue
            crudo = re.sub(r"^[.…\s]{3,}", "“ ", celdas[0])          # '...... PRIMERA' = ídem
            crudo = re.sub(r"\s*\((cerdo blanco)\)", "", crudo, flags=re.I)
            nombre = nombre_lerma(crudo, anterior, mesa_original)
            anterior = nombre
            def valor(c):
                n = re.search(r"\d+(?:[.,]\d+)?", c or "")
                return numero(n.group(0)) if n else None
            act, ant = valor(celdas[1]), valor(celdas[2] if len(celdas) > 2 else "")
            if act is None and ant is None:
                continue  # la lonja no da ese precio (p. ej. porcino selecto y graso)
            u = next((v for k, v in LERMA_UNIDAD_HTML if k in " ".join(celdas[1:]).lower()), "")
            und = u + (" vivo" if u == "€/kg" and mesa == "Porcino" else "")
            filas.append({"cat": mesa, "producto": nombre, "unidad": und, "ant": ant, "act": act})
        break
    return fecha, filas


def leer_lerma():
    """Lerma publica la sesión de cada semana como tabla en su página (actual y anterior). Los PDF anuales
    ('lonjahistoricoAAAA.pdf', una sesión por página) son su archivo: se usan solo si la tabla no se puede leer."""
    import pdfplumber
    pagina = "https://lerma.burgos.es/lonja"
    html = bajar(pagina).text
    fecha, filas = leer_lerma_html(html)
    tabla = BeautifulSoup(html, "html.parser").find("table")
    if tabla is not None:
        MATERIAL["lerma"] = {"html": str(tabla)}
    if fecha and len(filas) >= MINIMO_FILAS:
        print(f"[lerma] sesión de la página: {fecha}, {len(filas)} filas")
        return fecha, filas, pagina
    print(f"[lerma] la tabla de la página no se reconoce ({len(filas)} filas, fecha {fecha!r}); se prueba el histórico en PDF")
    pdfs = [(u, t) for u, t in enlaces_pdf(html, pagina) if re.search(r"lonja", u + " " + t, re.I)]
    con_año = []
    for u, t in pdfs:
        años = [int(a) for a in re.findall(r"(20\d\d)", u.rsplit("/", 1)[-1] + " " + t)]
        if años:
            con_año.append((max(años), u))
    if not con_año:
        for u, t in pdfs[:10]:
            print(f"[lerma] PDF visto: {t[:60]!r} | {u[:140]}")
        raise RuntimeError("No se encuentra el histórico anual de la Lonja de Lerma")
    año, url = max(con_año)
    print(f"[lerma] histórico elegido ({año}): {url[:160]}")
    if año < date.today().year - 1:
        print(f"[lerma] aviso: el histórico más reciente enlazado es de {año}")
    contenido = bajar(url).content
    if not contenido.startswith(b"%PDF-"):
        raise ValueError("El archivo descargado no es un PDF")
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        n = len(pdf.pages)
        if n > MAX_PAGINAS_TOTAL:
            raise ValueError(f"PDF con demasiadas páginas ({n})")
        texto = "\n".join((p.extract_text() or "") for p in pdf.pages[-3:])  # las 3 últimas bastan
    bloques = re.split(r"(?i)(?=lonja agropecuaria de lerma)", texto)
    for bloque in reversed(bloques):
        fecha, filas = leer_sesion_lerma(bloque)
        if fecha and len(filas) >= MINIMO_FILAS:
            print(f"[lerma] última sesión del PDF ({n} páginas): {fecha}, {len(filas)} filas")
            return fecha, filas, url
    diagnostico("lerma", bloques[-1] if bloques else texto, [], None)
    raise RuntimeError("No se reconoce la última sesión del histórico de Lerma")


# Material en bruto de la última lectura de cada lonja (lo que se descargó, ya en texto): con él se guardan casos
# de prueba reales en scraper/pruebas/casos/, y las pruebas comprueban que el lector sigue interpretándolos igual.
MATERIAL: dict[str, dict] = {}
INTERPRETES = {
    "leon": lambda m: interpretar_leon(m["entradas"])[:2],
    "segovia": interpretar_segovia,
    "salamanca": lambda m: leer_salamanca_csv(m["csv"]),
    "lerma": lambda m: leer_lerma_html(m["html"]),
}
CASOS = Path(__file__).resolve().parent / "pruebas" / "casos"
CASOS_POR_LONJA = 6


def filas_publicables(filas: list[dict]) -> list[dict]:
    """Las filas tal como se publicarían (después de la validación de aplicar)."""
    return [g for g in (limpiar_fila(dict(f)) for f in filas) if g]


def guardar_caso(lid: str, fecha: str, filas: list[dict], origen: str) -> None:
    """Guarda la lectura como caso de prueba: material descargado + resultado esperado. Solo las 6 últimas por lonja."""
    if lid not in MATERIAL or lid not in INTERPRETES or not fecha:
        return
    carpeta = CASOS / lid
    carpeta.mkdir(parents=True, exist_ok=True)
    caso = {"lonja": lid, "fecha": fecha, "origen": origen, "material": MATERIAL[lid],
            "esperado": {"fecha": fecha, "filas": filas_publicables(filas)}}
    (carpeta / f"{fecha}.json").write_text(json.dumps(caso, ensure_ascii=False, indent=1), encoding="utf-8")
    for viejo in sorted(carpeta.glob("*.json"))[:-CASOS_POR_LONJA]:
        viejo.unlink()


LECTORES = {"leon": leer_leon, "segovia": leer_segovia, "salamanca": leer_salamanca, "lerma": leer_lerma}


# ---------------------------------------------------------------------------
# Carga manual (respaldo)
# ---------------------------------------------------------------------------
def leer_manual(id_lonja: str):
    """data/manual/<lonja>.csv  ->  fecha;categoria;producto;unidad;anterior;actual"""
    ruta = MANUAL / f"{id_lonja}.csv"
    if not ruta.exists():
        return None
    if ruta.stat().st_size > 1_000_000:
        raise ValueError(f"{ruta.name}: archivo demasiado grande")
    filas, fecha = [], None
    with ruta.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            if len(filas) >= 600:
                break
            if not (r.get("producto") or "").strip():
                continue
            fecha = (r.get("fecha") or "").strip() or fecha
            filas.append({"cat": (r.get("categoria") or "").strip() or "General", "producto": r["producto"].strip(),
                          "unidad": (r.get("unidad") or "").strip(), "ant": numero(r.get("anterior")), "act": numero(r.get("actual"))})
    if fecha and re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", fecha):
        d, m, a = fecha.split("/")
        fecha = date(int(a), int(m), int(d)).isoformat()  # fecha imposible -> ValueError, lo gestiona main()
    return (fecha, filas, "carga manual") if fecha and filas else None


def limpiar_fila(f: dict) -> dict | None:
    """Valida una fila leída de una fuente externa antes de publicarla. Devuelve None si no es fiable."""
    def txt(v, mx):
        return re.sub(r"[\x00-\x1f\x7f<>\"'`]", " ", str(v or "")).strip()[:mx]
    producto, cat, unidad = txt(f.get("producto"), 80), txt(f.get("cat"), 40) or "General", txt(f.get("unidad"), 20)
    if len(producto) < 3 or not slug(producto):
        return None
    if unidad and not re.fullmatch(r"€/[A-Za-z. ]{1,14}", unidad):
        unidad = ""
    valores = [f.get("ant"), f.get("act")]
    if any(v is not None and not (0 <= v <= PRECIO_MAX) for v in valores):
        return None
    out = {"producto": producto, "cat": cat, "unidad": unidad, "ant": f.get("ant"), "act": f.get("act")}
    if f.get("rango"):
        out["rango"] = txt(f["rango"], 30)
    return out


# ---------------------------------------------------------------------------
# Fusión con los datos existentes
# ---------------------------------------------------------------------------
def palabras_nombre(id_producto: str, lonja_id: str) -> frozenset:
    """'leon-corderos-12-1-15-kg' -> {'corde', '12', '1', '15', 'kg'}: palabras del nombre recortadas a 5 letras,
    para reconocer el mismo producto con otro nombre (singular/plural, 'deshidratada'/'deshidratado')."""
    resto = id_producto[len(lonja_id) + 1:] if id_producto.startswith(lonja_id + "-") else id_producto
    return frozenset(w[:5] for w in resto.split("-") if w and w not in ("de", "del", "la", "el", "y", "sin", "con"))


def renombrado(p: dict, nuevos: list[dict], lonja_id: str) -> bool:
    """¿El producto p sigue cotizando con otro nombre? Solo cuenta un producto que aparece por primera vez en esta
    sesión, con la misma unidad y cuyas palabras contienen a las de p (o al revés): así 'Patata Agria' -> 'Agria'
    es un cambio de nombre, pero 'Trigo' no se oculta porque siga cotizando el 'Trigo duro' de siempre."""
    a = palabras_nombre(p["id"], lonja_id)
    for f in nuevos:
        if f.get("unidad") != p.get("unidad"):
            continue
        b = palabras_nombre(f["id"], lonja_id)
        if a and b and (a <= b or b <= a):
            return True
    return False


def sin_cotizar(lonja: dict, historial: dict, nuevas: list[dict], enlazados: set, fecha: str, misma: bool) -> list[dict]:
    """Productos de sesiones anteriores que no salen en esta. No se borran: se conservan sin precio actual y con
    su último precio y fecha («ult»), para que el agricultor vea que no cotizaron y cuándo fue la última vez.
    Se olvidan pasados DIAS_SIN_COTIZAR días."""
    ids = {f["id"] for f in nuevas}
    previos = {p["id"] for p in lonja.get("precios", [])}
    estrenados = [f for f in nuevas if f["id"] not in previos and f["id"] not in historial]
    limite = (date.fromisoformat(fecha) - timedelta(days=DIAS_SIN_COTIZAR)).isoformat()
    out = []
    for p in lonja.get("precios", []):
        if p["id"] in ids or p["id"] in enlazados or renombrado(p, estrenados, lonja["id"]):
            continue
        if p.get("act") is not None:
            if misma:  # estaba en esta misma sesión y la lectura corregida ya no lo trae: no se conserva
                continue
            serie = [q for q in historial.get(p["id"]) or [] if q[0] < fecha]
            ult = list(serie[-1]) if serie else [lonja.get("fecha"), p["act"]]
        else:
            ult = p.get("ult")
        if not ult or not ult[0] or ult[0] < limite or ult[0] >= fecha:
            continue
        out.append({k: p[k] for k in ("id", "cat", "producto", "unidad", "clave") if k in p}
                   | {"ant": None, "act": None, "ult": [ult[0], ult[1]]})
    return out


def aplicar(lonja: dict, historial: dict, fecha: str, filas: list[dict], origen: str) -> bool:
    filas = [g for g in (limpiar_fila(f) for f in filas) if g]
    if not fecha or len(filas) < MINIMO_FILAS:
        raise RuntimeError(f"Lectura incompleta: {len(filas)} filas válidas, fecha {fecha!r}")
    if not fecha_plausible(fecha):
        raise RuntimeError(f"Fecha de sesión fuera de rango: {fecha!r}")
    # Misma sesión leída otra vez: se actualiza si ha cambiado (corrección de la lonja, lector mejorado o la
    # «carga inicial» hecha a mano al crear la app). Lo cargado a mano en data/manual/ no se pisa.
    misma = lonja.get("fecha") == fecha and "carga manual" not in (lonja.get("origen"), origen)
    if lonja.get("fecha") and (fecha < lonja["fecha"] or (fecha == lonja["fecha"] and not misma)):
        return False  # ya tenemos una sesión más nueva (o esta misma, cargada a mano)
    previos = {f["id"]: f for f in lonja.get("precios", [])}
    por_clave = {f["clave"]: f for f in lonja.get("precios", []) if f.get("clave") and f.get("act") is not None}
    nuevas, vistos, enlazados = [], set(), set()
    for f in filas:
        f["id"] = f"{lonja['id']}-{slug(f['producto'])}"
        if f["id"] in vistos:  # mismo nombre en dos mesas (p. ej. 'Primera')
            f["id"] = f"{lonja['id']}-{slug(f['cat'])}-{slug(f['producto'])}"
        vistos.add(f["id"])
        clave = clave_de(f["producto"])
        if clave:
            f["clave"] = clave
        # El mismo producto pudo llamarse distinto la semana pasada: se enlaza por su clave
        previo = previos.get(f["id"]) or (por_clave.get(clave) if clave else None)
        if previo:
            enlazados.add(previo["id"])
        if f.get("ant") is None and previo:
            # Si la sesión anterior no lo cotizó, el «anterior» es su último precio conocido
            f["ant"] = previo.get("ant") if misma else (
                previo["act"] if previo.get("act") is not None else (previo.get("ult") or [None, None])[1])
        if previo and previo["id"] != f["id"] and f["id"] not in historial and previo["id"] in historial:
            historial[f["id"]] = list(historial[previo["id"]])
        if f.get("act") is None:
            serie = historial.get(f["id"]) or []
            anteriores = [p for p in serie if p[0] < fecha]
            if anteriores:
                f["ult"] = list(anteriores[-1])
        nuevas.append({k: f[k] for k in ("id", "cat", "producto", "unidad", "ant", "act", "rango", "clave", "ult") if k in f})
    nuevas += sin_cotizar(lonja, historial, nuevas, enlazados, fecha, misma)
    if misma and nuevas == lonja.get("precios") and origen == lonja.get("origen"):
        return False  # la misma sesión, leída igual: nada que publicar
    for f in nuevas:
        if f.get("act") is not None:
            serie = historial.setdefault(f["id"], [])
            if not serie or serie[-1][0] != fecha:
                serie.append([fecha, f["act"]])
            elif misma:
                serie[-1][1] = f["act"]
    lonja.update(precios=nuevas, fecha=fecha, origen=origen, estado="activa", error=None)
    return True


def recortar_historial(historial: dict) -> None:
    limite = (date.today() - timedelta(days=365 * AÑOS_HISTORIAL)).isoformat()
    for k in list(historial):
        historial[k] = [p for p in historial[k] if p[0] >= limite]


def main(solo: list[str]) -> int:
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    historial = datos.setdefault("historial", {})
    antes = json.dumps(datos, sort_keys=True)
    ahora = datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes")
    hoy = ahora[:10]
    fallos = 0

    for lonja in datos["lonjas"]:
        lid = lonja["id"]
        if solo and lid not in solo:
            continue
        lectura, error, manual = None, None, None
        try:
            manual = leer_manual(lid)
        except Exception as exc:  # noqa: BLE001  (un CSV mal escrito no debe tumbar al resto de lonjas)
            error = f"CSV manual no válido: {type(exc).__name__}"
            print(f"[{lid}] {error}: {exc}")
        if lid in LECTORES:
            try:
                lectura = LECTORES[lid]()
            except Exception as exc:  # noqa: BLE001
                error = f"Falló la lectura automática ({type(exc).__name__})"
                print(f"[{lid}] detalle: {exc}")  # el detalle completo queda solo en el registro de Actions
                traceback.print_exc()
        automatica = lectura
        if manual and (not lectura or (manual[0] or "") >= (lectura[0] or "")):
            lectura = manual
        if lectura:
            try:
                cambio = aplicar(lonja, historial, *lectura)
                print(f"[{lid}] sesión {lectura[0]}: {len(lectura[1])} filas" + (" (nueva)" if cambio else " (sin cambios)"))
                error = None  # hay datos válidos (automáticos o manuales)
                if lectura is automatica and (cambio or not (CASOS / lid).exists()):
                    guardar_caso(lid, lectura[0], lectura[1], lectura[2])
                if lid == "salamanca" and lectura[2] == SALAMANCA_DATASET:
                    lonja["fuente"], lonja["nota"] = SALAMANCA_DATASET, SALAMANCA_NOTA  # atribución que pide la licencia
            except Exception as exc:  # noqa: BLE001
                error = "Lectura incompleta o no válida"
                print(f"[{lid}] detalle: {exc}")
        # Estado de la fuente (lo usa la pantalla «Estado de las fuentes» y el aviso por GitHub).
        # La última lectura correcta se apunta una vez al día, para no publicar un cambio en cada pasada.
        if lid in LECTORES or manual:
            if error:
                lonja["fallos"] = min(FALLOS_TOPE, int(lonja.get("fallos") or 0) + 1)  # tope: no publicar un cambio en cada pasada
                lonja["fallo_desde"] = lonja.get("fallo_desde") or ahora
            else:
                if lonja.get("fallos"):
                    lonja["fallos"], lonja["fallo_desde"] = 0, None
                if (lonja.get("ultima_lectura") or "")[:10] != hoy:
                    lonja["ultima_lectura"] = ahora
        if error:
            fallos += 1
            print(f"[{lid}] ERROR: {error}")
            lonja["error"] = error[:120]  # el JSON es público: sin rutas, URLs ni mensajes internos
        elif lonja.get("error") and lectura:
            lonja["error"] = None

    recortar_historial(historial)
    if json.dumps(datos, sort_keys=True) != antes:
        datos["generado"] = ahora
        DATOS.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        print("precios.json actualizado")
    else:
        print("Sin novedades")
    # Un fallo de lectura no rompe el proceso: la app sigue con los datos anteriores
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

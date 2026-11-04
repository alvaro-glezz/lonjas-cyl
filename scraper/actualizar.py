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
AÑOS_HISTORIAL = 3

# --- Límites de seguridad -------------------------------------------------
# Solo se descargan páginas y PDF de estos dominios (y sus subdominios), siempre por https. Los enlaces a
# PDF salen del HTML de webs ajenas: sin esta lista, una web comprometida podría hacer que el robot
# descargue cualquier otra dirección. Si una lonja cambia de dominio, añádelo aquí.
DOMINIOS_PERMITIDOS = ("lasalina.es", "lonjadeleon.es", "fessegovia.es", "lerma.burgos.es")
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


def bajar(url: str) -> requests.Response:
    """Descarga segura: solo https y dominios conocidos, redirecciones revisadas una a una, tamaño limitado."""
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
        return "\n".join((p.extract_text() or "") for p in pdf.pages[:MAX_PAGINAS_PDF])


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
    candidatos = [p for p in unicos if re.search(patron, p[0] + " " + p[1], re.I)] or unicos
    con_fecha = [(fecha_de_enlace(u, t), u, t) for u, t in candidatos]
    for f, u, t in con_fecha[:8]:
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


def filas_de_tablas_html(html: str, cat_defecto: str, unidad_defecto: str = "") -> list[dict]:
    """Lee las tablas HTML de una entrada de blog (formato de la Lonja de León)."""
    sopa = BeautifulSoup(html, "html.parser")
    filas, cat, unidad = [], cat_defecto, unidad_defecto
    for tr in sopa.select("tr"):
        celdas = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        celdas = [c for c in celdas if c]
        if not celdas:
            continue
        linea = " ".join(celdas)
        if "€/t" in linea.replace(" ", "") and not re.search(r"\d", linea):
            unidad = "€/t"
        if len(celdas) == 1 or es_titulo(linea) or not re.search(r"\d|s/c", linea, re.I):
            if not re.search(r"cotizaci|anterior|actual|dif", linea, re.I) and len(linea) < 40:
                cat = bonito(linea).capitalize()
            continue
        f = leer_linea(linea)
        if f:
            f.update(cat=cat, unidad=unidad or unidad_defecto)
            filas.append(f)
    if not filas:  # sin tablas: probar como texto
        filas = leer_texto(sopa.get_text("\n"), unidad_defecto)
        for f in filas:
            if f["cat"] == "General":
                f["cat"] = cat_defecto
    return filas


def enlaces_pdf(html: str, base: str) -> list[tuple[str, str]]:
    sopa = BeautifulSoup(html, "html.parser")
    out = []
    for a in sopa.find_all("a", href=True):
        href = urljoin(base, a["href"])
        if ".pdf" in href.lower():
            out.append((href, a.get_text(" ", strip=True)))
    return out


# ---------------------------------------------------------------------------
# Lectores, uno por lonja. Cada uno devuelve (fecha_iso, filas, url_origen)
# ---------------------------------------------------------------------------
def leer_leon():
    """Web WordPress de la Lonja: una entrada por mesa ('Lonja cereal 29-10-2026')."""
    url = "https://www.lonjadeleon.es/wp-json/wp/v2/posts?per_page=40&_fields=date,title,link,content"
    entradas = bajar(url).json()
    por_fecha: dict[str, list] = {}
    for e in entradas:
        titulo = BeautifulSoup(e["title"]["rendered"], "html.parser").get_text()
        if not re.search(r"lonja|cotizac", titulo, re.I):
            continue
        f = fecha_en(titulo) or e["date"][:10]
        if not fecha_plausible(f):
            continue
        por_fecha.setdefault(f, []).append((titulo, e))
    if not por_fecha:
        raise RuntimeError("No hay entradas de cotizaciones en la web de la Lonja de León")
    fecha = max(por_fecha)
    filas = []
    for titulo, e in por_fecha[fecha]:
        mesa = re.sub(r"(?i)lonja( de)?|\d{1,2}-\d{1,2}-\d{2,4}", "", titulo).strip(" -") or "General"
        unidad = "€/t" if re.search(r"cereal|forraj|patat|girasol", mesa, re.I) else ""
        filas += filas_de_tablas_html(e["content"]["rendered"], mesa.capitalize(), unidad)
    return fecha, filas, por_fecha[fecha][0][1]["link"]


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
    texto = texto_pdf(bajar(url_pdf).content)
    fecha = fecha_en(url_pdf.replace("-", " ")) or fecha_en(e["title"]["rendered"]) or e["date"][:10]
    return fecha, leer_texto(texto, "€/t"), url_pdf


def leer_salamanca():
    """La Diputación (La Salina) publica cada lunes el PDF de la Lonja."""
    pagina = "https://www.lasalina.es/economiayhacienda/agriculturayganaderia/mercado/lonja/"
    html = bajar(pagina).text
    pdfs = enlaces_pdf(html, pagina)
    if not pdfs:
        raise RuntimeError("No hay PDF en la página de La Salina")
    url_pdf, fecha_nombre = elegir_pdf("salamanca", pdfs, r"lonja|cotiz")
    texto = texto_pdf(bajar(url_pdf).content)
    fecha = fecha_en(texto[:1500]) or fecha_nombre or fecha_en(texto)
    filas = leer_texto(texto)
    diagnostico("salamanca", texto, filas, fecha)
    return fecha, filas, url_pdf


def leer_lerma():
    """El Ayuntamiento de Lerma publica las cotizaciones de cada viernes."""
    pagina = "https://lerma.burgos.es/lonja"
    html = bajar(pagina).text
    pdfs = enlaces_pdf(html, pagina)
    fecha_nombre = None
    if pdfs:
        url, fecha_nombre = elegir_pdf("lerma", pdfs, r"lonja|cotiz|precio|sesi[oó]n|mercado")
        texto = texto_pdf(bajar(url).content)
    else:
        print("[lerma] la página no enlaza PDF; se lee el texto de la propia página")
        url, texto = pagina, BeautifulSoup(html, "html.parser").get_text("\n")
    fecha = fecha_en(texto[:1500]) or fecha_nombre or fecha_en(texto)
    filas = leer_texto(texto)
    diagnostico("lerma", texto, filas, fecha)
    return fecha, filas, url


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
def aplicar(lonja: dict, historial: dict, fecha: str, filas: list[dict], origen: str) -> bool:
    filas = [g for g in (limpiar_fila(f) for f in filas) if g]
    if not fecha or len(filas) < MINIMO_FILAS:
        raise RuntimeError(f"Lectura incompleta: {len(filas)} filas válidas, fecha {fecha!r}")
    if not fecha_plausible(fecha):
        raise RuntimeError(f"Fecha de sesión fuera de rango: {fecha!r}")
    if lonja.get("fecha") and fecha <= lonja["fecha"]:
        return False  # ya tenemos esta sesión (o una más nueva)
    previos = {f["id"]: f for f in lonja.get("precios", [])}
    por_clave = {f["clave"]: f for f in lonja.get("precios", []) if f.get("clave")}
    nuevas, vistos = [], set()
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
        if f.get("ant") is None and previo:
            f["ant"] = previo.get("act")
        if previo and previo["id"] != f["id"] and f["id"] not in historial and previo["id"] in historial:
            historial[f["id"]] = list(historial[previo["id"]])
        nuevas.append({k: f[k] for k in ("id", "cat", "producto", "unidad", "ant", "act", "rango", "clave") if k in f})
        if f.get("act") is not None:
            serie = historial.setdefault(f["id"], [])
            if not serie or serie[-1][0] != fecha:
                serie.append([fecha, f["act"]])
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
        if manual and (not lectura or (manual[0] or "") >= (lectura[0] or "")):
            lectura = manual
        if lectura:
            try:
                cambio = aplicar(lonja, historial, *lectura)
                print(f"[{lid}] sesión {lectura[0]}: {len(lectura[1])} filas" + (" (nueva)" if cambio else " (sin cambios)"))
                error = None  # hay datos válidos (automáticos o manuales)
            except Exception as exc:  # noqa: BLE001
                error = "Lectura incompleta o no válida"
                print(f"[{lid}] detalle: {exc}")
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

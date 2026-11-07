"""Genera las páginas que Google puede leer: una por producto, una por lonja y un índice, más sitemap.xml.

La app (index.html) pinta todo con JavaScript en una sola dirección con «#», y Google no indexa esas secciones
como páginas distintas. Estas páginas son HTML estático, rápidas y sin JavaScript, con los mismos datos de
data/precios.json. Cada una enlaza a la app para lo interactivo (avisos, calculadora, gráficos).

Lo ejecuta la tarea «Actualizar precios» después de leer las lonjas. Uso local:  python scraper/paginas.py
Solo escribe en precio/, lonja/, precios/, plazos/ y sitemap.xml. Nunca toca data/.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import date, datetime
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "precios.json"
# Dirección pública principal (la que Google debe tomar como buena). Si se compra un dominio, se cambia solo aquí.
WEB = "https://lonjas-cyl-khaki.vercel.app/"
CARPETAS = ("precio", "lonja", "precios", "plazos")
PLAZOS = RAIZ / "data" / "plazos.json"

# Producto (clave de la app) -> (nombre con artículo, nombre corto, categoría de la página)
PRODUCTOS = {
    "trigo": ("del trigo", "Trigo", "Cereales"),
    "cebada": ("de la cebada", "Cebada", "Cereales"),
    "maiz": ("del maíz", "Maíz", "Cereales"),
    "avena": ("de la avena", "Avena", "Cereales"),
    "centeno": ("del centeno", "Centeno", "Cereales"),
    "triticale": ("del triticale", "Triticale", "Cereales"),
    "girasol": ("del girasol", "Girasol", "Oleaginosas"),
    "alfalfa": ("de la alfalfa", "Alfalfa", "Forrajes"),
    "paja": ("de la paja", "Paja", "Forrajes"),
    "lechazo": ("del lechazo", "Lechazo", "Ovino"),
    "cerdo-normal": ("del cerdo normal", "Cerdo normal", "Porcino"),
    "cerdo-selecto": ("del cerdo selecto", "Cerdo selecto", "Porcino"),
    "lechones": ("de los lechones", "Lechones", "Porcino"),
}
# Páginas por sector: reúnen todas las categorías de la app que les corresponden
SECTORES = {
    "cereales": ("de los cereales", "Cereales", {"Cereales"}),
    "ovino": ("del ovino", "Ovino", {"Ovino", "Leche de oveja y de cabra"}),
    "porcino": ("del porcino", "Porcino", {"Porcino", "Porcino blanco", "Porcino ibérico"}),
    "vacuno": ("del vacuno", "Vacuno", {"Vacuno", "Vacuno de carne", "Bovino carne", "Vacuno de vida", "Vacas sacrificio", "Leche de vaca"}),
}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def num(v: float | None, dec: int | None = None) -> str:
    if v is None:
        return "—"
    if dec is None:
        dec = 0 if float(v).is_integer() else (3 if abs(v) < 10 and round(v, 2) != v else 2)
    s = f"{v:,.{dec}f}"
    return s.replace(",", " ").replace(".", ",").replace(" ", ".")


def fecha_larga(iso: str | None) -> str:
    if not iso:
        return "sin fecha"
    d = date.fromisoformat(iso[:10])
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def fecha_corta(iso: str | None) -> str:
    if not iso:
        return "—"
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {MESES[d.month - 1][:3]}"


def cambio(p: dict) -> tuple[str, str]:
    """(texto, clase) del cambio frente a la sesión anterior."""
    a, b = p.get("ant"), p.get("act")
    if a is None or b is None:
        return "—", ""
    d = b - a
    if abs(d) < 1e-9:
        return "repite", "igual"
    pct = d / a * 100 if a else 0
    signo = "+" if d > 0 else "−"
    return f"{signo}{num(abs(d))} ({signo}{num(abs(pct), 1)} %)", "sube" if d > 0 else "baja"


def lonjas_activas(datos: dict) -> list[dict]:
    return [l for l in datos.get("lonjas", []) if l.get("estado") != "suspendida"]


# ---------- piezas comunes ----------

def pagina(*, ruta: str, nivel: int, titulo: str, descripcion: str, h1: str, cuerpo: str, migas: list[tuple[str, str]],
           ld: list[dict]) -> str:
    """HTML completo. `nivel` = carpetas de profundidad (para enlaces relativos que valen en github.io y en Vercel)."""
    up = "../" * nivel
    canon = WEB + ruta
    ld_txt = "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)
    migas_html = " › ".join(f'<a href="{up}{escape(h)}">{escape(t)}</a>' if h is not None else escape(t) for t, h in migas)
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)}</title>
<meta name="description" content="{escape(descripcion)}">
<link rel="canonical" href="{canon}">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'self'; font-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'">
<meta name="theme-color" content="#24503c">
<meta property="og:type" content="website">
<meta property="og:locale" content="es_ES">
<meta property="og:site_name" content="Lonjas CyL">
<meta property="og:title" content="{escape(h1)}">
<meta property="og:description" content="{escape(descripcion)}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{WEB}icons/compartir.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{up}icons/icono.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{up}icons/icono-192.png">
<link rel="stylesheet" href="{up}paginas.css">
<script src="{up}contador.js" data-ruta="web:{escape(ruta.strip("/").replace("/", "-") or "inicio")}" defer></script>
{ld_txt}
</head>
<body>
<header class="cab"><div class="dentro">
  <a class="marca" href="{up}"><img src="{up}icons/icono.svg" width="30" height="30" alt="">Lonjas CyL</a>
  <a class="boton" href="{up}">Abrir la app</a>
</div></header>
<main class="dentro">
<nav class="migas" aria-label="Estás en">{migas_html}</nav>
<h1>{escape(h1)}</h1>
{cuerpo}
</main>
<footer class="pie"><div class="dentro">
<p><b>Precios orientativos.</b> Cada lonja cotiza en sus propias condiciones (calidad, punto de entrega, peso). No son una oferta ni una recomendación de compra o venta: confírmalo con tu lonja o comprador.</p>
<p>Fuentes: Lonja de Salamanca (datos abiertos de la Diputación de Salamanca, licencia CC BY 4.0), Lonja de León, Lonja de Segovia (FES) y Lonja de Lerma. <a href="{up}#metodo">Fuentes y método</a> · <a href="{up}precios/">Todos los precios</a></p>
<p>Lonjas CyL es una web independiente; no pertenece a ninguna lonja ni administración.</p>
</div></footer>
</body>
</html>
"""


def grafico(series: list[tuple[str, list]], unidad: str) -> str:
    """Gráfico de líneas en SVG estático (sin JavaScript). series = [(nombre, [[fecha, valor], ...]), ...]."""
    series = [(n, [(date.fromisoformat(f), v) for f, v in pts if v is not None]) for n, pts in series]
    series = [(n, pts) for n, pts in series if len(pts) >= 2]
    if not series:
        return ""
    W, H, iz, de, ar, ab = 480, 250, 44, 84, 12, 24
    xs = [d for _, pts in series for d, _ in pts]
    ys = [v for _, pts in series for _, v in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    marg = (y1 - y0) * 0.12 or abs(y1) * 0.05 or 1
    y0, y1 = y0 - marg, y1 + marg
    dx = (x1 - x0).days or 1
    X = lambda d: iz + (d - x0).days / dx * (W - iz - de)
    Y = lambda v: ar + (y1 - v) / (y1 - y0) * (H - ar - ab)
    colores = ["#24503c", "#b9861f", "#2f6db5", "#c0365f", "#8a4fb0"]
    partes = []
    for i in range(4):
        v = y0 + (y1 - y0) * (i + 0.5) / 4
        partes.append(f'<line x1="{iz}" x2="{W - de}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="rej"/>'
                      f'<text x="{iz - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" class="eje">{num(v, 0 if y1 - y0 > 20 else 2)}</text>')
    partes.append(f'<text x="{iz}" y="{H - 6}" class="eje">{fecha_corta(x0.isoformat())}</text>'
                  f'<text x="{W - de}" y="{H - 6}" text-anchor="end" class="eje">{fecha_corta(x1.isoformat())}</text>')
    etiquetas = []
    for i, (n, pts) in enumerate(series):
        c = colores[i % len(colores)]
        d = " ".join(f"{'M' if j == 0 else 'L'}{X(f):.1f},{Y(v):.1f}" for j, (f, v) in enumerate(pts))
        partes.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>')
        f, v = pts[-1]
        partes.append(f'<circle cx="{X(f):.1f}" cy="{Y(v):.1f}" r="3.5" fill="{c}"/>')
        etiquetas.append([Y(v), c, n])
    etiquetas.sort()
    for i in range(1, len(etiquetas)):  # que no se pisen los nombres
        etiquetas[i][0] = max(etiquetas[i][0], etiquetas[i - 1][0] + 14)
    for y, c, n in etiquetas:
        partes.append(f'<text x="{W - de + 8}" y="{y + 4:.1f}" fill="{c}" class="nom">{escape(n)}</text>')
    alt = "Evolución en " + unidad + ": " + "; ".join(f"{n} de {num(p[0][1])} a {num(p[-1][1])}" for n, p in series)
    return (f'<figure class="graf"><svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(alt)}">{"".join(partes)}</svg>'
            f'<figcaption>{escape(unidad)} · sesiones desde {fecha_larga(min(xs).isoformat())}</figcaption></figure>')


def tabla_precios(filas: list[tuple[dict, dict]], *, con_lonja: bool, nivel: int) -> str:
    up = "../" * nivel
    cab = "<th>Lonja</th>" if con_lonja else ""
    out = [f'<div class="tabla"><table><thead><tr>{cab}<th>Producto</th><th class="n">Precio</th><th class="n opc">Anterior</th>'
           f'<th class="n">Cambio</th><th class="opc">Sesión</th></tr></thead><tbody>']
    for l, p in filas:
        txt, cls = cambio(p)
        lon = f'<td><a href="{up}lonja/{l["id"]}/">{escape(l["nombre"].replace("Lonja de ", ""))}</a></td>' if con_lonja else ""
        if p.get("act") is None:
            ult = p.get("ult")
            precio = f'<span class="tenue">sin cotizar{f" · último {num(ult[1])} ({fecha_corta(ult[0])})" if ult else ""}</span>'
        else:
            precio = f"<b>{num(p['act'])}</b> <small>{escape(p['unidad'])}</small>"
        out.append(f'<tr>{lon}<td>{escape(p["producto"])}</td><td class="n">{precio}</td><td class="n opc">{num(p.get("ant"))}</td>'
                   f'<td class="n {cls}">{txt}</td><td class="opc">{fecha_corta(l.get("fecha"))}</td></tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


def ld_migas(migas: list[tuple[str, str | None]], ruta: str) -> dict:
    items = []
    for i, (t, h) in enumerate(migas, 1):
        items.append({"@type": "ListItem", "position": i, "name": t, "item": WEB + (h if h is not None else ruta)})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def ld_dataset(nombre: str, descripcion: str, ruta: str, modificado: str, lonjas: list[str]) -> dict:
    return {
        "@context": "https://schema.org", "@type": "Dataset", "name": nombre, "description": descripcion,
        "url": WEB + ruta, "dateModified": modificado, "inLanguage": "es",
        "spatialCoverage": {"@type": "Place", "name": "Castilla y León, España"},
        "isAccessibleForFree": True,
        "creator": {"@type": "Organization", "name": "Lonjas CyL", "url": WEB},
        "isBasedOn": lonjas,
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": WEB + "data/precios.json"}],
    }


# ---------- páginas ----------

def precios_de(datos: dict, filtro) -> list[tuple[dict, dict]]:
    return [(l, p) for l in lonjas_activas(datos) for p in l.get("precios", []) if filtro(p)]


def resumen(filas: list[tuple[dict, dict]], corto: str) -> tuple[str, str]:
    """Frase principal (HTML) y versión para la meta descripción, comparando lonjas de la misma unidad."""
    con = [(l, p) for l, p in filas if p.get("act") is not None]
    if not con:
        return f"<p class='lead'>Esta semana ninguna lonja ha publicado precio de {escape(corto.lower())}.</p>", ""
    unidad = max({p["unidad"] for _, p in con}, key=lambda u: sum(1 for _, p in con if p["unidad"] == u))
    con = sorted([(l, p) for l, p in con if p["unidad"] == unidad], key=lambda x: -x[1]["act"])
    (la, pa), (lb, pb) = con[0], con[-1]
    nom = lambda l: l["nombre"].replace("Lonja de ", "")
    if len(con) == 1:
        t = f"Esta semana {nom(la)} cotiza {pa['producto'].lower()} a {num(pa['act'])} {unidad} ({fecha_larga(la.get('fecha'))})."
        return f"<p class='lead'>{escape(t)}</p>", t
    dif = pa["act"] - pb["act"]
    t = (f"Esta semana se paga entre {num(pb['act'])} y {num(pa['act'])} {unidad}. Paga más {nom(la)} ({num(pa['act'])}, "
         f"{pa['producto'].lower()}), {num(dif)} {unidad} más que {nom(lb)}.")
    return f"<p class='lead'>{escape(t)}</p>", t


def enlaces_productos(nivel: int, actual: str | None = None) -> str:
    up = "../" * nivel
    a = [f'<a href="{up}precio/{k}/"{" aria-current=page" if k == actual else ""}>{escape(v[1])}</a>' for k, v in PRODUCTOS.items()]
    a += [f'<a href="{up}precio/{k}/"{" aria-current=page" if k == actual else ""}>{escape(v[1])}</a>' for k, v in SECTORES.items()]
    return '<nav class="chips" aria-label="Otros precios">' + "".join(a) + "</nav>"


def enlaces_lonjas(datos: dict, nivel: int) -> str:
    up = "../" * nivel
    return '<nav class="chips" aria-label="Lonjas">' + "".join(
        f'<a href="{up}lonja/{l["id"]}/">{escape(l["nombre"])}</a>' for l in lonjas_activas(datos)) + "</nav>"


def pagina_producto(datos: dict, clave: str) -> str | None:
    art, corto, _ = PRODUCTOS[clave]
    filas = precios_de(datos, lambda p: p.get("clave") == clave)
    if not filas:
        return None
    ruta = f"precio/{clave}/"
    lead, frase = resumen(filas, corto)
    fechas = sorted({l["fecha"] for l, _ in filas if l.get("fecha")})
    hasta = fechas[-1] if fechas else None
    series = [(l["nombre"].replace("Lonja de ", ""), datos.get("historial", {}).get(p["id"], [])) for l, p in filas]
    unidad = filas[0][1]["unidad"]
    h1 = f"Precio {art} hoy en las lonjas de Castilla y León"
    desc = (frase + " Comparativa de lonjas actualizada cada semana.") if frase else f"Cotizaciones {art} en las lonjas de Castilla y León."
    migas = [("Inicio", ""), ("Precios", "precios/"), (corto, None)]
    cuerpo = (f'{lead}<p class="fecha">Últimas sesiones hasta el {fecha_larga(hasta)}. Se actualiza solo cuando cada lonja publica.</p>'
              + tabla_precios(sorted(filas, key=lambda x: -(x[1].get("act") or 0)), con_lonja=True, nivel=2)
              + '<p class="nota">Cada lonja cotiza su propia calidad (por ejemplo, trigo blando o trigo pienso), así que compara también la descripción del producto.</p>'
              + grafico(series, unidad)
              + f'<section class="cta"><h2>Sigue el precio {escape(art)} en la app</h2><p>Avisos cuando cruce el precio que tú elijas, calculadora de venta con portes y gráficos con el histórico oficial de la Junta. Gratis y sin registro.</p>'
              f'<a class="boton" href="../../#comparar-{clave}">Comparar en la app</a></section>'
              + "<h2>Otros precios</h2>" + enlaces_productos(2, clave) + "<h2>Lonjas</h2>" + enlaces_lonjas(datos, 2))
    ld = [ld_migas(migas, ruta), ld_dataset(f"Precio {art} en las lonjas de Castilla y León", desc, ruta,
                                            datos.get("generado", "")[:10], sorted({l["fuente"] for l, _ in filas if l.get("fuente")}))]
    return pagina(ruta=ruta, nivel=2, titulo=f"Precio {art} hoy · lonjas de Castilla y León ({fecha_corta(hasta)}) | Lonjas CyL",
                  descripcion=desc, h1=h1, cuerpo=cuerpo, migas=migas, ld=ld)


def pagina_sector(datos: dict, clave: str) -> str | None:
    art, corto, cats = SECTORES[clave]
    filas = precios_de(datos, lambda p: p.get("cat") in cats)
    if not filas:
        return None
    ruta = f"precio/{clave}/"
    fechas = sorted({l["fecha"] for l, _ in filas if l.get("fecha")})
    con = [x for x in filas if x[1].get("act") is not None]
    suben = sum(1 for _, p in con if p.get("ant") is not None and p["act"] > p["ant"])
    bajan = sum(1 for _, p in con if p.get("ant") is not None and p["act"] < p["ant"])
    frase = f"{len(con)} cotizaciones {art} en {len({l['id'] for l, _ in con})} lonjas de Castilla y León: {suben} suben, {bajan} bajan y el resto repite."
    h1 = f"Precio {art} hoy en las lonjas de Castilla y León"
    migas = [("Inicio", ""), ("Precios", "precios/"), (corto, None)]
    bloques = []
    for l in lonjas_activas(datos):
        fl = [(l, p) for (ll, p) in filas if ll is l]
        if fl:
            bloques.append(f'<h2><a href="../../lonja/{l["id"]}/">{escape(l["nombre"])}</a> <small>sesión del {fecha_larga(l.get("fecha"))}</small></h2>'
                           + tabla_precios(fl, con_lonja=False, nivel=2))
    cuerpo = (f'<p class="lead">{escape(frase)}</p><p class="fecha">Últimas sesiones hasta el {fecha_larga(fechas[-1] if fechas else None)}.</p>'
              + "".join(bloques)
              + f'<section class="cta"><h2>Compara lonja por lonja</h2><p>En la app ves dónde se paga más cada semana, con avisos de precio y el histórico oficial.</p><a class="boton" href="../../#comparar">Abrir el comparador</a></section>'
              + "<h2>Otros precios</h2>" + enlaces_productos(2, clave))
    ld = [ld_migas(migas, ruta), ld_dataset(f"Precio {art} en las lonjas de Castilla y León", frase, ruta, datos.get("generado", "")[:10],
                                            sorted({l["fuente"] for l, _ in filas if l.get("fuente")}))]
    return pagina(ruta=ruta, nivel=2, titulo=f"Precio {art} hoy · lonjas de Castilla y León ({fecha_corta(fechas[-1] if fechas else None)}) | Lonjas CyL",
                  descripcion=frase, h1=h1, cuerpo=cuerpo, migas=migas, ld=ld)


def pagina_lonja(datos: dict, l: dict) -> str:
    ruta = f"lonja/{l['id']}/"
    ps = l.get("precios", [])
    cats: dict[str, list] = {}
    for p in ps:
        cats.setdefault(p["cat"], []).append((l, p))
    con = [p for p in ps if p.get("act") is not None]
    suben = sum(1 for p in con if p.get("ant") is not None and p["act"] > p["ant"])
    bajan = sum(1 for p in con if p.get("ant") is not None and p["act"] < p["ant"])
    frase = (f"Sesión del {fecha_larga(l.get('fecha'))}: {len(con)} precios, {suben} suben y {bajan} bajan. "
             f"La lonja cotiza los {l.get('dia', '').lower()}.")
    nombre = l["nombre"]
    h1 = f"Precios de la {nombre} hoy"
    migas = [("Inicio", ""), ("Precios", "precios/"), (nombre, None)]
    destacados = [(p, PRODUCTOS[p["clave"]]) for p in ps if p.get("clave") in PRODUCTOS]
    links = "".join(f'<a href="../../precio/{p["clave"]}/">Precio {escape(v[0])} en todas las lonjas</a>' for p, v in destacados)
    fuente = f'<p class="fecha">Fuente: <a href="{escape(l["fuente"])}" rel="nofollow">{escape(l.get("nota") or "web de la lonja")}</a>.</p>' if l.get("fuente") else ""
    cuerpo = (f'<p class="lead">{escape(frase)}</p>{fuente}'
              + "".join(f"<h2>{escape(c)}</h2>" + tabla_precios(f, con_lonja=False, nivel=2) for c, f in cats.items())
              + f'<section class="cta"><h2>¿Pagan más en otra lonja?</h2><p>Compara esta sesión con León, Salamanca, Segovia y Lerma en la app, y crea un aviso de precio.</p><a class="boton" href="../../#lonja-{l["id"]}">Ver en la app</a></section>'
              + (f'<h2>Comparar con otras lonjas</h2><nav class="chips">{links}</nav>' if links else "")
              + "<h2>Otras lonjas</h2>" + enlaces_lonjas(datos, 2))
    ld = [ld_migas(migas, ruta), ld_dataset(f"Cotizaciones de la {nombre}", frase, ruta, (l.get("fecha") or ""), [l["fuente"]] if l.get("fuente") else [])]
    return pagina(ruta=ruta, nivel=2, titulo=f"{nombre}: precios de hoy ({fecha_corta(l.get('fecha'))}) | Lonjas CyL",
                  descripcion=frase, h1=h1, cuerpo=cuerpo, migas=migas, ld=ld)


def pagina_indice(datos: dict, productos: list[str], sectores: list[str]) -> str:
    ruta = "precios/"
    filas = []
    for k in productos:
        fl = [x for x in precios_de(datos, lambda p, k=k: p.get("clave") == k) if x[1].get("act") is not None]
        if fl:
            u = fl[0][1]["unidad"]
            vs = [p["act"] for _, p in fl if p["unidad"] == u]
            rango = num(min(vs)) if min(vs) == max(vs) else f"{num(min(vs))}–{num(max(vs))}"
            filas.append(f'<tr><td><a href="../precio/{k}/">{escape(PRODUCTOS[k][1])}</a></td><td class="n"><b>{rango}</b> <small>{escape(u)}</small></td><td class="n">{len(vs)}</td></tr>')
    h1 = "Precios agrarios de hoy en las lonjas de Castilla y León"
    frase = "Cereales, forrajes, porcino, ovino y vacuno en las lonjas de Salamanca, León, Segovia y Lerma, comparados semana a semana."
    migas = [("Inicio", ""), ("Precios", None)]
    cuerpo = (f'<p class="lead">{escape(frase)}</p>'
              '<div class="tabla"><table><thead><tr><th>Producto</th><th class="n">Rango entre lonjas</th><th class="n">Lonjas</th></tr></thead><tbody>'
              + "".join(filas) + "</tbody></table></div>"
              + "<h2>Por sector</h2><nav class='chips'>" + "".join(f'<a href="../precio/{k}/">{escape(SECTORES[k][1])}</a>' for k in sectores) + "</nav>"
              + "<h2>Por lonja</h2>" + enlaces_lonjas(datos, 1)
              + '<section class="cta"><h2>La app</h2><p>Pizarra de la semana, comparador, avisos de precio, calculadora de venta e histórico oficial. Funciona sin conexión y se instala en el móvil.</p><a class="boton" href="../">Abrir Lonjas CyL</a></section>')
    return pagina(ruta=ruta, nivel=1, titulo="Precios de las lonjas de Castilla y León hoy | Lonjas CyL", descripcion=frase,
                  h1=h1, cuerpo=cuerpo, migas=migas, ld=[ld_migas(migas, ruta)])


def pagina_plazos(plazos: dict, hoy: str) -> str | None:
    """Calendario de la PAC (data/plazos.json) con su cuenta atrás calculada el día en que se genera la página."""
    lista = [p for p in plazos.get("plazos", []) if p.get("inicio") and p.get("fin") and p.get("titulo")]
    if not lista:
        return None
    d = lambda a, b: (date.fromisoformat(a) - date.fromisoformat(b)).days

    def estado(p: dict) -> tuple[int, str]:
        if hoy < p["inicio"]:
            n = d(p["inicio"], hoy)
            return 1, "Empieza mañana" if n == 1 else f"Empieza en {n} días"
        if hoy <= p["fin"]:
            n = d(p["fin"], hoy)
            return 0, "Último día" if n == 0 else "Termina mañana" if n == 1 else f"En curso: quedan {n} días"
        return 2, "Terminado"

    orden = sorted(lista, key=lambda p: (estado(p)[0], p["fin"] if estado(p)[0] == 0 else p["inicio"]))
    anios = sorted({p["inicio"][:4] for p in lista} | {p["fin"][:4] for p in lista})
    rango_anios = anios[0] if len(anios) == 1 else f"{anios[0]}–{anios[-1]}"
    vivo = next((p for p in orden if estado(p)[0] < 2), None)
    if vivo:
        frase = f"{vivo['titulo']}: {estado(vivo)[1].lower()} ({fecha_larga(vivo['fin'] if estado(vivo)[0] == 0 else vivo['inicio'])})."
    else:
        frase = "Calendario de cobros y trámites de la PAC."
    filas = "".join(
        f'<tr><td><a href="#{escape(p["id"])}">{escape(p["titulo"])}</a>{"" if p.get("confirmado", True) else " <small>(fecha prevista)</small>"}</td>'
        f'<td>{fecha_corta(p["inicio"])} {p["inicio"][:4]} – {fecha_corta(p["fin"])} {p["fin"][:4]}</td><td>{escape(estado(p)[1])}</td></tr>' for p in orden)
    fichas = "".join(
        f'<h2 id="{escape(p["id"])}">{escape(p["titulo"])}</h2>'
        f'<p class="fecha">Del {fecha_larga(p["inicio"])} al {fecha_larga(p["fin"])}{"" if p.get("confirmado", True) else " · fecha prevista, pendiente de publicar"}.</p>'
        + (f'<p>{escape(p["detalle"])}</p>' if p.get("detalle") else "")
        + (f'<p class="nota">Fuente: <a href="{escape(p["fuente"])}" rel="nofollow">{escape(p.get("fuente_nombre") or "documento oficial")}</a></p>'
           if str(p.get("fuente", "")).startswith("https://") else "") for p in orden)
    ruta = "plazos/"
    h1 = f"Calendario de la PAC {rango_anios}: plazos y pagos"
    migas = [("Inicio", ""), ("Plazos de la PAC", None)]
    cuerpo = (f'<p class="lead">{escape(frase)}</p><p class="fecha">Cuenta atrás a {fecha_larga(hoy)}.</p>'
              '<div class="tabla"><table><thead><tr><th>Plazo</th><th>Fechas</th><th>Estado</th></tr></thead><tbody>' + filas + "</tbody></table></div>"
              + fichas
              + '<p class="nota">Fechas generales de la PAC en España. Las «previstas» son el plazo habitual y aún no se han publicado para ese año. '
                'Cada pago depende de la Junta de Castilla y León y de tu expediente: consulta tu caso con tu entidad colaboradora.</p>'
              + '<section class="cta"><h2>Cuenta atrás en el móvil</h2><p>La app muestra estos plazos en su pantalla de inicio, junto a los precios de las lonjas de Castilla y León.</p><a class="boton" href="../#plazos">Abrir Lonjas CyL</a></section>')
    return pagina(ruta=ruta, nivel=1, titulo=f"Calendario PAC {rango_anios}: anticipo, pago del saldo y Solicitud Única | Lonjas CyL",
                  descripcion=f"Fechas de cobro y trámites de la PAC {rango_anios} con cuenta atrás: anticipo, saldo, Solicitud Única. {frase}",
                  h1=h1, cuerpo=cuerpo, migas=migas, ld=[ld_migas(migas, ruta)])


def sitemap(rutas: list[tuple[str, str]]) -> str:
    urls = "".join(f"<url><loc>{WEB}{r}</loc><lastmod>{m}</lastmod></url>" for r, m in rutas)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'


def generar(datos: dict, raiz: Path = RAIZ, plazos: dict | None = None) -> list[str]:
    """Escribe todas las páginas. Devuelve las rutas generadas. Borra antes las carpetas generadas (nada más)."""
    for c in CARPETAS:
        shutil.rmtree(raiz / c, ignore_errors=True)
    hoy = (datos.get("generado") or datetime.now().isoformat())[:10]
    hechas: list[tuple[str, str]] = [("", hoy)]

    def escribir(ruta: str, html: str | None, mod: str) -> bool:
        if not html:
            return False
        destino = raiz / ruta / "index.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(html, encoding="utf-8")
        hechas.append((ruta, mod))
        return True

    productos = [k for k in PRODUCTOS if escribir(f"precio/{k}/", pagina_producto(datos, k), hoy)]
    sectores = [k for k in SECTORES if escribir(f"precio/{k}/", pagina_sector(datos, k), hoy)]
    for l in lonjas_activas(datos):
        escribir(f"lonja/{l['id']}/", pagina_lonja(datos, l), (l.get("fecha") or hoy))
    escribir("precios/", pagina_indice(datos, productos, sectores), hoy)
    if plazos is None and (raiz / "data" / "plazos.json").is_file():
        plazos = json.loads((raiz / "data" / "plazos.json").read_text(encoding="utf-8"))
    if plazos:
        escribir("plazos/", pagina_plazos(plazos, date.today().isoformat()), (plazos.get("actualizado") or hoy))
    (raiz / "sitemap.xml").write_text(sitemap(hechas), encoding="utf-8")
    return [r for r, _ in hechas]


if __name__ == "__main__":
    rutas = generar(json.loads(DATOS.read_text(encoding="utf-8")))
    print(f"[páginas] {len(rutas)} direcciones en sitemap.xml")
    sys.exit(0)

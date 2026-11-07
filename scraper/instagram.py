"""Instagram de Lonjas CyL: crea las imágenes con los precios reales y las publica en la cuenta por la API oficial.

  python scraper/instagram.py --preparar   crea las imágenes de lo pendiente en redes/instagram/ (antes de guardar)
  python scraper/instagram.py --publicar   publica lo preparado, cuando ya está en internet (después de guardar)
  python scraper/instagram.py --muestra    crea imágenes de muestra en redes/muestra/ sin publicar nada

Qué publica (nunca inventa: todo sale de data/precios.json):
  * Cada sesión nueva de una lonja: una imagen con sus precios principales y lo que suben o bajan.
  * Una vez por semana (viernes o sábado), un carrusel «¿Dónde se paga más esta semana?» con trigo, cebada,
    maíz y centeno en las lonjas que han cotizado en los últimos 7 días.
No publica sesiones de hace más de 3 días ni repite: guarda lo hecho en data/instagram.json.

Necesita el secreto INSTAGRAM_TOKEN (GitHub -> Settings -> Secrets and variables -> Actions). Sin él no hace nada.
Vale cualquiera de los dos tipos de la API de Instagram de Meta:
  * «inicio de sesión de Facebook» (EAA…): token de la página de Facebook vinculada a la cuenta (o de usuario con
    acceso a esa página). El de página sacado de un token de usuario largo no caduca.
  * «inicio de sesión de Instagram» (IG…): caduca a los 60 días; el robot lo renueva una vez por semana.
El token nunca se imprime. Lo que caduca o falla se anota en data/instagram.json y avisar.py abre un aviso.
  python scraper/instagram.py --comprobar  comprueba la conexión (cuenta y caducidad) sin publicar
Con token de Facebook publica lo mismo en la página de Facebook vinculada (permiso pages_manage_posts).
Para no hacerlo: variable PUBLICAR_FACEBOOK=no.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paginas import WEB, fecha_larga, num  # noqa: E402
from telegram import PRINCIPALES  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "precios.json"
ESTADO = RAIZ / "data" / "instagram.json"
CARPETA = RAIZ / "redes" / "instagram"
LETRAS = Path(__file__).resolve().parent / "letras"
ICONO = RAIZ / "icons" / "icono-512.png"
API = "https://graph.instagram.com"          # token de «inicio de sesión de Instagram» (empieza por IG)
API_FB = "https://graph.facebook.com"        # token de «inicio de sesión de Facebook» (página vinculada a Instagram)
REPO_RAW = "https://raw.githubusercontent.com/alvaro-glezz/lonjas-cyl/{sha}/"
DIAS_MAX = 3                       # no se publican sesiones más antiguas
COMPARA = ["trigo", "cebada", "maiz", "centeno"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
ETIQUETAS_BASE = ["#lonjas", "#CastillayLeón", "#preciosagrarios", "#agricultura", "#ganadería", "#campo"]

# Identidad de la app
PINO, PINO_OSC, FONDO, HOJA, TINTA, TENUE, LINEA = "#24503c", "#1b3d2e", "#eef1ea", "#ffffff", "#18241d", "#5b6a60", "#d6ddd2"
PAJA, SUBE, BAJA, CLARO = "#e0b252", "#23774a", "#b3402a", "#cfe0d4"
ANCHO, ALTO = 1080, 1350


# ---------- textos ----------

def corto(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {MESES_CORTOS[d.month - 1]}"


def nombre_corto(l: dict) -> str:
    return l.get("nombre", l["id"]).replace("Lonja de ", "")


def cambio(p: dict) -> float | None:
    if p.get("act") is None or p.get("ant") is None:
        return None
    return round(p["act"] - p["ant"], 5)


def principales(l: dict, n: int = 8) -> list[dict]:
    con = [p for p in l.get("precios", []) if p.get("act") is not None]
    prin = sorted((p for p in con if p.get("clave") in PRINCIPALES), key=lambda p: PRINCIPALES.index(p["clave"]))
    resto = sorted((p for p in con if p.get("clave") not in PRINCIPALES and p.get("ant") not in (None, 0) and p["act"] != p["ant"]),
                   key=lambda p: -abs((p["act"] - p["ant"]) / p["ant"]))
    return (prin + resto)[:n]


def balance(l: dict) -> tuple[int, int, int]:
    con = [p for p in l.get("precios", []) if p.get("act") is not None and p.get("ant") is not None]
    return (sum(p["act"] > p["ant"] for p in con), sum(p["act"] < p["ant"] for p in con), sum(p["act"] == p["ant"] for p in con))


def texto_cambio(p: dict) -> str:
    d = cambio(p)
    if d is None:
        return ""
    return "=" if d == 0 else ("▲ +" if d > 0 else "▼ −") + num(abs(d))


def etiquetas(*extra: str) -> str:
    vistos, out = set(), []
    for e in list(extra) + ETIQUETAS_BASE:
        if e and e.lower() not in vistos:
            vistos.add(e.lower())
            out.append(e)
    return " ".join(out[:12])


def pie_texto(web: str) -> str:
    return (f"📍 Todos los precios y la comparativa entre lonjas, en el enlace de la bio ({web.split('//')[1].rstrip('/')}).\n"
            "Avisos gratis en Telegram: t.me/lonjas_cyl")


def texto_sesion(l: dict, web: str = WEB) -> str:
    f = l["fecha"]
    lineas = [f"📊 {l.get('nombre', l['id'])} · sesión del {DIAS[date.fromisoformat(f).weekday()]} {corto(f)}", ""]
    lineas += [f"{p['producto']}: {num(p['act'])} {p.get('unidad', '')} {texto_cambio(p)}".rstrip() for p in principales(l)]
    s, b, i = balance(l)
    sector = {"leon": "#León", "salamanca": "#Salamanca", "segovia": "#Segovia", "lerma": "#Burgos"}.get(l["id"], "")
    lineas += ["", f"▲ {s} suben · ▼ {b} bajan · = {i} repiten", "", pie_texto(web),
               f"Fuente: {l.get('nota') or l.get('nombre')}. Precios orientativos: confírmalos con tu lonja o comprador.", "",
               etiquetas(sector, "#cereales", "#lonja" + nombre_corto(l).replace(" ", ""))]
    return "\n".join(lineas)[:2150]


def comparativas(datos: dict, hoy: date) -> list[dict]:
    """Por producto: lonjas con sesión en los últimos 7 días, de mayor a menor precio (misma unidad)."""
    desde = (hoy - timedelta(days=7)).isoformat()
    out = []
    for clave in COMPARA:
        filas = [(l, p) for l in datos.get("lonjas", []) if l.get("estado") != "suspendida" and (l.get("fecha") or "") >= desde
                 for p in l.get("precios", []) if p.get("clave") == clave and p.get("act") is not None]
        if len(filas) < 2:
            continue
        unidad = max({p["unidad"] for _, p in filas}, key=lambda u: sum(p["unidad"] == u for _, p in filas))
        filas = sorted(((l, p) for l, p in filas if p["unidad"] == unidad), key=lambda x: -x[1]["act"])
        if len(filas) >= 2:
            out.append({"clave": clave, "unidad": unidad, "filas": filas})
    return out


def texto_comparativa(comps: list[dict], web: str = WEB) -> str:
    nombres = {"trigo": "Trigo", "cebada": "Cebada", "maiz": "Maíz", "centeno": "Centeno"}
    lineas = ["🌾 ¿Dónde se paga más esta semana?", ""]
    for c in comps:
        f = c["filas"]
        lineas.append(f"{nombres[c['clave']]} ({c['unidad']}): " + " · ".join(f"{nombre_corto(l)} {num(p['act'])}" for l, p in f)
                      + f" → {num(f[0][1]['act'] - f[-1][1]['act'])} de diferencia")
    lineas += ["", "Cada lonja cotiza su propia calidad: mira también la descripción del producto en la app.", "",
               pie_texto(web), "Precios orientativos de las últimas sesiones de cada lonja.", "",
               etiquetas("#trigo", "#cebada", "#cereales", "#comparativa")]
    return "\n".join(lineas)[:2150]


# ---------- imágenes ----------

def _letra(nombre: str, tam: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(LETRAS / f"{nombre}.ttf"), tam)


def _cifra(t):
    return _letra("barlow-condensed-latin-700-normal", t)


def _texto(t, peso=400):
    return _letra(f"public-sans-latin-{peso}-normal", t)


def _cabecera(img, d, titulo: str, sub: str, alto: int = 320):
    from PIL import Image
    d.rectangle([0, 0, ANCHO, alto], fill=PINO)
    ico = Image.open(ICONO).convert("RGB").resize((64, 64))
    img.paste(ico, (70, 58))
    d.text((150, 60), "Lonjas CyL", font=_cifra(54), fill=HOJA)
    tam = 92
    while tam > 60 and d.textlength(titulo, font=_cifra(tam)) > ANCHO - 140:
        tam -= 4
    d.text((70, 140), titulo, font=_cifra(tam), fill=HOJA)
    d.text((72, 262), _ajustar(d, sub, _texto(32), ANCHO - 140), font=_texto(32), fill=CLARO)


def _ajustar(d, texto: str, letra, ancho: int) -> str:
    if d.textlength(texto, font=letra) <= ancho:
        return texto
    while texto and d.textlength(texto + "…", font=letra) > ancho:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _flecha(d, x: int, y: int, sube: bool, color: str, t: int = 18):
    pts = [(x, y + t), (x + t, y + t), (x + t / 2, y)] if sube else [(x, y), (x + t, y), (x + t / 2, y + t)]
    d.polygon(pts, fill=color)


def _pie(d, fuente: str, web: str):
    d.line([70, ALTO - 150, ANCHO - 70, ALTO - 150], fill=LINEA, width=2)
    d.text((70, ALTO - 128), _ajustar(d, f"Precios orientativos · Fuente: {fuente}", _texto(26), ANCHO - 140), font=_texto(26), fill=TENUE)
    d.text((70, ALTO - 84), web.split("//")[1].rstrip("/"), font=_cifra(44), fill=PINO)
    d.text((ANCHO - 70, ALTO - 78), "Avisos en Telegram: t.me/lonjas_cyl", font=_texto(26, 600), fill=PINO, anchor="ra")


def imagen_sesion(l: dict, destino: Path, web: str = WEB) -> Path:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    f = l["fecha"]
    _cabecera(img, d, l.get("nombre", l["id"]), f"Sesión del {DIAS[date.fromisoformat(f).weekday()]} {fecha_larga(f)}")
    filas = principales(l)
    y, alto_fila = 360, 90
    d.rounded_rectangle([50, y - 10, ANCHO - 50, y + alto_fila * len(filas) + 10], radius=28, fill=HOJA)
    for i, p in enumerate(filas):
        yy = y + i * alto_fila
        if i:
            d.line([80, yy, ANCHO - 80, yy], fill=LINEA, width=2)
        d.text((80, yy + alto_fila / 2), _ajustar(d, p["producto"], _texto(34, 600), 400), font=_texto(34, 600), fill=TINTA, anchor="lm")
        precio = num(p["act"])
        d.text((700, yy + alto_fila / 2 + 4), precio, font=_cifra(66), fill=TINTA, anchor="rm")
        d.text((710, yy + alto_fila / 2 + 10), _ajustar(d, p.get("unidad", ""), _texto(22), 130), font=_texto(22), fill=TENUE, anchor="lm")
        dc = cambio(p)
        if dc is not None:
            color = SUBE if dc > 0 else BAJA if dc < 0 else TENUE
            if dc == 0:
                d.text((ANCHO - 80, yy + alto_fila / 2), "=", font=_texto(34, 700), fill=color, anchor="rm")
            else:
                t = num(abs(dc))
                w = d.textlength(t, font=_texto(30, 700))
                d.text((ANCHO - 80, yy + alto_fila / 2), t, font=_texto(30, 700), fill=color, anchor="rm")
                _flecha(d, int(ANCHO - 80 - w - 28), int(yy + alto_fila / 2 - 9), dc > 0, color)
    s, b, i = balance(l)
    yb = y + alto_fila * len(filas) + 44
    d.text((70, yb), f"{s} suben · {b} bajan · {i} repiten", font=_texto(32, 600), fill=TINTA)
    _pie(d, l.get("nota") or l.get("nombre", ""), web)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=90, optimize=True)
    return destino


def imagen_comparativa(c: dict, destino: Path, web: str = WEB) -> Path:
    from PIL import Image, ImageDraw
    nombres = {"trigo": "Trigo", "cebada": "Cebada", "maiz": "Maíz", "centeno": "Centeno"}
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    fechas = sorted(l["fecha"] for l, _ in c["filas"])
    _cabecera(img, d, f"{nombres[c['clave']]}: ¿dónde se paga más?", f"Últimas sesiones, del {corto(fechas[0])} al {corto(fechas[-1])} · {c['unidad']}")
    y, alto_fila = 370, 150
    for i, (l, p) in enumerate(c["filas"][:5]):
        yy = y + i * (alto_fila + 18)
        primero = i == 0
        d.rounded_rectangle([50, yy, ANCHO - 50, yy + alto_fila], radius=28, fill=PAJA if primero else HOJA)
        d.text((95, yy + alto_fila / 2), str(i + 1), font=_cifra(70), fill=TINTA if primero else TENUE, anchor="lm")
        d.text((180, yy + 48), nombre_corto(l), font=_texto(40, 700), fill=TINTA, anchor="lm")
        d.text((180, yy + 102), _ajustar(d, f"{p['producto']} · {corto(l['fecha'])}", _texto(26), 520), font=_texto(26), fill=TINTA if primero else TENUE, anchor="lm")
        d.text((ANCHO - 90, yy + alto_fila / 2 + 4), num(p["act"]), font=_cifra(92), fill=TINTA, anchor="rm")
    dif = c["filas"][0][1]["act"] - c["filas"][-1][1]["act"]
    yb = y + min(len(c["filas"]), 5) * (alto_fila + 18) + 20
    d.text((70, yb), f"Diferencia: {num(dif)} {c['unidad']}", font=_cifra(60), fill=PINO)
    d.text((70, yb + 78), "Cada lonja cotiza su propia calidad.", font=_texto(28), fill=TENUE)
    _pie(d, ", ".join(sorted({l.get('nombre', '') for l, _ in c['filas']})).replace("Lonja de ", ""), web)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=90, optimize=True)
    return destino


# ---------- qué toca publicar ----------

def pendientes(datos: dict, estado: dict, hoy: date) -> list[dict]:
    """Publicaciones que tocan: sesiones nuevas y, viernes o sábado, la comparativa de la semana (una vez)."""
    pub = estado.get("publicado", {})
    limite = (hoy - timedelta(days=DIAS_MAX)).isoformat()
    out = []
    for l in sorted(datos.get("lonjas", []), key=lambda l: l.get("fecha") or ""):
        f = l.get("fecha")
        if l.get("estado") == "suspendida" or not f or f < limite or f <= pub.get(l["id"], "") or not principales(l):
            continue
        out.append({"tipo": "sesion", "id": f"{f}-{l['id']}", "lonja": l["id"], "fecha": f,
                    "texto": texto_sesion(l), "imagenes": [f"redes/instagram/{f}-{l['id']}.jpg"]})
    semana = f"{hoy.isocalendar()[0]}-W{hoy.isocalendar()[1]:02d}"
    comps = comparativas(datos, hoy)
    if hoy.weekday() in (4, 5) and estado.get("comparativa") != semana and comps:
        out.append({"tipo": "comparativa", "id": f"{semana}-comparativa", "semana": semana, "texto": texto_comparativa(comps),
                    "imagenes": [f"redes/instagram/{semana}-{c['clave']}.jpg" for c in comps]})
    return out


def preparar(datos: dict, estado: dict, hoy: date, raiz: Path = RAIZ) -> list[dict]:
    """Crea las imágenes de lo pendiente y lo anota en estado['preparado']. No llama a Instagram."""
    lista = pendientes(datos, estado, hoy)
    lonjas = {l["id"]: l for l in datos.get("lonjas", [])}
    comps = {c["clave"]: c for c in comparativas(datos, hoy)}
    for item in lista:
        if item["tipo"] == "sesion":
            imagen_sesion(lonjas[item["lonja"]], raiz / item["imagenes"][0])
        else:
            for ruta in item["imagenes"]:
                imagen_comparativa(comps[ruta.rsplit("-", 1)[1][:-4]], raiz / ruta)
    estado["preparado"] = lista
    return lista


# ---------- Instagram ----------

class ErrorInstagram(RuntimeError):
    pass


def llamar(metodo: str, ruta: str, token: str, **params) -> dict:
    import requests
    params["access_token"] = token
    url = ruta if ruta.startswith("https://") else f"{API}/{ruta}"
    r = (requests.post if metodo == "POST" else requests.get)(url, data=params if metodo == "POST" else None,
                                                             params=None if metodo == "POST" else params, timeout=60)
    try:
        j = r.json()
    except ValueError:
        j = {}
    if r.status_code >= 400 or "error" in j:
        e = j.get("error") or {}
        # Nunca se imprime el token: solo la ruta y el mensaje de error de Instagram
        raise ErrorInstagram(f"Instagram {ruta.split('?')[0].rsplit('/', 1)[-1]}: {e.get('message') or r.status_code} (código {e.get('code')})")
    return j


def esperar_contenedor(cid: str, token: str, llamar=llamar, espera=time.sleep, ig: str = "me") -> None:
    base = ig.rsplit("/", 1)[0] + "/" if ig.startswith("https://") else ""
    for _ in range(30):
        st = llamar("GET", base + cid, token, fields="status_code").get("status_code")
        if st in (None, "FINISHED"):
            return
        if st in ("ERROR", "EXPIRED"):
            raise ErrorInstagram(f"Instagram no pudo procesar la imagen ({st})")
        espera(4)
    raise ErrorInstagram("Instagram tardó demasiado en procesar la imagen")


def cuenta(token: str, llamar=llamar) -> tuple[str, str, str]:
    """(dirección de la cuenta en la API, token con el que publicar, tipo).

    * Token de «inicio de sesión de Instagram» (empieza por «IG»): graph.instagram.com/me.
    * Token de «inicio de sesión de Facebook» (empieza por «EAA»): de página o de usuario. Se busca la página
      que tiene vinculada la cuenta de Instagram y se publica con el token de esa página."""
    if token.startswith("IG"):
        return f"{API}/me", token, "instagram"
    yo = llamar("GET", f"{API_FB}/me", token, fields="id,instagram_business_account")
    if yo.get("instagram_business_account"):
        return f"{API_FB}/{yo['instagram_business_account']['id']}", token, "pagina"
    for pag in llamar("GET", f"{API_FB}/me/accounts", token, fields="access_token,instagram_business_account").get("data", []):
        if pag.get("instagram_business_account") and pag.get("access_token"):
            return f"{API_FB}/{pag['instagram_business_account']['id']}", pag["access_token"], "usuario"
    raise ErrorInstagram("Ninguna página de Facebook de este token tiene una cuenta de Instagram vinculada")


def publicar_item(item: dict, base_url: str, token: str, llamar=llamar, espera=time.sleep, ig: str = "me") -> str:
    urls = [base_url + r for r in item["imagenes"]]
    media, publicar_ = f"{ig}/media", f"{ig}/media_publish"
    if len(urls) == 1:
        cid = llamar("POST", media, token, image_url=urls[0], caption=item["texto"])["id"]
    else:
        hijos = [llamar("POST", media, token, image_url=u, is_carousel_item="true")["id"] for u in urls[:10]]
        for h in hijos:
            esperar_contenedor(h, token, llamar, espera, ig)
        cid = llamar("POST", media, token, media_type="CAROUSEL", children=",".join(hijos), caption=item["texto"])["id"]
    esperar_contenedor(cid, token, llamar, espera, ig)
    return llamar("POST", publicar_, token, creation_id=cid)["id"]


def en_internet(url: str, intentos: int = 30, espera=time.sleep) -> bool:
    import requests
    for _ in range(intentos):
        try:
            r = requests.head(url, timeout=15, allow_redirects=True)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                return True
        except requests.RequestException:
            pass
        espera(10)
    return False


def renovar_token(estado: dict, token: str, hoy: date, llamar=llamar) -> None:
    """Una vez por semana alarga la vida del token (60 días) y anota cuándo caduca."""
    if estado.get("token_renovado") and (hoy - date.fromisoformat(estado["token_renovado"])).days < 7:
        return
    r = llamar("GET", "refresh_access_token", token, grant_type="ig_refresh_token")
    estado["token_renovado"] = hoy.isoformat()
    if r.get("expires_in"):
        estado["token_caduca"] = (hoy + timedelta(seconds=int(r["expires_in"]))).isoformat()
    if r.get("access_token") and r["access_token"] != token:
        estado["token_cambiado"] = hoy.isoformat()   # habría que guardar el token nuevo en GitHub: lo avisa avisar.py


def caducidad_fb(estado: dict, token: str, hoy: date, llamar=llamar) -> None:
    """Token de Facebook: anota cuándo caduca (0 = no caduca, como el de página sacado de un token largo)."""
    if estado.get("token_renovado") == hoy.isoformat():
        return
    d = llamar("GET", f"{API_FB}/debug_token", token, input_token=token).get("data", {})
    estado["token_renovado"] = hoy.isoformat()
    fin = d.get("expires_at") or 0
    if fin:
        estado["token_caduca"] = datetime.fromtimestamp(int(fin)).date().isoformat()
    else:
        estado.pop("token_caduca", None)


def pagina_fb(token: str, llamar=llamar) -> tuple[str, str] | None:
    """(id de la página de Facebook, token de la página) si el token es de Facebook; None si es de Instagram."""
    if token.startswith("IG"):
        return None
    yo = llamar("GET", f"{API_FB}/me", token, fields="id,instagram_business_account")
    if yo.get("instagram_business_account"):
        return yo["id"], token
    for pag in llamar("GET", f"{API_FB}/me/accounts", token, fields="id,access_token,instagram_business_account").get("data", []):
        if pag.get("instagram_business_account") and pag.get("access_token"):
            return pag["id"], pag["access_token"]
    return None


def publicar_facebook(item: dict, base_url: str, pagina: str, token: str, llamar=llamar) -> str:
    """La misma publicación en la página de Facebook: una foto, o varias fotos en una sola entrada."""
    urls = [base_url + r for r in item["imagenes"]]
    if len(urls) == 1:
        r = llamar("POST", f"{API_FB}/{pagina}/photos", token, url=urls[0], message=item["texto"])
        return r.get("post_id") or r["id"]
    fotos = [llamar("POST", f"{API_FB}/{pagina}/photos", token, url=u, published="false")["id"] for u in urls[:10]]
    extra = {f"attached_media[{i}]": json.dumps({"media_fbid": f}) for i, f in enumerate(fotos)}
    return llamar("POST", f"{API_FB}/{pagina}/feed", token, message=item["texto"], **extra)["id"]


def publicar(estado: dict, token: str, base_url: str, hoy: date, llamar=llamar, espera=time.sleep, ig: str = "me",
             fb: tuple[str, str] | None = None) -> list[str]:
    """Publica en Instagram y, si hay página de Facebook, también allí. Un fallo de Facebook no frena Instagram:
    se anota en estado['error_facebook'] (avisar.py lo avisa)."""
    hechas = []
    for item in list(estado.get("preparado", [])):
        mid = publicar_item(item, base_url, token, llamar, espera, ig)
        if item["tipo"] == "sesion":
            estado.setdefault("publicado", {})[item["lonja"]] = item["fecha"]
        else:
            estado["comparativa"] = item["semana"]
        fid = None
        if fb:
            try:
                fid = publicar_facebook(item, base_url, fb[0], fb[1], llamar)
                estado.pop("error_facebook", None)
            except ErrorInstagram as e:
                estado["error_facebook"] = {"fecha": hoy.isoformat(), "detalle": str(e).replace("Instagram ", "Facebook ", 1)}
        estado.setdefault("registro", []).append({"fecha": datetime.now().isoformat(timespec="minutes"), "id": item["id"], "media": mid,
                                                  **({"facebook": fid} if fid else {})})
        estado["registro"] = estado["registro"][-60:]
        estado["preparado"].remove(item)
        hechas.append(item["id"])
    return hechas


def guardar(estado: dict) -> None:
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    hoy = date.today()
    if "--muestra" in argv:
        dest = RAIZ / "redes" / "muestra"
        for l in datos["lonjas"]:
            if l.get("fecha") and principales(l):
                imagen_sesion(l, dest / f"sesion-{l['id']}.jpg")
        for c in comparativas(datos, hoy):
            imagen_comparativa(c, dest / f"comparativa-{c['clave']}.jpg")
        print(f"[instagram] Muestras en {dest}")
        return 0
    token = os.environ.get("INSTAGRAM_TOKEN", "").strip()
    if not token:
        print("[instagram] Sin configurar (falta el secreto INSTAGRAM_TOKEN): no se prepara ni se publica nada.")
        return 0
    estado = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.is_file() else {}
    if "--comprobar" in argv:      # prueba la conexión sin publicar nada
        ig, tk, tipo = cuenta(token)
        info = llamar("GET", ig, tk, fields="username,followers_count,media_count")
        print(f"[instagram] Conectado a @{info.get('username')} (token de {tipo}) · {info.get('media_count')} publicaciones")
        try:
            caducidad_fb(estado, token, hoy) if tipo != "instagram" else renovar_token(estado, token, hoy)
            print(f"[instagram] El token caduca: {estado.get('token_caduca') or 'no caduca'}")
        except ErrorInstagram as e:
            print(f"[instagram] No se pudo saber cuándo caduca el token: {e}")
        return 0
    try:
        if "--preparar" in argv:
            lista = preparar(datos, estado, hoy)
            print(f"[instagram] Preparadas: {', '.join(i['id'] for i in lista) or 'nada nuevo'}")
        elif "--publicar" in argv:
            if not estado.get("preparado"):
                print("[instagram] Nada que publicar.")
            else:
                sha = os.environ.get("GITHUB_SHA_GUARDADO", "").strip()
                primera = estado["preparado"][0]["imagenes"][0]
                base = WEB if en_internet(WEB + primera, intentos=24) else (REPO_RAW.format(sha=sha) if sha else None)
                if not base or not en_internet(base + primera, intentos=6):
                    print("[instagram] Las imágenes aún no están en internet: se publicarán en la próxima pasada.")
                else:
                    ig, tk, tipo = cuenta(token)
                    fb = pagina_fb(token) if os.environ.get("PUBLICAR_FACEBOOK", "si") != "no" else None
                    try:
                        hechas = publicar(estado, tk, base, hoy, ig=ig, fb=fb)
                        estado.pop("error", None)
                    except ErrorInstagram as e:
                        estado["error"] = {"fecha": hoy.isoformat(), "detalle": str(e)}
                        raise
                    print(f"[instagram] Publicadas: {', '.join(hechas)}" + (" (también en Facebook)" if fb and "error_facebook" not in estado else ""))
                    if estado.get("error_facebook"):
                        print(f"[facebook] No se pudo publicar: {estado['error_facebook']['detalle']}")
            if token.startswith("IG"):
                renovar_token(estado, token, hoy)
            else:
                caducidad_fb(estado, token, hoy)
            if estado.get("token_caduca"):
                print(f"[instagram] El token caduca el {estado['token_caduca']}")
    finally:
        guardar(estado)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

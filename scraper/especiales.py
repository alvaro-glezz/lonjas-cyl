"""Reels especiales (se publican a mano, en una fecha concreta): cómo instalar la app y explicación de funciones.

Usan el mismo dibujo, voz, música, subtítulos y cierre que los reels con historia (historias.py). Las pantallas de la
app son capturas reales (scraper/recursos/app-*.png, tomadas el 8 nov 2026 con los datos de ese día). Los menús de
Safari y Chrome están dibujados de forma sencilla, sin logotipos.

  python scraper/especiales.py instalar|explotacion [carpeta]    crea el reel sin publicar
  python scraper/especiales.py instalar --fotogramas             fotogramas de muestra
Se publican con la tarea «Redes sociales» y la franja «especial:<nombre>» (ver redes.py).
"""
from __future__ import annotations

import math
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import historias as h  # noqa: E402
from historias import H, W, Lapiz, _base, _img, _reducir, bocadillo, movil, pegar, persona, rebote, silo, suave, tractor  # noqa: E402
from instagram import CLARO, HOJA, ICONO, PAJA, PINO, TENUE, TINTA, _cifra, _texto, etiquetas  # noqa: E402
from paginas import WEB  # noqa: E402

RECURSOS = Path(__file__).resolve().parent / "recursos"
PW, PH = 420, 760                     # pantalla del móvil dibujado (historias.movil)
URL = WEB.split("//")[1].rstrip("/")


@lru_cache(maxsize=None)
def captura(nombre: str, desde: int = 0):
    """Captura real de la app ajustada a la pantalla del móvil (desde = píxeles de desplazamiento hacia abajo)."""
    from PIL import Image
    im = Image.open(RECURSOS / f"app-{nombre}.png").convert("RGB")
    k = im.width / PW
    alto = int(PH * k)
    y = min(int(desde * k), max(0, im.height - alto))
    return im.crop((0, y, im.width, y + alto)).resize((PW, PH), Image.LANCZOS)


def _velo(im, color: tuple):
    """Capa semitransparente encima (ImageDraw sustituiría los píxeles en vez de mezclarlos)."""
    from PIL import Image
    im.alpha_composite(Image.new("RGBA", im.size, color))


_SOLO_ARO = False                     # en las guías en foto, el toque es solo un aro para que se lea lo de debajo


def _toque(p, x, y, t):
    """Círculo que late donde hay que tocar."""
    if _SOLO_ARO:
        p.circulo(x, y, 40, None, outline=(214, 64, 40, 255), width=6)
        return
    r = 30 + 8 * math.sin(t * 7)
    p.circulo(x, y, r + 14, (233, 196, 106, 90))
    p.circulo(x, y, r, (233, 196, 106, 200), outline=TINTA, width=3)


def _icono_compartir(p, x, y, color):
    p.rect([x - 14, y - 6, x + 14, y + 22], None, r=4, outline=color, width=3)
    p.linea([(x, y - 22), (x, y + 8)], color, 3)
    p.linea([(x - 9, y - 13), (x, y - 22), (x + 9, y - 13)], color, 3)


def pantalla_safari(t: float, paso: str):
    """Navegador del iPhone con la app cargada. paso: 'compartir' (barra) u 'hoja' (menú de compartir)."""
    im = _img(PW, PH)
    im.paste(captura("hoy").resize((PW * h.SS, PH * h.SS)), (0, 0))
    p = Lapiz(im)
    p.rect([0, PH - 128, PW, PH], "#f4f4f6")
    p.rect([16, PH - 118, PW - 16, PH - 70], "#ffffff", r=14)
    p.texto((PW / 2, PH - 94), URL, _texto(19, 600), TINTA, anchor="mm")
    ys = PH - 36
    for i, x in enumerate((50, 125, 210, 295, 370)):
        if i == 2:
            _icono_compartir(p, x, ys, "#2f6fdf")
        elif i == 4:
            for k in (-9, 0, 9):
                p.circulo(x + k, ys, 3.5, "#2f6fdf")
        else:
            p.circulo(x, ys, 5, "#9aa5b1")
    if paso == "compartir":
        _toque(p, 210, ys, t)
    else:
        a = suave(t / .35)
        _velo(im, (0, 0, 0, int(110 * a)))
        y0 = PH - 470 * a
        p.rect([0, y0, PW, PH + 30], "#f2f2f7", r=26)
        p.texto((PW / 2, y0 + 36), "Lonjas CyL", _texto(22, 700), TINTA, anchor="mm")
        opciones = ["Copiar", "Añadir a la lista de lectura", "Añadir a favoritos", "Añadir a pantalla de inicio", "Buscar en la página"]
        for k, o in enumerate(opciones):
            yy = y0 + 80 + k * 62
            dest = k == 3
            p.rect([16, yy, PW - 16, yy + 54], PAJA if dest and t > 1.0 else "#ffffff", r=12)
            p.texto((36, yy + 27), o, _texto(19, 700 if dest else 400), TINTA, anchor="lm")
            if dest:
                p.rect([PW - 62, yy + 12, PW - 32, yy + 42], None, r=6, outline=TINTA, width=2)
                p.linea([(PW - 47, yy + 18), (PW - 47, yy + 36)], TINTA, 2)
                p.linea([(PW - 56, yy + 27), (PW - 38, yy + 27)], TINTA, 2)
                if t > 1.0:
                    _toque(p, PW - 47, yy + 27, t)
        if t > 2.6:                     # ventana final: «Añadir»
            b = suave((t - 2.6) / .3)
            _velo(im, (255, 255, 255, int(235 * b)))
            p.texto((30, 70), "Cancelar", _texto(21, 400), "#2f6fdf", anchor="lm")
            p.texto((PW - 30, 70), "Añadir", _texto(21, 700), "#2f6fdf", anchor="rm")
            from PIL import Image
            ico = Image.open(ICONO).convert("RGB").resize((88 * h.SS, 88 * h.SS))
            im.paste(ico, (40 * h.SS, 130 * h.SS))
            p.texto((150, 160), "Lonjas CyL", _texto(24, 700), TINTA, anchor="lm")
            p.texto((150, 196), URL, _texto(16, 400), TENUE, anchor="lm")
            _toque(p, PW - 62, 70, t)
    return _reducir(im)


def pantalla_chrome(t: float):
    """Navegador de Android: barra arriba con «⋮» y su menú con «Instalar aplicación»."""
    im = _img(PW, PH)
    im.paste(captura("hoy", 0).resize((PW * h.SS, (PH - 70) * h.SS)), (0, 70 * h.SS))
    p = Lapiz(im)
    p.rect([0, 0, PW, 70], "#ffffff")
    p.rect([14, 12, PW - 60, 58], "#eef0f3", r=23)
    p.texto((34, 35), URL, _texto(18, 600), TINTA, anchor="lm")
    for k in (-10, 0, 10):
        p.circulo(PW - 30, 35 + k, 3.5, TINTA)
    if t < 1.1:
        _toque(p, PW - 30, 35, t)
    else:
        a = suave((t - 1.1) / .3)
        x0 = PW - 300
        p.rect([x0, 60, PW - 10, 60 + 380 * a], "#ffffff", r=14, outline="#d7dbe0", width=1)
        if a > .9:
            opciones = ["Nueva pestaña", "Historial", "Descargas", "Marcadores", "Instalar aplicación", "Compartir…"]
            for k, o in enumerate(opciones):
                yy = 76 + k * 60
                dest = k == 4
                if dest:
                    p.rect([x0 + 8, yy - 6, PW - 18, yy + 46], PAJA, r=10)
                p.texto((x0 + 24, yy + 20), o, _texto(19, 700 if dest else 400), TINTA, anchor="lm")
            _toque(p, x0 + 200, 76 + 4 * 60 + 20, t)
    return _reducir(im)


def pantalla_inicio(t: float):
    """Pantalla de inicio con iconos genéricos; aparece el de Lonjas CyL, se toca y se abre la app."""
    from PIL import Image
    if t > 4.2:
        return captura("hoy")
    im = Image.new("RGB", (PW * h.SS, PH * h.SS), "#7fa7b9")
    p = Lapiz(im)
    colores = ["#e8a33d", "#5aa469", "#d9534f", "#4f7fb5", "#8e6bbf", "#f0c419", "#3cb2a6", "#c46b9e", "#6b8e23",
               "#e07a2e", "#5b6a75", "#2f9fd0", "#b85c38", "#7a9e3f", "#c94f6d"]
    k = 0
    for fila in range(5):
        for col in range(4):
            x, y = 34 + col * 96, 80 + fila * 120
            if (fila, col) == (2, 1):
                a = rebote(t / .6)
                if a > 0:
                    s = int(72 * a)
                    ico = Image.open(ICONO).convert("RGB").resize((s * h.SS, s * h.SS))
                    im.paste(ico, (int((x + 36 - s / 2) * h.SS), int((y + 36 - s / 2) * h.SS)))
                    p.texto((x + 36, y + 92), "Lonjas CyL", _texto(15, 700), HOJA, anchor="mm")
                    if t > 2.6:
                        _toque(p, x + 36, y + 36, t)
                continue
            p.rect([x, y, x + 72, y + 72], colores[k % len(colores)], r=18)
            k += 1
    return _reducir(im)


def _chip(texto: str):
    from PIL import Image, ImageDraw
    f = _cifra(54)
    ancho = int(ImageDraw.Draw(Image.new("RGB", (5, 5))).textlength(texto, font=f)) + 60
    im = Image.new("RGBA", (ancho, 84), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, ancho - 1, 83], radius=42, fill=TINTA)
    d.text((ancho / 2, 42), texto, font=f, fill=HOJA, anchor="mm")
    return im


def _movil_grande(img, pantalla, t, x=W / 2, abajo=1820, escala=1.25):
    a = rebote(t / .5)
    pegar(img, movil(pantalla), x, abajo + 80 * (1 - a), escala * (.85 + .15 * a), min(1, a * 1.4))


def escenas_instalar(datos=None, hoy=None):
    def e1(t, d):
        img = _base("campo", t)
        pegar(img, persona("ana", "movil", "contento"), 270, 1700)
        _movil_grande(img, captura("hoy"), t, 760, 1780, 1.0)
        return img

    def e2(t, d):
        img = _base("campo", t)
        _movil_grande(img, pantalla_safari(t, "compartir"), t)
        pegar(img, _chip("iPhone · Safari"), W / 2, 722)
        return img

    def e3(t, d):
        img = _base("campo", t)
        _movil_grande(img, pantalla_safari(t, "hoja"), 1.0)
        pegar(img, _chip("iPhone · Safari"), W / 2, 722)
        return img

    def e4(t, d):
        img = _base("campo", t)
        _movil_grande(img, pantalla_chrome(t), t)
        pegar(img, _chip("Android · Chrome"), W / 2, 722)
        return img

    def e5(t, d):
        img = _base("campo", t)
        _movil_grande(img, pantalla_inicio(t), 1.0)
        if t > 4.2:
            pegar(img, persona("julian", "brazos", "contento"), 170, 1900, .7)
        return img

    return [
        ("¿Quieres Lonjas Castilla y León en el móvil, como una aplicación más? Se instala en treinta segundos, sin pasar por la tienda.",
         "Instálala *en 30 segundos*", e1, 4.0),
        ("En iPhone, abre la web en Safari y toca el botón de compartir. Si no lo ves, está dentro de los tres puntos.",
         "iPhone: toca *Compartir*", e2, 4.0),
        ("Elige «Añadir a pantalla de inicio» y pulsa «Añadir».", "*Añadir a pantalla de inicio*", e3, 4.2),
        ("En Android, ábrela en Chrome, toca los tres puntos de arriba y elige «Instalar aplicación».",
         "Android: *Instalar aplicación*", e4, 4.2),
        ("Y listo: el icono aparece con tus aplicaciones. Se actualiza sola y funciona aunque no haya cobertura.",
         "Ya la tienes *como una app más*", e5, 4.2),
    ]


def escenas_explotacion(datos=None, hoy=None):
    def e1(t, d):
        img = _base("campo", t)
        pegar(img, silo(), 820, 1640, .95)
        pegar(img, persona("pedro", "pensar", "duda"), 330, 1700)
        if t > .8:
            pegar(img, bocadillo("¿Cuánto vale todo esto?", 520, "izq", 48), 470, 1000, rebote((t - .8) / .4))
        return img

    def e2(t, d):
        img = _base("campo", t)
        desde = 120 + 120 * suave((t - 1.2) / 2.0)
        _movil_grande(img, captura("explotacion", int(desde)), t)
        return img

    @lru_cache(maxsize=None)
    def tarjeta():
        im = captura("explotacion")
        # la tarjeta «Vale esta semana» está arriba, bajo la cabecera de la sección
        from PIL import Image
        caja = im.crop((6, 248, PW - 6, 362))
        return caja.resize((caja.width * 2, caja.height * 2), Image.LANCZOS).convert("RGBA")

    def e3(t, d):
        img = _base("campo", t)
        _movil_grande(img, captura("explotacion", 120), 1.0, abajo=1900, escala=1.1)
        a = rebote(t / .5)
        pegar(img, tarjeta(), W / 2, 1120, .95 * a, min(1, a))
        return img

    def e4(t, d):
        img = _base("tarde", t)
        pegar(img, silo(), 820, 1640, .95)
        pegar(img, persona("pedro", "brazos", "contento"), 330, 1700 - abs(12 * math.sin(t * 6)))
        if t > .6:
            pegar(img, bocadillo("¡Ahora decido con números!", 560, "izq", 46), 480, 1000, rebote((t - .6) / .4))
        return img

    return [
        ("Tienes el silo lleno y corderos en la nave. ¿Sabes cuánto vale todo eso esta semana?",
         "¿Cuánto vale *tu cosecha*?", e1, 4.0),
        ("En «Mi explotación» apuntas lo que tienes: toneladas de trigo, de cebada, kilos de cordero…",
         "Apúntalo en *Mi explotación*", e2, 4.4),
        ("La app lo valora con los precios de las lonjas de esta semana, y te dice cuánto ha cambiado desde la sesión anterior.",
         "Lo que vale *esta semana*", e3, 4.6),
        ("Se guarda solo en tu móvil, sin registro. Para decidir cuándo vender, con números.",
         "Para decidir *con números*", e4, 3.6),
    ]


def _con_toque(nombre: str, x: float, y: float, t: float, desde: int = 0):
    """Captura con un círculo que late donde hay que tocar (coordenadas de la pantalla de 420×760)."""
    from PIL import Image, ImageDraw
    im = captura(nombre, desde).convert("RGBA")
    capa = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    r = 26 + 6 * math.sin(t * 7)
    d.ellipse([x - r - 12, y - r - 12, x + r + 12, y + r + 12], fill=(233, 196, 106, 80))
    d.ellipse([x - r, y - r, x + r, y + r], fill=(233, 196, 106, 150), outline=(24, 36, 29, 255), width=3)
    im.alpha_composite(capa)
    return im.convert("RGB")


def escenas_tratamientos(datos=None, hoy=None):
    """Capturas reales del 11 nov 2026 con la previsión de AEMET para Peñafiel (lluvia hoy, rachas de 48 km/h mañana)."""
    def e1(t, d):
        img = _base("campo", t)
        pegar(img, tractor(), 760, 1720, .9)
        pegar(img, persona("pedro", "pensar", "duda"), 300, 1720)
        if t > .7:
            pegar(img, bocadillo("¿Trato hoy el cereal?", 520, "izq", 50), 450, 1020, rebote((t - .7) / .4))
        return img

    def e2(t, d):
        img = _base("campo", t)
        pant = _con_toque("hoy-campo", 50, 260, t) if t > 1.6 else captura("hoy-campo")
        _movil_grande(img, pant, t)
        return img

    def e3(t, d):
        img = _base("campo", t)
        desde = int(90 * suave((t - 1.4) / 1.6))
        _movil_grande(img, captura("tiempo", desde), t)
        return img

    @lru_cache(maxsize=None)
    def detalle():
        from PIL import Image
        caja = captura("tiempo-horas").crop((14, 280, PW - 14, 358))
        return caja.resize((caja.width * 2, caja.height * 2), Image.LANCZOS).convert("RGBA")

    def e4(t, d):
        img = _base("campo", t)
        pant = _con_toque("tiempo-horas", 187, 225, t) if t < 1.2 else captura("tiempo-horas")
        _movil_grande(img, pant, 1.0, abajo=1900, escala=1.1)
        if t > 1.2:
            a = rebote((t - 1.2) / .5)
            pegar(img, detalle(), W / 2, 900, .95 * a, min(1, a))
        return img

    def e5(t, d):
        img = _base("campo", t)
        _movil_grande(img, captura("tiempo-manana"), 1.0, abajo=1900, escala=1.1)
        return img

    def e6(t, d):
        img = _base("tarde", t)
        pegar(img, tractor(), 760, 1720, .9)
        pegar(img, persona("pedro", "brazos", "contento"), 300, 1720 - abs(12 * math.sin(t * 6)))
        if t > .6:
            pegar(img, bocadillo("Esperaré: no tiro el producto", 560, "izq", 46), 470, 1020, rebote((t - .6) / .4))
        return img

    return [
        ("Pedro quiere tratar el cereal. Pero si llueve o hace viento, el producto se pierde… y el dinero también.",
         "¿Se puede *tratar hoy*?", e1, 4.0),
        ("En Lonjas CyL, la pantalla Hoy ya te lo adelanta. En Peñafiel, hoy no.",
         "Míralo en *Hoy*", e2, 3.8),
        ("En Campo › Tiempo ves cada hora en color: verde, buena; amarilla, regular; roja, mala.",
         "Cada hora *en color*", e3, 4.4),
        ("Toca una hora y te dice el motivo: lluvia, viento, rachas, humedad o temperatura.",
         "Toca una hora: *el motivo*", e4, 4.6),
        ("Mañana tampoco: rachas de hasta 48 km/h. Con la previsión oficial de AEMET para tu municipio.",
         "Mañana *tampoco*", e5, 4.0),
        ("Así que Pedro espera al buen momento. Tratar cuando toca: menos deriva y menos producto tirado.",
         "Tratar *cuando toca*", e6, 4.0),
    ]


ESPECIALES = {
    "instalar": {"titulo": "Cómo instalar Lonjas CyL", "escenas": escenas_instalar,
                 "texto": ("📲 Lonjas CyL en tu móvil, como una app más (30 segundos, sin tienda de aplicaciones):\n\n"
                           "🍎 iPhone: abre la web en Safari → Compartir (en iOS 26, dentro de «⋯») → «Añadir a pantalla de "
                           "inicio» → Añadir.\n"
                           "🤖 Android: abre la web en Chrome → ⋮ → «Instalar aplicación» (o «Añadir a pantalla de inicio»).\n\n"
                           "Se actualiza sola, funciona sin cobertura y es gratis, sin registro.\n\n"
                           "Guárdalo para tenerlo a mano y pásaselo a quien le pueda servir.")},
    "explotacion": {"titulo": "Mi explotación", "escenas": escenas_explotacion,
                    "texto": ("¿Cuánto vale hoy lo que tienes en el silo? 🌾\n\n"
                              "En «Mi explotación» apuntas lo que tienes (toneladas de trigo, de cebada, kilos de cordero…) y Lonjas CyL "
                              "lo valora con los precios de las lonjas de esta semana: con la media, con la que más paga o con la tuya. "
                              "Y te dice cuánto ha cambiado desde la sesión anterior.\n\n"
                              "Se guarda solo en tu móvil, sin registro. Es una valoración orientativa: no descuenta portes ni "
                              "diferencias de calidad.\n\n"
                              "La encuentras en Hoy → «Para decidir».")},
}
ESPECIALES["tratamientos"] = {
    "titulo": "¿Se puede tratar hoy?", "escenas": escenas_tratamientos, "musica": "guitarra",
    "texto": ("🌦️ ¿Se puede tratar hoy? Lonjas CyL te lo dice hora a hora.\n\n"
              "En Campo → Tiempo eliges tu municipio y ves cada hora de hoy y de mañana en color: 🟩 buena, 🟨 regular, 🟥 mala. "
              "Toca una hora y te dice el motivo: viento, rachas, temperatura, humedad o lluvia en las horas siguientes. "
              "Los límites puedes ajustarlos a tu gusto.\n\n"
              "Previsión oficial de AEMET. Es orientativo: manda siempre la etiqueta del producto.")}
ETIQUETAS = {"tratamientos": ["#agricultores", "#fitosanitarios", "#castillayleon"], "instalar": ["#agricultores", "#lonjas", "#castillayleon"], "explotacion": ["#agricultores", "#cereal", "#castillayleon"]}


def texto_publicacion(nombre: str, web: str = WEB) -> str:
    e = ESPECIALES[nombre]
    nota = ("Ejemplo de la captura: 60 t de trigo, 45 t de cebada y 3.300 kg de lechazo, con los precios de las sesiones del 3 al 5 "
            "de noviembre de 2026. " if nombre == "explotacion" else
            "Capturas con la previsión de AEMET para Peñafiel del 11 de noviembre de 2026. " if nombre == "tratamientos" else "")
    return (f"{e['texto']}\n\n{h.redes.ig.pie_texto(web)}\n\n{nota}Ilustraciones y capturas reales de la app. 🔇 Con subtítulos: se entiende sin sonido.\n\n"
            + etiquetas(*ETIQUETAS[nombre], "#LonjasCyL"))


def item(nombre: str, hoy: date) -> dict | None:
    if nombre in GUIAS:                # foto con los pasos, no reel
        return item_guia(nombre, hoy)
    if nombre not in ESPECIALES:
        return None
    return {"tipo": "especial", "nombre": nombre, "id": f"{hoy}-especial-{nombre}", "texto": texto_publicacion(nombre),
            "video": f"{hoy}-especial-{nombre}.mp4"}


def reel(nombre: str, destino: Path, datos=None, hoy=None, web: str = WEB) -> Path:
    """Sin voz y con subtítulos (lo pidió el dueño de la app el 8 nov 2026)."""
    musica = h.redes.guitarra if ESPECIALES[nombre].get("musica") == "guitarra" else None
    return h.reel(0, destino, datos, hoy, web, escenas=ESPECIALES[nombre]["escenas"](datos, hoy), voz=False, leyendas=True,
                  musica_fn=musica)


# ---------- Guías en imagen (una foto con los pasos): especial:iphone y especial:android ----------
# Mismas pantallas dibujadas que el reel «instalar», congeladas en el momento de cada toque.

GUIAS = {
    "iphone": {
        "titulo": "Instálala en tu iPhone",
        "navegador": "Safari",
        "pantallas": lambda: [pantalla_safari(0.25, "compartir"), pantalla_safari(1.6, "hoja"), pantalla_safari(3.0, "hoja")],
        "pasos": ["Toca Compartir: el cuadrado con la flecha (en iOS 26, primero «···»).",
                  "Baja y toca «Añadir a pantalla de inicio».",
                  "Toca «Añadir», arriba a la derecha. ¡Ya está!"],
        "texto": ("📲 Cómo tener Lonjas CyL en tu iPhone, como una app más (30 segundos):\n\n"
                  "0️⃣ Abre {url} en Safari.\n"
                  "1️⃣ Toca Compartir (el cuadrado con la flecha hacia arriba). En iOS 26 está dentro de «···».\n"
                  "2️⃣ Baja un poco y toca «Añadir a pantalla de inicio».\n"
                  "3️⃣ Toca «Añadir». Te aparece el icono junto a tus otras apps.\n\n"
                  "Sin tienda de aplicaciones, gratis y sin registro. Se actualiza sola con cada sesión de las lonjas.\n\n"
                  "¿Tienes Android? Esta noche publicamos los pasos. Guárdalo y pásaselo a quien le pueda servir."),
    },
    "android": {
        "titulo": "Instálala en tu Android",
        "navegador": "Chrome",
        "pantallas": lambda: [pantalla_chrome(0.3), pantalla_chrome(2.0), pantalla_inicio(3.0)],
        "pasos": ["Toca los tres puntos de arriba a la derecha.",
                  "Toca «Instalar aplicación» (o «Añadir a pantalla de inicio»).",
                  "Confirma con «Instalar». El icono aparece en tu pantalla."],
        "texto": ("📲 Cómo tener Lonjas CyL en tu móvil Android, como una app más (30 segundos):\n\n"
                  "0️⃣ Abre {url} en Chrome.\n"
                  "1️⃣ Toca los tres puntos (⋮), arriba a la derecha.\n"
                  "2️⃣ Toca «Instalar aplicación» (en algunos móviles pone «Añadir a pantalla de inicio»).\n"
                  "3️⃣ Confirma con «Instalar». Te aparece el icono junto a tus otras apps.\n\n"
                  "Sin tienda de aplicaciones, gratis y sin registro. Se actualiza sola con cada sesión de las lonjas.\n\n"
                  "¿Tienes iPhone? Los pasos están en nuestra publicación de hoy a mediodía. Guárdalo y pásaselo a quien le pueda servir."),
    },
}


def _numero(d, x, y, n):
    d.ellipse([x - 38, y - 38, x + 38, y + 38], fill=PAJA, outline=TINTA, width=4)
    d.text((x, y + 2), str(n), font=_cifra(54), fill=TINTA, anchor="mm")


def _lineas(d, texto: str, letra, ancho: int) -> list[str]:
    out, linea = [], ""
    for pal in texto.split():
        prueba = (linea + " " + pal).strip()
        if d.textlength(prueba, font=letra) <= ancho:
            linea = prueba
        else:
            out.append(linea)
            linea = pal
    return out + [linea] if linea else out


def imagen_guia(so: str, destino: Path, web: str = WEB) -> Path:
    """Una foto 1080×1350 con los tres pasos (móvil dibujado + explicación corta) para Instagram y Facebook."""
    from PIL import Image, ImageDraw
    from instagram import ALTO, ANCHO, FONDO, LINEA, _cabecera
    g = GUIAS[so]
    url = web.split("//")[1].rstrip("/")
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    _cabecera(img, d, g["titulo"], "3 pasos · 30 segundos · gratis y sin registro")
    # Paso previo: abrir la web en el navegador
    d.rounded_rectangle([50, 345, ANCHO - 50, 435], radius=26, fill=HOJA, outline=LINEA, width=2)
    d.text((80, 390), f"Antes: abre en {g['navegador']}", font=_texto(32, 600), fill=TINTA, anchor="lm")
    d.text((ANCHO - 80, 392), url, font=_cifra(44), fill=PINO, anchor="rm")
    # Los tres pasos
    global _SOLO_ARO
    letra = _texto(28, 600)
    _SOLO_ARO = True
    try:
        pantallas = g["pantallas"]()
    finally:
        _SOLO_ARO = False
    for i, (pant, paso) in enumerate(zip(pantallas, g["pasos"])):
        cx = 190 + i * 350
        tel = movil(pant)
        k = 0.66
        tel = tel.resize((int(tel.width * k), int(tel.height * k)), Image.LANCZOS)
        img.paste(tel, (int(cx - tel.width / 2), 478), tel)
        _numero(d, cx - tel.width / 2 + 6, 486, i + 1)
        y = 478 + tel.height + 22
        for linea in _lineas(d, paso, letra, 316)[:4]:
            d.text((cx, y), linea, font=letra, fill=TINTA, anchor="ma")
            y += 37
    # Pie
    d.line([70, ALTO - 100, ANCHO - 70, ALTO - 100], fill=LINEA, width=2)
    d.text((ANCHO / 2, ALTO - 52), "Se actualiza sola · funciona sin cobertura · avisos en t.me/lonjas_cyl", font=_texto(26, 600),
           fill=TENUE, anchor="mm")
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, quality=92)
    return destino


def item_guia(so: str, hoy: date, web: str = WEB) -> dict:
    url = web.split("//")[1].rstrip("/")
    texto = (GUIAS[so]["texto"].format(url=url) + f"\n\n{h.redes.ig.pie_texto(web)}\n\n"
             + etiquetas("#agricultores", "#lonjas", "#castillayleon", "#LonjasCyL"))
    return {"tipo": "guia", "so": so, "id": f"{hoy}-guia-{so}", "texto": texto, "imagenes": [f"{hoy}-guia-{so}.jpg"]}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nombre = args[0] if args else "instalar"
    carpeta = Path(args[1]) if len(args) > 1 else h.redes.SALIDA / "especiales"
    if "--fotogramas" in sys.argv:
        carpeta.mkdir(parents=True, exist_ok=True)
        for i, (texto, cap, dib, minimo) in enumerate(ESPECIALES[nombre]["escenas"]()):
            dur = max(minimo, h.estimar(texto) + .55)
            for frac in (.35, .9):
                img = dib(dur * frac, dur).convert("RGB")
                img.paste(h.marca(), (60, 150), h.marca())
                abajo = h.subtitulo(img, cap, 1.0)
                h.leyenda(img, texto, dur * frac, dur, abajo + 22)
                f = carpeta / f"{nombre}-e{i + 1}-{int(frac * 100)}.jpg"
                img.save(f, quality=85)
                print(f)
    else:
        print(reel(nombre, carpeta / f"especial-{nombre}.mp4"))

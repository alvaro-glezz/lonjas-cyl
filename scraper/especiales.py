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
from historias import H, W, Lapiz, _base, _img, _reducir, bocadillo, movil, pegar, persona, rebote, silo, suave  # noqa: E402
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


def _toque(p, x, y, t):
    """Círculo que late donde hay que tocar."""
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
ETIQUETAS = {"instalar": ["#agricultores", "#lonjas", "#castillayleon"], "explotacion": ["#agricultores", "#cereal", "#castillayleon"]}


def texto_publicacion(nombre: str, web: str = WEB) -> str:
    e = ESPECIALES[nombre]
    nota = ("Ejemplo de la captura: 60 t de trigo, 45 t de cebada y 3.300 kg de lechazo, con los precios de las sesiones del 3 al 5 "
            "de noviembre de 2026. " if nombre == "explotacion" else "")
    return (f"{e['texto']}\n\n{h.redes.ig.pie_texto(web)}\n\n{nota}Ilustraciones y capturas reales de la app. 🔇 Con subtítulos: se entiende sin sonido.\n\n"
            + etiquetas(*ETIQUETAS[nombre], "#LonjasCyL"))


def item(nombre: str, hoy: date) -> dict | None:
    if nombre not in ESPECIALES:
        return None
    return {"tipo": "especial", "nombre": nombre, "id": f"{hoy}-especial-{nombre}", "texto": texto_publicacion(nombre),
            "video": f"{hoy}-especial-{nombre}.mp4"}


def reel(nombre: str, destino: Path, datos=None, hoy=None, web: str = WEB) -> Path:
    """Sin voz y con subtítulos (lo pidió el dueño de la app el 8 nov 2026)."""
    return h.reel(0, destino, datos, hoy, web, escenas=ESPECIALES[nombre]["escenas"](datos, hoy), voz=False, leyendas=True)


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

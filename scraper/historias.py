"""Cinco reels con historia: los problemas que resuelve Lonjas CyL, contados con ilustraciones animadas.

Cada reel es una historia corta (un agricultor, un problema, la solución en la app) con voz (Piper, como los demás
reels), subtítulos grandes (mucha gente los ve sin sonido) y la música de acordes de redes.py. Las ilustraciones se
dibujan aquí mismo con Pillow: no hay imágenes de terceros.

Las cifras que salen en pantalla son reales: las del móvil, de data/precios.json del día en que se crea el vídeo;
los 13 €/t del primer reel, la diferencia mediana del trigo entre lonjas de CyL en la misma semana en 2025
(histórico de la app). Las personas y las ofertas son inventadas, y el texto de la publicación lo dice.

  python scraper/historias.py [n] [carpeta]     crea el reel n (1-5) o todos, sin publicar
  python scraper/historias.py --fotogramas      guarda fotogramas de muestra (para revisar el dibujo)
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
import wave
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import redes  # noqa: E402
from instagram import BAJA, CLARO, HOJA, ICONO, PAJA, PINO, SUBE, TENUE, TINTA, _cifra, _texto, etiquetas, nombre_corto  # noqa: E402
from paginas import WEB, num  # noqa: E402

W, H, FPS = 1080, 1920, 30
SS = 2                                   # los dibujos se hacen al doble y se reducen (bordes suaves)
FUNDIDO = 0.25                           # segundos de fundido entre escenas
INICIO = date(2026, 11, 9)               # primera publicación (lunes); luego una por día laborable, a las 19:00

# Colores de las ilustraciones (además de los de la marca)
CIELO_A, CIELO_B = "#a8d4e0", "#fbeacb"
TARDE_A, TARDE_B = "#f2b07a", "#fde3b8"
CERRO, CERRO_2 = "#9db67f", "#7f9e66"
TRIGO, TRIGO_2, TRIGO_3 = "#e7bd5a", "#d9a640", "#c48f2e"
PIEL, PIEL_2 = "#eab58c", "#d39a6f"
PARED, PARED_2, MADERA = "#f4e7d4", "#ead8bf", "#a8714a"
OSC = "#1d2b24"


# ---------- utilidades de dibujo ----------

def _img(w: int, h: int):
    from PIL import Image
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def _reducir(im):
    from PIL import Image
    return im.resize((im.width // SS, im.height // SS), Image.LANCZOS)


class Lapiz:
    """ImageDraw con coordenadas en píxeles finales (multiplica por SS)."""

    def __init__(self, im):
        from PIL import ImageDraw
        self.d = ImageDraw.Draw(im)

    @staticmethod
    def _k(v):
        return [x * SS for x in v]

    def rect(self, caja, fill, r=0, outline=None, width=0):
        self.d.rounded_rectangle(self._k(caja), radius=r * SS, fill=fill, outline=outline, width=width * SS)

    def elipse(self, caja, fill, outline=None, width=0):
        self.d.ellipse(self._k(caja), fill=fill, outline=outline, width=width * SS)

    def circulo(self, x, y, r, fill, outline=None, width=0):
        self.elipse([x - r, y - r, x + r, y + r], fill, outline, width)

    def poli(self, puntos, fill):
        self.d.polygon([(x * SS, y * SS) for x, y in puntos], fill=fill)

    def linea(self, puntos, fill, width, redonda=True):
        p = [(x * SS, y * SS) for x, y in puntos]
        self.d.line(p, fill=fill, width=width * SS, joint="curve")
        if redonda:
            for x, y in (p[0], p[-1]):
                r = width * SS / 2
                self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def arco(self, caja, a0, a1, fill, width):
        self.d.arc(self._k(caja), a0, a1, fill=fill, width=width * SS)

    def tarta(self, caja, a0, a1, fill):
        self.d.pieslice(self._k(caja), a0, a1, fill=fill)

    def texto(self, xy, t, letra, fill, anchor="la"):
        from PIL import ImageFont
        f = ImageFont.truetype(letra.path, letra.size * SS)
        self.d.text((xy[0] * SS, xy[1] * SS), t, font=f, fill=fill, anchor=anchor)


def _mezcla(a: str, b: str, t: float) -> tuple:
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return tuple(int(x + (y - x) * t) for x, y in zip(ca, cb))


def suave(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def rebote(t: float) -> float:
    """0 -> 1 con un pequeño rebote al final (para cosas que «aparecen»)."""
    t = max(0.0, min(1.0, t))
    c = 1.7
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def pegar(lienzo, sprite, cx: float, abajo: float, escala: float = 1.0, alfa: float = 1.0, giro: float = 0.0):
    """Pega un sprite RGBA centrado en cx y con su borde inferior en `abajo`."""
    from PIL import Image
    if alfa <= 0 or escala <= 0.01:
        return
    s = sprite
    if escala != 1.0:
        s = s.resize((max(1, int(s.width * escala)), max(1, int(s.height * escala))), Image.BILINEAR)
    if giro:
        s = s.rotate(giro, resample=Image.BICUBIC, expand=True)
    if alfa < 1:
        a = s.getchannel("A").point(lambda v: int(v * alfa))
        s = s.copy()
        s.putalpha(a)
    lienzo.paste(s, (int(cx - s.width / 2), int(abajo - s.height)), s)


def pegar_centro(lienzo, sprite, cx, cy, escala=1.0, alfa=1.0, giro=0.0):
    h = sprite.height * escala
    if giro:
        # el giro con expand cambia el alto: se centra por el centro real
        from PIL import Image
        s = sprite.resize((max(1, int(sprite.width * escala)), max(1, int(sprite.height * escala))), Image.BILINEAR)
        s = s.rotate(giro, resample=Image.BICUBIC, expand=True)
        pegar(lienzo, s, cx, cy + s.height / 2, 1.0, alfa)
        return
    pegar(lienzo, sprite, cx, cy + h / 2, escala, alfa)


# ---------- fondos ----------

def _degradado(arriba: str, abajo: str, alto: int):
    from PIL import Image
    franja = Image.new("RGB", (1, alto))
    for y in range(alto):
        franja.putpixel((0, y), _mezcla(arriba, abajo, y / max(1, alto - 1)))
    return franja.resize((W, alto))


@lru_cache(maxsize=None)
def fondo(tipo: str):
    """'campo' (mañana), 'tarde' (atardecer) o 'cocina'. Devuelve RGB de W×H."""
    from PIL import Image
    img = Image.new("RGB", (W, H), CIELO_B)
    if tipo in ("campo", "tarde"):
        a, b = (CIELO_A, CIELO_B) if tipo == "campo" else (TARDE_A, TARDE_B)
        img.paste(_degradado(a, b, 1250), (0, 0))
        capa = _img(W, H)
        p = Lapiz(capa)
        sol = (790, 1000)
        p.circulo(*sol, 120 if tipo == "campo" else 150, "#fff3cf" if tipo == "campo" else "#ffd08a")
        p.circulo(*sol, 90 if tipo == "campo" else 115, "#ffe39a" if tipo == "campo" else "#ffb35c")
        # cerros lejanos con un pueblo (iglesia con torre)
        cerro = [(0, 1150)] + [(x, 1110 - 40 * math.sin(x / 170) - 25 * math.sin(x / 61)) for x in range(0, W + 20, 20)] + [(W, 1250), (0, 1250)]
        p.poli(cerro, CERRO)
        for x, y, w, h in ((160, 1060, 70, 50), (225, 1070, 55, 40), (280, 1050, 80, 60)):
            p.rect([x, y, x + w, y + h], "#e9dcc4")
            p.poli([(x - 6, y), (x + w / 2, y - 26), (x + w + 6, y)], "#c26a48")
        p.rect([370, 985, 410, 1110], "#e9dcc4")
        p.poli([(364, 985), (390, 945), (416, 985)], "#c26a48")
        p.rect([382, 1000, 398, 1022], "#8b6a4c", r=8)
        p.rect([410, 1040, 520, 1110], "#e9dcc4")
        p.poli([(404, 1040), (465, 1010), (526, 1040)], "#c26a48")
        p.poli([(0, 1200)] + [(x, 1170 - 22 * math.sin(x / 230 + 1.3)) for x in range(0, W + 20, 20)] + [(W, 1300), (0, 1300)], CERRO_2)
        # campo de cereal en perspectiva
        p.poli([(0, 1190), (W, 1170), (W, H), (0, H)], TRIGO)
        for i in range(-12, 13):
            x0 = 540 + i * 26
            x1 = 540 + i * 230
            p.linea([(x0, 1185), (x1, H)], TRIGO_2, 7, redonda=False)
        p.poli([(0, 1560), (W, 1500), (W, H), (0, H)], TRIGO_2)
        for i in range(36):
            x = 15 + i * 31
            y = 1530 - (x / W) * 60
            for k in range(3):
                p.linea([(x + k * 8, y + 10), (x + k * 8 - 6 + k * 6, y - 40 - (k % 2) * 14)], TRIGO_3, 4)
                p.elipse([x + k * 8 - 13 + k * 6, y - 66 - (k % 2) * 14, x + k * 8 + 1 + k * 6, y - 30 - (k % 2) * 14], TRIGO)
        img.paste(_reducir(capa), (0, 0), _reducir(capa))
    else:  # cocina
        img.paste(Image.new("RGB", (W, 1380), PARED), (0, 0))
        capa = _img(W, H)
        p = Lapiz(capa)
        for y in range(1100, 1380, 46):            # azulejos
            for x in range(-23 * ((y // 46) % 2), W, 92):
                p.rect([x + 3, y + 3, x + 89, y + 43], PARED_2, r=6)
        # ventana con el campo
        p.rect([600, 640, 980, 1020], "#ffffff", r=18)
        p.rect([616, 656, 964, 1004], CIELO_A, r=10)
        p.rect([616, 880, 964, 1004], TRIGO, r=0)
        p.poli([(616, 880), (700, 850), (800, 870), (900, 840), (964, 860), (964, 900), (616, 900)], CERRO)
        p.circulo(880, 760, 36, "#ffe39a")
        p.rect([786, 656, 794, 1004], "#ffffff")
        p.rect([616, 826, 964, 834], "#ffffff")
        # reloj de pared
        p.circulo(270, 760, 92, "#ffffff", outline="#5d4a3a", width=10)
        # encimera / mesa
        p.rect([-20, 1380, W + 20, 1440], MADERA)
        p.rect([-20, 1440, W + 20, H], "#c8905f")
        for y in range(1480, H, 70):
            p.linea([(0, y), (W, y)], "#b97f50", 4, redonda=False)
        img.paste(_reducir(capa), (0, 0), _reducir(capa))
    return img


def reloj(lienzo, h: float, m: float, cx: int = 270, cy: int = 760):
    """Agujas del reloj de pared de la cocina (h y m pueden ser decimales para animar)."""
    capa = _img(W, H)
    p = Lapiz(capa)
    for i in range(12):
        a = i / 12 * 2 * math.pi
        p.linea([(cx + 66 * math.sin(a), cy - 66 * math.cos(a)), (cx + 76 * math.sin(a), cy - 76 * math.cos(a))], "#5d4a3a", 5)
    ah = (h % 12 + m / 60) / 12 * 2 * math.pi
    am = m / 60 * 2 * math.pi
    p.linea([(cx, cy), (cx + 42 * math.sin(ah), cy - 42 * math.cos(ah))], OSC, 11)
    p.linea([(cx, cy), (cx + 64 * math.sin(am), cy - 64 * math.cos(am))], OSC, 7)
    p.circulo(cx, cy, 9, BAJA)
    lienzo.paste(_reducir(capa), (0, 0), _reducir(capa))


@lru_cache(maxsize=None)
def nube(ancho: int = 260):
    im = _img(ancho, ancho // 2)
    p = Lapiz(im)
    a = ancho
    for x, y, r in ((a * .28, a * .32, a * .17), (a * .5, a * .22, a * .2), (a * .72, a * .32, a * .16)):
        p.circulo(x, y, r, "#ffffff")
    p.rect([a * .1, a * .3, a * .9, a * .48], "#ffffff", r=int(a * .09))
    return _reducir(im)


def nubes(lienzo, t: float):
    for x0, y, an, v in ((120, 760, 240, 14), (620, 680, 300, 9), (980, 860, 200, 18)):
        x = (x0 + v * t * 3) % (W + 400) - 200
        pegar(lienzo, nube(an), x, y)


# ---------- personajes y objetos ----------

PERSONAS = {
    # gorra/pelo, camisa, pantalón, barba
    "julian": {"gorra": PINO, "camisa": "#4f7fb5", "pantalon": "#3b4656", "pelo": None, "barba": None},
    "marisa": {"gorra": None, "camisa": "#3f8a63", "pantalon": "#40384a", "pelo": "#5a3b28", "barba": None},
    "pedro": {"gorra": BAJA, "camisa": "#e3c26b", "pantalon": "#3b4656", "pelo": None, "barba": "#6b5444"},
    "ana": {"gorra": None, "camisa": "#e08b3a", "pantalon": "#334a5c", "pelo": "#2e2420", "barba": None},
    "luis": {"gorra": "#e07a2e", "camisa": "#6d8f4e", "pantalon": "#2f3a48", "pelo": None, "barba": None},
    "comprador": {"gorra": "#5b5b5b", "camisa": "#ffffff", "pantalon": "#2b2b33", "pelo": None, "barba": None, "chaleco": "#3a3a46"},
}


@lru_cache(maxsize=None)
def persona(quien: str, pose: str = "normal", cara: str = "contento"):
    """Personaje de pie, 400×760 (pies abajo). pose: normal, movil, oreja, pensar, brazos, saludo, mano. cara: contento,
    serio, duda, sorpresa, triste."""
    c = PERSONAS[quien]
    im = _img(400, 780)
    p = Lapiz(im)
    cx = 200
    # piernas y zapatos
    p.rect([142, 470, 196, 742], c["pantalon"], r=22)
    p.rect([204, 470, 258, 742], c["pantalon"], r=22)
    p.rect([128, 724, 198, 760], "#3a2a20", r=16)
    p.rect([202, 724, 272, 760], "#3a2a20", r=16)
    # pelo largo detrás (ellas)
    if c["pelo"] and quien == "ana":
        p.rect([150, 140, 250, 330], c["pelo"], r=40)
    # cuerpo
    p.rect([118, 248, 282, 500], c["camisa"], r=58)
    if c.get("chaleco"):
        p.rect([128, 260, 196, 496], c["chaleco"], r=40)
        p.rect([204, 260, 272, 496], c["chaleco"], r=40)
    p.poli([(176, 250), (200, 286), (224, 250)], PIEL)          # cuello de la camisa
    p.rect([118, 440, 282, 474], "#4a3a2c", r=10)               # cinturón

    def brazo(puntos):
        p.linea(puntos, c["camisa"] if not c.get("chaleco") else "#ffffff", 46)
        x, y = puntos[-1]
        p.circulo(x, y, 25, PIEL)

    movil = lambda x, y: (p.rect([x - 22, y - 46, x + 22, y + 30], OSC, r=10), p.rect([x - 16, y - 38, x + 16, y + 20], "#9fd3b4", r=6))  # noqa: E731
    if pose == "movil":
        brazo([(136, 290), (110, 420), (170, 400)])
        brazo([(264, 290), (290, 420), (232, 400)])
        movil(200, 400)
    elif pose == "oreja":
        brazo([(136, 290), (112, 400), (126, 470)])
        brazo([(264, 290), (318, 260), (262, 182)])
        p.rect([248, 132, 280, 214], OSC, r=10)
    elif pose == "pensar":
        brazo([(136, 290), (120, 400), (186, 380)])
        brazo([(264, 290), (290, 360), (232, 232)])
    elif pose == "brazos":                                        # brazos arriba, contento
        brazo([(136, 290), (70, 210), (60, 120)])
        brazo([(264, 290), (330, 210), (340, 120)])
    elif pose == "saludo":
        brazo([(136, 290), (112, 400), (126, 470)])
        brazo([(264, 290), (340, 230), (350, 140)])
    elif pose == "mano":                                          # tiende la mano hacia la izquierda
        brazo([(136, 290), (70, 330), (20, 340)])
        brazo([(264, 290), (288, 400), (274, 470)])
    else:
        brazo([(136, 290), (112, 400), (126, 470)])
        brazo([(264, 290), (288, 400), (274, 470)])
    # cabeza
    p.rect([182, 200, 218, 260], PIEL_2, r=12)                    # cuello
    p.circulo(cx - 72, 160, 16, PIEL_2)
    p.circulo(cx + 72, 160, 16, PIEL_2)
    p.circulo(cx, 150, 76, PIEL)
    if c["barba"]:
        p.tarta([cx - 62, 120, cx + 62, 232], 10, 170, c["barba"])
        p.rect([cx - 30, 172, cx + 30, 182], c["barba"], r=5)
        p.elipse([cx - 22, 184, cx + 22, 204], PIEL)
    # ojos y cejas
    oj = 150
    for s in (-1, 1):
        if cara == "sorpresa":
            p.circulo(cx + s * 28, oj, 10, OSC)
        else:
            p.circulo(cx + s * 28, oj, 8, OSC)
        if cara in ("duda", "triste"):
            p.linea([(cx + s * 16, oj - 22 - (8 if (s == 1 and cara == "duda") else 0)), (cx + s * 40, oj - 26 + (s * 4 if cara == "triste" else 0))], OSC, 5)
        else:
            p.linea([(cx + s * 16, oj - 26), (cx + s * 40, oj - 28)], OSC, 5)
    # boca
    if cara == "contento":
        p.arco([cx - 30, 158, cx + 30, 200], 20, 160, "#8a3b2a", 6)
    elif cara == "sorpresa":
        p.elipse([cx - 13, 178, cx + 13, 206], "#8a3b2a")
    elif cara == "triste":
        p.arco([cx - 26, 186, cx + 26, 220], 200, 340, "#8a3b2a", 6)
    elif cara == "duda":
        p.linea([(cx - 20, 194), (cx + 22, 186)], "#8a3b2a", 6)
    else:
        p.linea([(cx - 20, 192), (cx + 20, 192)], "#8a3b2a", 6)
    p.circulo(cx - 42, 176, 12, "#f2a083")
    p.circulo(cx + 42, 176, 12, "#f2a083")
    # gorra o pelo
    if c["gorra"]:
        p.tarta([cx - 80, 70, cx + 80, 200], 180, 360, c["gorra"])
        p.rect([cx - 80, 126, cx + 118, 146], c["gorra"], r=10)
        p.circulo(cx, 74, 9, c["gorra"])
    elif c["pelo"]:
        p.tarta([cx - 82, 66, cx + 82, 196], 180, 360, c["pelo"])
        p.tarta([cx - 82, 96, cx - 10, 176], 120, 300, c["pelo"])
        if quien == "marisa":
            p.circulo(cx + 30, 70, 34, c["pelo"])                 # moño
        else:
            p.circulo(cx + 60, 92, 22, BAJA)                      # coletero
    return _reducir(im)


@lru_cache(maxsize=None)
def tractor(color: str = "#c9452f"):
    im = _img(640, 440)
    p = Lapiz(im)
    p.rect([150, 180, 520, 330], color, r=26)
    p.rect([330, 40, 520, 200], color, r=18)
    p.rect([350, 62, 500, 180], "#cfe7ee", r=12)
    p.rect([180, 120, 210, 182], "#4a4a4a", r=6)                 # tubo de escape
    p.rect([100, 260, 200, 312], "#9a9a9a", r=12)
    for x, y, r in ((440, 330, 108), (190, 360, 70)):
        p.circulo(x, y, r, "#2b2b2b")
        p.circulo(x, y, r * .55, "#e7bd5a")
        p.circulo(x, y, r * .18, "#2b2b2b")
    return _reducir(im)


@lru_cache(maxsize=None)
def silo():
    im = _img(300, 700)
    p = Lapiz(im)
    p.rect([40, 140, 260, 700], "#c9d2d6", r=8)
    for y in range(170, 700, 60):
        p.linea([(40, y), (260, y)], "#aab4b9", 5, redonda=False)
    p.tarta([30, 40, 270, 250], 180, 360, "#aab4b9")
    p.rect([130, 20, 170, 60], "#aab4b9", r=6)
    p.rect([110, 560, 190, 700], "#7e8a90", r=6)
    return _reducir(im)


@lru_cache(maxsize=None)
def cafe(humo: bool = True):
    im = _img(160, 220)
    p = Lapiz(im)
    p.rect([20, 90, 130, 210], "#ffffff", r=18)
    p.arco([110, 110, 160, 170], 270, 90, "#ffffff", 12)
    p.rect([30, 100, 120, 118], "#7a4a2e", r=6)
    if humo:
        for x in (55, 85):
            p.linea([(x, 80), (x - 10, 55), (x + 6, 30), (x - 4, 8)], "#ffffffcc", 7)
    return _reducir(im)


@lru_cache(maxsize=None)
def bocadillo(texto: str, ancho: int = 560, hacia: str = "izq", tam: int = 50, fondo_: str = "#ffffff", tinta: str = TINTA):
    """Bocadillo de diálogo con la cola abajo (hacia izquierda o derecha)."""
    from PIL import Image, ImageDraw
    letra = _texto(tam, 700)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    lineas = redes._partir(tmp, texto, letra, ancho - 80)
    alto = 50 + len(lineas) * int(tam * 1.25)
    im = _img(ancho, alto + 60)
    p = Lapiz(im)
    p.rect([0, 0, ancho, alto], fondo_, r=40)
    if hacia == "izq":
        p.poli([(90, alto - 4), (60, alto + 52), (170, alto - 4)], fondo_)
    else:
        p.poli([(ancho - 170, alto - 4), (ancho - 60, alto + 52), (ancho - 90, alto - 4)], fondo_)
    y = 26
    for l in lineas:
        p.texto((ancho / 2, y), l, letra, tinta, anchor="ma")
        y += int(tam * 1.25)
    return _reducir(im)


@lru_cache(maxsize=None)
def ventana(titulo: str, tipo: str, giro_: int = 0):
    """Una «web» o un «PDF» de los que hay que abrir uno a uno."""
    im = _img(440, 330)
    p = Lapiz(im)
    p.rect([6, 10, 440, 330], "#00000022", r=22)
    p.rect([0, 0, 432, 320], "#ffffff", r=22)
    barra = "#c84b36" if tipo == "pdf" else "#5f7f9a"
    p.rect([0, 0, 432, 70], barra, r=22)
    p.rect([0, 40, 432, 70], barra)
    for i, col in enumerate(("#ffffff99", "#ffffff66", "#ffffff44")):
        p.circulo(30 + i * 30, 35, 9, col)
    p.texto((120, 35), titulo, _texto(32, 700), "#ffffff", anchor="lm")
    if tipo == "pdf":
        for i in range(6):
            p.rect([34, 100 + i * 34, 398 - (i % 3) * 60, 116 + i * 34], "#d9d9d9", r=6)
    else:
        for i in range(4):
            p.rect([34, 96 + i * 52, 230, 130 + i * 52], "#e9eef1", r=6)
            p.rect([250, 96 + i * 52, 398, 130 + i * 52], "#e9eef1", r=6)
    return _reducir(im)


@lru_cache(maxsize=None)
def billete(valor: str = "€"):
    im = _img(150, 90)
    p = Lapiz(im)
    p.rect([0, 0, 150, 90], "#7fb38d", r=12)
    p.rect([10, 10, 140, 80], "#a8d1b2", r=8)
    p.circulo(75, 45, 26, "#7fb38d")
    p.texto((75, 46), valor, _cifra(40), "#ffffff", anchor="mm")
    return _reducir(im)


@lru_cache(maxsize=None)
def interrogante(color: str = BAJA, tam: int = 120):
    im = _img(tam, tam)
    p = Lapiz(im)
    p.circulo(tam / 2, tam / 2, tam / 2 - 2, "#ffffff")
    p.texto((tam / 2, tam / 2 + 4), "?", _cifra(int(tam * .8)), color, anchor="mm")
    return _reducir(im)


# ---------- el móvil con la app ----------

def _pantalla_lista(titulo: str, sub: str, filas: list[tuple[str, str, float]], destacar: int = 0, unidad: str = ""):
    """filas = [(nombre, texto del precio, 0..1 largo de la barra)]."""
    im = _img(420, 760)
    p = Lapiz(im)
    p.rect([0, 0, 420, 760], "#eef1ea")
    p.rect([0, 0, 420, 150], PINO)
    p.texto((28, 52), "Lonjas CyL", _cifra(40), HOJA, anchor="lm")
    p.texto((28, 106), titulo, _texto(30, 700), HOJA, anchor="lm")
    p.texto((28, 182), sub, _texto(22, 600), TENUE, anchor="lm")
    y = 214
    for i, (nombre, precio, largo) in enumerate(filas[:5]):
        top = i == destacar
        p.rect([18, y, 402, y + 98], PAJA if top else "#ffffff", r=18)
        p.texto((40, y + 34), nombre, _texto(28, 700), TINTA, anchor="lm")
        if precio:
            p.texto((384, y + 34), precio, _cifra(40), TINTA, anchor="rm")
        p.rect([40, y + 64, 40 + 320 * max(.08, largo), y + 78], PINO if top else "#b9cbbf", r=7)
        y += 112
    if unidad:
        p.texto((210, y + 18), unidad, _texto(22, 600), TENUE, anchor="mm")
    return _reducir(im)


def movil(pantalla):
    """Marco de móvil alrededor de una pantalla de 420×760."""
    from PIL import Image
    im = _img(470, 860)
    p = Lapiz(im)
    p.rect([0, 0, 470, 860], OSC, r=60)
    p.rect([150, 22, 320, 40], "#000000", r=9)
    m = _reducir(im)
    hueco = Image.new("L", (420, 760), 0)
    from PIL import ImageDraw
    ImageDraw.Draw(hueco).rounded_rectangle([0, 0, 419, 759], radius=34, fill=255)
    m.paste(pantalla.convert("RGB"), (25, 52), hueco)
    return m


# ---------- datos reales para el móvil ----------

def lista_real(datos: dict | None, clave: str, hoy: date):
    """Última sesión de cada lonja para un producto (datos reales) o None."""
    r = redes.ranking(datos, clave, hoy) if datos else None
    if not r:
        return None
    vals = [p["act"] for _, p in r["filas"]]
    lo, hi = min(vals), max(vals)
    filas = [(nombre_corto(l), num(p["act"]), .35 + .65 * ((p["act"] - lo) / (hi - lo) if hi > lo else 1)) for l, p in r["filas"]]
    return {"filas": filas, "unidad": r["unidad"], "media": sum(vals) / len(vals), "max": hi,
            "fechas": sorted(l["fecha"] for l, _ in r["filas"])}


def pantalla_producto(datos, clave: str, nombre: str, hoy: date):
    lr = lista_real(datos, clave, hoy)
    if lr:
        return _pantalla_lista(nombre, "Última sesión de cada lonja", lr["filas"], 0, lr["unidad"])
    filas = [(n, "", 1 - i * .15) for i, n in enumerate(("Salamanca", "León", "Segovia", "Lerma"))]
    return _pantalla_lista(nombre, "Última sesión de cada lonja", filas, 0)


# ---------- texto en pantalla ----------

def subtitulo(lienzo, texto: str, t: float, y: int = 250, entra: bool = True):
    """Rótulo grande arriba. Lo que va entre *asteriscos* sale en amarillo paja. Entra deslizándose (salvo `entra=False`:
    el primer fotograma del reel es la portada y debe llevar el rótulo)."""
    from PIL import Image, ImageDraw
    a = suave(t / 0.35) if entra else 1.0
    if a <= 0:
        return
    letra = _cifra(86)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    # partir respetando los trozos resaltados
    palabras, resalta = [], False
    for trozo in texto.split("*"):
        for pal in trozo.split():
            if palabras and pal[0] in ",.;:!?…":
                palabras.append(("\b" + pal, resalta))
            else:
                palabras.append((pal, resalta))
        resalta = not resalta
    lineas, actual = [], []
    for pal in palabras:
        prueba = " ".join(x for x, _ in actual + [pal])
        if actual and tmp.textlength(prueba, font=letra) > W - 200:
            lineas.append(actual)
            actual = [pal]
        else:
            actual.append(pal)
    if actual:
        lineas.append(actual)
    alto = 40 + len(lineas) * 94
    ancho = max(tmp.textlength(" ".join(x for x, _ in l).replace(" \b", ""), font=letra) for l in lineas) + 90
    capa = Image.new("RGBA", (int(ancho), alto + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    d.rounded_rectangle([0, 10, ancho, alto + 10], radius=34, fill=(0, 0, 0, 50))
    d.rounded_rectangle([0, 0, ancho, alto], radius=34, fill=PINO)
    yy = 22
    for l in lineas:
        x = (ancho - tmp.textlength(" ".join(w for w, _ in l).replace(" \b", ""), font=letra)) / 2
        for w, r in l:
            if w.startswith("\b"):                 # signo de puntuación pegado a la palabra anterior
                w = w[1:]
                x -= tmp.textlength(" ", font=letra)
            d.text((x, yy), w, font=letra, fill=PAJA if r else HOJA)
            x += tmp.textlength(w + " ", font=letra)
        yy += 94
    pegar(lienzo, capa, W / 2, y + capa.height - 40 * (1 - a), 1.0, a)


@lru_cache(maxsize=None)
def marca():
    from PIL import Image, ImageDraw
    capa = Image.new("RGBA", (330, 74), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    d.rounded_rectangle([0, 0, 329, 73], radius=37, fill=(255, 255, 255, 230))
    ico = Image.open(ICONO).convert("RGB").resize((54, 54))
    capa.paste(ico, (12, 10))
    d.text((80, 38), "Lonjas CyL", font=_cifra(44), fill=PINO, anchor="lm")
    return capa



# ---------- las cinco historias ----------
# Cada escena: (voz, subtítulo, dibujo(t, dur) -> imagen RGB, duración mínima)

def _base(tipo: str, t: float, con_nubes: bool = True):
    img = fondo(tipo).copy()
    if con_nubes and tipo in ("campo", "tarde"):
        nubes(img, t)
    return img


def _respira(t: float, amp: float = 6, vel: float = 2.2) -> float:
    return amp * math.sin(t * vel)


def historia_1(datos, hoy):
    """La llamada: vender sin comparar."""
    def e1(t, d):
        img = _base("campo", t)
        pegar(img, persona("julian", "oreja", "contento"), 470, 1640 + _respira(t, 3))
        for k in range(3):                       # el teléfono suena
            r = 40 + ((t * 70 + k * 40) % 120)
            from PIL import ImageDraw
            ImageDraw.Draw(img).arc([560 - r, 1030 - r, 560 + r, 1030 + r], -50, 50, fill=PINO, width=8)
        return img

    def e2(t, d):
        img = _base("campo", t)
        pegar(img, persona("julian", "oreja", "contento"), 470, 1640)
        pegar(img, bocadillo("Te lo pago a buen precio. ¿Trato hecho?", 600, "der"), 420, 1000, rebote(t / .5))
        if t > 1.4:
            pegar(img, bocadillo("¡Hecho!", 300, "izq", 60, PAJA), 760, 1180, rebote((t - 1.4) / .4))
        return img

    def e3(t, d):
        img = _base("campo", t)
        pegar(img, persona("julian", "normal", "serio"), 250, 1650)
        # dos montones: lo que le pagaron y lo que marcaba otra lonja
        from PIL import ImageDraw
        dr = ImageDraw.Draw(img)
        a = suave(t / 1.0)
        b = suave((t - .6) / 1.0)
        for x, alto, txt, col in ((540, 330 * a, "Lo que cobró", "#b9cbbf"), (810, 430 * b, "Otra lonja", PAJA)):
            dr.rounded_rectangle([x - 90, 1430 - alto, x + 90, 1430], radius=18, fill=col)
            dr.rounded_rectangle([x - 112, 1446, x + 112, 1498], radius=26, fill=HOJA)
            dr.text((x, 1472), txt, font=_texto(32, 700), fill=TINTA, anchor="mm")
        if b > .9:
            pegar(img, bocadillo("+13 €/t", 330, "izq", 58, "#ffffff", SUBE), 810, 990, rebote((t - 1.6) / .4))
        return img

    def e4(t, d):
        img = _base("campo", t, False)
        from PIL import Image, ImageDraw
        velo = Image.new("RGBA", (W, H), (36, 80, 60, 215))
        img.paste(velo, (0, 0), velo)
        dr = ImageDraw.Draw(img)
        n = int(round(13 * suave(t / 1.2)))
        dr.text((W / 2 - 40, 820), f"{n} €/t", font=_cifra(230), fill=PAJA, anchor="mm")
        dr.text((W / 2 - 40, 960), "diferencia habitual en trigo", font=_texto(44, 700), fill=HOJA, anchor="mm")
        a = suave((t - 2.0) / .6)
        if a > 0:
            dr.text((W / 2 - 40, 1100), "× 100 t", font=_cifra(110), fill=_mezcla(PINO, "#ffffff", a), anchor="mm")
        b = suave((t - 3.4) / .6)
        if b > 0:
            dr.text((W / 2 - 40, 1245), "= 1.300 €", font=_cifra(150), fill=_mezcla(PINO, PAJA, b), anchor="mm")
            for k in range(6):                    # los billetes que se van
                tt = (t - 3.6 - k * .25)
                if tt > 0:
                    pegar(img, billete(), 160 + k * 150 + 30 * math.sin(tt * 3), 1330 + 300 * tt, 1.0, max(0, 1 - tt / 2), giro=20 * math.sin(tt * 2 + k))
        dr.text((W / 2 - 40, 1360), "Mediana de 2025 entre lonjas de CyL, misma semana", font=_texto(28, 600), fill=CLARO, anchor="mm")
        return img

    def e5(t, d):
        img = _base("campo", t)
        pegar(img, persona("julian", "movil", "contento"), 270, 1660)
        pegar(img, movil(pantalla_producto(datos, "trigo", "Trigo", hoy)), 700, 1560 - 60 * (1 - rebote(t / .6)), .9 * rebote(t / .6))
        return img

    return [
        ("Julián vendió su trigo en cinco minutos.", "Julián vendió su trigo *en 5 minutos*", e1, 2.6),
        ("Le llamaron, le dieron un precio, y dijo que sí. Sin mirar nada más.", "Le llamaron. Le dieron un precio. *Dijo que sí.*", e2, 3.4),
        ("Esa misma semana, otra lonja de Castilla y León marcaba más.", "Esa semana, otra lonja *marcaba más*", e3, 3.0),
        ("En dos mil veinticinco, entre las lonjas de la región, la diferencia habitual en el trigo fue de trece euros la tonelada. "
         "Con cien toneladas, mil trescientos euros.", "¿Cuánto es eso?", e4, 6.0),
        ("Ahora, antes de decir que sí, Julián mira todas las lonjas en una sola pantalla.", "Antes de decir que sí, *mira todas las lonjas*", e5, 3.6),
    ]


def historia_2(datos, hoy):
    """La mañana perdida: cada lonja publica a su manera."""
    def e1(t, d):
        img = _base("cocina", t)
        reloj(img, 7, 0 + t * 2)
        pegar(img, persona("marisa", "movil", "serio"), 560, 1620)
        pegar(img, cafe(True), 860, 1410)
        return img

    wins = [("Web de lonja", "web", -6, 300, 870), ("PDF semanal", "pdf", 5, 760, 820), ("Otra tabla", "web", 4, 330, 1130),
            ("Otro PDF…", "pdf", -4, 770, 1100)]

    def e2(t, d):
        img = _base("cocina", t)
        reloj(img, 8, 15 + t * 20)
        pegar(img, persona("marisa", "movil", "duda"), 560, 1620)
        pegar(img, cafe(True), 860, 1410)
        for i, (tit, tipo, g, x, y) in enumerate(wins):
            a = rebote((t - i * .9) / .45)
            if a > 0:
                pegar_centro(img, ventana(tit, tipo), x, y, .95 * a, giro=g)
        return img

    def e3(t, d):
        img = _base("cocina", t)
        h = 8.25 + 2.25 * suave(t / 1.6)
        reloj(img, int(h), (h % 1) * 60)
        pegar(img, persona("marisa", "normal", "triste"), 560, 1620)
        pegar(img, cafe(False), 860, 1410)
        for i, (tit, tipo, g, x, y) in enumerate(wins):
            pegar_centro(img, ventana(tit, tipo), x, y + 6 * math.sin(t * 3 + i), .95, alfa=.55, giro=g)
        return img

    def e4(t, d):
        img = _base("cocina", t)
        reloj(img, 7, 5)
        pegar(img, persona("marisa", "movil", "contento"), 300, 1620)
        pegar(img, cafe(True), 860, 1410)
        pegar(img, movil(pantalla_producto(datos, "cebada", "Cebada", hoy)), 700, 1560 - 60 * (1 - rebote(t / .6)), .9 * rebote(t / .6))
        return img

    def e5(t, d):
        img = _base("campo", t)
        x = 300 + 260 * suave(t / 2.0)
        pegar(img, persona("marisa", "saludo", "contento"), x, 1660 - abs(10 * math.sin(t * 7)))
        return img

    return [
        ("Son las siete. Marisa solo quiere saber a cómo está la cebada.", "7:00. Marisa quiere saber *a cómo está la cebada*", e1, 3.0),
        ("Abre la web de una lonja. Luego un PDF. Luego otra tabla. Y otra más.", "Una web. Un PDF. Otra tabla. *Otra más…*", e2, 4.2),
        ("Cuando termina, son las diez y media. Y el café, frío.", "10:30. *El café, frío.*", e3, 3.0),
        ("Lonjas Castilla y León junta todas las lonjas de la región en una sola pantalla, y se actualiza sola.",
         "Todas las lonjas, *en una pantalla*", e4, 4.2),
        ("Un vistazo, y al tajo.", "Un vistazo… *y al tajo*", e5, 2.4),
    ]


def historia_3(datos, hoy):
    """¿Me están pagando bien?: una oferta sin referencia."""
    lr = lista_real(datos, "cebada", hoy)

    def e1(t, d):
        img = _base("campo", t)
        pegar(img, persona("comprador", "mano", "contento"), 760, 1640)
        pegar(img, persona("pedro", "normal", "serio"), 300, 1650)
        pegar(img, bocadillo("Te doy un buen precio por la cebada.", 560, "der"), 640, 1010, rebote(t / .5))
        return img

    def e2(t, d):
        img = _base("campo", t)
        pegar(img, persona("comprador", "normal", "contento"), 760, 1640)
        pegar(img, persona("pedro", "pensar", "duda"), 300, 1650)
        for k in range(3):
            a = t * 1.6 + k * 2.1
            pegar_centro(img, interrogante(BAJA, 110), 300 + 210 * math.cos(a), 950 + 70 * math.sin(a), rebote((t - k * .3) / .4))
        return img

    def pantalla_oferta(t):
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (420, 760), "#eef1ea")
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 420, 150], fill=PINO)
        d.text((28, 52), "Lonjas CyL", font=_cifra(40), fill=HOJA, anchor="lm")
        d.text((28, 106), "¿Me están pagando bien?", font=_texto(28, 700), fill=HOJA, anchor="lm")
        if lr:
            media = lr["media"]
            oferta = math.floor(media - 9)
            u = lr["unidad"]
        else:
            media, oferta, u = None, None, "€/t"
        d.text((28, 190), "Cebada · tu oferta", font=_texto(24, 600), fill=TENUE, anchor="lm")
        d.rounded_rectangle([20, 214, 400, 300], radius=16, fill="#ffffff", outline="#b9cbbf", width=3)
        escrito = f"{oferta}" if oferta else "—"
        n = int(len(escrito) * suave(t / 1.2))
        d.text((44, 258), escrito[:n] + ("|" if int(t * 3) % 2 == 0 and n < len(escrito) + 1 else ""), font=_cifra(56), fill=TINTA, anchor="lm")
        d.text((380, 258), u, font=_texto(24, 600), fill=TENUE, anchor="rm")
        a = suave((t - 1.6) / .5)
        if a > 0 and media:
            d.rounded_rectangle([20, 330, 400, 440], radius=18, fill=_mezcla("#eef1ea", "#f6d9cf", a))
            d.text((40, 366), "Por debajo de la media", font=_texto(30, 700), fill=BAJA, anchor="lm")
            d.text((40, 408), f"Media de las lonjas: {num(media, 0)} {u}", font=_texto(22, 600), fill=TINTA, anchor="lm")
            for i, (nombre, precio, largo) in enumerate(lr["filas"][:4]):
                y = 470 + i * 66
                b = suave((t - 2.0 - i * .2) / .4)
                if b <= 0:
                    continue
                d.text((30, y + 20), nombre, font=_texto(24, 700), fill=TINTA, anchor="lm")
                d.text((390, y + 20), precio, font=_cifra(36), fill=TINTA, anchor="rm")
                d.rounded_rectangle([30, y + 40, 30 + 330 * largo * b, y + 50], radius=5, fill="#b9cbbf")
        return im

    def e3(t, d):
        img = _base("campo", t)
        pegar(img, persona("pedro", "movil", "serio"), 270, 1660)
        pegar(img, movil(pantalla_oferta(t)), 700, 1560 - 60 * (1 - rebote(t / .6)), .9 * rebote(t / .6))
        return img

    def e4(t, d):
        img = _base("campo", t)
        pegar(img, persona("comprador", "mano", "sorpresa"), 680, 1640)
        pegar(img, persona("pedro", "saludo", "contento"), 330, 1650)
        pegar(img, bocadillo("Hablemos con datos.", 470, "izq", 54, PAJA), 360, 1000, rebote(t / .5))
        return img

    return [
        ("Te ofrecen un precio por la cebada. ¿Es bueno? ¿Es malo?", "Te ofrecen un precio… *¿es bueno?*", e1, 3.0),
        ("El que compra lo sabe. Pedro, no.", "El que compra lo sabe. *Pedro, no.*", e2, 2.6),
        ("Con la herramienta: ¿me están pagando bien?, mete la oferta y la compara al momento con las lonjas de la semana.",
         "Mete la oferta y *compárala al momento*", e3, 4.6),
        ("Y negocia con datos. No a ciegas.", "Negocia *con datos*, no a ciegas", e4, 2.6),
    ]


def historia_4(datos, hoy):
    """¿Vendo o espero?: el precio de hoy, en contexto."""
    def e1(t, d):
        img = _base("tarde", t)
        pegar(img, silo(), 780, 1560)
        pegar(img, persona("ana", "pensar", "duda"), 340, 1650)
        return img

    def e2(t, d):
        img = _base("tarde", t)
        pegar(img, persona("ana", "pensar", "duda"), 340, 1650)
        from PIL import ImageDraw
        dr = ImageDraw.Draw(img)
        # un camino hacia el futuro que se pierde en la niebla
        pts = [(560 + i * 40, 1180 - 120 * math.sin(i / 2.2) - i * 18) for i in range(0, 1 + int(9 * suave(t / 1.4)))]
        for i in range(len(pts) - 1):
            if i % 2 == 0:
                dr.line([pts[i], pts[i + 1]], fill=PINO, width=12)
        if t > 1.3:
            pegar_centro(img, interrogante(PINO, 160), 900, 950, rebote((t - 1.3) / .4))
        return img

    def termo(t):
        from PIL import Image, ImageDraw
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        x0, y0, y1 = 300, 700, 1420
        d.rounded_rectangle([x0 - 50, y0, x0 + 50, y1], radius=50, fill="#ffffff")
        d.ellipse([x0 - 85, y1 - 60, x0 + 85, y1 + 110], fill="#ffffff")
        nivel = .2 + .52 * suave(t / 1.8) + .02 * math.sin(t * 4)
        col = _mezcla("#4f8fc0", "#d0503a", nivel)
        d.ellipse([x0 - 65, y1 - 40, x0 + 65, y1 + 90], fill=col)
        d.rounded_rectangle([x0 - 28, y1 - (y1 - y0 - 30) * nivel, x0 + 28, y1], radius=28, fill=col)
        for i, (txt, f) in enumerate((("Caro", .92), ("Normal", .5), ("Barato", .1))):
            y = y1 - (y1 - y0 - 30) * f
            d.line([x0 + 60, y, x0 + 110, y], fill=TINTA, width=6)
            d.text((x0 + 130, y), txt, font=_cifra(64), fill=TINTA, anchor="lm")
        if t > 1.8:
            a = rebote((t - 1.8) / .4)
            y = y1 - (y1 - y0 - 30) * nivel
            d.rounded_rectangle([x0 - 270, y - 46, x0 - 80, y + 46], radius=46, fill=PINO)
            d.text((x0 - 175, y), "Hoy", font=_cifra(64), fill=HOJA, anchor="mm")
        return im

    def e3(t, d):
        img = _base("tarde", t, False)
        from PIL import Image
        velo = Image.new("RGBA", (W, H), (255, 245, 228, 170))
        img.paste(velo, (0, 0), velo)
        tm = termo(t)
        img.paste(tm, (0, 0), tm)
        pegar(img, persona("ana", "normal", "sorpresa"), 800, 1660, .8)
        return img

    def pantalla_termo():
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (420, 760), "#eef1ea")
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 420, 150], fill=PINO)
        d.text((28, 52), "Lonjas CyL", font=_cifra(40), fill=HOJA, anchor="lm")
        d.text((28, 106), "¿Caro o barato?", font=_texto(30, 700), fill=HOJA, anchor="lm")
        d.text((28, 190), "El precio de hoy frente a", font=_texto(24, 600), fill=TENUE, anchor="lm")
        d.text((28, 222), "los dos últimos años", font=_texto(24, 600), fill=TENUE, anchor="lm")
        # histograma de semanas y la marca de hoy (ilustrativo, sin cifras)
        alturas = [3, 5, 8, 12, 16, 19, 17, 14, 11, 8, 6, 4, 2]
        for i, h in enumerate(alturas):
            x = 30 + i * 28
            d.rounded_rectangle([x, 560 - h * 14, x + 22, 560], radius=6, fill="#b9cbbf")
        d.line([290, 280, 290, 570], fill=BAJA, width=5)
        d.rounded_rectangle([238, 262, 342, 304], radius=20, fill=BAJA)
        d.text((290, 283), "Hoy", font=_texto(24, 700), fill=HOJA, anchor="mm")
        d.text((30, 600), "Barato", font=_texto(22, 600), fill=TENUE, anchor="lm")
        d.text((390, 600), "Caro", font=_texto(22, 600), fill=TENUE, anchor="rm")
        d.rounded_rectangle([20, 650, 400, 730], radius=18, fill="#ffffff")
        d.text((210, 690), "No es una previsión", font=_texto(26, 700), fill=TINTA, anchor="mm")
        return im

    def e4(t, d):
        img = _base("tarde", t)
        pegar(img, silo(), 160, 1560, .8)
        pegar(img, persona("ana", "movil", "contento"), 400, 1660)
        pegar(img, movil(pantalla_termo()), 760, 1560 - 60 * (1 - rebote(t / .6)), .85 * rebote(t / .6))
        return img

    return [
        ("Ana tiene el silo lleno y una duda: ¿vendo ya, o espero?", "Silo lleno. Una duda: *¿vendo o espero?*", e1, 3.0),
        ("Nadie puede saber lo que hará el mercado.", "Nadie sabe *qué hará el mercado*", e2, 2.6),
        ("Pero sí se puede saber si el precio de hoy está alto o bajo, comparado con los dos últimos años.",
         "Pero sí: *¿está caro o barato hoy?*", e3, 4.0),
        ("Eso hace el termómetro de Lonjas Castilla y León. No adivina el futuro: pone el presente en contexto. Y la decisión, la tomas tú.",
         "El presente, *en contexto*. Tú decides.", e4, 5.0),
    ]


def historia_5(datos, hoy):
    """Se me pasó: no se puede estar mirando precios todo el día."""
    def e1(t, d):
        img = _base("campo", t)
        x = -200 + (W + 300) * (t / max(d, 1)) * .75
        pegar(img, tractor(), x, 1560 + 4 * math.sin(t * 18))
        for k in range(5):                      # polvo
            r = 20 + 12 * k
            from PIL import ImageDraw
            ImageDraw.Draw(img).ellipse([x - 300 - k * 50 - r, 1500 - r - k * 6, x - 300 - k * 50 + r, 1500 + r - k * 6], fill="#ead2a0")
        return img

    def hoja(dia, num_):
        from PIL import Image, ImageDraw
        im = Image.new("RGBA", (360, 400), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, 359, 399], radius=30, fill="#ffffff")
        d.rounded_rectangle([0, 0, 359, 110], radius=30, fill=BAJA)
        d.rectangle([0, 70, 359, 110], fill=BAJA)
        d.text((180, 58), dia, font=_cifra(64), fill=HOJA, anchor="mm")
        d.text((180, 260), str(num_), font=_cifra(200), fill=TINTA, anchor="mm")
        return im

    def e2(t, d):
        img = _base("campo", t)
        pegar(img, persona("luis", "normal", "triste"), 300, 1650)
        dias = [("VIERNES", 13), ("SÁBADO", 14), ("DOMINGO", 15), ("LUNES", 16)]
        k = min(3, int(t / .75))
        pegar(img, hoja(*dias[k]), 760, 1300, 1.0)
        if t > 3.0:
            pegar(img, bocadillo("¡Si llegó el viernes!", 460, "izq", 50), 360, 980, rebote((t - 3.0) / .4))
        return img

    def pantalla_chat(t):
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (420, 760), "#e3ece6")
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 420, 120], fill=PINO)
        d.text((28, 48), "@lonjascyl_bot", font=_texto(28, 700), fill=HOJA, anchor="lm")
        d.text((28, 88), "robot de avisos", font=_texto(22, 400), fill=CLARO, anchor="lm")
        msg = "/aviso cebada más de 230"
        n = int(len(msg) * suave(t / 1.4))
        d.rounded_rectangle([60, 160, 400, 230], radius=20, fill="#cfe8d6")
        d.text((80, 195), msg[:n], font=_texto(24, 700), fill=TINTA, anchor="lm")
        a = suave((t - 1.8) / .4)
        if a > 0:
            d.rounded_rectangle([20, 260, 380, 380], radius=20, fill=_mezcla("#e3ece6", "#ffffff", a))
            d.text((40, 300), "Hecho. Te escribo", font=_texto(24, 700), fill=TINTA, anchor="lm")
            d.text((40, 340), "cuando una sesión lo cruce.", font=_texto(24, 400), fill=TINTA, anchor="lm")
        return im

    def e3(t, d):
        img = _base("campo", t)
        pegar(img, persona("luis", "movil", "serio"), 270, 1660)
        pegar(img, movil(pantalla_chat(t)), 700, 1560 - 60 * (1 - rebote(t / .6)), .9 * rebote(t / .6))
        return img

    @lru_cache(maxsize=None)
    def aviso():
        from PIL import Image, ImageDraw
        im = Image.new("RGBA", (760, 170), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 8, 759, 169], radius=34, fill=(0, 0, 0, 50))
        d.rounded_rectangle([0, 0, 759, 160], radius=34, fill="#ffffff")
        d.ellipse([28, 40, 108, 120], fill=PAJA)
        d.pieslice([46, 52, 90, 100], 180, 360, fill=PINO)         # campanita
        d.rectangle([46, 75, 90, 92], fill=PINO)
        d.rounded_rectangle([40, 88, 96, 96], radius=4, fill=PINO)
        d.ellipse([61, 94, 75, 108], fill=PINO)
        d.ellipse([63, 44, 73, 54], fill=PINO)
        d.text((134, 56), "Aviso de Lonjas CyL", font=_texto(30, 700), fill=TINTA, anchor="lm")
        d.text((134, 106), "La cebada ha pasado de 230 €/t", font=_texto(30, 400), fill=TINTA, anchor="lm")
        return im

    def e4(t, d):
        img = _base("campo", t)
        pegar(img, tractor(), 640, 1560 + 4 * math.sin(t * 18))
        pegar(img, persona("luis", "brazos", "contento"), 230, 1650 - abs(14 * math.sin(t * 6)))
        a = rebote(t / .5)
        pegar(img, aviso(), 520, 900 - 40 * (1 - a), 1.0, min(1, a))
        return img

    return [
        ("Luis pasa el día en el tractor. No puede estar pendiente de los precios.", "Luis pasa el día *en el tractor*", e1, 3.2),
        ("La cebada llegó al precio que esperaba... y él se enteró tres días tarde.", "Llegó al precio… *y se enteró tarde*", e2, 3.8),
        ("Ahora tiene un aviso en Telegram: elige el producto y el precio, y cuando una lonja lo cruza, le llega un mensaje.",
         "Pon un aviso *en Telegram*", e3, 4.6),
        ("Tú, a lo tuyo. Lonjas Castilla y León te avisa.", "Tú a lo tuyo. *Te avisamos.*", e4, 2.8),
    ]


HISTORIAS = {
    1: {"id": "llamada", "titulo": "La llamada", "escenas": historia_1,
        "texto": ("Julián vendió su trigo en cinco minutos. Le llamaron, le dieron un precio y dijo que sí.\n\n"
                  "Esa semana, otra lonja de Castilla y León marcaba más. En 2025, la diferencia habitual en trigo entre lonjas "
                  "de CyL en la misma semana fue de 13 €/t (mediana; histórico de Lonjas CyL). Con 100 t, 1.300 €.\n\n"
                  "Antes de decir que sí, mira todas las lonjas en una pantalla. Gratis y sin registro.")},
    2: {"id": "manana", "titulo": "La mañana perdida", "escenas": historia_2,
        "texto": ("Una web. Un PDF. Otra tabla. Otra más… y el café, frío.\n\n"
                  "Cada lonja publica a su manera y en su día. Lonjas CyL las junta todas (Salamanca, León, Segovia, Lerma…) "
                  "en una sola pantalla y se actualiza sola. Un vistazo y al tajo.")},
    3: {"id": "oferta", "titulo": "¿Me están pagando bien?", "escenas": historia_3,
        "texto": ("Te ofrecen un precio por la cebada. ¿Es bueno? El que compra lo sabe.\n\n"
                  "Con «¿Me están pagando bien?» metes la oferta y la comparas al momento con las lonjas de esta semana. "
                  "Ojo: cada lonja da un precio de referencia en sus condiciones (calidad, entrega, porte).\n\n"
                  "Negocia con datos, no a ciegas.")},
    4: {"id": "termometro", "titulo": "¿Vendo o espero?", "escenas": historia_4,
        "texto": ("Silo lleno y una duda: ¿vendo o espero?\n\n"
                  "Nadie sabe qué hará el mercado. Pero sí se puede saber si el precio de hoy está alto o bajo frente a los dos "
                  "últimos años. Eso hace el termómetro «¿Caro o barato?» de Lonjas CyL. No es una previsión: es el presente "
                  "en contexto. La decisión es tuya.")},
    5: {"id": "aviso", "titulo": "Se me pasó", "escenas": historia_5,
        "texto": ("Todo el día en el tractor. La cebada llegó al precio que esperabas… y te enteras tres días tarde.\n\n"
                  "Pon un aviso gratis con nuestro robot de Telegram (@lonjascyl_bot): «/aviso cebada más de 230». "
                  "Cuando una sesión lo cruce, te escribe.\n\nTú a lo tuyo. Lonjas CyL te avisa.")},
}

ETIQUETAS = ["#trigo", "#cebada", "#agricultores", "#cereal", "#preciosdelcereal"]


def texto_publicacion(n: int, web: str = WEB) -> str:
    h = HISTORIAS[n]
    return (f"{h['texto']}\n\n{redes.ig.pie_texto(web)}\n\n"
            f"Historia inventada e ilustrada; las cifras son reales. {redes.AVISO_VOZ}\n\n"
            + etiquetas(*ETIQUETAS[:3], "#LonjasCyL"))


# ---------- voz, duración y vídeo ----------

def _voz_escena(texto: str, destino: Path) -> Path | None:
    return redes.voz(texto, destino)


def _leer_wav(f: Path) -> tuple[bytes, int]:
    with wave.open(str(f)) as w:
        assert w.getsampwidth() == 2 and w.getnchannels() == 1
        return w.readframes(w.getnframes()), w.getframerate()


def estimar(texto: str) -> float:
    """Duración aproximada de la voz (sin Piper): ~2,7 palabras por segundo."""
    return len(texto.split()) / 2.7 + .3


def plan(escenas: list, voces: list[Path | None]) -> list[float]:
    durs = []
    for (texto, _, _, minimo), v in zip(escenas, voces):
        hablado = redes.duracion_wav(v) if v else estimar(texto)
        durs.append(round(max(minimo, hablado + .55), 2))
    return durs


def reel(n: int, destino: Path, datos: dict | None = None, hoy: date | None = None, web: str = WEB) -> Path:
    hoy = hoy or date.today()
    escenas = HISTORIAS[n]["escenas"](datos, hoy)
    tmp = destino.with_name(destino.stem + "-tmp")
    tmp.mkdir(parents=True, exist_ok=True)
    cierre_voz = "Lonjas Castilla y León. Gratis, y sin registro."
    voces = [_voz_escena(e[0], tmp / f"v{i}.wav") for i, e in enumerate(escenas)]
    voz_cierre = _voz_escena(cierre_voz, tmp / "vc.wav")
    durs = plan(escenas, voces) + [max(3.0, (redes.duracion_wav(voz_cierre) if voz_cierre else estimar(cierre_voz)) + .9)]
    total = sum(durs)
    # pista de voz alineada con las escenas (cada frase empieza 0,2 s después de su escena)
    pista = None
    if any(voces) or voz_cierre:
        tasa = next(_leer_wav(v)[1] for v in voces + [voz_cierre] if v)
        buf = bytearray(int(total * tasa) * 2 + 4)
        t0 = 0.0
        for v, dur in zip(voces + [voz_cierre], durs):
            if v:
                pcm, _ = _leer_wav(v)
                i = int((t0 + .2) * tasa) * 2
                buf[i:i + len(pcm)] = pcm[:max(0, len(buf) - i)]
            t0 += dur
        pista = tmp / "voz.wav"
        with wave.open(str(pista), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(tasa)
            w.writeframes(bytes(buf))
    musica = redes.musica(tmp / "musica.wav", total)
    cierre = redes._cierre(web)
    escenas_v = [(d, e[1], e[2]) for d, e in zip(durs, escenas)] + [(durs[-1], None, None)]
    parcial = destino.with_name(destino.stem + ".parcial.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(musica)]
    if pista:
        cmd += ["-i", str(pista), "-filter_complex",
                "[1:a]volume=0.40[m];[2:a]aresample=48000,volume=1.25[v];[m][v]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89:level=false[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-ar", "48000", "-shortest", "-movflags", "+faststart", str(parcial)]
    from PIL import Image
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    anterior = None
    try:
        for j, (dur, cap, dib) in enumerate(escenas_v):
            for k in range(int(round(dur * FPS))):
                t = k / FPS
                if dib is None:
                    img = cierre.copy()
                else:
                    img = dib(t, dur).convert("RGB")
                    img.paste(marca(), (60, 150), marca())
                    subtitulo(img, cap, t, entra=j > 0)
                if anterior is not None and t < FUNDIDO:
                    img = Image.blend(anterior, img, t / FUNDIDO)
                proc.stdin.write(img.tobytes())
                ultimo = img
            anterior = ultimo
    finally:
        proc.stdin.close()
        ok = proc.wait() == 0
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    if not ok:
        parcial.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg no pudo crear el vídeo")
    parcial.replace(destino)
    return destino


def fotogramas(n: int, carpeta: Path, datos=None, hoy=None) -> list[Path]:
    """Un fotograma por escena, en su momento más lleno (para revisar el dibujo sin renderizar el vídeo)."""
    hoy = hoy or date.today()
    out = []
    escenas = HISTORIAS[n]["escenas"](datos, hoy)
    for i, (texto, cap, dib, minimo) in enumerate(escenas):
        dur = max(minimo, estimar(texto) + .55)
        img = dib(dur * .8, dur).convert("RGB")
        img.paste(marca(), (60, 150), marca())
        subtitulo(img, cap, 1.0)
        f = carpeta / f"h{n}-e{i + 1}.jpg"
        carpeta.mkdir(parents=True, exist_ok=True)
        img.save(f, quality=88)
        out.append(f)
    return out


# ---------- calendario ----------

def siguiente(estado: dict, hoy: date) -> int | None:
    """Qué historia toca hoy: desde INICIO, una por día laborable, en orden, hasta publicar las cinco."""
    if hoy < INICIO or hoy.weekday() >= 5:
        return None
    hechas = set(estado.get("historias", []))
    return next((n for n in sorted(HISTORIAS) if n not in hechas), None)


def item(n: int, hoy: date) -> dict:
    return {"tipo": "historia", "n": n, "id": f"{hoy}-historia-{n}-{HISTORIAS[n]['id']}", "texto": texto_publicacion(n),
            "video": f"{hoy}-historia-{n}-{HISTORIAS[n]['id']}.mp4"}


if __name__ == "__main__":
    import json
    datos = json.loads(redes.ig.DATOS.read_text(encoding="utf-8"))
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    carpeta = Path(args[1]) if len(args) > 1 else redes.SALIDA / "historias"
    nums = [int(args[0])] if args and args[0] != "todas" else sorted(HISTORIAS)
    for n in nums:
        if "--fotogramas" in sys.argv:
            for f in fotogramas(n, carpeta, datos):
                print(f)
        else:
            print(reel(n, carpeta / f"historia-{n}-{HISTORIAS[n]['id']}.mp4", datos))

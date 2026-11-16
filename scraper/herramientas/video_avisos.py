"""Vídeo sin voz: cómo crear avisos de precio con el robot de Telegram de Lonjas CyL (1080x1920, 30 fps).

Uso: python scraper/herramientas/video_avisos.py [salida.mp4]
Luego se le pone una pista de audio muda para que Telegram lo trate como vídeo y no como GIF:
  ffmpeg -i salida.mp4 -f lavfi -i anullsrc=r=44100:cl=stereo -c:v copy -c:a aac -b:a 32k -shortest canal/avisos-telegram.mp4
Las respuestas del robot que salen en el vídeo son las reales del 16 nov 2026."""
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
LETRAS = REPO / "scraper" / "letras"
ICONO = REPO / "icons" / "icono-512.png"
EMOJI_F = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
SALIDA = Path(sys.argv[1] if len(sys.argv) > 1 else REPO / "canal" / "avisos-telegram-sin-audio.mp4")

W, H, FPS = 1080, 1920, 30
PINO, PINO_OSC, FONDO, HOJA, TINTA, TENUE, LINEA = "#24503c", "#1b3d2e", "#eef1ea", "#ffffff", "#18241d", "#5b6a60", "#d6ddd2"
PAJA, CLARO, SUBE_OSC = "#e0b252", "#cfe0d4", "#1b3d2e"
BURBUJA_YO = "#dcefc9"

CHAT_Y0, CHAT_Y1 = 250, 1470          # zona del chat
INPUT_Y0, INPUT_Y1 = 1470, 1590       # barra de escribir
CAP_Y0 = 1590                         # franja de explicación


@lru_cache(None)
def letra(peso: int, t: int):
    return ImageFont.truetype(str(LETRAS / f"public-sans-latin-{peso}-normal.ttf"), t)


@lru_cache(None)
def cifra(t: int):
    return ImageFont.truetype(str(LETRAS / "barlow-condensed-latin-700-normal.ttf"), t)


@lru_cache(None)
def emoji(ch: str, t: int) -> Image.Image:
    f = ImageFont.truetype(EMOJI_F, 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox())
    return im.resize((t, round(im.height * t / im.width)), Image.LANCZOS)


EMOJIS = {"✅", "🔔"}


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


# ---------- texto con negritas (<b>) y emojis, con ajuste de líneas ----------
def fichas(linea: str):
    out, negrita = [], False
    for trozo in re.split(r"(<b>|</b>)", linea):
        if trozo == "<b>":
            negrita = True
        elif trozo == "</b>":
            negrita = False
        else:
            if trozo[:1].isspace() and out:
                out[-1] = (out[-1][0] + " ", out[-1][1])
            for pal in re.findall(r"\S+\s*", trozo):
                out.append((pal, negrita))
    return out


def medir(pal: str, negrita: bool, t: int) -> int:
    if pal.strip() in EMOJIS:
        return t + 12
    return round(letra(700 if negrita else 400, t).getlength(pal))


def maquetar(texto: str, ancho: int, t: int):
    lineas = []
    for bruta in texto.split("\n"):
        if not bruta.strip():
            lineas.append([])
            continue
        actual, x = [], 0
        for pal, neg in fichas(bruta):
            w = medir(pal, neg, t)
            if actual and x + medir(pal.rstrip(), neg, t) > ancho:
                lineas.append(actual)
                actual, x = [], 0
            actual.append((pal, neg, x))
            x += w
        lineas.append(actual)
    return lineas


def pintar_texto(img: Image.Image, x0: int, y0: int, lineas, t: int, alto: int, color=TINTA):
    d = ImageDraw.Draw(img)
    for i, linea in enumerate(lineas):
        y = y0 + i * alto
        for pal, neg, x in linea:
            if pal.strip() in EMOJIS:
                e = emoji(pal.strip(), t)
                img.alpha_composite(e, (x0 + x, y + (alto - e.height) // 2 - 4))
            else:
                d.text((x0 + x, y), pal, font=letra(700 if neg else 400, t), fill=color)


# ---------- burbujas ----------
T_MSG, ALTO_L, PAD, ANCHO_MAX = 36, 50, 30, 780


@lru_cache(None)
def burbuja(texto: str, mio: bool) -> Image.Image:
    lineas = maquetar(texto, ANCHO_MAX - 2 * PAD, T_MSG)
    ancho = max([max([x + medir(p.rstrip(), n, T_MSG) for p, n, x in l], default=0) for l in lineas] + [120]) + 2 * PAD
    alto = len(lineas) * ALTO_L + 2 * PAD - 6
    hora_w = 70
    if mio:
        ancho = max(ancho, 200)
    img = Image.new("RGBA", (ancho + 10, alto + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 6, ancho + 4, alto + 6], 30, fill=(0, 0, 0, 28))       # sombra suave
    d.rounded_rectangle([0, 0, ancho, alto], 30, fill=BURBUJA_YO if mio else HOJA)
    pintar_texto(img, PAD, PAD - 4, lineas, T_MSG, ALTO_L)
    if mio:
        d.text((ancho - PAD + 6, alto - 14), "✓✓", font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22),
               fill="#4fa36b", anchor="rs")
    return img


@lru_cache(None)
def puntos(fase: int) -> Image.Image:
    img = Image.new("RGBA", (170, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, 160, 86], 30, fill=HOJA)
    for i in range(3):
        c = TENUE if i == fase % 3 else LINEA
        d.ellipse([34 + i * 34, 33, 54 + i * 34, 53], fill=c)
    return img


@lru_cache(None)
def separador(texto: str) -> Image.Image:
    f = letra(600, 28)
    w = round(f.getlength(texto)) + 50
    img = Image.new("RGBA", (w, 56), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, 52], 26, fill=(36, 80, 60, 200))
    d.text((w // 2, 26), texto, font=f, fill=HOJA, anchor="mm")
    return img


# ---------- guion ----------
USUARIO, ROBOT = True, False
R1 = ("✅ Aviso 1 creado: Trigo en Salamanca · suba a 240 €/t o más.\nAhora: 234 €/t (Salamanca, 9 nov).\n"
      "Te escribiré en cuanto una sesión llegue a ese precio.\nVer tus avisos: /avisos")
R2 = ("✅ Aviso 2 creado: Cerdo normal en cualquier lonja · baje a 1,05 €/kg vivo o menos.\nAhora: 1,10 €/kg vivo (Lerma, 13 nov).\n"
      "Te escribiré en cuanto una sesión llegue a ese precio.\nVer tus avisos: /avisos")
R3 = ("🔔 <b>Tus avisos</b>\n\n1. Trigo en Salamanca · suba a 240 €/t o más · ahora 234\n"
      "2. Cerdo normal en cualquier lonja · baje a 1,05 €/kg vivo o menos · ahora 1,10\n\nBorrar: /borrar 1 · /borrar todos")
R4 = ("🔔 <b>Aviso cumplido</b>\nTrigo en Salamanca: <b>240 €/t</b> (sesión del lunes).\nPediste que te avisara si subía a 240 €/t.\n"
      "Te volveré a avisar si vuelve a cruzar ese precio. Borrarlo: /borrar 1")
R5 = "Borrado: Trigo en Salamanca · suba a 240 €/t o más."

INTRO, OUTRO = 4.0, 5.0
# (instante, tipo, dato) — los instantes son desde que empieza el chat
GUION = []
RIOS = []      # textos de la franja inferior: (instante, número, texto)


def mensaje_usuario(t, texto):
    escribir = min(1.6, 0.35 + 0.045 * len(texto))
    GUION.append((t, "teclear", (texto, escribir)))
    GUION.append((t + escribir + 0.25, "msg", (texto, USUARIO)))
    return t + escribir + 0.25


def respuesta(t, texto, espera=0.9):
    GUION.append((t + 0.2, "puntos", espera))
    GUION.append((t + 0.2 + espera, "msg", (texto, ROBOT)))
    return t + 0.2 + espera


t = 0.3
RIOS.append((0.0, "1", "Abre el robot @lonjascyl_bot en Telegram y pulsa «Iniciar»"))
t = 3.8
RIOS.append((t, "2", "Escribe /aviso + producto + lonja + precio"))
t = mensaje_usuario(t + 0.4, "/aviso trigo salamanca 240")
t = respuesta(t, R1) + 3.6
RIOS.append((t, "2", "Sin lonja vale cualquiera. Para bajadas: «baja de»"))
t = mensaje_usuario(t + 0.4, "/aviso cerdo baja de 1,05")
t = respuesta(t, R2) + 3.6
RIOS.append((t, "3", "Escribe /avisos para ver los que tienes"))
t = mensaje_usuario(t + 0.4, "/avisos")
t = respuesta(t, R3) + 3.8
RIOS.append((t, "4", "Cuando una lonja llegue a tu precio, te escribe sola"))
GUION.append((t + 0.4, "sep", "Días después · ejemplo"))
t = respuesta(t + 0.9, R4, 0.7) + 4.2
RIOS.append((t, "5", "Para quitarlo: /borrar 1 (o /borrar todos)"))
t = mensaje_usuario(t + 0.4, "/borrar 1")
t = respuesta(t, R5, 0.7) + 3.0
CHAT_DUR = t
TOTAL = INTRO + CHAT_DUR + OUTRO


# ---------- pantallas ----------
@lru_cache(None)
def icono(t: int) -> Image.Image:
    im = Image.open(ICONO).convert("RGBA").resize((t, t), Image.LANCZOS)
    m = Image.new("L", (t, t), 0)
    ImageDraw.Draw(m).ellipse([0, 0, t - 1, t - 1], fill=255)
    out = Image.new("RGBA", (t, t), (0, 0, 0, 0))
    out.paste(im, (0, 0), m)
    return out


@lru_cache(None)
def fondo_chat() -> Image.Image:
    img = Image.new("RGBA", (W, H), FONDO)
    d = ImageDraw.Draw(img)
    # cabecera tipo Telegram
    d.rectangle([0, 0, W, CHAT_Y0], fill=PINO)
    d.text((48, 125), "‹", font=letra(400, 90), fill=HOJA, anchor="lm")
    img.alpha_composite(icono(120), (110, 65))
    d.text((260, 100), "Lonjas CyL", font=letra(700, 46), fill=HOJA, anchor="lm")
    d.text((260, 158), "@lonjascyl_bot · robot", font=letra(400, 32), fill=CLARO, anchor="lm")
    # trama suave
    for y in range(CHAT_Y0 + 40, CHAT_Y1, 90):
        for x in range(40 + (y // 90 % 2) * 45, W, 90):
            d.ellipse([x, y, x + 6, y + 6], fill="#e3e8de")
    # barra de escribir
    d.rectangle([0, INPUT_Y0, W, INPUT_Y1], fill=HOJA)
    d.line([0, INPUT_Y0, W, INPUT_Y0], fill=LINEA, width=2)
    d.ellipse([W - 120, INPUT_Y0 + 18, W - 36, INPUT_Y0 + 102], fill=PINO)
    d.polygon([(W - 96, INPUT_Y0 + 42), (W - 52, INPUT_Y0 + 60), (W - 96, INPUT_Y0 + 78), (W - 88, INPUT_Y0 + 60)], fill=HOJA)
    # franja inferior
    d.rectangle([0, CAP_Y0, W, H], fill=PINO_OSC)
    return img


def franja(img: Image.Image, tc: float):
    actual = [r for r in RIOS if r[0] <= tc]
    if not actual:
        return
    t0, num, texto = actual[-1]
    a = ease((tc - t0) / 0.35)
    capa = Image.new("RGBA", (W, H - CAP_Y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    d.ellipse([60, 70, 160, 170], fill=PAJA)
    d.text((110, 122), num, font=cifra(72), fill=PINO_OSC, anchor="mm")
    f = letra(700, 50)
    lineas = maquetar("<b>" + texto + "</b>", W - 260, 50)
    y0 = 120 - len(lineas) * 64 // 2 + 4
    pintar_texto(capa, 200, y0, lineas, 50, 64, color=HOJA)
    d.text((W // 2, 280), "Lonjas CyL · avisos de precio gratis", font=letra(600, 28), fill=CLARO, anchor="mm")
    if a < 1:
        capa.putalpha(capa.getchannel("A").point(lambda v: int(v * a)))
        dy = int((1 - a) * 30)
    else:
        dy = 0
    img.alpha_composite(capa, (0, CAP_Y0 + dy))


def chat(tc: float) -> Image.Image:
    img = fondo_chat().copy()
    d = ImageDraw.Draw(img)
    # qué hay escrito en la barra
    escrito = ""
    for t0, tipo, dato in GUION:
        if tipo == "teclear" and t0 <= tc < t0 + dato[1] + 0.25:
            n = int(len(dato[0]) * min(1, (tc - t0) / dato[1]))
            escrito = dato[0][:n]
    if tc < 3.4:  # botón «Iniciar» de Telegram
        d.rectangle([0, INPUT_Y0, W, INPUT_Y1], fill=HOJA)
        pulsado = 2.2 <= tc < 2.6
        d.text((W // 2, (INPUT_Y0 + INPUT_Y1) // 2), "INICIAR", font=letra(700, 44), fill=SUBE_OSC if pulsado else PINO, anchor="mm")
        if 2.2 <= tc < 3.0:
            r = int(40 + (tc - 2.2) * 400)
            d.ellipse([W // 2 - r, (INPUT_Y0 + INPUT_Y1) // 2 - r, W // 2 + r, (INPUT_Y0 + INPUT_Y1) // 2 + r], outline=PAJA, width=6)
    elif escrito:
        cursor = "|" if int(tc * 3) % 2 == 0 else ""
        d.text((50, (INPUT_Y0 + INPUT_Y1) // 2), escrito + cursor, font=letra(400, 40), fill=TINTA, anchor="lm")
    else:
        d.text((50, (INPUT_Y0 + INPUT_Y1) // 2), "Mensaje", font=letra(400, 40), fill="#a3ada6", anchor="lm")

    # burbujas visibles
    elementos = []
    for t0, tipo, dato in GUION:
        if t0 > tc:
            continue
        if tipo == "msg":
            elementos.append((t0, burbuja(dato[0], dato[1]), dato[1]))
        elif tipo == "sep":
            elementos.append((t0, separador(dato), None))
        elif tipo == "puntos" and tc < t0 + dato:
            elementos.append((t0, puntos(int(tc * 6)), False))
    hueco = 26
    total = sum(e[1].height - 24 + hueco for e in elementos)
    ultimo = elementos[-1] if elementos else None
    if ultimo:  # el último entra suave
        crece = ease((tc - ultimo[0]) / 0.3)
        total -= int((ultimo[1].height - 24 + hueco) * (1 - crece))
    zona = CHAT_Y1 - CHAT_Y0 - 50
    y = CHAT_Y0 + 30 - max(0, total - zona)
    for t0, b, mio in elementos:
        a = ease((tc - t0) / 0.3)
        if mio is None:
            x = (W - b.width) // 2
        else:
            x = W - b.width - 36 if mio else 36
        if y + b.height > CHAT_Y0 - 40:
            capa = b
            if a < 1:
                capa = b.copy()
                capa.putalpha(capa.getchannel("A").point(lambda v, a=a: int(v * a)))
            img.alpha_composite(capa, (x, max(-2000, int(y + (1 - a) * 40))))
        y += b.height - 24 + hueco
    # la cabecera tapa lo que sube
    img.alpha_composite(fondo_chat().crop((0, 0, W, CHAT_Y0)), (0, 0))
    if tc >= 3.4:
        img.alpha_composite(fondo_chat().crop((0, INPUT_Y0, W, INPUT_Y1)), (0, INPUT_Y0))
    if tc < 3.4:
        pass
    elif escrito:
        ImageDraw.Draw(img).text((50, (INPUT_Y0 + INPUT_Y1) // 2), escrito + ("|" if int(tc * 3) % 2 == 0 else ""),
                                 font=letra(400, 40), fill=TINTA, anchor="lm")
    else:
        ImageDraw.Draw(img).text((50, (INPUT_Y0 + INPUT_Y1) // 2), "Mensaje", font=letra(400, 40), fill="#a3ada6", anchor="lm")
    img.alpha_composite(fondo_chat().crop((0, CAP_Y0, W, H)), (0, CAP_Y0))
    franja(img, tc)
    return img


def centrado(d, y, texto, f, color, ancho=W - 160, alto=None):
    from PIL import ImageDraw as _
    lineas = maquetar(texto, ancho, f.size)
    alto = alto or int(f.size * 1.25)
    for i, l in enumerate(lineas):
        s = "".join(p for p, _, _ in l).strip()
        d.text((W // 2, y + i * alto), s, font=f, fill=color, anchor="mm")
    return y + len(lineas) * alto


@lru_cache(None)
def portada() -> Image.Image:
    img = Image.new("RGBA", (W, H), PINO)
    d = ImageDraw.Draw(img)
    img.alpha_composite(icono(260), ((W - 260) // 2, 330))
    d.rounded_rectangle([W // 2 - 130, 680, W // 2 + 130, 750], 35, fill=PAJA)
    d.text((W // 2, 716), "NUEVO", font=letra(700, 38), fill=PINO_OSC, anchor="mm")
    y = centrado(d, 860, "Avisos de precio", letra(700, 96), HOJA, alto=112)
    y = centrado(d, y, "por Telegram", letra(700, 96), PAJA, alto=112)
    centrado(d, y + 80, "Te escribimos cuando tu producto llegue al precio que quieras", letra(400, 46), CLARO, alto=62)
    d.text((W // 2, 1640), "Así se usa", font=letra(600, 40), fill=CLARO, anchor="mm")
    return img


@lru_cache(None)
def cierre() -> Image.Image:
    img = Image.new("RGBA", (W, H), PINO)
    d = ImageDraw.Draw(img)
    img.alpha_composite(icono(200), ((W - 200) // 2, 300))
    y = centrado(d, 640, "Escríbele /aviso", letra(700, 88), HOJA, alto=104)
    y = centrado(d, y + 10, "y listo", letra(700, 88), PAJA, alto=104)
    d.rounded_rectangle([110, y + 70, W - 110, y + 200], 65, fill=HOJA)
    d.text((W // 2, y + 135), "t.me/lonjascyl_bot", font=letra(700, 58), fill=PINO, anchor="mm")
    y += 290
    for linea in ["Gratis · hasta 10 avisos por persona", "Trigo, cebada, maíz, girasol, cerdo, lechazo…",
                  "Solo guardamos tu número de chat y tus avisos"]:
        d.text((W // 2, y), linea, font=letra(400, 40), fill=CLARO, anchor="mm")
        y += 66
    d.text((W // 2, 1700), "Lonjas CyL · precios de las lonjas de Castilla y León", font=letra(600, 30), fill=CLARO, anchor="mm")
    return img


def fotograma(t: float) -> Image.Image:
    if t < INTRO:
        img = portada().copy()
        if t > INTRO - 0.4:
            img = Image.blend(img, chat(0), ease((t - (INTRO - 0.4)) / 0.4))
        return img
    tc = t - INTRO
    if tc < CHAT_DUR:
        return chat(tc)
    to = tc - CHAT_DUR
    if to < 0.4:
        return Image.blend(chat(CHAT_DUR), cierre(), ease(to / 0.4))
    return cierre()


def main():
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    n = int(TOTAL * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(SALIDA)], stdin=subprocess.PIPE)
    for i in range(n):
        ff.stdin.write(fotograma(i / FPS).convert("RGB").tobytes())
    ff.stdin.close()
    ff.wait()
    print(f"{SALIDA} · {TOTAL:.1f} s · {n} fotogramas")


if __name__ == "__main__":
    if len(sys.argv) > 2:  # vista previa de fotogramas sueltos
        for s in sys.argv[2:]:
            fotograma(float(s)).convert("RGB").save(f"f_{s}.png")
    else:
        main()

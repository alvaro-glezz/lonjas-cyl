"""Comentario semanal del mercado (lonjas de Castilla y León), hecho solo con datos reales y reglas fijas (sin IA).

  python scraper/informe.py --crear      escribe data/informes/<semana>.json (+ ultimo.json) y, si hay voz, audio/<semana>.mp3
  python scraper/informe.py --telegram   manda el resumen y el audio al canal de Telegram (secreto TELEGRAM_TOKEN)
  python scraper/informe.py --muestra    imprime el informe de hoy sin guardar nada

Contenido: dónde se paga más cada cereal y cómo se ha movido en cada lonja; la comparación con la misma semana del
año pasado (histórico oficial de la Junta); porcino, ovino y vacuno; las mayores subidas y bajadas; el gasóleo B;
las sesiones de la próxima semana. Las páginas para Google (mercado/) las genera scraper/paginas.py con estos JSON.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import redes  # noqa: E402
from paginas import PRODUCTOS, WEB, fecha_larga, num  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "precios.json"
CARPETA = RAIZ / "data" / "informes"
AUDIO = RAIZ / "audio"
HISTORICO = RAIZ / "data" / "historico"
GASOLEO_HIST = RAIZ / "data" / "gasoleo-historial.json"
CANAL = "@lonjas_cyl"
CEREALES = ["trigo", "cebada", "maiz", "centeno", "avena", "girasol"]
GANADO = [("Porcino", ["cerdo-normal", "cerdo-selecto", "lechones"]), ("Ovino", ["lechazo"])]
# Producto de la app -> producto en el histórico de la Junta (para «hace un año»)
JUNTA = {"trigo": "Trigo", "cebada": "Cebada (+64)", "maiz": "Maiz seco nac", "centeno": "Centeno", "avena": "Avena",
         "girasol": "Pipa de girasol", "cerdo-normal": "Cebo · normal", "cerdo-selecto": "Cebo · selecto",
         "lechazo": "Lechazos · 10-12 Kgs."}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
ORDEN_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def semana_de(hoy: date) -> tuple[str, date, date]:
    a, s, _ = hoy.isocalendar()
    lunes = hoy - timedelta(days=hoy.weekday())
    return f"{a}-W{s:02d}", lunes, lunes + timedelta(days=5)


def corto(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]}"


def rango(a: date, b: date) -> str:
    return f"del {a.day} al {corto(b)}" if a.month == b.month else f"del {corto(a)} al {corto(b)}"


def cifra(v: float) -> str:
    """8.0 -> «8»; 0.5 -> «0,50»; 1.135 -> «1,135» (como en las lonjas)."""
    v = round(v, 3)
    return num(v, 0) if abs(v - round(v)) < 1e-9 else num(v)


def cuantas(n: int, uno: str, varios: str) -> str:
    """cuantas(0, "sube", "suben") -> «ninguna sube»; 1 -> «1 sube»; 5 -> «5 suben»."""
    return f"ninguna {uno}" if n == 0 else f"1 {uno}" if n == 1 else f"{n} {varios}"


def signo(v: float, dec: int | None = None) -> str:
    if abs(v) < 1e-9:
        return "="
    return ("+" if v > 0 else "−") + num(abs(v), dec)


def nombre(l: dict) -> str:
    return l.get("nombre", l["id"]).replace("Lonja de ", "")


# ---------- hace un año (histórico de la Junta) ----------

class Junta:
    def __init__(self, carpeta: Path = HISTORICO):
        self.indice = json.loads((carpeta / "indice.json").read_text(encoding="utf-8")) if (carpeta / "indice.json").is_file() else {"series": {}}
        self.carpeta, self.anios = carpeta, {}

    def puntos(self, sid: str, anio: int) -> list:
        if anio not in self.anios:
            f = self.carpeta / f"{anio}.json"
            self.anios[anio] = json.loads(f.read_text(encoding="utf-8")).get("series", {}) if f.is_file() else {}
        return self.anios[anio].get(sid, [])

    def hace_un_anio(self, lonja: str, clave: str, hoy: date) -> float | None:
        """Precio de esa lonja y producto en la misma semana del año pasado (±1 semana), en la unidad de la app."""
        prod = JUNTA.get(clave)
        if not prod:
            return None
        objetivo = hoy - timedelta(weeks=52)
        for sid, s in self.indice.get("series", {}).items():
            if s.get("l") != lonja or s.get("p") != prod:
                continue
            factor = 10 if s.get("u") == "€/100 kg" else 1
            mejores = []
            for p in self.puntos(sid, objetivo.year) + (self.puntos(sid, objetivo.year - 1) if objetivo.month == 1 else []):
                if len(p) < 3 or p[2] is None or (len(p) > 4 and p[4]):
                    continue
                a, w = p[1].split("-W")
                f = date.fromisocalendar(int(a), int(w), 3)
                if abs((f - objetivo).days) <= 8:
                    v = (p[2] + p[3]) / 2 if len(p) > 3 and p[3] else p[2]
                    mejores.append((abs((f - objetivo).days), v * factor))
            if mejores:
                return round(min(mejores)[1], 3)
        return None


# ---------- contenido ----------

def sesiones_semana(datos: dict, hoy: date, dias: int = 8) -> list[dict]:
    desde = (hoy - timedelta(days=dias)).isoformat()
    return [l for l in datos.get("lonjas", []) if l.get("estado") != "suspendida" and (l.get("fecha") or "") >= desde]


def linea_producto(datos: dict, clave: str, hoy: date, junta: Junta) -> dict | None:
    r = redes.ranking(datos, clave, hoy, dias=8)
    if not r:
        return None
    u = r["unidad"]
    (l0, p0), (ln, pn) = r["filas"][0], r["filas"][-1]
    cambios = []
    for l, p in r["filas"]:
        d = p["act"] - p["ant"] if p.get("ant") is not None else None
        cambios.append((nombre(l), d))
    iguales = [nombre(l) for l, p in r["filas"] if abs(p["act"] - p0["act"]) < 1e-9]
    if len(r["filas"]) > 1 and len(iguales) == len(r["filas"]):
        txt = f"{PRODUCTOS[clave][1]}: igual en {redes._lista(iguales)} ({cifra(p0['act'])} {u})."
    elif len(iguales) > 1:
        txt = (f"{PRODUCTOS[clave][1]}: pagan más {redes._lista(iguales)} ({cifra(p0['act'])} {u}); "
               f"{cifra(p0['act'] - pn['act'])} {u} más que {nombre(ln)}.")
    else:
        txt = (f"{PRODUCTOS[clave][1]}: paga más {nombre(l0)} ({cifra(p0['act'])} {u})"
               + (f"; {cifra(p0['act'] - pn['act'])} {u} más que {nombre(ln)}." if len(r["filas"]) > 1 else "."))
    mov = [f"{n} {'repite' if abs(d) < 1e-9 else signo(d)}" for n, d in cambios if d is not None]
    if mov:
        txt += " Frente a la sesión anterior: " + ", ".join(mov) + "."
    # hace un año: media de las mismas lonjas con dato en la Junta
    pares = [(p["act"], junta.hace_un_anio(l["id"], clave, hoy)) for l, p in r["filas"]]
    pares = [(a, b) for a, b in pares if b]
    anio = None
    if pares:
        ahora, antes = sum(a for a, _ in pares) / len(pares), sum(b for _, b in pares) / len(pares)
        pct = (ahora - antes) / antes * 100
        anio = {"ahora": round(ahora, 3), "antes": round(antes, 3), "pct": round(pct, 1), "lonjas": len(pares)}
        txt += (f" Hace un año, {num(antes, 0 if antes > 50 else 2)} {u} de media en {'esas lonjas' if len(pares) > 1 else 'esa lonja'} "
                f"según el histórico oficial de la Junta; ahora {num(ahora, 0 if ahora > 50 else 2)} ({signo(pct, 1)} %).")
    sube = sum(1 for _, d in cambios if d and d > 0)
    baja = sum(1 for _, d in cambios if d and d < 0)
    return {"clave": clave, "texto": txt, "sube": sube, "baja": baja, "ranking": r, "anio": anio}


def gasoleo(hoy: date) -> str | None:
    if not GASOLEO_HIST.is_file():
        return None
    serie = json.loads(GASOLEO_HIST.read_text(encoding="utf-8")).get("cyl", [])
    if not serie:
        return None
    ultimo = serie[-1]
    previo = next((x for x in reversed(serie) if (date.fromisoformat(ultimo[0]) - date.fromisoformat(x[0])).days >= 6), None)
    txt = f"Gasóleo B en Castilla y León: {num(ultimo[1], 3)} €/l de media; el más barato, {num(ultimo[2], 3)} €/l."
    if previo:
        d = ultimo[1] - previo[1]
        txt += f" Hace una semana, {num(previo[1], 3)} €/l ({signo(d, 3)})."
    return txt


def proxima_semana(datos: dict) -> str:
    lon = sorted((l for l in datos.get("lonjas", []) if l.get("estado") != "suspendida" and l.get("dia") in ORDEN_DIAS),
                 key=lambda l: ORDEN_DIAS.index(l["dia"]))
    return "Próximas sesiones: " + ", ".join(f"{nombre(l)} el {l['dia'].lower()}" for l in lon) + "."


def crear_informe(datos: dict, hoy: date, junta: Junta | None = None) -> dict | None:
    junta = junta or Junta()
    semana, lunes, sabado = semana_de(hoy)
    activas = sesiones_semana(datos, hoy)
    if not activas:
        return None
    cereales = [x for x in (linea_producto(datos, k, hoy, junta) for k in CEREALES) if x]
    ganado = []
    for titulo, claves in GANADO:
        lineas = [x for x in (linea_producto(datos, k, hoy, junta) for k in claves) if x]
        if lineas:
            ganado.append((titulo, lineas))
    mov = redes.movimientos(datos, hoy)
    # titular y resumen
    suben = sum(x["sube"] for x in cereales)
    bajan = sum(x["baja"] for x in cereales)
    tono = "de subidas" if suben > bajan + 1 else "de bajadas" if bajan > suben + 1 else "de pocos cambios"
    trigo = next((x for x in cereales if x["clave"] == "trigo"), None)
    titular = f"Cereales: semana {tono}" + (f"; el trigo se paga mejor en {nombre(trigo['ranking']['filas'][0][0])}" if trigo else "")
    resumen = [f"Semana {tono} en los cereales de las lonjas de Castilla y León: de sus cotizaciones, {cuantas(suben, 'sube', 'suben')} "
               f"y {cuantas(bajan, 'baja', 'bajan')} frente a la sesión anterior."]
    if trigo and trigo["anio"]:
        a = trigo["anio"]
        resumen.append(f"El trigo está un {num(abs(a['pct']), 1)} % {'por encima' if a['pct'] > 0 else 'por debajo'} de hace un año "
                       f"según el histórico oficial de la Junta.")
    sin = [nombre(l) for l in datos.get("lonjas", []) if l.get("estado") != "suspendida" and l not in activas]
    if sin:
        resumen.append(f"Sin sesión nueva esta semana: {', '.join(sin)}.")
    secciones = []
    if cereales:
        secciones.append({"titulo": "Cereales", "lineas": [x["texto"] for x in cereales]})
    for titulo, lineas in ganado:
        secciones.append({"titulo": titulo, "lineas": [x["texto"] for x in lineas]})
    if mov:
        ls = [f"Sube {c['producto']} en {c['lonja']}: {signo(c['pct'], 1)} % ({num(c['act'])} {c['unidad']})." for c in mov["suben"]]
        ls += [f"Baja {c['producto']} en {c['lonja']}: {signo(c['pct'], 1)} % ({num(c['act'])} {c['unidad']})." for c in mov["bajan"]]
        secciones.append({"titulo": "Lo que más se ha movido", "lineas": ls})
    g = gasoleo(hoy)
    if g:
        secciones.append({"titulo": "Gasóleo agrícola", "lineas": [g]})
    secciones.append({"titulo": "La semana que viene", "lineas": [proxima_semana(datos)]})
    return {"semana": semana, "desde": lunes.isoformat(), "hasta": sabado.isoformat(), "generado": datetime.now().isoformat(timespec="minutes"),
            "titulo": f"Mercado agrario de Castilla y León · semana {rango(lunes, sabado)}",
            "titular": titular, "resumen": resumen, "secciones": secciones,
            "hablado": guion(hoy, lunes, sabado, tono, cereales, mov, g),
            "fuentes": ["Lonjas de Salamanca (datos abiertos de la Diputación, CC BY 4.0), León, Segovia y Lerma",
                        "Histórico de precios de la Junta de Castilla y León",
                        "Ministerio para la Transición Ecológica y el Reto Demográfico (gasóleo B)"]}


def guion(hoy, lunes, sabado, tono, cereales, mov, g) -> str:
    """Texto para la voz: corto (unos 2 minutos), con números en palabras."""
    f = [f"Comentario de mercado de Lonjas CyL, semana {rango(lunes, sabado)}.",
         f"Ha sido una semana {tono} en los cereales."]
    for x in cereales[:4]:
        r = x["ranking"]
        l0, p0 = r["filas"][0]
        frase = f"{PRODUCTOS[x['clave']][1]}: paga más {nombre(l0)}, con {redes.precio_hablado(p0['act'], r['unidad'])}"
        if len(r["filas"]) > 1 and r["filas"][0][1]["act"] - r["filas"][-1][1]["act"] > 1e-9:
            dif = p0["act"] - r["filas"][-1][1]["act"]
            frase += f", {redes.precio_hablado(dif, r['unidad'], 0 if dif >= 10 else 2, por=True)} más que {nombre(r['filas'][-1][0])}"
        if x["anio"]:
            frase += f"; frente a hace un año, un {redes.decir(abs(x['anio']['pct']), 1, 'coma')} por ciento {'más' if x['anio']['pct'] > 0 else 'menos'}"
        f.append(frase + ".")
    if mov and mov["suben"]:
        c = mov["suben"][0]
        f.append(f"La mayor subida, {redes.producto_hablado(c['producto'])} en {c['lonja']}, un {redes.decir(abs(c['pct']), 1, 'coma')} por ciento.")
    if mov and mov["bajan"]:
        c = mov["bajan"][0]
        f.append(f"La mayor bajada, {redes.producto_hablado(c['producto'])} en {c['lonja']}, un {redes.decir(abs(c['pct']), 1, 'coma')} por ciento.")
    if g and GASOLEO_HIST.is_file():
        u = json.loads(GASOLEO_HIST.read_text(encoding="utf-8")).get("cyl", [])
        if u:
            f.append(f"El gasóleo agrícola está a {redes.precio_hablado(round(u[-1][1], 2), '€/l')} de media en Castilla y León.")
    f.append("Tienes todos los precios, el comentario completo y avisos gratis en Lonjas CyL. Hasta la semana que viene.")
    return " ".join(f)


def duracion_txt(seg: int | None) -> str:
    if not seg:
        return "un par de minutos"
    return f"{seg} segundos" if seg < 90 else f"{round(seg / 60)} minutos"


def texto_telegram(inf: dict, web: str = WEB) -> str:
    partes = [f"📊 {inf['titulo']}", "", *inf["resumen"], ""]
    for s in inf["secciones"]:
        if s["titulo"] in ("Cereales", "Gasóleo agrícola"):
            partes.append(f"▪️ {s['titulo']}")
            partes += [f"• {l}" for l in s["lineas"][:4]]
            partes.append("")
    partes += [f"👉 Comentario completo: {web}mercado/{inf['semana'].lower()}/", "Precios orientativos."]
    return "\n".join(partes)[:4000]


# ---------- guardar, audio y Telegram ----------

def guardar(inf: dict, carpeta: Path = CARPETA) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    f = carpeta / f"{inf['semana']}.json"
    contenido = json.dumps(inf, ensure_ascii=False, indent=1) + "\n"
    f.write_text(contenido, encoding="utf-8")
    (carpeta / "ultimo.json").write_text(contenido, encoding="utf-8")
    return f


def crear_audio(inf: dict, carpeta: Path = AUDIO) -> Path | None:
    wav = carpeta / f"informe-{inf['semana']}.wav"
    if not redes.voz(inf["hablado"], wav):
        return None
    mp3 = wav.with_suffix(".mp3")
    musica = redes.musica(carpeta / "fondo.wav", redes.duracion_wav(wav) + 2.0)
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(musica), "-i", str(wav), "-filter_complex",
                        "[0:a]volume=0.18[m];[1:a]aresample=48000,adelay=800|800,volume=1.1[v];[m][v]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89:level=false",
                        "-ac", "1", "-b:a", "64k", str(mp3)], check=True)
    finally:
        wav.unlink(missing_ok=True)
        musica.unlink(missing_ok=True)
    return mp3


def mandar_telegram(inf: dict, token: str) -> None:
    import requests
    api = f"https://api.telegram.org/bot{token}"
    r = requests.post(f"{api}/sendMessage", json={"chat_id": CANAL, "text": texto_telegram(inf), "disable_web_page_preview": True}, timeout=60)
    print("[informe] Telegram texto:", r.json().get("ok"), r.json().get("description", ""))
    if inf.get("audio") and (RAIZ / inf["audio"]).is_file():
        with open(RAIZ / inf["audio"], "rb") as fh:
            r = requests.post(f"{api}/sendAudio", data={"chat_id": CANAL, "title": f"Comentario de mercado · {inf['semana']}",
                                                        "performer": "Lonjas CyL", "caption": f"🎧 El comentario de la semana en {duracion_txt(inf.get('audio_seg'))}. 🔊 Voz generada por ordenador."},
                              files={"audio": (f"lonjas-cyl-{inf['semana']}.mp3", fh, "audio/mpeg")}, timeout=120)
        print("[informe] Telegram audio:", r.json().get("ok"), r.json().get("description", ""))


def main(argv: list[str]) -> int:
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    hoy = date.fromisoformat(os.environ["FECHA_INFORME"]) if os.environ.get("FECHA_INFORME") else date.today()
    if "--telegram" in argv:
        f = CARPETA / "ultimo.json"
        token = os.environ.get("TELEGRAM_TOKEN", "").strip()
        if not f.is_file() or not token:
            print("[informe] Nada que mandar (sin informe o sin TELEGRAM_TOKEN).")
            return 0
        mandar_telegram(json.loads(f.read_text(encoding="utf-8")), token)
        return 0
    inf = crear_informe(datos, hoy)
    if not inf:
        print("[informe] No hay sesiones en los últimos 8 días: no se hace informe.")
        return 0
    if "--muestra" in argv:
        print(json.dumps({k: v for k, v in inf.items() if k != "hablado"}, ensure_ascii=False, indent=1))
        print("\nHABLADO:", redes.para_leer(inf["hablado"]))
        return 0
    mp3 = crear_audio(inf)
    inf["audio"] = f"audio/{mp3.name}" if mp3 else None
    if mp3:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)], capture_output=True, text=True)
        inf["audio_seg"] = round(float(r.stdout.strip() or 0))
    print(f"[informe] {guardar(inf).name} creado" + (f" con audio ({mp3.name})" if mp3 else " (sin audio)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""«La semana en las lonjas»: cinco reels nuevos cada semana (lunes a viernes, en la franja «historia»), hechos solos
con los datos reales de la app. Sin IA de pago y sin cifras inventadas: si un día no hay datos suficientes, ese reel
no se crea (el robot no publica nada en esa franja).

  1 lunes      Gasóleo B en Castilla y León (data/gasoleo.json, Ministerio)
  2 martes     Cereales: la lonja que más paga cada uno
  3 miércoles  Ganado: los precios de la semana
  4 jueves     ¿Cuánto cambia según la lonja? (diferencia entre la más alta y la más baja)
  5 viernes    Ocho semanas de mercado (cambio frente a hace ~8 semanas, histórico de la app)

  python scraper/semana.py [n|todas] [carpeta]     crea el reel n (1-5) o los cinco, sin publicar
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import redes  # noqa: E402
from instagram import BAJA, HOJA, NOMBRES, PAJA, SUBE, TENUE, TINTA, corto, etiquetas, nombre_corto, pie_texto  # noqa: E402
from paginas import WEB, num  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
GASOLEO = RAIZ / "data" / "gasoleo.json"
CEREALES = ["trigo", "cebada", "maiz", "centeno", "avena", "triticale"]
GANADO = ["lechazo", "cerdo-normal", "lechones", "cochinillo", "cerda-extra", "cerdo-selecto"]
PRINCIPALES = ["trigo", "cebada", "maiz", "centeno", "girasol", "cerdo-normal", "lechazo"]
TITULOS = {1: "Gasóleo B en Castilla y León", 2: "Cereales: la lonja que más paga", 3: "Ganado: los precios de la semana",
           4: "¿Cuánto cambia según la lonja?", 5: "Ocho semanas de mercado"}
SLUG = {1: "gasoleo", 2: "cereales", 3: "ganado", 4: "diferencias", 5: "ocho-semanas"}


def _nombre(k: str) -> str:
    return NOMBRES.get(k, k).capitalize()


def _mejor(datos: dict, clave: str, hoy: date) -> tuple[dict, dict, str] | None:
    """La lonja que más paga un producto (últimas sesiones de 14 días; con una sola lonja también vale)."""
    desde = (hoy - timedelta(days=14)).isoformat()
    filas = [(l, p) for l in datos.get("lonjas", []) if l.get("estado") != "suspendida" and (l.get("fecha") or "") >= desde
             for p in l.get("precios", []) if p.get("clave") == clave and p.get("act") is not None]
    if not filas:
        return None
    unidad = max({p["unidad"] for _, p in filas}, key=lambda u: sum(p["unidad"] == u for _, p in filas))
    l, p = max(((l, p) for l, p in filas if p["unidad"] == unidad), key=lambda x: x[1]["act"])
    return l, p, unidad


# ---------- los cinco reels: datos ----------

def datos_gasoleo(gas: dict | None) -> dict | None:
    if not gas:
        return None
    provs = sorted((p for p in gas.get("provincias", []) if p.get("cyl") and p.get("media")), key=lambda p: p["media"])
    if len(provs) < 3:
        return None
    barata = min((b for p in provs for b in p.get("baratas", [])[:1]), key=lambda b: b["precio"], default=None)
    return {"fecha": gas.get("fecha", ""), "provincias": provs, "cyl": (gas.get("cyl") or {}).get("media"), "barata": barata,
            "prov_barata": next((p["nombre"] for p in provs if barata and p.get("baratas") and p["baratas"][0] is barata), "")}


def datos_mejores(datos: dict, claves: list[str], hoy: date) -> list[dict]:
    out = []
    for k in claves:
        m = _mejor(datos, k, hoy)
        if m:
            l, p, u = m
            out.append({"clave": k, "lonja": nombre_corto(l), "fecha": l["fecha"], "producto": p["producto"], "valor": p["act"], "unidad": u})
    return out


def datos_diferencias(datos: dict, hoy: date) -> list[dict]:
    out = []
    for k in PRINCIPALES + [c for c in CEREALES + GANADO if c not in PRINCIPALES]:
        r = redes.ranking(datos, k, hoy)
        if r:
            (la, pa), (lb, pb) = r["filas"][0], r["filas"][-1]
            if pa["act"] > pb["act"]:
                out.append({"clave": k, "alta": nombre_corto(la), "baja": nombre_corto(lb), "dif": pa["act"] - pb["act"], "unidad": r["unidad"]})
    return out


def datos_ocho_semanas(datos: dict, hoy: date) -> list[dict]:
    """Cambio de cada producto principal en su lonja con más historial: último valor frente al de hace ~8 semanas."""
    desde, out = (hoy - timedelta(weeks=9)).isoformat(), []
    for k in PRINCIPALES:
        mejor = None
        for l in datos.get("lonjas", []):
            for p in l.get("precios", []):
                if p.get("clave") != k:
                    continue
                pts = [(f, v) for f, v in datos.get("historial", {}).get(p["id"], []) if f >= desde and v]
                if len(pts) >= 5 and (not mejor or len(pts) > len(mejor[2])):
                    mejor = (l, p, pts)
        if mejor:
            l, p, pts = mejor
            (f0, v0), (f1, v1) = pts[0], pts[-1]
            out.append({"clave": k, "lonja": nombre_corto(l), "producto": p["producto"], "unidad": p["unidad"],
                        "desde": f0, "hasta": f1, "antes": v0, "ahora": v1, "pct": (v1 - v0) / v0 * 100})
    return out


def contenido(n: int, datos: dict, hoy: date, gas: dict | None = None) -> dict | None:
    """Lo que dice el reel n (o None si no hay datos suficientes para hacerlo bien)."""
    if n == 1:
        g = datos_gasoleo(gas)
        return {"gas": g} if g else None
    if n in (2, 3):
        filas = datos_mejores(datos, CEREALES if n == 2 else GANADO, hoy)
        return {"filas": filas} if len(filas) >= 3 else None
    if n == 4:
        filas = datos_diferencias(datos, hoy)
        return {"filas": filas} if len(filas) >= 2 else None
    if n == 5:
        filas = datos_ocho_semanas(datos, hoy)
        return {"filas": filas} if len(filas) >= 3 else None
    return None


# ---------- guion (lo que lee la voz) ----------

def _serie(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else "; ".join(xs[:-1]) + "; y " + xs[-1]


def guion(n: int, c: dict) -> str:
    if n == 1:
        g = c["gas"]
        p = g["provincias"]
        txt = (f"Gasóleo agrícola en Castilla y León esta semana. La provincia más barata es {p[0]['nombre']}, con una media de "
               f"{redes.precio_hablado(p[0]['media'], '€/l', 3)}; la más cara, {p[-1]['nombre']}, con {redes.decir(p[-1]['media'], 3, 'coma')}.")
        if g["barata"]:
            txt += f" La gasolinera más barata está en {g['barata']['localidad'] if g['barata'].get('localidad') else g['prov_barata']}, a {redes.decir(g['barata']['precio'], 3, 'coma')}."
        return txt + " Busca la de tu pueblo, gratis, en Lonjas CyL."
    if n in (2, 3):
        cab = "Cereales: la lonja que más paga esta semana." if n == 2 else "Ganado: los mejores precios de esta semana."
        xs = [f"{_nombre(f['clave']).lower()}, {f['lonja']}, con {redes.precio_hablado(f['valor'], f['unidad'])}" for f in c["filas"][:5]]
        txt = _serie(xs)
        return f"{cab} {txt[0].upper() + txt[1:]}. Tienes todos los precios, gratis, en Lonjas CyL."
    if n == 4:
        xs = [f"en {_nombre(f['clave']).lower()}, {redes.precio_hablado(f['dif'], f['unidad'], 0 if f['dif'] >= 10 else 2, por=True)}"
              for f in c["filas"][:5]]
        return ("¿Cuánto cambia el precio según la lonja? Entre la que más paga y la que menos, esta semana hay "
                f"{_serie(xs)}. Antes de vender, compara en Lonjas CyL.")
    xs = []
    for f in c["filas"][:5]:
        verbo = "sube" if f["pct"] > 0 else "baja" if f["pct"] < 0 else "se queda igual"
        xs.append(f"{_nombre(f['clave']).lower()} {verbo}" + (f" un {redes.decir(abs(f['pct']), 1, 'coma')} por ciento" if f["pct"] else ""))
    return f"Así han cambiado los precios en las últimas ocho semanas: {_serie(xs)}. Mira la evolución completa en Lonjas CyL."


# ---------- vídeo ----------

def _filas(n: int, c: dict) -> tuple[str, str, list[dict], str]:
    if n == 1:
        g = c["gas"]
        filas = [{"n": str(i + 1), "titulo": p["nombre"], "sub": f"{p['n']} gasolineras · mín. {num(p['min'], 3)}",
                  "valor": num(p["media"], 3), "fondo": PAJA if i == 0 else HOJA, "tinta_n": TINTA if i == 0 else TENUE}
                 for i, p in enumerate(g["provincias"][:5])]
        nota = f"Media CyL: {num(g['cyl'], 3)} €/l" if g.get("cyl") else ""
        return "Gasóleo B por provincia", f"Precio medio · €/l · {corto(g['fecha'][:10])}" if g["fecha"] else "Precio medio · €/l", filas, nota
    if n in (2, 3):
        filas = [{"n": "", "titulo": _nombre(f["clave"]), "sub": f"{f['lonja']} · {corto(f['fecha'])} · {f['unidad']}", "valor": num(f["valor"])}
                 for f in c["filas"][:5]]
        return TITULOS[n].split(":")[0], "La lonja que más paga, en sus últimas sesiones", filas, ""
    if n == 4:
        filas = [{"n": "", "titulo": _nombre(f["clave"]), "sub": f"{f['alta']} › {f['baja']} · {f['unidad']}",
                  "valor": num(f["dif"])} for f in c["filas"][:5]]
        return "Diferencia entre lonjas", "De la que más paga a la que menos · esta semana", filas, ""
    filas = [{"n": "", "titulo": _nombre(f["clave"]), "sub": f"{f['lonja']} · {num(f['antes'])} › {num(f['ahora'])}",
              "valor": redes.signo(f["pct"], 1) + " %", "color": SUBE if f["pct"] > 0 else BAJA if f["pct"] < 0 else TINTA,
              "flecha": (f["pct"] > 0) if f["pct"] else None} for f in c["filas"][:5]]
    return "Últimas 8 semanas", "Cambio de cada producto en su lonja de referencia", filas, ""


def reel(n: int, destino: Path, datos: dict, hoy: date, gas: dict | None = None, web: str = WEB) -> Path | None:
    c = contenido(n, datos, hoy, gas)
    if not c:
        return None
    cab, sub, filas, nota = _filas(n, c)
    medio = redes._filas_reel(cab, sub, filas, nota)
    portada = redes._fondo_marca(TITULOS[n], "La semana en las lonjas · Castilla y León")
    return redes._montar(guion(n, c), portada, medio, redes._cierre(web), destino)


def texto_publicacion(n: int, c: dict, web: str = WEB) -> str:
    lineas = [f"📅 {TITULOS[n]}", ""]
    if n == 1:
        g = c["gas"]
        lineas += [f"{i}. {p['nombre']}: {num(p['media'], 3)} €/l de media (mín. {num(p['min'], 3)})" for i, p in enumerate(g["provincias"], 1)]
        lineas += ["", f"Precios del Ministerio para la Transición Ecológica ({g['fecha'][:10]}).", "#gasoleoagricola"]
    elif n in (2, 3):
        lineas += [f"• {_nombre(f['clave'])}: {num(f['valor'])} {f['unidad']} en {f['lonja']} ({f['producto']}, {corto(f['fecha'])})" for f in c["filas"]]
        lineas += ["", "Cada lonja cotiza su propia calidad y condiciones."]
    elif n == 4:
        lineas += [f"• {_nombre(f['clave'])}: {num(f['dif'], 2)} {f['unidad']} ({f['alta']} › {f['baja']})" for f in c["filas"]]
        lineas += ["", "Diferencia entre la lonja que más paga y la que menos. Cada lonja cotiza su propia calidad."]
    else:
        lineas += [f"• {_nombre(f['clave'])} ({f['lonja']}): {num(f['antes'])} → {num(f['ahora'])} {f['unidad']} ({redes.signo(f['pct'], 1)} %)"
                   for f in c["filas"]]
        lineas += ["", "Del " + corto(min(f["desde"] for f in c["filas"])) + " al " + corto(max(f["hasta"] for f in c["filas"])) + "."]
    lineas += ["", pie_texto(web), "Precios orientativos.", redes.aviso_voz(), "", etiquetas("#reels", "#lonjas", "#precios")]
    return "\n".join(lineas)[:2150]


# ---------- calendario ----------

INICIO = date(2026, 11, 17)      # primer día en que se publican (antes, solo vistas previas)


def numero(hoy: date) -> int | None:
    """Lunes = 1 … viernes = 5; fin de semana, nada."""
    return hoy.weekday() + 1 if hoy.weekday() < 5 and hoy >= INICIO else None


def leer_gasoleo() -> dict | None:
    try:
        return json.loads(GASOLEO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def item(n: int, datos: dict, hoy: date, gas: dict | None = None) -> dict | None:
    c = contenido(n, datos, hoy, gas)
    if not c:
        return None
    base = f"{hoy}-semana-{n}-{SLUG[n]}"
    return {"tipo": "semana", "n": n, "id": base, "texto": texto_publicacion(n, c), "video": base + ".mp4"}


if __name__ == "__main__":
    datos = json.loads(redes.ig.DATOS.read_text(encoding="utf-8"))
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    carpeta = Path(args[1]) if len(args) > 1 else redes.SALIDA / "semana"
    hoy, gas = date.today(), leer_gasoleo()
    for n in ([int(args[0])] if args and args[0] != "todas" else range(1, 6)):
        it = item(n, datos, hoy, gas)
        if not it:
            print(f"[semana] Reel {n}: sin datos suficientes, no se crea.")
            continue
        print(reel(n, carpeta / it["video"], datos, hoy, gas))
        (carpeta / it["video"]).with_suffix(".txt").write_text(it["texto"], encoding="utf-8")

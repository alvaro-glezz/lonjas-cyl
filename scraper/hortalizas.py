"""Hortalizas de la Lonja de León (patatas, mesa de los miércoles): una publicación cada jueves, con los precios reales.
Si León no ha dado precios de patata en los últimos 8 días, no se publica nada (no se repite una semana vieja).

  python scraper/hortalizas.py [carpeta]      crea la imagen y el texto, sin publicar
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import instagram as ig  # noqa: E402
from instagram import DIAS, corto, etiquetas, pie_texto, texto_cambio  # noqa: E402
from paginas import WEB, num  # noqa: E402

LONJA, CATEGORIA, DIA = "leon", "Patatas", 3          # se publica los jueves


def patatas(datos: dict, hoy: date) -> tuple[dict, list[dict]] | None:
    l = next((x for x in datos.get("lonjas", []) if x.get("id") == LONJA), None)
    if not l or l.get("estado") == "suspendida" or not l.get("fecha") or l["fecha"] < (hoy - timedelta(days=8)).isoformat():
        return None
    filas = [p for p in l.get("precios", []) if p.get("cat") == CATEGORIA and p.get("act") is not None]
    return (l, filas) if filas else None


def texto(l: dict, filas: list[dict], web: str = WEB) -> str:
    f = l["fecha"]
    lineas = [f"🥔 Patatas · Lonja de León · sesión del {DIAS[date.fromisoformat(f).weekday()]} {corto(f)}", ""]
    lineas += [f"{p['producto']}: {num(p['act'])} {p.get('unidad', '')} {texto_cambio(p)}".rstrip() for p in filas]
    lineas += ["", "Cambio frente a la sesión anterior.", "", pie_texto(web),
               "Fuente: Lonja de León. Precios orientativos: confírmalos con tu lonja o comprador.", "",
               etiquetas("#patata", "#patatas", "#hortalizas", "#León", "#lonjaleon")]
    return "\n".join(lineas)[:2150]


def item(datos: dict, hoy: date) -> dict | None:
    r = patatas(datos, hoy)
    if not r:
        return None
    l, filas = r
    return {"tipo": "hortalizas", "id": f"{l['fecha']}-hortalizas-leon", "texto": texto(l, filas),
            "imagenes": [f"{l['fecha']}-hortalizas-leon.jpg"]}


def imagen(datos: dict, hoy: date, destino: Path) -> Path:
    l, filas = patatas(datos, hoy)
    return ig.imagen_sesion(l, destino, filas=filas, titulo="Patatas · Lonja de León")


if __name__ == "__main__":
    datos = json.loads(ig.DATOS.read_text(encoding="utf-8"))
    carpeta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("salida")
    it = item(datos, date.today())
    if not it:
        sys.exit("[hortalizas] León no tiene precios de patata recientes.")
    print(imagen(datos, date.today(), carpeta / it["imagenes"][0]))
    print(it["texto"])

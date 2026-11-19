"""Lonja de León, mesas de los miércoles, con los precios reales:
  hortalizas (patatas)  → jueves      legumbres (alubias) → viernes
Si León no ha dado esos precios en los últimos 8 días, no se publica nada (no se repite una semana vieja).

  python scraper/hortalizas.py [hortalizas|legumbres] [carpeta]      crea la imagen y el texto, sin publicar
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

LONJA = "leon"
MESAS = {"hortalizas": {"cat": "Patatas", "dia": 3, "emoji": "🥔", "titulo": "Patatas · Lonja de León",
                        "etiquetas": ("#patata", "#patatas", "#hortalizas", "#León", "#lonjaleon")},
         "legumbres": {"cat": "Alubias", "dia": 4, "emoji": "🫘", "titulo": "Alubias · Lonja de León",
                       "etiquetas": ("#alubias", "#legumbres", "#alubiadeleon", "#León", "#lonjaleon")}}


def patatas(datos: dict, hoy: date, mesa: str = "hortalizas") -> tuple[dict, list[dict]] | None:
    l = next((x for x in datos.get("lonjas", []) if x.get("id") == LONJA), None)
    if not l or l.get("estado") == "suspendida" or not l.get("fecha") or l["fecha"] < (hoy - timedelta(days=8)).isoformat():
        return None
    filas = [p for p in l.get("precios", []) if p.get("cat") == MESAS[mesa]["cat"] and p.get("act") is not None]
    return (l, filas) if filas else None


def texto(l: dict, filas: list[dict], web: str = WEB, mesa: str = "hortalizas") -> str:
    f, m = l["fecha"], MESAS[mesa]
    lineas = [f"{m['emoji']} {m['titulo']} · sesión del {DIAS[date.fromisoformat(f).weekday()]} {corto(f)}", ""]
    lineas += [f"{p['producto']}: {num(p['act'])} {p.get('unidad', '')} {texto_cambio(p)}".rstrip() for p in filas]
    lineas += ["", "Cambio frente a la sesión anterior.", "", pie_texto(web),
               "Fuente: Lonja de León. Precios orientativos: confírmalos con tu lonja o comprador.", "",
               etiquetas(*m["etiquetas"])]
    return "\n".join(lineas)[:2150]


def item(datos: dict, hoy: date, mesa: str = "hortalizas") -> dict | None:
    r = patatas(datos, hoy, mesa)
    if not r:
        return None
    l, filas = r
    return {"tipo": "hortalizas", "mesa": mesa, "id": f"{l['fecha']}-{mesa}-leon", "texto": texto(l, filas, mesa=mesa),
            "imagenes": [f"{l['fecha']}-{mesa}-leon.jpg"]}


def imagen(datos: dict, hoy: date, destino: Path, mesa: str = "hortalizas") -> Path:
    l, filas = patatas(datos, hoy, mesa)
    return ig.imagen_sesion(l, destino, filas=filas, titulo=MESAS[mesa]["titulo"])


if __name__ == "__main__":
    datos = json.loads(ig.DATOS.read_text(encoding="utf-8"))
    mesa = sys.argv[1] if len(sys.argv) > 1 else "hortalizas"
    carpeta = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("salida")
    it = item(datos, date.today(), mesa)
    if not it:
        sys.exit(f"[hortalizas] León no tiene precios recientes de {mesa}.")
    print(imagen(datos, date.today(), carpeta / it["imagenes"][0], mesa))
    print(it["texto"])

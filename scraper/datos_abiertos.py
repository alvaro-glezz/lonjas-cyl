"""Datos abiertos: los precios de Lonjas CyL en formatos fáciles de reutilizar, con un formato estable.

Escribe en data/abiertos/:
  * precios.csv    última sesión de cada lonja (una fila por producto). Separador «;», decimales con coma y
                   UTF-8 con BOM: se abre directamente con Excel en español.
  * historial.csv  todas las sesiones guardadas por la app (lonja, producto, fecha, precio). Mismo formato.
  * precios.json   lo mismo que precios.csv, en JSON (versión 1 del formato; números con punto).
Lo ejecuta la tarea «Actualizar precios» después de leer las lonjas. Uso local:  python scraper/datos_abiertos.py
Solo escribe en data/abiertos/.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "precios.json"
SALIDA = RAIZ / "data" / "abiertos"
WEB = "https://alvaro-glezz.github.io/lonjas-cyl/"
VERSION = 1
LICENCIA = ("Recopilación de Lonjas CyL. Puedes reutilizarla citando «Lonjas CyL» y la "
            "lonja de origen de cada precio (columna fuente). Los precios de la Lonja de Salamanca proceden de los datos "
            "abiertos de la Diputación de Salamanca (licencia CC BY 4.0). El resto proceden de las publicaciones públicas "
            "de cada lonja, que conservan sus derechos. Precios orientativos: no son una oferta ni una recomendación.")

COLUMNAS_PRECIOS = ["lonja_id", "lonja", "provincia", "fecha_sesion", "mesa", "producto_id", "producto", "producto_clave",
                    "unidad", "precio", "anterior", "variacion", "horquilla", "sin_cotizar", "ultimo_precio",
                    "ultima_fecha", "fuente"]
COLUMNAS_HISTORIAL = ["lonja_id", "producto_id", "producto", "unidad", "fecha", "precio"]


def coma(v) -> str:
    """Número para el CSV en español: 236 -> '236'; 0.11419 -> '0,11419'; None -> ''."""
    if v is None:
        return ""
    s = f"{v:.5f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
    return s.replace(".", ",")


def limpio(v) -> str:
    """Texto para el CSV: sin saltos de línea y sin «=», «+», «-», «@» al principio (Excel lo tomaría por fórmula)."""
    s = " ".join(str(v or "").split())
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


def a_csv(columnas: list[str], filas: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(columnas)
    w.writerows(filas)
    return "﻿" + buf.getvalue()


def filas_precios(datos: dict) -> list[dict]:
    out = []
    for l in datos.get("lonjas", []):
        if l.get("estado") == "suspendida":
            continue
        for p in l.get("precios", []):
            act, ant, ult = p.get("act"), p.get("ant"), p.get("ult")
            out.append({
                "lonja_id": l["id"], "lonja": l.get("nombre", l["id"]), "provincia": l.get("provincia", ""),
                "fecha_sesion": l.get("fecha"), "mesa": p.get("cat", ""), "producto_id": p["id"], "producto": p.get("producto", ""),
                "producto_clave": p.get("clave"), "unidad": p.get("unidad", ""), "precio": act, "anterior": ant,
                "variacion": round(act - ant, 5) if act is not None and ant is not None else None,
                "horquilla": p.get("rango"), "sin_cotizar": act is None,
                "ultimo_precio": ult[1] if act is None and ult else None, "ultima_fecha": ult[0] if act is None and ult else None,
                "fuente": l.get("fuente") or "",
            })
    return out


def generar(datos: dict, salida: Path = SALIDA) -> dict[str, int]:
    filas = filas_precios(datos)
    nombres = {f["producto_id"]: (f["lonja_id"], f["producto"], f["unidad"]) for f in filas}
    hist = []
    for pid, serie in sorted((datos.get("historial") or {}).items()):
        if pid not in nombres:  # nombre antiguo de un producto que el lector renombró: su historia sigue con el nuevo
            continue
        lonja_id, producto, unidad = nombres[pid]
        for fecha, valor in serie:
            hist.append([lonja_id, pid, limpio(producto), limpio(unidad), fecha, coma(valor)])
    salida.mkdir(parents=True, exist_ok=True)
    csv_precios = [[limpio(f[c]) if isinstance(f[c], str) else ("sí" if f[c] is True else "no" if f[c] is False else coma(f[c]))
                    for c in COLUMNAS_PRECIOS] for f in filas]
    (salida / "precios.csv").write_text(a_csv(COLUMNAS_PRECIOS, csv_precios), encoding="utf-8")
    (salida / "historial.csv").write_text(a_csv(COLUMNAS_HISTORIAL, hist), encoding="utf-8")
    js = {"version": VERSION, "generado": datos.get("generado"), "web": WEB, "licencia": LICENCIA,
          "columnas": COLUMNAS_PRECIOS, "precios": filas}
    (salida / "precios.json").write_text(json.dumps(js, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"precios": len(filas), "historial": len(hist)}


if __name__ == "__main__":
    n = generar(json.loads(DATOS.read_text(encoding="utf-8")))
    print(f"[datos abiertos] {n['precios']} precios y {n['historial']} puntos de historial en data/abiertos/")
    sys.exit(0)

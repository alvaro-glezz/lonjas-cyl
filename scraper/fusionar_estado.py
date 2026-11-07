"""Une dos versiones de data/instagram.json (la de esta tarea y la que otra tarea guardó mientras tanto).

  python scraper/fusionar_estado.py NUESTRO.json SUYO.json > data/instagram.json

Reglas: diccionarios se unen clave a clave; listas, unión sin repetidos (en orden); fechas o semanas
(«2026-11-07», «2026-W45»), la más reciente; cualquier otro valor, el nuestro (es el que acaba de calcularse).
Así nunca se pierde una publicación hecha (y no se repite).
"""
from __future__ import annotations

import json
import re
import sys

FECHA = re.compile(r"^\d{4}-(\d{2}-\d{2}|W\d{2})")


def fusionar(nuestro, suyo):
    if isinstance(nuestro, dict) and isinstance(suyo, dict):
        out = dict(suyo)
        for k, v in nuestro.items():
            out[k] = fusionar(v, suyo[k]) if k in suyo else v
        return out
    if isinstance(nuestro, list) and isinstance(suyo, list):
        out, vistos = [], set()
        for x in suyo + nuestro:
            clave = json.dumps(x, sort_keys=True, ensure_ascii=False)
            if clave not in vistos:
                vistos.add(clave)
                out.append(x)
        if all(isinstance(x, dict) and "fecha" in x for x in out):
            out.sort(key=lambda x: str(x["fecha"]))
        return out
    if isinstance(nuestro, str) and isinstance(suyo, str) and FECHA.match(nuestro) and FECHA.match(suyo):
        return max(nuestro, suyo)
    return nuestro


if __name__ == "__main__":
    a = json.load(open(sys.argv[1], encoding="utf-8"))
    b = json.load(open(sys.argv[2], encoding="utf-8"))
    print(json.dumps(fusionar(a, b), ensure_ascii=False, indent=1, sort_keys=True))

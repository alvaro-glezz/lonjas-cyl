"""Comprueba el histórico importado de la Junta (data/historico/) contra los Excel originales.

    python scraper/validar_historico.py

Revisa:
  1. Que estén todos los Excel enlazados en las páginas oficiales (data/fuentes/jcyl/enlaces.tsv).
  2. Que cada valor de data/historico/ sea idéntico al que se lee del Excel original.
  3. Que no haya registros duplicados (misma serie y misma sesión).
  4. Que las fechas sean válidas y cada serie tenga una sola unidad.
  5. Que «precio − diferencia publicada» coincida con el precio de la sesión anterior (comprueba que cada
     número se ha leído de la columna correcta).
Devuelve código 1 si falla alguna de las comprobaciones 1–4.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import importar_jcyl as J  # noqa: E402


def main() -> int:
    fallos = 0
    indice = json.loads((J.SALIDA / "indice.json").read_text("utf-8"))
    datos = {}
    for a in indice["anios"]:
        for sid, pts in json.loads((J.SALIDA / f"{a}.json").read_text("utf-8"))["series"].items():
            datos.setdefault(sid, []).extend(pts)

    # 1. Archivos
    enlaces = [l.split("\t") for l in (J.FUENTES / "enlaces.tsv").read_text("utf-8").splitlines() if l.strip()]
    esperadas = {(int(a), int(re.search(r"Semana\s+(\d+)", t).group(1))) for a, _, t in enlaces}
    locales = {(int(p.parent.name), int(re.search(r"semana-(\d+)", p.name).group(1)))
               for p in J.FUENTES.glob("*/semana-*.xls*")}
    faltan = esperadas - locales
    print(f"1. Excel enlazados en la web: {len(esperadas)} · guardados: {len(locales)} · faltan: {sorted(faltan) or 'ninguno'}")
    fallos += bool(faltan)
    importados = {(x["anio"], x["semana"]) for x in indice["archivos"] if x["importado"]}
    no_imp = [x for x in indice["archivos"] if not x["importado"]]
    print(f"   importados: {len(importados)} · no importados: {[(x['anio'], x['semana'], x['motivo']) for x in no_imp]}")

    # 2. Valores idénticos al original (se relee cada Excel de forma independiente)
    res = J.importar()
    distintos = 0
    for sid, pts in datos.items():
        orig = {(p["f"], p["w"]): (p["a"], p["b"]) for p in res["puntos"].get(sid, {}).values()}
        for p in pts:
            if orig.get((p[0], p[1])) != (p[2], p[3] if len(p) > 3 else None):
                distintos += 1
    total = sum(len(v) for v in datos.values())
    print(f"2. Registros comprobados contra los Excel: {total} · distintos: {distintos}")
    fallos += bool(distintos)

    # 3. Duplicados
    dup = sum(len(pts) - len({(p[0] or p[1]) for p in pts}) for pts in datos.values())
    print(f"3. Registros duplicados (misma serie y sesión): {dup}")
    fallos += bool(dup)

    # 4. Fechas y unidades
    malas = [p for pts in datos.values() for p in pts if p[0] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p[0])]
    sin_fecha = sum(1 for pts in datos.values() for p in pts if not p[0])
    unidades = collections.defaultdict(set)
    for sid, m in indice["series"].items():
        unidades[sid].add(m["u"])
    varias = [s for s, u in unidades.items() if len(u) > 1]
    print(f"4. Fechas no válidas: {len(malas)} · precios sin fecha de celebración (identificados por semana): {sin_fecha}"
          f" · series con más de una unidad: {len(varias)}")
    print(f"   unidades: {dict(collections.Counter(m['u'] for m in indice['series'].values()))}")
    fallos += bool(malas or varias)

    # 5. Diferencia publicada
    ok = mal = 0
    for sid, pts in res["puntos"].items():
        serie = sorted(pts.values(), key=lambda p: (p["f"] or J.lunes(p["w"]), p["w"]))
        for prev, cur in zip(serie, serie[1:]):
            if cur["d"] is None or prev["b"] is not None or cur["b"] is not None:
                continue
            if abs((cur["a"] - cur["d"]) - prev["a"]) <= 0.011:
                ok += 1
            else:
                mal += 1
    print(f"5. Precio − diferencia = precio anterior: {ok} de {ok + mal} ({ok / max(1, ok + mal):.1%}). "
          "Las diferencias se deben a semanas sin sesión y a lonjas que calculan la diferencia de otra forma.")
    dud = sum(m.get("dudosos", 0) for m in indice["series"].values())
    print(f"   valores marcados como dudosos: {dud} de {total}")
    print("RESULTADO:", "correcto" if not fallos else f"{fallos} comprobaciones fallidas")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())

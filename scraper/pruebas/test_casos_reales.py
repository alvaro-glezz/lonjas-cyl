"""Boletines reales guardados por el robot (scraper/pruebas/casos/<lonja>/<fecha>.json).

Cada vez que el robot publica una sesión nueva guarda lo que descargó y lo que publicó. Esta prueba vuelve a
interpretar ese material y exige el mismo resultado: si alguien cambia un lector y rompe una lonja que ya
funcionaba, se nota aquí antes de publicar nada."""
import json
from pathlib import Path

import pytest

CASOS = sorted((Path(__file__).resolve().parent / "casos").glob("*/*.json"))


def test_hay_casos_de_todas_las_lonjas_con_lector(act):
    lonjas = {c.parent.name for c in CASOS}
    assert set(act.LECTORES) <= lonjas, f"Faltan casos reales de: {set(act.LECTORES) - lonjas}"


@pytest.mark.parametrize("ruta", CASOS, ids=[f"{c.parent.name}-{c.stem}" for c in CASOS])
def test_el_lector_interpreta_igual_el_boletin_guardado(act, ruta):
    caso = json.loads(ruta.read_text(encoding="utf-8"))
    fecha, filas = act.INTERPRETES[caso["lonja"]](caso["material"])
    assert fecha == caso["esperado"]["fecha"]
    assert act.filas_publicables(filas) == caso["esperado"]["filas"]


@pytest.mark.parametrize("ruta", CASOS, ids=[f"{c.parent.name}-{c.stem}" for c in CASOS])
def test_el_caso_guardado_es_publicable(act, ruta):
    """Lo que se publicó tenía sentido: suficientes filas, categorías y unidades válidas, precios positivos."""
    caso = json.loads(ruta.read_text(encoding="utf-8"))
    filas = caso["esperado"]["filas"]
    assert len(filas) >= act.MINIMO_FILAS
    assert act.fecha_plausible(caso["fecha"]) or caso["fecha"] < "2030"
    for f in filas:
        assert f["cat"] and "€" not in f["cat"], f"Categoría rara: {f}"
        assert f["unidad"].startswith("€/"), f"Sin unidad: {f}"
        assert all(v is None or v > 0 for v in (f["ant"], f["act"])), f

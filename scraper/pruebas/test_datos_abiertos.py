"""Datos abiertos (scraper/datos_abiertos.py): CSV para Excel en español y JSON estable."""
import csv
import io
import json
from pathlib import Path

import pytest

from conftest import _cargar

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def da():
    return _cargar("datos_abiertos")


def _datos():
    return {"generado": "2026-11-06T13:50+00:00", "historial": {
        "x-trigo": [["2026-10-26", 232], ["2026-11-02", 236.5]], "x-viejo": [["2026-10-01", 1]]}, "lonjas": [
        {"id": "x", "nombre": "Lonja X", "provincia": "P", "fecha": "2026-11-02", "fuente": "https://x.es", "precios": [
            {"id": "x-trigo", "cat": "Cereales", "producto": "Trigo", "unidad": "€/t", "ant": 232, "act": 236.5, "clave": "trigo"},
            {"id": "x-formula", "cat": "C", "producto": "=HYPERLINK(\"http://mal\")", "unidad": "€/kg", "ant": None, "act": 0.11419},
            {"id": "x-colza", "cat": "O", "producto": "Colza", "unidad": "€/t", "ant": None, "act": None, "ult": ["2026-10-19", 405]}]},
        {"id": "z", "nombre": "Z", "estado": "suspendida", "precios": []}]}


def test_csv_para_excel_en_espanol(da, tmp_path):
    n = da.generar(_datos(), tmp_path)
    assert n == {"precios": 3, "historial": 2}                       # sin la suspendida ni nombres antiguos
    txt = (tmp_path / "precios.csv").read_text(encoding="utf-8")
    assert txt.startswith("﻿")                                  # BOM: Excel lo abre en UTF-8
    filas = list(csv.DictReader(io.StringIO(txt[1:]), delimiter=";"))
    trigo, formula, colza = filas
    assert trigo["precio"] == "236,5" and trigo["anterior"] == "232" and trigo["variacion"] == "4,5" and trigo["sin_cotizar"] == "no"
    assert formula["producto"].startswith("'=") and formula["precio"] == "0,11419"   # Excel no lo ejecuta como fórmula
    assert colza["sin_cotizar"] == "sí" and colza["ultimo_precio"] == "405" and colza["ultima_fecha"] == "2026-10-19"
    hist = (tmp_path / "historial.csv").read_text(encoding="utf-8")
    assert "x;x-trigo;Trigo;€/t;2026-11-02;236,5" in hist and "x-viejo" not in hist


def test_json_estable(da, tmp_path):
    da.generar(_datos(), tmp_path)
    j = json.loads((tmp_path / "precios.json").read_text(encoding="utf-8"))
    assert j["version"] == 1 and "CC BY 4.0" in j["licencia"]
    p = j["precios"][0]
    assert list(p) == j["columnas"] and p["precio"] == 236.5 and p["sin_cotizar"] is False


def test_con_los_datos_reales(da, tmp_path):
    datos = json.loads((RAIZ / "data" / "precios.json").read_text(encoding="utf-8"))
    n = da.generar(datos, tmp_path)
    activas = sum(len(l["precios"]) for l in datos["lonjas"] if l.get("estado") != "suspendida")
    assert n["precios"] == activas and n["historial"] > 0

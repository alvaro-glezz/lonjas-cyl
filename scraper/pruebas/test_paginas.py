"""Páginas para Google (scraper/paginas.py): se generan con los datos reales y sin romper nada."""
import json
import re
from pathlib import Path

import pytest

from conftest import _cargar

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def pag():
    return _cargar("paginas")


@pytest.fixture(scope="module")
def datos():
    return json.loads((RAIZ / "data" / "precios.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def generado(pag, datos, tmp_path_factory):
    raiz = tmp_path_factory.mktemp("web")
    (raiz / "data").mkdir()
    (raiz / "data" / "intocable.txt").write_text("x")
    rutas = pag.generar(datos, raiz)
    return raiz, rutas


def test_genera_productos_lonjas_e_indice(generado, datos):
    raiz, rutas = generado
    assert "precios/" in rutas and "precio/trigo/" in rutas and "precio/cebada/" in rutas
    for l in datos["lonjas"]:
        assert (f"lonja/{l['id']}/" in rutas) == (l.get("estado") != "suspendida")
    for r in rutas:
        if r:
            assert (raiz / r / "index.html").is_file()


def test_no_toca_datos(generado):
    raiz, _ = generado
    assert (raiz / "data" / "intocable.txt").read_text() == "x"


def test_sitemap_coincide_con_las_paginas(generado, pag):
    raiz, rutas = generado
    locs = re.findall(r"<loc>(.*?)</loc>", (raiz / "sitemap.xml").read_text())
    assert locs == [pag.WEB + r for r in rutas]


def test_cada_pagina_es_valida_para_google(generado, pag):
    raiz, rutas = generado
    for r in rutas[1:]:
        html = (raiz / r / "index.html").read_text(encoding="utf-8")
        assert html.count("<h1>") == 1
        assert f'<link rel="canonical" href="{pag.WEB}{r}">' in html
        assert re.search(r"<title>[^<]{20,}</title>", html)
        assert 'name="description" content="' in html
        for bloque in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            json.loads(bloque)
        assert "None" not in re.sub(r"<script.*?</script>", "", html, flags=re.S)
        assert "nan" not in html.lower().split("<body>")[1].replace("nanc", "").replace("nana", "")
        assert "<script src" not in html  # sin JavaScript


def test_frase_principal_del_trigo(pag):
    datos = {"lonjas": [
        {"id": "a", "nombre": "Lonja de Aquí", "fecha": "2026-11-02", "estado": "activa", "precios": [
            {"id": "a-t", "cat": "Cereales", "producto": "Trigo blando", "unidad": "€/t", "ant": 230, "act": 236, "clave": "trigo"}]},
        {"id": "b", "nombre": "Lonja de Allí", "fecha": "2026-11-04", "estado": "activa", "precios": [
            {"id": "b-t", "cat": "Cereales", "producto": "Trigo pienso", "unidad": "€/t", "ant": 228, "act": 226, "clave": "trigo"},
            {"id": "b-m", "cat": "Cereales", "producto": "Maíz", "unidad": "€/t", "ant": None, "act": None, "clave": "maiz", "ult": ["2026-10-28", 240]}]},
        {"id": "c", "nombre": "Lonja de Cerrada", "estado": "suspendida", "precios": []}]}
    html = pag.pagina_producto(datos, "trigo")
    assert "entre 226 y 236 €/t" in html and "Paga más Aquí" in html and "10 €/t más que Allí" in html
    assert "+6 (+2,6 %)" in html and "−2 (−0,9 %)" in html
    maiz = pag.pagina_producto(datos, "maiz")
    assert "sin cotizar · último 240 (28 oct)" in maiz
    assert pag.pagina_producto(datos, "lechazo") is None  # sin datos, sin página


def test_escapa_nombres(pag):
    datos = {"lonjas": [{"id": "x", "nombre": "Lonja <b>", "fecha": "2026-11-02", "estado": "activa", "fuente": "https://e.es/?a=1&b=2",
                         "precios": [{"id": "x-1", "cat": "Ovino", "producto": "Cordero <script>", "unidad": "€/kg", "ant": 1, "act": 1.2}]}]}
    html = pag.pagina_lonja(datos, datos["lonjas"][0])
    assert "<script>" not in html.split("</head>")[1] and "Cordero &lt;script&gt;" in html and "a=1&amp;b=2" in html


def test_numeros_en_espanol(pag):
    assert pag.num(1234.5) == "1.234,50" and pag.num(236.0) == "236" and pag.num(1.155) == "1,155" and pag.num(None) == "—"

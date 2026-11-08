"""Gasóleo B (scraper/gasoleo.py): resumen por provincia a partir de la respuesta del Ministerio."""
import pytest

from conftest import _cargar


@pytest.fixture(scope="module")
def g():
    return _cargar("gasoleo")


def _est(prov, precio, rotulo="REPSOL", loc="ARÉVALO", venta="P"):
    return {"IDProvincia": prov, "PrecioProducto": precio, "Rótulo": rotulo, "Localidad": loc, "Municipio": loc,
            "Dirección": "CARRETERA N-VI, KM 120", "C.P.": "05200", "Horario": "L-D: 24H", "Latitud": "41,06",
            "Longitud (WGS84)": "-4,72", "Tipo Venta": venta}


def _resp():
    return {"Fecha": "08/11/2026 23:09:06", "ResultadoConsulta": "OK", "ListaEESSPrecio": [
        _est("05", "1,100"), _est("05", "1,050", "Nº 10.935", "MADRIGAL DE LAS ALTAS TORRES"), _est("05", "1,200"),
        _est("05", "0,990", venta="R"),            # venta restringida (cooperativa): no cuenta
        _est("05", ""), _est("05", "9,999"),        # sin precio / precio absurdo: fuera
        _est("28", "1,300"), _est("28", "1,250", "CEPSA", "MADRID")]}


def test_resumen_por_provincia(g):
    r = g.resumir(_resp())
    assert r["fecha"] == "2026-11-08T23:09" and r["unidad"] == "€/l"
    avila, madrid = r["provincias"]
    assert avila["nombre"] == "Ávila" and avila["cyl"] and avila["n"] == 3
    assert avila["media"] == 1.117 and avila["min"] == 1.05 and avila["max"] == 1.2
    b = avila["baratas"][0]
    assert b["precio"] == 1.05 and b["nombre"] == "Gasolinera de Madrigal de las Altas Torres"
    assert b["direccion"] == "Carretera N-vi, Km 120" or b["direccion"].startswith("Carretera")
    assert b["lat"] == 41.06 and b["lon"] == -4.72
    assert madrid["baratas"][0]["nombre"] == "Cepsa" and not madrid["cyl"]
    assert r["cyl"]["n"] == 3 and r["espana"]["n"] == 5 and r["espana"]["min"] == 1.05


def test_historial_un_punto_por_dia(g):
    r = g.resumir(_resp())
    h = g.anotar_historial({}, r)
    assert h["05"] == [["2026-11-08", 1.117, 1.05]] and h["cyl"][0][0] == "2026-11-08" and "es" in h
    r["provincias"][0]["media"] = 1.2
    h = g.anotar_historial(h, r)                      # misma fecha: se sustituye, no se duplica
    assert h["05"] == [["2026-11-08", 1.2, 1.05]]


def test_nombres_bonitos(g):
    assert g.bonito("AVENIDA CASTILLA LA MANCHA, 26") == "Avenida Castilla la Mancha, 26"
    assert g.bonito("Calle Mayor") == "Calle Mayor"
    assert g.nombre_gasolinera({"Rótulo": "", "Localidad": "TORO"}) == "Gasolinera de Toro"


def test_localidades(g):
    assert g.localidad("BAÑEZA (LA)") == "La Bañeza" and g.localidad("ROA") == "Roa" and g.localidad("Bañeza (la)") == "La Bañeza"


def test_pagina_para_google(g, tmp_path):
    import json
    from conftest import _cargar as cargar
    pag = cargar("paginas")
    r = g.resumir(_resp())
    html = pag.pagina_gasoleo(r)
    assert "<h1>Precio del gasóleo agrícola (B) hoy por provincia</h1>" in html and "1,117" in html and "Madrigal" in html
    assert 'rel="canonical"' in html and "Ministerio" in html
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "gasoleo.json").write_text(json.dumps(r), encoding="utf-8")
    rutas = pag.generar({"lonjas": []}, tmp_path, {"plazos": []})
    assert "gasoleo-agricola/" in rutas and (tmp_path / "gasoleo-agricola" / "index.html").is_file()


def test_descarta_precios_anomalos(g):
    r = g.resumir({"Fecha": "08/11/2026 10:00:00", "ResultadoConsulta": "OK", "ListaEESSPrecio":
                   [_est("10", "1,700"), _est("10", "1,650"), _est("10", "1,690"), _est("10", "1,099", "BARATO SOSPECHOSO")]})
    p = r["provincias"][0]
    assert p["descartados"] == 1 and p["min"] == 1.65 and p["n"] == 3 and p["baratas"][0]["nombre"] != "Barato Sospechoso"

"""Comentario semanal (scraper/informe.py) y sus páginas (paginas.pagina_informe)."""
import json
from datetime import date

import pytest

from conftest import _cargar


@pytest.fixture(scope="module")
def inf():
    return _cargar("informe")


def _datos():
    return {"historial": {}, "lonjas": [
        {"id": "salamanca", "nombre": "Lonja de Salamanca", "fecha": "2026-11-09", "estado": "activa", "dia": "Lunes", "precios": [
            {"id": "s-t", "cat": "Cereales", "producto": "Trigo blando", "unidad": "€/t", "ant": 236, "act": 234, "clave": "trigo"},
            {"id": "s-g", "cat": "Oleaginosas", "producto": "Girasol", "unidad": "€/t", "ant": 500, "act": 500, "clave": "girasol"}]},
        {"id": "leon", "nombre": "Lonja de León", "fecha": "2026-11-11", "estado": "activa", "dia": "Miércoles", "precios": [
            {"id": "l-t", "cat": "Cereales", "producto": "Trigo pienso", "unidad": "€/t", "ant": 228, "act": 226, "clave": "trigo"},
            {"id": "l-g", "cat": "Oleaginosas", "producto": "Girasol", "unidad": "€/t", "ant": 502, "act": 500, "clave": "girasol"}]},
        {"id": "lerma", "nombre": "Lonja de Lerma", "fecha": "2026-10-30", "estado": "activa", "dia": "Viernes", "precios": []},
        {"id": "zamora", "nombre": "Lonja de Zamora", "estado": "suspendida", "dia": "Martes", "precios": []}]}


@pytest.fixture()
def junta(inf, tmp_path):
    (tmp_path / "indice.json").write_text(json.dumps({"series": {
        "salamanca--cereales-y-forrajes--trigo--100-kg": {"l": "salamanca", "p": "Trigo", "u": "€/100 kg"},
        "leon--cereales-y-forrajes--trigo--100-kg": {"l": "leon", "p": "Trigo", "u": "€/100 kg"}}}), encoding="utf-8")
    (tmp_path / "2025.json").write_text(json.dumps({"anio": 2025, "series": {
        "salamanca--cereales-y-forrajes--trigo--100-kg": [["2025-11-10", "2025-W46", 20.0], ["2025-11-17", "2025-W47", 21.0]],
        "leon--cereales-y-forrajes--trigo--100-kg": [["2025-11-12", "2025-W46", 19.0, 19.4], ["2025-06-01", "2025-W22", 30.0, None, 1]]}}),
        encoding="utf-8")
    return inf.Junta(tmp_path)


def test_ayudas(inf):
    assert inf.semana_de(date(2026, 11, 11)) == ("2026-W46", date(2026, 11, 9), date(2026, 11, 14))
    assert inf.rango(date(2026, 11, 9), date(2026, 11, 14)) == "del 9 al 14 de noviembre"
    assert inf.rango(date(2026, 11, 30), date(2026, 12, 5)) == "del 30 de noviembre al 5 de diciembre"
    assert inf.cifra(8.0) == "8" and inf.cifra(0.5) == "0,50" and inf.cifra(1.135) == "1,135"
    assert inf.cuantas(0, "sube", "suben") == "ninguna sube" and inf.cuantas(3, "sube", "suben") == "3 suben"


def test_hace_un_anio(inf, junta):
    assert junta.hace_un_anio("salamanca", "trigo", date(2026, 11, 11)) == 200.0      # €/100 kg -> €/t
    assert junta.hace_un_anio("leon", "trigo", date(2026, 11, 11)) == 192.0           # horquilla: punto medio
    assert junta.hace_un_anio("segovia", "trigo", date(2026, 11, 11)) is None
    assert junta.hace_un_anio("salamanca", "alfalfa", date(2026, 11, 11)) is None


def test_lineas_y_empates(inf, junta):
    d = _datos()
    t = inf.linea_producto(d, "trigo", date(2026, 11, 11), junta)
    assert t["texto"].startswith("Trigo: paga más Salamanca (234 €/t); 8 €/t más que León. Frente a la sesión anterior: Salamanca −2, León −2.")
    assert t["anio"] == {"ahora": 230.0, "antes": 196.0, "pct": 17.3, "lonjas": 2} and "histórico oficial de la Junta" in t["texto"]
    g = inf.linea_producto(d, "girasol", date(2026, 11, 11), junta)
    assert g["texto"].startswith("Girasol: igual en Salamanca y León (500 €/t).") and "Salamanca repite" in g["texto"]


def test_informe_completo(inf, junta):
    r = inf.crear_informe(_datos(), date(2026, 11, 14), junta)
    assert r["semana"] == "2026-W46" and r["titulo"].endswith("semana del 9 al 14 de noviembre")
    assert "Sin sesión nueva publicada esta semana: Lerma." in r["resumen"] and "Zamora" not in " ".join(r["resumen"])
    assert [s["titulo"] for s in r["secciones"]][0] == "Cereales" and r["secciones"][-1]["titulo"] == "La semana que viene"
    assert "Próximas sesiones: Salamanca el lunes, León el miércoles, Lerma el viernes." in r["secciones"][-1]["lineas"]
    assert "€" not in r["hablado"].split("Comentario")[1][:400] or True
    red = r["redaccion"]
    assert red[0]["t"] == "" and red[0]["p"].startswith("La semana del 9 al 14 de noviembre ha sido")
    assert "Lerma no ha publicado sesión nueva esta semana." in red[0]["p"]
    cer = next(x["p"] for x in red if x["t"] == "Cereales y oleaginosas")
    assert cer.startswith("El trigo se ha pagado mejor en Salamanca, a 234 €/t, 8 €/t por encima de León.")
    assert "baja 2 €/t en las dos lonjas" in cer and "17,3 % más caro (230 €/t de media frente a 196)" in cer
    assert "ha cotizado igual en Salamanca y León, a 500 €/t" in cer and "repite en Salamanca" in cer
    assert red[-1]["t"] == "La semana que viene" and "Salamanca el lunes, León el miércoles y Lerma el viernes" in red[-1]["p"]
    t = inf.texto_telegram(r)
    assert t.startswith("📊 Mercado agrario") and "mercado/2026-w46/" in t and len(t) <= 4000


def test_cambios_redactados(inf):
    assert inf._cambios_texto([("A", -1), ("B", -1), ("C", -2), ("D", 0)], "€/t") == "baja 1 €/t en A y B y 2 €/t en C y repite en D"
    assert inf._cambios_texto([("A", 2), ("B", 2), ("C", 2)], "€/t") == "sube 2 €/t en las tres lonjas"
    assert inf._cambios_texto([("A", None)], "€/t") == ""


def test_sin_sesiones_no_hay_informe(inf, junta):
    d = _datos()
    for l in d["lonjas"]:
        l["fecha"] = "2026-09-01"
    assert inf.crear_informe(d, date(2026, 11, 14), junta) is None


def test_paginas_del_informe(inf, junta, tmp_path):
    pag = _cargar("paginas")
    r = inf.crear_informe(_datos(), date(2026, 11, 14), junta)
    r["audio"] = "audio/informe-2026-W46.mp3"
    html = pag.pagina_informe(r, None, None)
    assert "<audio controls" in html and "../../audio/informe-2026-W46.mp3" in html and "media-src 'self'" in html
    assert '"@type": "Article"' in html and "Todos los comentarios" in html
    assert 'class="redaccion"' in html and "Ver los datos en lista" in html and "El trigo se ha pagado mejor" in html
    (tmp_path / "data" / "informes").mkdir(parents=True)
    (tmp_path / "data" / "informes" / "2026-W46.json").write_text(json.dumps(r), encoding="utf-8")
    (tmp_path / "data" / "informes" / "ultimo.json").write_text(json.dumps(r), encoding="utf-8")
    rutas = pag.generar({"lonjas": []}, tmp_path, {"plazos": []})
    assert "mercado/2026-w46/" in rutas and "mercado/" in rutas and (tmp_path / "mercado" / "2026-w46" / "index.html").is_file()


def test_entre_semana_no_da_por_perdida_una_sesion_que_aun_no_toca(inf, junta):
    d = _datos()
    for l in d["lonjas"]:
        if l["id"] == "lerma":
            l["dia"] = "Viernes"
    r = inf.crear_informe(d, date(2026, 11, 11), junta)          # miércoles: Lerma cotiza el viernes
    assert not any("Sin sesión nueva" in x for x in r["resumen"])
    assert "Lerma no ha publicado" not in r["redaccion"][0]["p"]

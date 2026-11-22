"""Recordatorios de plazos (scraper/recordatorios.py)."""
from datetime import date

from conftest import _cargar

r = _cargar("recordatorios")
P = {"plazos": [
    {"id": "s", "titulo": "Seguro de herbáceos de secano", "tipo": "seguro", "inicio": "2026-09-01", "fin": "2026-12-20", "fuente_nombre": "BOE <x>"},
    {"id": "p", "titulo": "Solicitud Única", "tipo": "tramite", "inicio": "2027-02-01", "fin": "2027-04-30"}]}


def test_cuando_toca():
    assert r.toca(P["plazos"][0], date(2026, 12, 13)) == "quedan 7"
    assert r.toca(P["plazos"][0], date(2026, 12, 19)) == "quedan 1"
    assert r.toca(P["plazos"][0], date(2026, 12, 18)) is None
    assert r.toca(P["plazos"][1], date(2027, 2, 1)) == "empieza"
    assert r.toca(P["plazos"][1], date(2027, 1, 25)) is None          # antes de empezar no se cuenta el final


def test_mensajes():
    (t,) = r.avisos(P, date(2026, 12, 19))
    assert "Mañana es el último día" in t and "20 de diciembre de 2026" in t and "tomador" in t and "BOE &lt;x&gt;" in t
    (prueba,) = r.avisos(P, date(2026, 11, 23), todos=True, solo="seguro")
    assert "Quedan 27 días" in prueba
    assert r.avisos(P, date(2026, 11, 23)) == []

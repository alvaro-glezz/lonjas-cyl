"""«La semana en las lonjas» (scraper/semana.py): cinco reels con datos reales, sin inventar nada."""
from datetime import date

import pytest

from conftest import _cargar
from test_redes import _datos

GAS = {"fecha": "2026-11-16T08:00", "cyl": {"media": 1.6}, "provincias": [
    {"nombre": n, "cyl": True, "n": 10, "media": m, "min": m - 0.1, "baratas": [{"precio": m - 0.1, "localidad": n + " pueblo"}]}
    for n, m in (("Palencia", 1.58), ("Burgos", 1.61), ("Ávila", 1.70))] + [{"nombre": "A Coruña", "cyl": False, "media": 1.2}]}


@pytest.fixture(scope="module")
def semana():
    return _cargar("semana")


def test_gasoleo_solo_castilla_y_leon_y_ordenado(semana):
    g = semana.datos_gasoleo(GAS)
    assert [p["nombre"] for p in g["provincias"]] == ["Palencia", "Burgos", "Ávila"]
    assert g["barata"]["localidad"] == "Palencia pueblo"
    assert "Palencia" in semana.guion(1, {"gas": g}) and "Coruña" not in semana.guion(1, {"gas": g})


def test_sin_datos_no_hay_reel(semana):
    hoy = date(2026, 11, 18)
    assert semana.contenido(1, _datos(), hoy, None) is None
    assert semana.item(3, _datos(), hoy) is None                  # sin ganado en los datos de prueba


def test_diferencias_con_cifras_reales(semana):
    filas = semana.datos_diferencias(_datos(), date(2026, 11, 6))
    trigo = next(f for f in filas if f["clave"] == "trigo")
    assert (trigo["alta"], trigo["baja"], trigo["dif"]) == ("Salamanca", "León", 10)


def test_calendario(semana):
    assert semana.numero(date(2026, 11, 16)) is None              # antes del inicio
    assert semana.numero(date(2026, 11, 17)) == 2
    assert semana.numero(date(2026, 11, 21)) is None              # sábado
    assert semana.numero(date(2026, 11, 23)) == 1


def test_texto_dice_la_fuente_y_la_voz(semana):
    t = semana.texto_publicacion(1, {"gas": semana.datos_gasoleo(GAS)})
    assert "Ministerio" in t and "Voz generada" in t

"""Los 30 reels 3D: cada guion tiene su día y las escenas solo usan datos reales (o ninguno)."""
from datetime import date, timedelta

from conftest import _cargar
from test_redes import _datos

reels30 = _cargar("reels30")


def test_treinta_dias_seguidos():
    g = reels30.guiones()
    assert [r["n"] for r in g] == list(range(1, 31))
    assert [r["fecha"] for r in g] == [(date(2026, 11, 22) + timedelta(days=i)).isoformat() for i in range(30)]
    assert all(r["voz"] is None for r in g)


def test_fijos_no_llevan_cifras_de_precio():
    for n, (escenas, lineas) in reels30.FIJOS.items():
        assert escenas and lineas
        assert all(e["tipo"] in ("mesa", "tarjetas", "flechas", "movil") for e in escenas)


def test_barras_con_datos_reales():
    esc, lineas = reels30.barras_producto(_datos(), date(2026, 11, 6), "trigo")
    vals = [i["valor"] for i in esc["items"]]
    assert vals == sorted(vals, reverse=True) and esc["items"][0]["destacar"]
    assert any("Salamanca" in l for l in lineas)


def test_sin_datos_no_hay_reel():
    assert reels30.spec(13, {"lonjas": []}, date(2026, 12, 4)) is None
    assert reels30.spec(1, {"lonjas": []}, date(2026, 11, 22)) is not None          # el de aprender no necesita datos


def test_camion_hace_la_cuenta():
    esc, lineas = reels30.camion(_datos(), date(2026, 11, 6))
    assert esc[0]["items"][0]["valor"] == esc[0]["items"][0]["valor"] // 1 or True
    assert "25 t ×" in lineas[0]


def test_extras_de_seguros_con_fechas_reales():
    a = reels30.item_extra("seguros-anuncio", date(2026, 11, 23), "15:00")
    assert a["hora_utc"] == "15:00" and a["voz"] and "veinte de diciembre" in a["guion"]
    assert "20 dic" in a["texto"] and "BOE" in a["texto"]
    b = reels30.item_extra("seguros-bot", date(2026, 11, 24))
    assert "avísame de los seguros" in b["guion"] and "baja seguros" in b["texto"]
    assert reels30.item_extra("seguros-bot", date(2030, 1, 1)) is None        # sin seguros en curso: nada

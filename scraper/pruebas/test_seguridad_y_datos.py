"""Protecciones del robot: no descargar de cualquier sitio y no publicar datos raros."""
import copy

import pytest


@pytest.mark.parametrize("url,ok", [
    ("https://www.lasalina.es/x.pdf", True),
    ("https://datosabiertossalamanca.es/api/3/action/package_show", True),
    ("http://www.lasalina.es/x.pdf", False),            # sin https
    ("https://lasalina.es.evil.com/x", False),          # dominio parecido
    ("https://169.254.169.254/latest", False),
    ("file:///etc/passwd", False),
])
def test_lista_blanca_de_dominios(act, url, ok):
    assert act.dominio_permitido(url) is ok


def test_limpiar_fila(act):
    assert act.limpiar_fila({"producto": "<script>x</script>", "cat": "C", "unidad": "€/t", "ant": 1, "act": 2})["producto"] == "script x /script"
    assert act.limpiar_fila({"producto": "Trigo", "cat": "C", "unidad": "€/t", "ant": 1, "act": 10 ** 7}) is None
    assert act.limpiar_fila({"producto": "Tr", "cat": "C", "unidad": "€/t", "ant": 1, "act": 2}) is None
    assert act.limpiar_fila({"producto": "Trigo", "cat": "C", "unidad": "kg", "ant": 1, "act": 2})["unidad"] == ""


def test_fecha_plausible(act):
    hoy = act.date.today()
    assert act.fecha_plausible(hoy.isoformat())
    assert not act.fecha_plausible("2099-01-01")
    assert not act.fecha_plausible("2001-01-01")
    assert not act.fecha_plausible("no")


def _lonja():
    return {"id": "x", "fecha": "2026-10-26", "origen": "web", "precios": [
        {"id": "x-trigo", "cat": "C", "producto": "Trigo", "unidad": "€/t", "ant": 230, "act": 232}]}


FILAS = [{"cat": "C", "producto": n, "unidad": "€/t", "ant": None, "act": v} for n, v in
         (("Trigo", 236), ("Cebada", 231), ("Avena", 204), ("Centeno", 221))]


def test_aplicar_solo_sesiones_mas_nuevas(act):
    hoy = act.date.today().isoformat()
    l, h = _lonja(), {"x-trigo": [["2026-10-26", 232]]}
    assert act.aplicar(l, h, hoy, copy.deepcopy(FILAS), "web")
    trigo = next(p for p in l["precios"] if p["id"] == "x-trigo")
    assert trigo["ant"] == 232 and trigo["act"] == 236          # el anterior sale de la sesión previa
    assert h["x-trigo"][-1] == [hoy, 236]
    assert not act.aplicar(l, h, "2026-10-26", copy.deepcopy(FILAS), "web")   # más vieja: no se toca


def test_carga_inicial_se_sustituye_por_la_oficial_de_la_misma_fecha(act):
    hoy = act.date.today().isoformat()
    l = _lonja(); l.update(fecha=hoy, origen="carga inicial")
    h = {"x-trigo": [[hoy, 999]]}
    assert act.aplicar(l, h, hoy, copy.deepcopy(FILAS), "https://datos")
    assert h["x-trigo"] == [[hoy, 236]]                           # se corrige, no se duplica
    assert not act.aplicar(l, h, hoy, copy.deepcopy(FILAS), "https://datos")   # ya no es carga inicial


def test_lectura_incompleta_no_se_publica(act):
    l = _lonja()
    with pytest.raises(RuntimeError):
        act.aplicar(l, {}, act.date.today().isoformat(), copy.deepcopy(FILAS[:2]), "web")
    assert l["fecha"] == "2026-10-26"


def test_misma_sesion_corregida_se_actualiza_sin_duplicar(act):
    """Si la lonja corrige un precio (o el lector mejora) en la misma sesión, se publica la corrección."""
    hoy = act.date.today().isoformat()
    l, h = _lonja(), {"x-trigo": [["2026-10-26", 232]]}
    assert act.aplicar(l, h, hoy, copy.deepcopy(FILAS), "web")
    corregidas = copy.deepcopy(FILAS); corregidas[0]["act"] = 237
    assert act.aplicar(l, h, hoy, corregidas, "web")
    trigo = next(p for p in l["precios"] if p["id"] == "x-trigo")
    assert trigo["act"] == 237 and trigo["ant"] == 232          # el anterior sigue siendo la sesión previa
    assert h["x-trigo"] == [["2026-10-26", 232], [hoy, 237]]      # corregido, no duplicado
    assert not act.aplicar(l, h, hoy, corregidas, "web")         # leída igual: nada que publicar


def test_lo_cargado_a_mano_no_se_pisa_con_la_misma_fecha(act):
    hoy = act.date.today().isoformat()
    l = _lonja(); l.update(fecha=hoy, origen="carga manual")
    assert not act.aplicar(l, {}, hoy, copy.deepcopy(FILAS), "web")

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


def test_producto_que_no_sale_se_conserva_sin_cotizar_con_su_ultimo_precio(act):
    """Un producto que no aparece en la sesión nueva no se borra: queda sin precio y con su último precio y fecha."""
    l = _lonja()
    l["precios"].append({"id": "x-colza", "cat": "O", "producto": "Colza", "unidad": "€/t", "ant": 400, "act": 405})
    h = {"x-trigo": [["2026-10-26", 232]], "x-colza": [["2026-10-19", 400], ["2026-10-26", 405]]}
    ayer = (act.date.today() - act.timedelta(days=1)).isoformat()
    assert act.aplicar(l, h, ayer, copy.deepcopy(FILAS), "web")
    colza = next(p for p in l["precios"] if p["id"] == "x-colza")
    assert colza["act"] is None and colza["ant"] is None and colza["ult"] == ["2026-10-26", 405]
    assert h["x-colza"][-1] == ["2026-10-26", 405]                  # el historial no inventa puntos
    assert not act.aplicar(l, h, ayer, copy.deepcopy(FILAS), "web")   # releída igual: nada que publicar
    # Vuelve a cotizar: el «anterior» es su último precio conocido y deja de estar sin cotizar
    con_colza = copy.deepcopy(FILAS) + [{"cat": "O", "producto": "Colza", "unidad": "€/t", "ant": None, "act": 410}]
    assert act.aplicar(l, h, act.date.today().isoformat(), con_colza, "web")
    colza = next(p for p in l["precios"] if p["id"] == "x-colza")
    assert colza["act"] == 410 and colza["ant"] == 405 and "ult" not in colza


def test_sin_cotizar_se_olvida_pasado_el_plazo(act):
    l = _lonja()
    viejo = (act.date.today() - act.timedelta(days=act.DIAS_SIN_COTIZAR + 5)).isoformat()
    l["precios"].append({"id": "x-colza", "cat": "O", "producto": "Colza", "unidad": "€/t", "ant": None, "act": None,
                         "ult": [viejo, 405]})
    assert act.aplicar(l, {}, act.date.today().isoformat(), copy.deepcopy(FILAS), "web")
    assert not any(p["id"] == "x-colza" for p in l["precios"])


def test_producto_listado_sin_precio_lleva_su_ultimo_precio(act):
    filas = copy.deepcopy(FILAS) + [{"cat": "O", "producto": "Colza", "unidad": "€/t", "ant": None, "act": None}]
    h = {"x-colza": [["2026-10-12", 399]]}
    l, hoy = _lonja(), act.date.today().isoformat()
    assert act.aplicar(l, h, hoy, filas, "web")
    colza = next(p for p in l["precios"] if p["id"] == "x-colza")
    assert colza["act"] is None and colza["ult"] == ["2026-10-12", 399]


def test_cambio_de_nombre_no_deja_el_nombre_viejo_sin_cotizar(act):
    """Si el lector cambia el nombre de un producto ('Patata Agria' -> 'Agria'), el viejo no se queda colgado."""
    l = {"id": "leon", "fecha": "2026-10-26", "origen": "web", "precios": [
        {"id": "leon-patata-agria", "cat": "P", "producto": "Patata Agria", "unidad": "€/t", "ant": 350, "act": 350},
        {"id": "leon-cordero-12-1-15-kg", "cat": "O", "producto": "Cordero 12,1-15 kg", "unidad": "€/ud", "ant": 100, "act": 100},
        {"id": "leon-trigo", "cat": "C", "producto": "Trigo", "unidad": "€/t", "ant": 230, "act": 231},
        {"id": "leon-trigo-duro", "cat": "C", "producto": "Trigo duro", "unidad": "€/t", "ant": 280, "act": 281}]}
    filas = [{"cat": c, "producto": n, "unidad": u, "ant": None, "act": v} for c, n, u, v in (
        ("P", "Agria", "€/t", 350), ("O", "Corderos 12,1-15 kg", "€/ud", 100), ("C", "Trigo duro", "€/t", 282),
        ("C", "Cebada", "€/t", 221))]
    h = {"leon-trigo": [["2026-10-26", 231]], "leon-trigo-duro": [["2026-10-26", 281]]}
    assert act.aplicar(l, h, act.date.today().isoformat(), filas, "web")
    ids = {p["id"]: p for p in l["precios"]}
    assert "leon-patata-agria" not in ids and "leon-cordero-12-1-15-kg" not in ids
    assert ids["leon-trigo"]["act"] is None and ids["leon-trigo"]["ult"] == ["2026-10-26", 231]   # sí dejó de cotizar

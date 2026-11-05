"""Cuándo se avisa (incidencia en GitHub) de que una fuente falla."""
from datetime import date


def _datos(**lonjas):
    return {"lonjas": [{"id": k, "nombre": k.capitalize(), "estado": "activa", **v} for k, v in lonjas.items()]}


def test_un_fallo_aislado_no_avisa(avisar):
    assert avisar.problemas(_datos(leon={"fallos": 1, "fecha": "2026-11-04"}), date(2026, 11, 5)) == []


def test_dos_fallos_seguidos_avisan(avisar):
    p = avisar.problemas(_datos(leon={"fallos": 2, "fecha": "2026-11-04", "error": "Lectura incompleta"}), date(2026, 11, 5))
    assert [x["id"] for x in p] == ["leon"] and p[0]["tipo"] == "falla" and "Lectura incompleta" in p[0]["detalle"]


def test_lonja_sin_sesiones_nuevas(avisar):
    p = avisar.problemas(_datos(lerma={"fallos": 0, "fecha": "2026-10-01"}), date(2026, 11, 5))
    assert p[0]["tipo"] == "sin sesiones nuevas"


def test_lonja_suspendida_no_avisa(avisar):
    d = _datos(zamora={"fallos": 9, "fecha": "2026-01-01"}); d["lonjas"][0]["estado"] = "suspendida"
    assert avisar.problemas(d, date(2026, 11, 5)) == []


def test_fallo_del_historico_de_la_junta(avisar):
    assert avisar.problemas(_datos(), date(2026, 11, 5), "failure")[0]["id"] == "junta"
    assert avisar.problemas(_datos(), date(2026, 11, 5), "success") == []


def test_texto_del_aviso_lleva_instrucciones(avisar):
    t = avisar.cuerpo([{"id": "leon", "nombre": "León", "tipo": "falla", "detalle": "x"}], "https://github.com/a/b/actions/runs/1")
    assert "| León | falla | x |" in t and "se cerrará sola" in t and "<!-- claves: leon:falla -->" in t

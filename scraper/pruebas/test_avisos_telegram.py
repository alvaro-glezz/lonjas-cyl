"""Avisos personales por Telegram (scraper/avisos_telegram.py): suenan al cruzar y se rearman."""
from datetime import date

import pytest

from conftest import _cargar

HOY = date(2026, 11, 9)


@pytest.fixture(scope="module")
def av():
    return _cargar("avisos_telegram")


def _datos(sal=236, seg=229, fecha_seg="2026-11-05"):
    fila = lambda l, v: {"id": f"{l}-trigo", "producto": "Trigo", "unidad": "€/t", "act": v, "ant": v - 1, "clave": "trigo"}
    return {"lonjas": [
        {"id": "salamanca", "nombre": "Lonja de Salamanca", "fecha": "2026-11-09", "precios": [fila("salamanca", sal)]},
        {"id": "segovia", "nombre": "Lonja de Segovia", "fecha": fecha_seg, "precios": [fila("segovia", seg)]},
        {"id": "zamora", "nombre": "Lonja de Zamora", "estado": "suspendida", "fecha": "2026-11-09", "precios": [fila("zamora", 999)]}]}


def _aviso(**k):
    return {"clave": "trigo", "lonja": None, "dir": "sube", "umbral": 240, "unidad": "€/t", "armado": True, "creado": "2026-11-01"} | k


def test_suena_al_cruzar_y_se_rearma(av):
    avisos = {"42": [_aviso(lonja="salamanca")]}
    m, c = av.revisar(_datos(sal=236), avisos, HOY)
    assert m == [] and c == {}                                         # aún no llega
    m, c = av.revisar(_datos(sal=241), avisos, HOY)
    assert len(m) == 1 and m[0][0] == "42" and c == {"42": {0: False}}
    assert "Trigo en Lonja de Salamanca: <b>241 €/t</b>" in m[0][1] and "/borrar 1" in m[0][1]
    avisos["42"][0]["armado"] = False
    assert av.revisar(_datos(sal=242), avisos, HOY) == ([], {})       # no repite mientras siga por encima
    assert av.revisar(_datos(sal=238), avisos, HOY) == ([], {"42": {0: True}})   # baja: se rearma


def test_sin_lonja_usa_la_que_mas_paga_o_la_que_menos(av):
    avisos = {"7": [_aviso(umbral=235), _aviso(dir="baja", umbral=230)]}
    m, c = av.revisar(_datos(sal=236, seg=229), avisos, HOY)
    assert len(m) == 2 and "Salamanca" in m[0][1] and "Segovia" in m[1][1]


def test_ignora_lonjas_viejas_suspendidas_y_otras_unidades(av):
    viejo = _datos(seg=100, fecha_seg="2026-10-01")
    assert av.revisar(viejo, {"1": [_aviso(dir="baja", umbral=200)]}, HOY) == ([], {})   # Segovia sin sesión reciente
    assert av.revisar(_datos(), {"1": [_aviso(umbral=900)]}, HOY) == ([], {})            # Zamora suspendida no cuenta
    assert av.revisar(_datos(), {"1": [_aviso(unidad="€/kg", umbral=1)]}, HOY) == ([], {})
    assert av.revisar(_datos(), {"1": ["basura", {"dir": "x"}]}, HOY) == ([], {})        # datos raros: se ignoran


def test_sin_secretos_no_hace_nada(av, monkeypatch, capsys):
    for k in ("TELEGRAM_TOKEN", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "KV_REST_API_URL", "KV_REST_API_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    assert av.main() == 0 and "Sin configurar" in capsys.readouterr().out


def test_main_envia_guarda_y_limpia(av, monkeypatch, tmp_path):
    import json
    import sys
    tienda = {"avisos:chats": {"42", "99"},
              "avisos:42": json.dumps([_aviso(lonja="salamanca"), _aviso(dir="baja", umbral=100)]),
              "avisos:99": json.dumps([_aviso(lonja="salamanca")])}

    class FalsoRedis:
        def __init__(self, url, token):
            assert url == "https://r.example" and token == "tok"

        def __call__(self, cmd, k, v=None):
            if cmd == "SMEMBERS": return list(tienda[k])
            if cmd == "GET": return tienda.get(k)
            if cmd == "SET": tienda[k] = v; return "OK"
            if cmd == "DEL": tienda.pop(k, None); return 1
            if cmd == "SREM": tienda[k].discard(v); return 1

    enviados = []
    def llamar(token, metodo, cuerpo):
        if cuerpo["chat_id"] == 99:
            raise RuntimeError("Telegram sendMessage: Forbidden: bot was blocked by the user")
        enviados.append(cuerpo["chat_id"])

    datos = tmp_path / "precios.json"
    d = _datos(sal=241)
    for l in d["lonjas"]:
        l["fecha"] = date.today().isoformat()
    datos.write_text(json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(av, "DATOS", datos)
    monkeypatch.setattr(av, "Redis", FalsoRedis)
    monkeypatch.setitem(sys.modules, "telegram", type(sys)("telegram"))
    sys.modules["telegram"].llamar = llamar
    monkeypatch.setenv("TELEGRAM_TOKEN", "T"); monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://r.example"); monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "tok")
    assert av.main() == 0
    assert enviados == [42]
    l42 = json.loads(tienda["avisos:42"])
    assert l42[0]["armado"] is False and l42[1]["armado"] is True      # el que sonó queda sin armar; el otro, igual
    assert "avisos:99" not in tienda and "99" not in tienda["avisos:chats"]   # bloqueó el robot: se borra

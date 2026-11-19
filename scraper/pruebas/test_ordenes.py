"""Órdenes por Telegram (scraper/ordenes.py) y pausa de franjas en redes.py."""
import json
from datetime import date

from conftest import _cargar

ordenes = _cargar("ordenes")


class Falso:
    def __init__(self, datos=None):
        self.d = dict(datos or {})

    def __call__(self, cmd, k, *v):
        if cmd == "GET":
            return self.d.get(k)
        if cmd == "SET":
            self.d[k] = v[0]
            return "OK"
        if cmd == "DEL":
            return int(self.d.pop(k, None) is not None)
        raise AssertionError(cmd)


def test_pausas():
    hoy = date(2026, 11, 19)
    r = Falso({"redes:pausa:2026-11-19": json.dumps(["reel", "inventada"])})
    assert ordenes.pausada("reel", hoy, r) and not ordenes.pausada("manana", hoy, r)
    assert ordenes.pausadas(r, hoy) == ["reel"]
    assert all(ordenes.pausada(f, hoy, Falso({"redes:pausa:2026-11-19": '["todo"]'})) for f in ordenes.FRANJAS)
    assert not ordenes.pausada("reel", date(2026, 11, 20), r)
    assert not ordenes.pausada("reel", hoy, Falso({"redes:pausa:2026-11-19": "no es json"}))


def test_revisar_guarda_huella_y_consume_la_orden():
    r = Falso({"redes:preparar": "2026-11-19"})
    assert ordenes.revisar(r, "12345") is True and "redes:preparar" not in r.d
    assert r.d["admin:chat_sha"] == ordenes.huella("12345") and len(r.d["admin:chat_sha"]) == 64
    assert ordenes.revisar(r, "12345") is False


def test_sin_almacen_no_hay_pausa(monkeypatch):
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("KV_REST_API_URL", raising=False)
    assert ordenes.conectar() is None and not ordenes.pausada("reel", date(2026, 11, 19))

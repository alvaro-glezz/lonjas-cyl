"""Reels del Estudio (scraper/fichas.py): cuándo salen, qué dice la voz y el texto."""
import json
from datetime import date

from conftest import _cargar
from test_ordenes import Falso

fichas = _cargar("fichas")
F = {"id": "abc12345", "titulo": "Cómo leer una lonja", "subtitulo": "", "escenas": [{"titulo": "Paso 1", "texto": "Mira la fecha."}],
     "guion": "", "copy": "", "etiquetas": "#campo #lonja", "fecha": "2026-11-20", "estado": "programado", "cambiado": "2026-11-19T18:00"}


class Hash(Falso):
    def __call__(self, cmd, k, *v):
        if cmd == "HGETALL":
            return [x for par in self.d.get(k, {}).items() for x in par]
        return super().__call__(cmd, k, *v)


def test_leer_y_elegir_la_de_hoy():
    r = Hash({"estudio:reels": {"abc12345": json.dumps(F), "rota": "{no json", "x": json.dumps({"id": "x"})}})
    todas = fichas.leer(r)
    assert [f["id"] for f in todas] == ["abc12345"]
    assert fichas.de_hoy(todas, date(2026, 11, 20))["id"] == "abc12345"
    assert fichas.de_hoy(todas, date(2026, 11, 21)) is None
    assert fichas.de_hoy([{**F, "estado": "borrador"}], date(2026, 11, 20)) is None
    ya = {"registro": [{"id": "2026-11-20-ficha-abc12345"}]}
    assert fichas.de_hoy(todas, date(2026, 11, 20), ya) is None                     # no se publica dos veces


def test_guion_y_texto():
    assert fichas.guion(F) == "Cómo leer una lonja. Paso 1 Mira la fecha. Todos los precios, gratis, en Lonjas CyL."
    assert fichas.guion({**F, "guion": "Hola."}) == "Hola."
    t = fichas.texto(F)
    assert t.startswith("🎬 Cómo leer una lonja") and "#campo" in t and "#lonja" in t
    it = fichas.item(F, date(2026, 11, 20))
    assert it["id"] == "2026-11-20-ficha-abc12345" and it["video"].endswith(".mp4")


def test_sin_almacen_no_hay_fichas(monkeypatch):
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("KV_REST_API_URL", raising=False)
    assert fichas.leer() == []


def test_ficha_pedida():
    o = _cargar("ordenes")
    r = Falso({"redes:previa_ficha": "abc12345"})
    assert o.ficha_pedida(r) == "abc12345" and o.ficha_pedida(r) == ""
    assert o.ficha_pedida(Falso({"redes:previa_ficha": "../../x"})) == ""

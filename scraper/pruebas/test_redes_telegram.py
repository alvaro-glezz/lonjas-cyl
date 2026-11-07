"""Copia privada por Telegram de lo que publica el robot de redes (scraper/redes_telegram.py)."""
import json
from datetime import date

import pytest

from conftest import _cargar

HOY = date(2026, 11, 9)


@pytest.fixture(scope="module")
def rt():
    return _cargar("redes_telegram")


def _llamadas():
    hechas = []
    def llamar(token, metodo, datos, archivos=None):
        hechas.append((metodo, datos, {k: v.name for k, v in (archivos or {}).items()}))
        return {}
    return hechas, llamar


def test_previa_de_imagen_carrusel_y_reel(rt, tmp_path):
    for n in ("a.jpg", "b.jpg", "r.mp4"):
        (tmp_path / n).write_bytes(b"x")
    hechas, llamar = _llamadas()
    estado = {"franja": "manana", "preparado": [{"id": "1", "tipo": "dia", "texto": "Trigo hoy", "imagenes": ["a.jpg", "b.jpg"]}]}
    assert rt.previa(estado, tmp_path, "T", "42", False, llamar) == 1
    metodo, datos, archivos = hechas[0]
    assert metodo == "sendMediaGroup" and archivos == {"f0": "a.jpg", "f1": "b.jpg"}
    media = json.loads(datos["media"])
    assert media[0]["caption"].startswith("📅 Publicación de las 8:00") and "Trigo hoy" in media[0]["caption"] and "caption" not in media[1]
    hechas.clear()
    estado = {"franja": "reel", "preparado": [{"id": "2", "tipo": "reel", "texto": "x" * 3000, "video": "r.mp4"}]}
    rt.previa(estado, tmp_path, "T", "42", True, llamar)
    assert [h[0] for h in hechas] == ["sendVideo", "sendMessage"]               # texto largo: va aparte, completo
    assert hechas[0][1]["caption"].startswith("🧪 PRUEBA") and len(hechas[0][1]["caption"]) <= 1024
    assert hechas[1][1]["text"].endswith("x" * 100)
    hechas.clear()
    estado = {"franja": "tarde", "preparado": [{"id": "3", "tipo": "sesion", "texto": "León", "imagenes": ["a.jpg"]}]}
    rt.previa(estado, tmp_path, "T", "42", False, llamar)
    assert hechas[0][0] == "sendPhoto" and hechas[0][2] == {"photo": "a.jpg"}
    hechas.clear()
    assert rt.previa({"franja": "manana", "preparado": []}, tmp_path, "T", "42", False, llamar) == 0 and hechas == []


def test_resultado(rt):
    hoy = HOY.isoformat()
    ok = {"franja": "reel", "franjas": {hoy: ["manana", "reel"]}, "preparado": []}
    assert rt.resultado(ok, HOY, False) == "✅ Reel de las 13:30: publicado en Instagram y Facebook."
    assert "Facebook falló" in rt.resultado(ok | {"error_facebook": {"fecha": hoy, "detalle": "x"}}, HOY, False)
    assert rt.resultado({"franja": "reel", "error": {"fecha": hoy, "detalle": "Instagram: token caducado"}}, HOY, False).startswith("❌")
    assert rt.resultado({"franja": "reel"}, HOY, True).startswith("🧪")
    assert rt.resultado({"franja": "reel", "franjas": {}}, HOY, False).startswith("⚠️")


def test_sin_secretos_no_hace_nada(rt, monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_ADMIN_CHAT", raising=False)
    monkeypatch.setenv("TELEGRAM_TOKEN", "T")
    assert rt.main(["--previa"]) == 0 and "Sin configurar" in capsys.readouterr().out

"""Reels con historia (scraper/historias.py): calendario, textos, dibujo y publicación simulada."""
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from conftest import _cargar
from test_redes import _datos


@pytest.fixture(scope="module")
def hist():
    return _cargar("historias")


@pytest.fixture(scope="module")
def redes():
    return _cargar("redes")


def test_calendario_lunes_a_viernes_desde_el_9(hist):
    assert hist.siguiente({}, date(2026, 11, 7)) is None                     # sábado antes de empezar
    assert hist.siguiente({}, date(2026, 11, 9)) == 1                        # lunes
    assert hist.siguiente({"historias": [1, 2]}, date(2026, 11, 11)) == 3
    assert hist.siguiente({"historias": [1, 2, 3, 4]}, date(2026, 11, 14)) is None   # sábado: nada
    assert hist.siguiente({"historias": [1, 2, 3, 4]}, date(2026, 11, 16)) == 5      # si un día falló, sigue el lunes
    assert hist.siguiente({"historias": [1, 2, 3, 4, 5]}, date(2026, 11, 17)) is None


def test_textos_honestos(hist):
    for n in hist.HISTORIAS:
        t = hist.texto_publicacion(n)
        assert "Historia inventada" in t and "Voz generada por ordenador" in t and "#LonjasCyL" in t
        assert len(t) < 2200                                                  # límite de Instagram


def test_elegir_y_crear_historia(redes, tmp_path):
    item = redes.elegir("historia", _datos(), {}, date(2026, 11, 9))
    assert item["tipo"] == "historia" and item["n"] == 1 and item["video"].endswith(".mp4")
    assert redes.elegir("historia", _datos(), {}, date(2026, 11, 8)) is None


def test_un_fotograma_por_escena(hist, tmp_path):
    for n in hist.HISTORIAS:
        fs = hist.fotogramas(n, tmp_path, _datos(), date(2026, 11, 9))
        assert len(fs) >= 4 and all(f.stat().st_size > 20000 for f in fs)


def test_movil_con_precios_reales(hist):
    lr = hist.lista_real(_datos(), "trigo", date(2026, 11, 9))
    assert [f[0] for f in lr["filas"]] == ["Salamanca", "León"] and lr["filas"][0][1] == "236"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sin ffmpeg")
def test_reel_y_publicacion_simulada(redes, tmp_path, monkeypatch):
    ig = _cargar("instagram")
    hist = _cargar("historias")
    monkeypatch.setattr(hist, "plan", lambda escenas, voces: [0.4] * len(escenas))   # vídeo corto para la prueba
    estado = {}
    item = redes.crear(_datos(), estado, "historia", date(2026, 11, 9), tmp_path)
    video = tmp_path / item["video"]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                               capture_output=True, text=True).stdout)
    assert dur > 2

    def falsa(metodo, ruta, token, **p):
        if ruta.endswith("/media"):
            assert p["media_type"] == "REELS"
        return {"id": "x"} if ruta.endswith(("/media", "/media_publish", "/videos")) else {"status_code": "FINISHED"}

    ig.publicar(estado, "EAA", "https://cdn/", date(2026, 11, 9), llamar=falsa, espera=lambda s: None,
                ig="https://graph.facebook.com/1", fb=("2", "EAA"))
    assert estado["historias"] == [1]
    redes.marcar(estado, "historia", date(2026, 11, 9))
    assert redes.crear(_datos(), estado, "historia", date(2026, 11, 9), tmp_path) is None   # una al día


def test_tarea_programada():
    y = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "redes.yml").read_text(encoding="utf-8")
    assert '"55 17 * * 1-5"' in y and "github.event.schedule == '55 17 * * 1-5' && 'historia'" in y

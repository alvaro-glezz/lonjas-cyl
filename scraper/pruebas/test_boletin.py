"""Boletín semanal por correo (scraper/boletin.py): el correo y el envío a Brevo (simulado)."""
import pytest

from conftest import _cargar


@pytest.fixture(scope="module")
def b():
    return _cargar("boletin")


INF = {"semana": "2026-W46", "desde": "2026-11-09", "hasta": "2026-11-14", "titulo": "Mercado agrario",
       "titular": "Cereales: semana de bajadas <b>", "resumen": ["Ninguna sube y 12 bajan."],
       "redaccion": [{"t": "", "p": "Primer párrafo & datos."}, {"t": "Porcino", "p": "El cerdo baja."}],
       "fuentes": ["Lonja de Salamanca"], "audio": "audio/x.mp3"}
GAS = {"cyl": {"media": 1.666}, "provincias": [
    {"nombre": "Burgos", "cyl": True, "baratas": [{"precio": 1.479, "localidad": "Roa"}]},
    {"nombre": "León", "cyl": True, "baratas": [{"precio": 1.55, "localidad": "La Bañeza"}]}]}


def test_correo(b):
    h = b.html_correo(INF, GAS, "https://web.es/")
    assert "Cereales: semana de bajadas &lt;b&gt;" in h and "<b>" not in h.split("<body")[1].split("Cereales")[0][-5:]
    assert "Primer párrafo &amp; datos." in h and ">Porcino</h2>" in h
    assert "{{ unsubscribe }}" in h                       # Brevo pone aquí el enlace de baja
    assert "https://web.es/mercado/2026-w46/" in h and "Escuchar el comentario" in h
    assert "1,666 €/l de media" in h and "1,479 €/l en Roa (Burgos)" in h
    assert "9 – 14 de noviembre de 2026" in h
    assert b.rango("2026-11-30", "2026-12-05") == "30 de noviembre – 5 de diciembre de 2026"
    assert b.asunto(INF).endswith("· Lonjas CyL")


def test_envio_simulado(b):
    llamadas = []

    def post(ruta, cuerpo):
        llamadas.append((ruta, cuerpo))
        return {"id": 77} if ruta == "/emailCampaigns" else {}

    cid = b.enviar(INF, "<html></html>", 3, "boletin@lonjascyl.es", "clave", post=post)
    assert cid == 77 and llamadas[1][0] == "/emailCampaigns/77/sendNow"
    c = llamadas[0][1]
    assert c["recipients"] == {"listIds": [3]} and c["sender"] == {"name": "Lonjas CyL", "email": "boletin@lonjascyl.es"}
    assert c["name"] == "Boletín 2026-W46" and c["previewText"] == "Ninguna sube y 12 bajan."


def test_sin_configurar_no_envia(b, monkeypatch, capsys):
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    assert b.main(["--enviar"]) == 0
    assert "Sin configurar" in capsys.readouterr().out or "No hay comentario" in capsys.readouterr().out

"""Canal de Telegram (scraper/telegram.py): qué se publica, cuándo y sin repetir."""
from datetime import date

import pytest

from conftest import _cargar


@pytest.fixture(scope="module")
def tg():
    return _cargar("telegram")


def _lonja(id_="x", fecha="2026-11-05", nombre="Lonja de <X>"):
    return {"id": id_, "nombre": nombre, "fecha": fecha, "nota": None, "precios": [
        {"id": f"{id_}-trigo", "producto": "Trigo pienso", "unidad": "€/t", "ant": 231, "act": 229, "clave": "trigo"},
        {"id": f"{id_}-cebada", "producto": "Cebada", "unidad": "€/t", "ant": 221, "act": 221, "clave": "cebada"},
        {"id": f"{id_}-cordero", "producto": "Cordero 23-25 kg", "unidad": "€/kg vivo", "ant": 5.0, "act": 5.5},
        {"id": f"{id_}-colza", "producto": "Colza", "unidad": "€/t", "ant": None, "act": None, "ult": ["2026-10-01", 400]}]}


def test_mensaje_de_la_sesion(tg):
    m = tg.mensaje_sesion(_lonja())
    assert "Lonja de &lt;X&gt;" in m and "<X>" not in m                 # HTML de Telegram escapado
    assert "sesión del jueves 5 nov" in m
    assert "Trigo pienso: <b>229</b> €/t ▼ −2" in m and "Cebada: <b>221</b> €/t =" in m
    assert "Lo que más se mueve" in m and "Cordero 23-25 kg: <b>5,50</b>" in m
    assert "Colza" not in m                                             # sin cotizar: no se publica
    assert "▲ 1 suben · ▼ 1 bajan · = 1 repiten" in m and "lonja/x/" in m and len(m) <= 4000


def test_solo_sesiones_nuevas_y_sin_repetir(tg):
    datos = {"lonjas": [_lonja("a", "2026-11-05"), _lonja("b", "2026-10-20"), dict(_lonja("z"), estado="suspendida")]}
    enviados = []
    llamar = lambda token, metodo, cuerpo: enviados.append((metodo, cuerpo["chat_id"])) or {}
    estado = {}
    hoy = date(2026, 11, 6)
    assert tg.publicar(datos, estado, "T", "@canal", hoy, llamar) == ["a"]   # «b» es vieja para la primera vez
    assert estado == {"publicado": {"a": "2026-11-05"}} and enviados == [("sendMessage", "@canal")]
    assert tg.publicar(datos, estado, "T", "@canal", hoy, llamar) == []      # no repite
    datos["lonjas"][0]["fecha"] = "2026-11-12"
    assert tg.publicar(datos, estado, "T", "@canal", date(2026, 11, 12), llamar) == ["a"]


def test_si_telegram_falla_no_se_marca_como_publicada(tg):
    def falla(token, metodo, cuerpo):
        raise RuntimeError("Telegram sendMessage: Forbidden")
    estado = {}
    with pytest.raises(RuntimeError):
        tg.publicar({"lonjas": [_lonja()]}, estado, "T", "@c", date(2026, 11, 6), falla)
    assert estado == {}


def test_configurar_valida_y_conecta_el_robot(tg):
    hechas = []
    llamar = lambda token, metodo, cuerpo: hechas.append((metodo, cuerpo)) or {"url": cuerpo.get("url")}
    tg.configurar("T", "https://lonjas.vercel.app", "s" * 32, llamar)
    wh = dict(hechas)["setWebhook"]
    assert wh["url"] == "https://lonjas.vercel.app/api/telegram" and wh["secret_token"] == "s" * 32
    with pytest.raises(ValueError):
        tg.configurar("T", "http://inseguro.es", "s" * 32, llamar)
    with pytest.raises(ValueError):
        tg.configurar("T", "https://x.es/otra/ruta", "s" * 32, llamar)
    with pytest.raises(ValueError):
        tg.configurar("T", "https://x.es", "corto", llamar)


def test_sin_token_no_hace_nada(tg, monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    assert tg.main([]) == 0
    assert "Sin configurar" in capsys.readouterr().out

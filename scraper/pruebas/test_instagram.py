"""Instagram (scraper/instagram.py): qué toca publicar, textos, imágenes y llamadas a la API (simulada)."""
import json
from datetime import date
from pathlib import Path

import pytest

from conftest import _cargar

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def ig():
    return _cargar("instagram")


@pytest.fixture(scope="module")
def avisar():
    return _cargar("avisar")


def _datos():
    return {"lonjas": [
        {"id": "salamanca", "nombre": "Lonja de Salamanca", "fecha": "2026-11-02", "estado": "activa", "nota": "Datos abiertos",
         "precios": [{"id": "s-t", "cat": "Cereales", "producto": "Trigo blando", "unidad": "€/t", "ant": 230, "act": 236, "clave": "trigo"},
                     {"id": "s-c", "cat": "Cereales", "producto": "Cebada", "unidad": "€/t", "ant": 232, "act": 231, "clave": "cebada"}]},
        {"id": "leon", "nombre": "Lonja de León", "fecha": "2026-11-04", "estado": "activa",
         "precios": [{"id": "l-t", "cat": "Cereales", "producto": "Trigo pienso", "unidad": "€/t", "ant": 226, "act": 226, "clave": "trigo"},
                     {"id": "l-c", "cat": "Cereales", "producto": "Cebada", "unidad": "€/t", "ant": 222, "act": 221, "clave": "cebada"},
                     {"id": "l-x", "cat": "Ovino", "producto": "Cordero <18 kg", "unidad": "€/kg vivo", "ant": 4.0, "act": 4.2},
                     {"id": "l-n", "cat": "Cereales", "producto": "Maíz", "unidad": "€/t", "ant": None, "act": None, "clave": "maiz"}]},
        {"id": "zamora", "nombre": "Lonja de Zamora", "fecha": "2026-11-05", "estado": "suspendida", "precios": []}]}


def test_pendientes_sesiones_recientes_y_sin_repetir(ig):
    d = _datos()
    p = ig.pendientes(d, {}, date(2026, 11, 5))     # jueves: sin comparativa; Salamanca (día 2) dentro de 3 días
    assert [x["id"] for x in p] == ["2026-11-02-salamanca", "2026-11-04-leon"]
    p = ig.pendientes(d, {"publicado": {"salamanca": "2026-11-02"}}, date(2026, 11, 6))
    assert [x["id"] for x in p] == ["2026-11-04-leon", "2026-W45-comparativa"]   # viernes: comparativa
    assert ig.pendientes(d, {"publicado": {"leon": "2026-11-04"}, "comparativa": "2026-W45"}, date(2026, 11, 7)) == []


def test_textos(ig):
    d = _datos()
    t = ig.texto_sesion(d["lonjas"][1])
    assert t.startswith("📊 Lonja de León · sesión del miércoles 4 nov")
    assert "Trigo pienso: 226 €/t =" in t and "Cordero <18 kg: 4,20 €/kg vivo ▲ +0,20" in t
    assert "Maíz" not in t                                   # sin cotizar: no sale
    assert "#León" in t and "orientativos" in t and len(t) <= 2200
    c = ig.texto_comparativa(ig.comparativas(d, date(2026, 11, 6)))
    assert "Trigo (€/t): Salamanca 236 · León 226 → 10 de diferencia" in c


def test_imagenes_jpeg_1080x1350(ig, tmp_path):
    from PIL import Image
    d = _datos()
    datos_reales = json.loads((RAIZ / "data" / "precios.json").read_text(encoding="utf-8"))
    for l in d["lonjas"][:2] + [l for l in datos_reales["lonjas"] if l.get("fecha") and ig.principales(l)]:
        f = ig.imagen_sesion(l, tmp_path / f"{l['id']}.jpg")
        im = Image.open(f)
        assert im.format == "JPEG" and im.size == (1080, 1350)
    for c in ig.comparativas(d, date(2026, 11, 6)):
        assert Image.open(ig.imagen_comparativa(c, tmp_path / f"c-{c['clave']}.jpg")).size == (1080, 1350)


def test_preparar_y_publicar_con_api_simulada(ig, tmp_path):
    d = _datos()
    estado = {}
    lista = ig.preparar(d, estado, date(2026, 11, 6), tmp_path)
    assert [x["tipo"] for x in lista] == ["sesion", "comparativa"]   # Salamanca (día 2) ya tiene más de 3 días
    for x in lista:
        for r in x["imagenes"]:
            assert (tmp_path / r).is_file()
    llamadas = []

    def falsa(metodo, ruta, token, **p):
        assert token == "secreto"
        llamadas.append((metodo, ruta, p))
        if ruta == "me/media":
            return {"id": f"c{len(llamadas)}"}
        if ruta == "me/media_publish":
            return {"id": "m" + p["creation_id"]}
        if ruta == "refresh_access_token":
            return {"access_token": "secreto", "expires_in": 5184000}
        return {"status_code": "FINISHED"}

    hechas = ig.publicar(estado, "secreto", "https://web.es/", date(2026, 11, 6), llamar=falsa, espera=lambda s: None)
    assert hechas == ["2026-11-04-leon", "2026-W45-comparativa"]
    assert estado["publicado"] == {"leon": "2026-11-04"} and estado["comparativa"] == "2026-W45"
    assert estado["preparado"] == [] and len(estado["registro"]) == 2
    carrusel = [p for m, r, p in llamadas if p.get("media_type") == "CAROUSEL"]
    assert len(carrusel) == 1 and carrusel[0]["children"].count(",") >= 1
    assert all(p["image_url"].startswith("https://web.es/redes/instagram/") for m, r, p in llamadas if "image_url" in p)
    ig.renovar_token(estado, "secreto", date(2026, 11, 6), llamar=falsa)
    assert estado["token_caduca"] == "2027-01-05" and "token_cambiado" not in estado


def test_si_falla_no_marca_como_publicado(ig, tmp_path):
    estado = {}
    ig.preparar(_datos(), estado, date(2026, 11, 5), tmp_path)

    def falla(metodo, ruta, token, **p):
        raise ig.ErrorInstagram("Instagram me/media: Invalid image (código 9004)")

    with pytest.raises(ig.ErrorInstagram):
        ig.publicar(estado, "t", "https://web.es/", date(2026, 11, 5), llamar=falla, espera=lambda s: None)
    assert "publicado" not in estado and len(estado["preparado"]) == 2   # se reintenta en la próxima pasada


def test_sin_token_no_hace_nada(ig, monkeypatch, capsys):
    monkeypatch.delenv("INSTAGRAM_TOKEN", raising=False)
    assert ig.main(["--preparar"]) == 0
    assert "Sin configurar" in capsys.readouterr().out


def test_aviso_token_instagram(avisar):
    assert avisar.problema_instagram(None, date(2026, 11, 6)) is None
    assert avisar.problema_instagram({"token_caduca": "2027-01-05"}, date(2026, 11, 6)) is None
    assert avisar.problema_instagram({"token_caduca": "2026-11-12"}, date(2026, 11, 6))["id"] == "instagram"
    assert avisar.problema_instagram({"token_cambiado": "2026-11-06"}, date(2026, 11, 6))["tipo"] == "token por renovar"


def test_cuenta_con_token_de_facebook(ig):
    def falsa(metodo, ruta, token, **p):
        if ruta.endswith("/me"):
            return {"id": "u1"} if token == "EAAusuario" else {"id": "pag1", "instagram_business_account": {"id": "1784"}}
        if ruta.endswith("/me/accounts"):
            return {"data": [{"id": "otra"}, {"id": "pag1", "access_token": "EAApagina", "instagram_business_account": {"id": "1784"}}]}
        raise AssertionError(ruta)
    assert ig.cuenta("IGabc", falsa) == ("https://graph.instagram.com/me", "IGabc", "instagram")
    assert ig.cuenta("EAApagina", falsa) == ("https://graph.facebook.com/1784", "EAApagina", "pagina")
    assert ig.cuenta("EAAusuario", falsa) == ("https://graph.facebook.com/1784", "EAApagina", "usuario")
    with pytest.raises(ig.ErrorInstagram):
        ig.cuenta("EAAusuario", lambda m, r, t, **p: {"data": []} if r.endswith("accounts") else {"id": "u"})


def test_publicar_por_facebook(ig, tmp_path):
    estado = {}
    ig.preparar(_datos(), estado, date(2026, 11, 5), tmp_path)
    rutas = []

    def falsa(metodo, ruta, token, **p):
        rutas.append(ruta)
        if ruta.endswith("/media"):
            return {"id": "c9"}
        if ruta.endswith("/media_publish"):
            return {"id": "m9"}
        return {"status_code": "FINISHED"}

    ig.publicar(estado, "EAApagina", "https://web.es/", date(2026, 11, 5), llamar=falsa, espera=lambda s: None,
                ig="https://graph.facebook.com/1784")
    assert "https://graph.facebook.com/1784/media" in rutas and "https://graph.facebook.com/1784/media_publish" in rutas
    assert "https://graph.facebook.com/c9" in rutas            # comprobación del contenedor en el mismo servidor


def test_aviso_si_falla_la_publicacion(avisar):
    p = avisar.problema_instagram({"error": {"fecha": "2026-11-07", "detalle": "Invalid OAuth access token"}}, date(2026, 11, 7))
    assert p["tipo"] == "no publica" and "Invalid OAuth" in p["detalle"]


def test_tambien_en_facebook(ig, tmp_path):
    estado = {}
    ig.preparar(_datos(), estado, date(2026, 11, 6), tmp_path)     # León (1 imagen) + comparativa (carrusel)
    llamadas = []

    def falsa(metodo, ruta, token, **p):
        llamadas.append((ruta, p))
        if ruta.endswith("/media"):
            return {"id": "c1"}
        if ruta.endswith("/media_publish"):
            return {"id": "m1"}
        if ruta.endswith("/photos"):
            return {"id": "f1", "post_id": "pag_1"} if p.get("published") != "false" else {"id": f"foto{len(llamadas)}"}
        if ruta.endswith("/feed"):
            assert "attached_media[0]" in p and "attached_media[1]" in p
            return {"id": "pag_2"}
        return {"status_code": "FINISHED"}

    ig.publicar(estado, "EAA", "https://web.es/", date(2026, 11, 6), llamar=falsa, espera=lambda s: None,
                ig="https://graph.facebook.com/1784", fb=("1368", "EAApag"))
    assert [r.get("facebook") for r in estado["registro"]] == ["pag_1", "pag_2"] and "error_facebook" not in estado
    assert any(r == "https://graph.facebook.com/1368/photos" and p.get("message", "").startswith("📊") for r, p in llamadas)


def test_si_falla_facebook_instagram_sigue(ig, tmp_path, avisar):
    estado = {}
    ig.preparar(_datos(), estado, date(2026, 11, 5), tmp_path)

    def falsa(metodo, ruta, token, **p):
        if "/1368/" in ruta:
            raise ig.ErrorInstagram("Instagram photos: (#200) requires pages_manage_posts (código 200)")
        return {"id": "x"} if ruta.endswith(("/media", "/media_publish")) else {"status_code": "FINISHED"}

    hechas = ig.publicar(estado, "EAA", "https://web.es/", date(2026, 11, 5), llamar=falsa, espera=lambda s: None,
                         ig="https://graph.facebook.com/1784", fb=("1368", "EAApag"))
    assert hechas == ["2026-11-02-salamanca", "2026-11-04-leon"] and estado["preparado"] == []
    assert "pages_manage_posts" in estado["error_facebook"]["detalle"] and estado["error_facebook"]["detalle"].startswith("Facebook")
    assert avisar.problema_instagram(estado, date(2026, 11, 5))["nombre"] == "Página de Facebook"

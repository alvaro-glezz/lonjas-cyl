"""Calendario de redes (scraper/redes.py): qué toca en cada franja, archivos que crea y publicación simulada."""
import shutil
import subprocess
from datetime import date, datetime

import pytest

from conftest import _cargar


@pytest.fixture(scope="module")
def redes():
    return _cargar("redes")


def _datos():
    hist = {"s-t": [["2026-10-12", 228], ["2026-10-19", 230], ["2026-10-26", 232], ["2026-11-02", 236]],
            "l-t": [["2026-10-14", 230], ["2026-10-21", 230], ["2026-10-28", 228], ["2026-11-04", 226]]}
    return {"historial": hist, "lonjas": [
        {"id": "salamanca", "nombre": "Lonja de Salamanca", "fecha": "2026-11-02", "estado": "activa", "dia": "Lunes",
         "precios": [{"id": "s-t", "cat": "Cereales", "producto": "Trigo blando", "unidad": "€/t", "ant": 232, "act": 236, "clave": "trigo"},
                     {"id": "s-c", "cat": "Cereales", "producto": "Cebada", "unidad": "€/t", "ant": 232, "act": 231, "clave": "cebada"}]},
        {"id": "leon", "nombre": "Lonja de León", "fecha": "2026-11-04", "estado": "activa", "dia": "Miércoles",
         "precios": [{"id": "l-t", "cat": "Cereales", "producto": "Trigo pienso", "unidad": "€/t", "ant": 228, "act": 226, "clave": "trigo"},
                     {"id": "l-c", "cat": "Cereales", "producto": "Cebada", "unidad": "€/t", "ant": 222, "act": 221, "clave": "cebada"}]}]}


def test_franja_por_hora(redes):
    assert [redes.franja_por_hora(datetime(2026, 11, 9, h, 5)) for h in (7, 12, 18)] == ["manana", "reel", "tarde"]


def test_manana_sesion_nueva_y_si_no_producto_del_dia(redes):
    d = _datos()
    item = redes.elegir("manana", d, {}, date(2026, 11, 5))          # León (día 4) aún sin publicar
    assert item["tipo"] == "sesion"
    hecho = {"publicado": {"salamanca": "2026-11-02", "leon": "2026-11-04"}}
    item = redes.elegir("manana", d, hecho, date(2026, 11, 5))       # jueves -> centeno no hay -> sigue la rueda
    assert item["tipo"] == "dia" and item["clave"] in ("trigo", "cebada")
    assert item["texto"].startswith("📈 Precio") and "Diferencia" in item["texto"]
    assert redes.elegir("manana", d, hecho, date(2026, 11, 8)) is None   # domingo: descanso


def test_tarde_solo_si_hay_algo(redes):
    d = _datos()
    hecho = {"publicado": {"salamanca": "2026-11-02", "leon": "2026-11-04"}}
    assert redes.elegir("tarde", d, hecho, date(2026, 11, 5)) is None                 # jueves sin nada nuevo
    assert redes.elegir("tarde", d, hecho, date(2026, 11, 6))["tipo"] == "comparativa"  # viernes
    assert redes.elegir("tarde", d, dict(hecho, comparativa="2026-W45"), date(2026, 11, 6)) is None


def test_reel_alterna(redes):
    d = _datos()
    lunes, martes = redes.elegir("reel", d, {}, date(2026, 11, 9)), redes.elegir("reel", d, {}, date(2026, 11, 10))
    assert lunes["reel"] == "ranking" and lunes["video"].endswith(".mp4")
    assert martes["reel"] in ("movimientos", "ranking")
    assert "¿Dónde se paga más" in redes.texto_reel_ranking(redes.ranking(d, "trigo", date(2026, 11, 9)))


def test_titulos_en_espanol(redes):
    assert redes.titulo_ranking("trigo") == "¿Dónde se paga más el trigo?"
    assert redes.titulo_ranking("cebada") == "¿Dónde se paga más la cebada?"
    assert redes.titulo_ranking("lechones") == "¿Dónde se paga más los lechones?"


def test_crear_y_no_repetir_franja(redes, tmp_path):
    d = _datos()
    estado = {"publicado": {"salamanca": "2026-11-02", "leon": "2026-11-04"}}
    item = redes.crear(d, estado, "manana", date(2026, 11, 5), tmp_path)
    assert all((tmp_path / f).is_file() for f in item["imagenes"]) and estado["preparado"] == [item]
    redes.marcar(estado, "manana", date(2026, 11, 5))
    assert redes.crear(d, estado, "manana", date(2026, 11, 5), tmp_path) is None and estado["preparado"] == []
    assert redes.crear(d, estado, "manana", date(2026, 11, 5), tmp_path, forzar=True) is not None


def test_publicar_dia_no_toca_sesiones(redes, tmp_path):
    ig = _cargar("instagram")
    d = _datos()
    estado = {"publicado": {"salamanca": "2026-11-02", "leon": "2026-11-04"}}
    redes.crear(d, estado, "manana", date(2026, 11, 5), tmp_path)

    def falsa(metodo, ruta, token, **p):
        return {"id": "x"} if ruta.endswith(("/media", "/media_publish", "/photos", "/feed")) else {"status_code": "FINISHED"}

    ig.publicar(estado, "EAA", "https://cdn/", date(2026, 11, 5), llamar=falsa, espera=lambda s: None,
                ig="https://graph.facebook.com/1", fb=("2", "EAA"))
    assert estado["publicado"] == {"salamanca": "2026-11-02", "leon": "2026-11-04"} and "comparativa" not in estado


def test_reel_con_api_simulada(redes, tmp_path):
    ig = _cargar("instagram")
    estado = {"preparado": [{"tipo": "reel", "id": "r", "texto": "t", "video": "r.mp4"}]}
    llamadas = []

    def falsa(metodo, ruta, token, **p):
        llamadas.append((ruta, p))
        if ruta.endswith("/media"):
            return {"id": "c"}
        if ruta.endswith("/media_publish"):
            return {"id": "m"}
        if ruta.endswith("/videos"):
            return {"id": "v"}
        return {"status_code": "FINISHED"}

    ig.publicar(estado, "EAA", "https://cdn/", date(2026, 11, 9), llamar=falsa, espera=lambda s: None,
                ig="https://graph.facebook.com/1", fb=("2", "EAA"))
    media = [p for r, p in llamadas if r.endswith("/media")][0]
    assert media["media_type"] == "REELS" and media["video_url"] == "https://cdn/r.mp4" and media["share_to_feed"] == "true"
    assert [p for r, p in llamadas if r.endswith("/videos")][0]["file_url"] == "https://cdn/r.mp4"
    assert estado["registro"][-1] == {**estado["registro"][-1], "media": "m", "facebook": "v"}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sin ffmpeg")
def test_reel_de_verdad(redes, tmp_path):
    r = redes.ranking(_datos(), "trigo", date(2026, 11, 9))
    f = redes.reel_ranking(r, tmp_path / "r.mp4")
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height", "-of", "csv=p=0", str(f)],
                          capture_output=True, text=True).stdout.split()
    assert "h264,1080,1920" in info and "aac" in info
    assert not (tmp_path / "r.wav").exists()


def test_numeros_hablados(redes):
    assert redes.decir(236) == "doscientos treinta y seis" and redes.decir(9.45) == "nueve con cuarenta y cinco"
    assert redes.decir(1.155) == "uno con ciento cincuenta y cinco" and redes.decir(4.8, 1, "coma") == "cuatro coma ocho"
    assert redes.precio_hablado(231, "€/t") == "doscientos treinta y un euros la tonelada"
    assert redes.precio_hablado(10, "€/t", 0, por=True) == "diez euros por tonelada"
    assert redes.producto_hablado("Oveja desvieje 2ª") == "oveja desvieje segunda" and redes.producto_hablado("Cebada 62 kg/hl") == "cebada"
    g = redes.guion_ranking(redes.ranking(_datos(), "trigo", date(2026, 11, 9)))
    assert g.startswith("¿Dónde se paga más el trigo esta semana? Paga más Salamanca, con doscientos treinta y seis euros la tonelada; le sigue León, con doscientos veintiséis.")
    assert "€" not in g and "CyL" not in redes.para_leer(g) and redes.para_leer(g).endswith("en Lonjas Castilla y León.")
    assert redes.precio_hablado(9.9, "€/kg vivo") == "nueve euros con noventa céntimos el kilo vivo"
    assert redes.precio_hablado(0.45, "€/kg vivo", 2, por=True) == "cuarenta y cinco céntimos por kilo vivo"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sin ffmpeg")
def test_reel_con_voz_dura_lo_que_la_narracion(redes, tmp_path, monkeypatch):
    def voz_falsa(texto, destino):            # 15 s de «voz» (un tono): sin descargar el modelo
        redes.musica(destino, 15, 22050)
        return destino
    monkeypatch.setattr(redes, "voz", voz_falsa)
    f = redes.reel_ranking(redes.ranking(_datos(), "trigo", date(2026, 11, 9)), tmp_path / "v.mp4")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                               capture_output=True, text=True).stdout)
    assert 15.5 <= dur <= 16.6 and not list(tmp_path.glob("*.wav"))
    assert redes.AVISO_VOZ in redes.texto_reel_ranking(redes.ranking(_datos(), "trigo", date(2026, 11, 9)))


def test_fusionar_registro_sin_perder_nada():
    f = _cargar("fusionar_estado").fusionar
    nuestro = {"publicado": {"leon": "2026-11-04"}, "franjas": {"2026-11-07": ["reel"]}, "preparado": [],
               "registro": [{"fecha": "2026-11-07T16:00", "id": "reel"}], "token_caduca": None}
    suyo = {"publicado": {"leon": "2026-11-04", "segovia": "2026-11-05"}, "franjas": {"2026-11-07": ["manana"]},
            "comparativa": "2026-W45", "historias": {"hechas": [1]},
            "registro": [{"fecha": "2026-11-07T13:01", "id": "leon"}]}
    u = f(nuestro, suyo)
    assert u["publicado"] == {"leon": "2026-11-04", "segovia": "2026-11-05"} and u["comparativa"] == "2026-W45"
    assert u["franjas"]["2026-11-07"] == ["manana", "reel"] and u["historias"] == {"hechas": [1]}
    assert [r["id"] for r in u["registro"]] == ["leon", "reel"]
    assert f({"publicado": {"leon": "2026-11-04"}}, {"publicado": {"leon": "2026-11-11"}})["publicado"]["leon"] == "2026-11-11"


def test_reels_especiales_cualquier_dia():
    import redes as r
    from datetime import date
    domingo = date(2026, 11, 8)
    it = r.elegir("especial:instalar", {"lonjas": []}, {}, domingo)
    assert it["tipo"] == "especial" and it["video"] == "2026-11-08-especial-instalar.mp4"
    assert "Añadir a pantalla de inicio" in it["texto"] and "#LonjasCyL" in it["texto"] and "CC BY 3.0" not in it["texto"] and "subtítulos" in it["texto"]
    assert r.elegir("especial:explotacion", {"lonjas": []}, {}, domingo)["id"] == "2026-11-08-especial-explotacion"
    assert r.elegir("especial:no-existe", {"lonjas": []}, {}, domingo) is None
    assert r.elegir("reel", {"lonjas": []}, {}, domingo) is None          # el domingo, lo demás no publica

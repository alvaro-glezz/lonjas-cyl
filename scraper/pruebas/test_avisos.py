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


class _GitHubFalso:
    """Imita la API de incidencias de GitHub para probar el aviso sin tocar el repositorio real."""
    def __init__(self):
        self.incidencias, self.llamadas = [], []

    def __call__(self):            # requests.Session()
        return self

    headers = {}

    def _resp(self, datos):
        class R:
            def __init__(s, d): s.d = d
            def json(s): return s.d
            def raise_for_status(s): pass
        return R(datos)

    def get(self, url, params=None, timeout=None):
        self.llamadas.append(("GET", url))
        return self._resp([i for i in self.incidencias if i["state"] == "open"])

    def post(self, url, json=None, timeout=None):
        self.llamadas.append(("POST", url))
        if url.endswith("/issues"):
            self.incidencias.append({"number": len(self.incidencias) + 1, "state": "open", "body": json["body"], "html_url": "x"})
        return self._resp({"html_url": "x"})

    def patch(self, url, json=None, timeout=None):
        self.llamadas.append(("PATCH", url))
        n = int(url.rsplit("/", 1)[1]); inc = self.incidencias[n - 1]
        inc.update({k: v for k, v in json.items() if k in ("body", "state")})
        return self._resp({})


def test_flujo_completo_de_la_incidencia(avisar, monkeypatch, tmp_path):
    import json, requests
    gh = _GitHubFalso()
    monkeypatch.setattr(requests, "Session", gh)
    monkeypatch.setenv("GITHUB_REPOSITORY", "dueño/lonjas"); monkeypatch.setenv("GITHUB_TOKEN", "x"); monkeypatch.setenv("GITHUB_RUN_ID", "1")
    monkeypatch.delenv("JCYL_RESULTADO", raising=False)
    datos = tmp_path / "precios.json"; monkeypatch.setattr(avisar, "DATOS", datos)
    hoy = date.today().isoformat()
    def escribir(fallos_leon):
        datos.write_text(json.dumps(_datos(leon={"fallos": fallos_leon, "fecha": hoy, "error": "x"}, lerma={"fallos": 0, "fecha": hoy})))
    escribir(2); avisar.main([])
    assert len(gh.incidencias) == 1 and gh.incidencias[0]["state"] == "open"          # se abre
    escribir(3); avisar.main([])
    assert len(gh.incidencias) == 1 and not any(m == "PATCH" for m, _ in gh.llamadas)  # mismo problema: no se repite
    escribir(0); avisar.main([])
    assert gh.incidencias[0]["state"] == "closed"                                      # se cierra sola
    escribir(0); n = len(gh.llamadas); avisar.main([])
    assert [m for m, _ in gh.llamadas[n:]] == ["GET"]                                  # todo bien y nada abierto: solo mira


def test_calendario_de_plazos_por_actualizar(avisar):
    from datetime import date
    plazos = {"plazos": [{"id": "a", "fin": "2027-06-30"}]}
    assert avisar.problema_plazos(plazos, date(2027, 5, 1)) is None          # quedan 60 días
    p = avisar.problema_plazos(plazos, date(2027, 6, 10))                       # quedan 20 días
    assert p and p["id"] == "plazos" and "2027-06-30" in p["detalle"]
    assert avisar.problema_plazos({"plazos": []}, date(2027, 1, 1))["tipo"] == "por actualizar"
    assert avisar.problema_plazos(None, date(2027, 1, 1)) is None
    assert any(x["id"] == "plazos" for x in avisar.problemas({"lonjas": []}, date(2027, 6, 10), None, plazos))

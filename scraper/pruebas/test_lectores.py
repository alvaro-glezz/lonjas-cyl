"""Reglas concretas de cada lector, con fragmentos reales de los boletines."""
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_fechas(act):
    assert act.fecha_en("Lonja cereal 04-11-2026") == "2026-11-04"
    assert act.fecha_en("FECHA DE CELEBRACIÓN 30 DE OCTUBRE DE 2026") == "2026-10-30"
    assert act.fecha_en("lonja-2026-Noviembre-3-11391.pdf".replace("-", " ")) == "2026-11-03"
    assert act.fecha_en("31/02/2026") is None          # fecha imposible
    assert act.fecha_en("sin fecha") is None


def test_lerma_tabla_de_la_pagina(act):
    html = """<table><tr><td>COTIZACIONES AL CIERRE</td><td>FECHA DE CELEBRACIÓN 30 DE OCTUBRE DE 2026</td></tr>
    <tr><td></td><td><h4>CEREALES</h4></td><td>ACTUAL</td><td>ANTERIOR</td></tr>
    <tr><td></td><td>TRIGO TIPO III</td><td>231 €/TONELADA</td><td>232 €/TONELADA</td></tr>
    <tr><td></td><td>CEBADA DOS CARRERAS</td><td>223 €/TONELADA</td><td>223 €/TONELADA</td></tr>
    <tr><td></td><td><h4>PORCINO CEBADO</h4></td><td></td><td></td></tr>
    <tr><td></td><td>SELECTO</td><td>- €/Kg</td><td>(- €/Kg)</td></tr>
    <tr><td></td><td>NORMAL (CERDO BLANCO)</td><td>1,168 €/Kg</td><td>(1,208 €/Kg)</td></tr>
    <tr><td></td><td><h4>GANADO VACUNO</h4></td><td></td><td></td></tr>
    <tr><td></td><td>AÑOJOS EXTRA</td><td>5,68 €/Kg</td><td>(5,68 €/Kg)</td></tr>
    <tr><td></td><td>........... PRIMERA</td><td>5,36 €/Kg</td><td>(5,36 €/Kg)</td></tr>
    <tr><td>COMENTARIO</td></tr></table>"""
    fecha, filas = act.leer_lerma_html(html)
    assert fecha == "2026-10-30"
    nombres = {f["producto"]: f for f in filas}
    assert nombres["Trigo tipo III"] == {"cat": "Cereales", "producto": "Trigo tipo III", "unidad": "€/t", "ant": 232, "act": 231}
    assert nombres["Cerdo normal"]["unidad"] == "€/kg vivo" and nombres["Cerdo normal"]["act"] == 1.168
    assert "Cerdo selecto" not in nombres               # «-»: la lonja no da ese precio
    assert nombres["Añojos primera"]["act"] == 5.36     # los puntos repiten la primera parte del nombre


def test_lerma_historico_pdf_real_2024(act):
    """Archivo anual real de Lerma (una sesión por página): se usa si falla la tabla de la página."""
    texto = (FIXTURES / "lerma-historico-2024-texto.txt").read_text(encoding="utf-8")
    bloque = texto.split("=== página 1 de 49 ===")[1].split("===")[0]
    fecha, filas = act.leer_sesion_lerma(bloque)
    assert fecha == "2024-01-05"
    nombres = {f["producto"]: f for f in filas}
    assert nombres["Trigo tipo III"]["act"] == 230 and nombres["Trigo tipo III"]["unidad"] == "€/t"
    assert nombres["Terneras carne rosada"]["act"] == 4.98     # «“ “ rosada» = ídem
    assert nombres["Vacas industria"]["act"] == 1.56


def test_leon_tablas(act):
    html = """<table><tr><td>VACUNO</td><td>COTIZACION ANTERIOR</td><td>COTIZACION ACTUAL</td><td>DIF.</td></tr>
    <tr><td>GANADO VIDA</td><td>€/Unidad</td><td>€/Unidad</td><td></td></tr>
    <tr><td>Pasteros macho (200 kg)</td><td>1.100,00</td><td>1.100,00</td><td>=</td></tr>
    <tr><td>BOVINO CARNE</td><td>€/Kg. Canal</td><td>€/Kg. Canal</td><td></td></tr>
    <tr><td>Hembras 180-200 kg.</td><td></td><td></td><td></td></tr>
    <tr><td>R</td><td>6,85</td><td>6,85</td><td>=</td></tr>
    <tr><td>VACAS SACRIFICIO</td><td>€/Kg. Canal</td><td>€/Kg. Canal</td><td></td></tr>
    <tr><td>Fábrica y Segunda</td><td>3,60/4,60</td><td>3,60/4,60</td><td>=</td></tr>
    <tr><td>Maíz</td><td>S/C*</td><td>S/C*</td><td></td></tr></table>"""
    filas = {f["producto"]: f for f in act.filas_de_tablas_html(html, "Vacuno")}
    assert filas["Pasteros macho (200 kg)"] == {"producto": "Pasteros macho (200 kg)", "cat": "Ganado vida", "unidad": "€/ud", "ant": 1100, "act": 1100}
    assert filas["Hembras 180-200 kg R"]["unidad"] == "€/kg canal"
    assert filas["Fábrica y Segunda"]["act"] == 4.1 and filas["Fábrica y Segunda"]["rango"] == "3,60–4,60"
    assert filas["Maíz"]["act"] is None


def test_leon_combina_mesas_de_dias_distintos(act):
    """Cereal se publica el miércoles y vacuno el jueves anterior: deben salir los dos."""
    def entrada(titulo, fecha, producto):
        return {"date": fecha + "T10:00:00", "link": "https://www.lonjadeleon.es/x", "title": {"rendered": titulo},
                "content": {"rendered": f"<table><tr><td>X</td><td>COTIZACION ANTERIOR</td><td>COTIZACION ACTUAL</td></tr>"
                                        f"<tr><td></td><td>€/t</td><td>€/t</td></tr><tr><td>{producto}</td><td>10,00</td><td>11,00</td></tr></table>"}}
    hoy = act.date.today()
    f1, f2, f3 = (hoy - act.timedelta(days=d) for d in (1, 7, 40))
    ent = [entrada(f"Lonja cereal {f1:%d-%m-%Y}", f1.isoformat(), "Trigo"),
           entrada(f"Lonja carne de vacuno {f2:%d-%m-%Y}", f2.isoformat(), "Frisones"),
           entrada(f"Lonja carne vacuno {f3:%d-%m-%Y}", f3.isoformat(), "Viejo"),      # misma mesa, más antigua
           entrada(f"Lonja patatas {f3:%d-%m-%Y}", f3.isoformat(), "Agria"),          # demasiado antigua
           entrada("LA GEOPOLÍTICA SIGUE INFLUENCIANDO", f1.isoformat(), "Nada")]      # noticia del blog
    fecha, filas, _, usadas = act.interpretar_leon(ent)
    assert fecha == f1.isoformat()
    assert sorted(f["producto"] for f in filas) == ["Frisones", "Trigo"]
    assert len(usadas) == 2


def test_segovia_texto_real(act):
    texto = """Cebada de 62 kgHl* 223,00 0,00 223,00
Trigo pienso 72 kg/Hl. 232,00 -1,00 231,00
Colza 9-2-42 (Hum-Imp-gras) S/C S/C S/C Tm/ Origen
Cordero lechal 10-12 Kg. para
9,35 0,10 9,45 104
sacrificio
Cordero recental 15,1-19 Kg. 7,37 0,10 7,47 127,36
Forraje 135,00 135,00 agricultor
Cerdas desvieje extra 0,270 0,00 0,270
Producto inventado 5,00 0,00 5,00"""
    filas = {f["producto"]: f for f in act.leer_segovia_texto(texto)}
    assert filas["Trigo pienso 72 kg/hl"]["act"] == 231 and filas["Trigo pienso 72 kg/hl"]["ant"] == 232
    assert filas["Colza 9-2-42"]["act"] is None
    assert filas["Lechazo 10-12 kg"]["act"] == 9.45        # nombre en dos líneas
    assert filas["Recental 15,1-19 kg"]["act"] == 7.47     # el «15,1» del nombre no es un precio
    assert filas["Forraje"]["act"] == 135                  # sin columna de diferencia
    assert filas["Cerda desvieje extra"]["unidad"] == "€/kg vivo"
    assert not any("inventado" in k.lower() for k in filas)   # lo desconocido no se publica


def test_salamanca_csv(act):
    csv = '''"ID";"FECHA";"MESA";"PRODUCTO";"CATEGORIA";"VALOR1";"VALOR2";
"1";"2026-11-03";"CEREALES";"Cereales";"Trigo Blando p.e. > 72 kg/Hl";"236";"0";
"2";"2026-11-03";"OVINO";"Oveja";"Sacrificio";",9";"1,4";
"3";"2026-11-03";"CEREALES";"Oleaginosas";"Girasol";"0";"0";
"4";"2026-11-03";"DESPIECE DE IBÉRICO";"Magros";"Presa";"17,2";"17,7";
"5";"2026-10-26";"CEREALES";"Cereales";"Trigo Blando p.e. > 72 kg/Hl";"238";"0";
"6";"2026-10-26";"OVINO";"Oveja";"Sacrificio";",9";"1,4";
"7";"2026-10-1'''
    fecha, filas = act.leer_salamanca_csv(csv)
    assert fecha == "2026-11-03"
    f = {x["producto"]: x for x in filas}
    assert f["Trigo blando"] == {"cat": "Cereales", "producto": "Trigo blando", "unidad": "€/t", "act": 236, "ant": 238}
    assert f["Oveja de sacrificio"]["act"] == 1.15 and f["Oveja de sacrificio"]["rango"] == "0,9–1,4"
    assert "Girasol" not in f                       # 0 = no cotizó
    assert not any("Presa" in k for k in f)         # despiece: no se publica


def test_elegir_pdf_descarta_estatutos(act):
    pdfs = [("https://www.lasalina.es/doc/EstatutosLonja.pdf", "Estatutos de la Lonja"),
            ("https://www.lasalina.es/pdfs/lonja-2026-Octubre-27-1.pdf", ""),
            ("https://www.lasalina.es/pdfs/lonja-2026-Noviembre-3-2.pdf", "")]
    url, fecha = act.elegir_pdf("prueba", pdfs, r"lonja")
    assert url.endswith("Noviembre-3-2.pdf") and fecha == "2026-11-03"


def test_lechones_comparables_solo_los_de_20_kg():
    # El «lechón tipo Lerma» no dice su peso y cotiza ~10 € por debajo: no se mezcla con los de 20 kg (10 nov 2026)
    from comun import clave_de
    assert clave_de("Lechones base 20 kg") == "lechones"
    assert clave_de("Lechones 20 kg") == "lechones"
    assert clave_de("Lechones 20kg") == "lechones"
    assert clave_de("Lechón tipo Lerma") is None
    assert clave_de("Lechones 200 kg") is None

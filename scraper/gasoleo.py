"""Gasóleo agrícola (Gasóleo B): precio medio por provincia y gasolineras más baratas.

Fuente oficial: Ministerio para la Transición Ecológica y el Reto Demográfico, servicio de precios de carburantes
(el mismo que usa el Geoportal de gasolineras, geoportalgasolineras.es). Se actualiza cada media hora; aquí se lee
en cada pasada del robot y se guarda:
  data/gasoleo.json            precio de hoy por provincia (media, mínimo, máximo, nº de gasolineras, 3 más baratas)
  data/gasoleo-historial.json  por provincia: [fecha, media, mínimo] de cada día (para gráficos)

Uso:  python scraper/gasoleo.py
Si el servicio falla, no toca nada (se queda el último dato bueno, con su fecha).
"""
from __future__ import annotations

import json
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "data" / "gasoleo.json"
HISTORIAL = RAIZ / "data" / "gasoleo-historial.json"
URL = ("https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/"
       "EstacionesTerrestres/FiltroProducto/6")          # 6 = Gasóleo B
FUENTE = "Ministerio para la Transición Ecológica y el Reto Demográfico (Geoportal de gasolineras)"
FUENTE_URL = "https://geoportalgasolineras.es/geoportal-instalaciones/Inicio"
DIAS_HISTORIAL = 400
CYL = ["05", "09", "24", "34", "37", "40", "42", "47", "49"]

# Código INE de provincia -> nombre para mostrar
PROVINCIAS = {
    "01": "Álava", "02": "Albacete", "03": "Alicante", "04": "Almería", "05": "Ávila", "06": "Badajoz", "07": "Illes Balears",
    "08": "Barcelona", "09": "Burgos", "10": "Cáceres", "11": "Cádiz", "12": "Castellón", "13": "Ciudad Real", "14": "Córdoba",
    "15": "A Coruña", "16": "Cuenca", "17": "Girona", "18": "Granada", "19": "Guadalajara", "20": "Gipuzkoa", "21": "Huelva",
    "22": "Huesca", "23": "Jaén", "24": "León", "25": "Lleida", "26": "La Rioja", "27": "Lugo", "28": "Madrid", "29": "Málaga",
    "30": "Murcia", "31": "Navarra", "32": "Ourense", "33": "Asturias", "34": "Palencia", "35": "Las Palmas", "36": "Pontevedra",
    "37": "Salamanca", "38": "Santa Cruz de Tenerife", "39": "Cantabria", "40": "Segovia", "41": "Sevilla", "42": "Soria",
    "43": "Tarragona", "44": "Teruel", "45": "Toledo", "46": "Valencia", "47": "Valladolid", "48": "Bizkaia", "49": "Zamora",
    "50": "Zaragoza", "51": "Ceuta", "52": "Melilla",
}
MINUSCULAS = {"de", "del", "la", "las", "el", "los", "y", "a", "en"}


def numero(t: str | None) -> float | None:
    try:
        return float((t or "").strip().replace(",", "."))
    except ValueError:
        return None


def bonito(t: str) -> str:
    """«AVENIDA CASTILLA LA MANCHA, 26» -> «Avenida Castilla la Mancha, 26»; «Nº 10.935» se deja igual."""
    t = " ".join((t or "").split())
    if not t or not t.isupper():
        return t
    pal = t.lower().split(" ")
    return " ".join(p if (i and p in MINUSCULAS) else p[:1].upper() + p[1:] for i, p in enumerate(pal))


def nombre_gasolinera(e: dict) -> str:
    """El rótulo; si es solo un número de registro («Nº 10.935») o está vacío, «Gasolinera de <localidad>»."""
    r = bonito(e.get("Rótulo", ""))
    if not r or r.lower().startswith(("nº", "n°", "no ")) or r.replace(".", "").replace(" ", "").isdigit():
        return f"Gasolinera de {bonito(e.get('Localidad') or e.get('Municipio') or '')}".strip()
    return r


def estacion(e: dict, precio: float) -> dict:
    return {"nombre": nombre_gasolinera(e), "precio": precio, "direccion": bonito(e.get("Dirección", "")),
            "localidad": bonito(e.get("Localidad") or e.get("Municipio") or ""), "cp": e.get("C.P.", ""),
            "horario": (e.get("Horario") or "").strip(), "lat": numero(e.get("Latitud")), "lon": numero(e.get("Longitud (WGS84)"))}


def resumir(respuesta: dict) -> dict:
    """De la respuesta del Ministerio al resumen por provincia (solo venta al público y precios con sentido)."""
    por_prov: dict[str, list[tuple[float, dict]]] = {}
    for e in respuesta.get("ListaEESSPrecio", []):
        p = numero(e.get("PrecioProducto"))
        prov = (e.get("IDProvincia") or "").zfill(2)
        if p is None or not 0.3 < p < 4 or prov not in PROVINCIAS or e.get("Tipo Venta", "P") != "P":
            continue
        por_prov.setdefault(prov, []).append((p, e))
    provincias = []
    sin_tilde = lambda t: unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower()
    for prov, lista in sorted(por_prov.items(), key=lambda x: sin_tilde(PROVINCIAS[x[0]])):
        precios = [p for p, _ in lista]
        baratas = sorted(lista, key=lambda x: (x[0], x[1].get("Localidad", "")))[:3]
        provincias.append({"id": prov, "nombre": PROVINCIAS[prov], "cyl": prov in CYL, "n": len(lista),
                           "media": round(mean(precios), 3), "mediana": round(median(precios), 3),
                           "min": min(precios), "max": max(precios), "baratas": [estacion(e, p) for p, e in baratas]})
    todos = [p for lista in por_prov.values() for p, _ in lista]
    cyl = [p for prov in CYL for p, _ in por_prov.get(prov, [])]
    try:
        f = datetime.strptime(respuesta.get("Fecha", ""), "%d/%m/%Y %H:%M:%S").isoformat(timespec="minutes")
    except ValueError:
        f = datetime.now().isoformat(timespec="minutes")
    return {"fecha": f, "fuente": FUENTE, "fuente_url": FUENTE_URL, "unidad": "€/l",
            "espana": {"media": round(mean(todos), 3), "min": min(todos), "n": len(todos)} if todos else None,
            "cyl": {"media": round(mean(cyl), 3), "min": min(cyl), "n": len(cyl)} if cyl else None,
            "provincias": provincias}


def anotar_historial(hist: dict, resumen: dict) -> dict:
    """Un punto por provincia y día ([fecha, media, mínimo]); si ya hay del día, se sustituye por el nuevo."""
    dia = resumen["fecha"][:10]
    for p in resumen["provincias"] + [{"id": "cyl", **(resumen["cyl"] or {})}, {"id": "es", **(resumen["espana"] or {})}]:
        if "media" not in p:
            continue
        serie = [x for x in hist.get(p["id"], []) if x[0] != dia]
        serie.append([dia, p["media"], p["min"]])
        hist[p["id"]] = sorted(serie)[-DIAS_HISTORIAL:]
    return hist


def descargar() -> dict:
    import requests
    r = requests.get(URL, headers={"Accept": "application/json", "User-Agent": "LonjasCyL/1.0 (precios agrarios)"}, timeout=90)
    r.raise_for_status()
    d = r.json()
    if d.get("ResultadoConsulta") != "OK" or not d.get("ListaEESSPrecio"):
        raise RuntimeError(f"Respuesta inesperada del Ministerio: {d.get('ResultadoConsulta')}")
    return d


def main() -> int:
    try:
        resumen = resumir(descargar())
    except Exception as e:  # noqa: BLE001 - se queda el último dato bueno
        print(f"[gasóleo] No se pudo leer el servicio del Ministerio: {e}")
        return 0
    if len(resumen["provincias"]) < 30:
        print(f"[gasóleo] Solo {len(resumen['provincias'])} provincias: no se guarda (parece un fallo del servicio).")
        return 0
    SALIDA.write_text(json.dumps(resumen, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    hist = json.loads(HISTORIAL.read_text(encoding="utf-8")) if HISTORIAL.is_file() else {}
    HISTORIAL.write_text(json.dumps(anotar_historial(hist, resumen), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    c = resumen["cyl"]
    print(f"[gasóleo] {resumen['fecha']}: {len(resumen['provincias'])} provincias, {resumen['espana']['n']} gasolineras; "
          f"media España {resumen['espana']['media']} €/l" + (f", Castilla y León {c['media']} €/l" if c else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

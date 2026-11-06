"""Avisa cuando una fuente de precios falla, abriendo (o actualizando) una incidencia en GitHub.

Lo ejecuta la tarea «Actualizar precios» después de cada pasada del robot. GitHub manda por correo las incidencias
nuevas a quien vigila el repositorio (el dueño, por defecto), así que no hace falta ningún servicio más.

  * Una lonja con 2 o más lecturas fallidas seguidas  -> aviso «falla».
  * Una lonja activa sin sesión nueva en más de 15 días -> aviso «sin sesiones nuevas» (puede ser normal en
    vacaciones: el aviso lo dice).
  * Si el histórico de la Junta no se pudo actualizar  -> aviso.
Cuando todo vuelve a estar bien, la incidencia se cierra sola con un comentario.

Uso local (sin tocar GitHub):  python scraper/avisar.py --simular
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "precios.json"
ETIQUETA = "aviso-fuentes"
TITULO = "⚠️ Lonjas CyL: hay fuentes de precios con problemas"
FALLOS_PARA_AVISAR = 2
DIAS_SIN_SESION = 15


DIAS_AVISO_PLAZOS = 30


def problema_plazos(plazos: dict | None, hoy: date) -> dict | None:
    """El calendario de la PAC (data/plazos.json) se edita a mano: avisa cuando quedan menos de 30 días para que
    termine el último plazo que tiene, para añadir los nuevos a tiempo."""
    if not plazos:
        return None
    fines = sorted(p["fin"] for p in plazos.get("plazos", []) if p.get("fin"))
    if fines and (date.fromisoformat(fines[-1]) - hoy).days >= DIAS_AVISO_PLAZOS:
        return None
    return {"id": "plazos", "nombre": "Calendario de plazos de la PAC", "tipo": "por actualizar",
            "detalle": (f"El último plazo del calendario termina el {fines[-1]}. " if fines else "El calendario está vacío. ")
                       + "Añade las fechas nuevas en data/plazos.json (con su fuente oficial)."}


def problemas(datos: dict, hoy: date, jcyl: str | None = None, plazos: dict | None = None) -> list[dict]:
    """Lista de problemas actuales, uno por lonja (y uno para el histórico de la Junta y otro para los plazos)."""
    out = []
    pl = problema_plazos(plazos, hoy)
    if pl:
        out.append(pl)
    for l in datos.get("lonjas", []):
        if l.get("estado") == "suspendida":
            continue
        fallos = int(l.get("fallos") or 0)
        if fallos >= FALLOS_PARA_AVISAR:
            out.append({"id": l["id"], "nombre": l.get("nombre", l["id"]), "tipo": "falla",
                        "detalle": f"{fallos} lecturas seguidas sin éxito (desde {(l.get('fallo_desde') or '')[:16].replace('T', ' ')}). "
                                   f"Motivo: {l.get('error') or 'desconocido'}."})
            continue
        if l.get("fecha"):
            dias = (hoy - date.fromisoformat(l["fecha"])).days
            if dias > DIAS_SIN_SESION:
                out.append({"id": l["id"], "nombre": l.get("nombre", l["id"]), "tipo": "sin sesiones nuevas",
                            "detalle": f"La última sesión publicada es del {l['fecha']} (hace {dias} días). "
                                       "Puede ser normal (vacaciones, la lonja no se reunió) o que haya cambiado su web."})
    if jcyl and jcyl not in ("success", "skipped"):
        out.append({"id": "junta", "nombre": "Histórico de la Junta de Castilla y León", "tipo": "falla",
                    "detalle": "No se pudo actualizar el histórico oficial en esta pasada (los precios del día sí se publicaron)."})
    return out


def cuerpo(lista: list[dict], enlace_registro: str | None) -> str:
    filas = "\n".join(f"| {p['nombre']} | {p['tipo']} | {p['detalle']} |" for p in lista)
    return f"""El robot que actualiza los precios ha detectado problemas. **La app sigue funcionando**: muestra los últimos precios buenos de cada lonja.

| Fuente | Problema | Detalle |
|---|---|---|
{filas}

**Qué hacer**
1. Abre el registro de la última pasada{f" ([enlace]({enlace_registro}))" if enlace_registro else ""} y busca las líneas que empiezan por el nombre de la lonja.
2. Si una lonja ha cambiado su web, pásale el registro a Claude para adaptar el lector.
3. Mientras tanto, puedes cargar esa semana a mano con un CSV en `data/manual/` (ver `data/manual/LEEME.txt`).

Esta incidencia se actualiza sola en cada pasada y **se cerrará sola** cuando todo vuelva a funcionar.

<!-- claves: {",".join(sorted(p["id"] + ":" + p["tipo"] for p in lista))} -->"""


def main(argv: list[str]) -> int:
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    ruta_plazos = RAIZ / "data" / "plazos.json"
    plazos = json.loads(ruta_plazos.read_text(encoding="utf-8")) if ruta_plazos.is_file() else None
    lista = problemas(datos, date.today(), os.environ.get("JCYL_RESULTADO"), plazos)
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    run = os.environ.get("GITHUB_RUN_ID")
    enlace = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/actions/runs/{run}" if repo and run else None
    for p in lista:
        print(f"[aviso] {p['nombre']}: {p['tipo']} — {p['detalle']}")
    if not lista:
        print("[aviso] Todas las fuentes funcionan.")
    if "--simular" in argv or not (repo and token):
        print("[aviso] (simulación: no se toca GitHub)")
        return 0

    import requests  # solo hace falta en GitHub
    api = f"https://api.github.com/repos/{repo}"
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                      "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "AppLonjasCyL-avisos"})
    abiertas = s.get(f"{api}/issues", params={"labels": ETIQUETA, "state": "open", "per_page": 10}, timeout=30)
    abiertas.raise_for_status()
    abierta = next(iter(abiertas.json()), None)
    if lista:
        texto = cuerpo(lista, enlace)
        if not abierta:
            r = s.post(f"{api}/issues", json={"title": TITULO, "body": texto, "labels": [ETIQUETA]}, timeout=30)
            r.raise_for_status()
            print(f"[aviso] Incidencia abierta: {r.json().get('html_url')}")
        elif abierta.get("body", "").split("<!-- claves:")[-1] != texto.split("<!-- claves:")[-1]:
            s.patch(f"{api}/issues/{abierta['number']}", json={"body": texto}, timeout=30).raise_for_status()
            s.post(f"{api}/issues/{abierta['number']}/comments", timeout=30,
                   json={"body": "Han cambiado las fuentes con problemas:\n\n" + "\n".join(f"- **{p['nombre']}**: {p['tipo']}" for p in lista)}).raise_for_status()
            print(f"[aviso] Incidencia #{abierta['number']} actualizada")
        else:
            print(f"[aviso] Incidencia #{abierta['number']} sigue abierta (sin cambios)")
    elif abierta:
        s.post(f"{api}/issues/{abierta['number']}/comments", timeout=30,
               json={"body": f"✅ Todas las fuentes vuelven a funcionar ({datetime.now().strftime('%d/%m/%Y %H:%M')}). Cierro el aviso."}).raise_for_status()
        s.patch(f"{api}/issues/{abierta['number']}", json={"state": "closed", "state_reason": "completed"}, timeout=30).raise_for_status()
        print(f"[aviso] Incidencia #{abierta['number']} cerrada")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

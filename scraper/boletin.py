"""Boletín semanal por correo: el comentario del mercado de la semana (data/informes/ultimo.json) en un correo,
enviado con Brevo (plan gratuito: 300 correos al día, contactos ilimitados).

  python scraper/boletin.py --muestra   crea salida/boletin.html para verlo, sin enviar nada
  python scraper/boletin.py --enviar    lo envía a la lista de Brevo (una vez por semana como mucho)

Configuración:
  * Secretos de GitHub: BREVO_API_KEY (la clave de la API de Brevo) y BREVO_REMITENTE (el correo remitente,
    verificado en Brevo). Nunca van en el código.
  * data/boletin.json: {"lista": <número de la lista de Brevo>, "alta": "<enlace al formulario de alta de Brevo>",
    "enviados": ["2026-W46", ...]}. La lista y el enlace no son secretos.
Sin la clave o sin lista, no hace nada. La baja la gestiona Brevo ({{ unsubscribe }} en el pie).
"""
from __future__ import annotations

import json
import os
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paginas import MESES, WEB  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
INFORME = RAIZ / "data" / "informes" / "ultimo.json"
GASOLEO = RAIZ / "data" / "gasoleo.json"
CONFIG = RAIZ / "data" / "boletin.json"
API = "https://api.brevo.com/v3"
REMITENTE_NOMBRE = "Lonjas CyL"

# Colores de la app (en los correos los estilos van escritos en cada etiqueta: muchos lectores ignoran <style>)
PINO, FONDO, HOJA, TINTA, TENUE, LINEA, PAJA = "#24503c", "#eef1ea", "#ffffff", "#18241d", "#5b6a60", "#d6ddd2", "#e0b252"
LETRA = "font-family:Arial,Helvetica,sans-serif"


def leer(f: Path, defecto):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def rango(desde: str, hasta: str) -> str:
    """«9 – 14 de noviembre de 2026»; si cambia de mes, «30 de noviembre – 5 de diciembre de 2026»."""
    a, b = (list(map(int, x.split("-"))) for x in (desde, hasta))
    if a[1] == b[1]:
        return f"{a[2]} – {b[2]} de {MESES[b[1] - 1]} de {b[0]}"
    return f"{a[2]} de {MESES[a[1] - 1]} – {b[2]} de {MESES[b[1] - 1]} de {b[0]}"


def asunto(inf: dict) -> str:
    return f"{inf.get('titular') or 'El mercado de la semana'} · Lonjas CyL"[:150]


def url_semana(inf: dict, web: str = WEB) -> str:
    return f"{web}mercado/{inf['semana'].lower()}/"


def linea_gasoleo(g: dict | None) -> str:
    if not g or not g.get("cyl"):
        return ""
    l3 = lambda v: f"{v:.3f}".replace(".", ",")
    cyl = [p for p in g.get("provincias", []) if p.get("cyl") and p.get("baratas")]
    b = min(cyl, key=lambda p: p["baratas"][0]["precio"]) if cyl else None
    txt = f"Gasóleo agrícola (B): {l3(g['cyl']['media'])} €/l de media en Castilla y León"
    if b:
        txt += f"; el más barato, {l3(b['baratas'][0]['precio'])} €/l en {b['baratas'][0]['localidad']} ({b['nombre']})"
    return txt + "."


def html_correo(inf: dict, g: dict | None = None, web: str = WEB) -> str:
    """Correo en HTML de tabla (lo que mejor se ve en Gmail, Outlook y el móvil), 600 px como mucho."""
    u = url_semana(inf, web)
    p = lambda t, extra="": f'<p style="margin:0 0 14px;{LETRA};font-size:16px;line-height:1.55;color:{TINTA};{extra}">{t}</p>'
    cuerpo = []
    for bloque in inf.get("redaccion", []):
        if bloque.get("t"):
            cuerpo.append(f'<h2 style="margin:22px 0 8px;{LETRA};font-size:18px;color:{PINO};">{escape(bloque["t"])}</h2>')
        if bloque.get("p"):
            cuerpo.append(p(escape(bloque["p"])))
    gas = linea_gasoleo(g)
    if gas:
        cuerpo.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 16px;"><tr>'
                      f'<td style="background:{FONDO};border-radius:10px;padding:12px 14px;{LETRA};font-size:15px;color:{TINTA};">⛽ {escape(gas)} '
                      f'<a href="{web}#gasoleo" style="color:{PINO};">Ver gasolineras</a></td></tr></table>')
    audio = (f'<a href="{u}" style="display:inline-block;margin:6px 0 18px;padding:12px 18px;background:{PAJA};color:{TINTA};'
             f'text-decoration:none;border-radius:999px;{LETRA};font-weight:bold;font-size:15px;">▶ Escuchar el comentario</a>') if inf.get("audio") else ""
    fuentes = escape("; ".join(inf.get("fuentes", [])))
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(inf.get('titulo', 'Boletín'))}</title></head>
<body style="margin:0;padding:0;background:{FONDO};">
<div style="display:none;max-height:0;overflow:hidden;">{escape((inf.get('resumen') or [''])[0])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO};"><tr><td align="center" style="padding:16px 8px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:{HOJA};border-radius:14px;overflow:hidden;">
<tr><td style="background:{PINO};padding:18px 22px;{LETRA};">
  <div style="font-size:22px;font-weight:bold;color:#ffffff;letter-spacing:.5px;">LONJAS CYL</div>
  <div style="font-size:13px;color:#cfe0d4;margin-top:2px;">Boletín semanal · {escape(rango(inf['desde'], inf['hasta']))}</div>
</td></tr>
<tr><td style="padding:22px 22px 8px;">
  <h1 style="margin:0 0 14px;{LETRA};font-size:24px;line-height:1.25;color:{TINTA};">{escape(inf.get('titular', ''))}</h1>
  {audio}
  {''.join(cuerpo)}
  <a href="{u}" style="display:inline-block;margin:8px 0 6px;padding:12px 18px;background:{PINO};color:#ffffff;text-decoration:none;border-radius:999px;{LETRA};font-weight:bold;font-size:15px;">Ver precios y gráficos</a>
</td></tr>
<tr><td style="padding:16px 22px 22px;border-top:1px solid {LINEA};{LETRA};font-size:12px;line-height:1.5;color:{TENUE};">
  Precios orientativos: cada lonja cotiza en sus propias condiciones; confírmalos con tu lonja o comprador. Fuentes: {fuentes}.<br>
  Lonjas CyL es una web independiente; no pertenece a ninguna lonja ni administración.<br>
  Recibes este correo porque te apuntaste al boletín. <a href="{{{{ unsubscribe }}}}" style="color:{TENUE};">Darse de baja</a> · <a href="{web}" style="color:{TENUE};">Abrir la app</a> · <a href="https://t.me/lonjas_cyl" style="color:{TENUE};">Canal de Telegram</a>
</td></tr>
</table></td></tr></table>
</body></html>
"""


def enviar(inf: dict, html: str, lista: int, remitente: str, clave: str, post=None) -> int:
    """Crea la campaña en Brevo y la envía ya. Devuelve el id de la campaña."""
    if post is None:
        import requests

        def post(ruta, cuerpo):
            r = requests.post(API + ruta, json=cuerpo, timeout=60,
                              headers={"api-key": clave, "accept": "application/json", "content-type": "application/json"})
            if r.status_code >= 400:
                raise RuntimeError(f"Brevo {ruta}: {r.status_code} {r.text[:300]}")
            return r.json() if r.content else {}
    camp = post("/emailCampaigns", {
        "name": f"Boletín {inf['semana']}", "subject": asunto(inf),
        "previewText": (inf.get("resumen") or [""])[0][:140],
        "sender": {"name": REMITENTE_NOMBRE, "email": remitente},
        "htmlContent": html, "recipients": {"listIds": [int(lista)]}, "inlineImageActivation": False,
    })
    post(f"/emailCampaigns/{camp['id']}/sendNow", {})
    return camp["id"]


def main(argv: list[str]) -> int:
    inf = leer(INFORME, None)
    if not inf or not inf.get("semana"):
        print("[boletín] No hay comentario semanal: nada que enviar.")
        return 0
    html = html_correo(inf, leer(GASOLEO, None))
    if "--muestra" in argv:
        f = RAIZ / "salida" / "boletin.html"
        f.parent.mkdir(exist_ok=True)
        f.write_text(html, encoding="utf-8")
        print(f"[boletín] Muestra en {f} · asunto: {asunto(inf)}")
        return 0
    cfg = leer(CONFIG, {})
    clave, remitente = os.environ.get("BREVO_API_KEY", "").strip(), os.environ.get("BREVO_REMITENTE", "").strip()
    if not (clave and remitente and cfg.get("lista")):
        print("[boletín] Sin configurar (faltan BREVO_API_KEY, BREVO_REMITENTE o la lista en data/boletin.json): no se envía.")
        return 0
    if inf["semana"] in cfg.get("enviados", []):
        print(f"[boletín] La semana {inf['semana']} ya se envió.")
        return 0
    cid = enviar(inf, html, cfg["lista"], remitente, clave)
    cfg["enviados"] = (cfg.get("enviados", []) + [inf["semana"]])[-60:]
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[boletín] Enviado el boletín {inf['semana']} (campaña {cid}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

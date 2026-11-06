"use strict";
/* Página #datos: datos abiertos (CSV y JSON que genera scraper/datos_abiertos.py) y configurador del widget
   (widget/) para que otras webs pongan los precios. */
const WIDGET = { lonja: "", p: "trigo", tema: "claro" };

function urlWidget() {
  const u = new URL("widget/", location.href);
  u.hash = "";
  u.search = "";
  if (WIDGET.lonja) u.searchParams.set("lonja", WIDGET.lonja);
  if (WIDGET.p && WIDGET.p !== "principales") u.searchParams.set("p", WIDGET.p);
  if (WIDGET.tema === "oscuro") u.searchParams.set("tema", "oscuro");
  return u.href;
}
function filasWidget() {
  if (WIDGET.lonja) {
    const l = DATOS.lonjas.find(x => x.id === WIDGET.lonja);
    if (!l) return 4;
    if (WIDGET.p === "principales") return Math.min(8, Math.max(1, l.precios.filter(f => f.act != null && ["trigo", "cebada", "maiz", "girasol", "cerdo-normal", "lechones", "lechazo"].includes(f.clave)).length || 8));
    return Math.max(1, l.precios.filter(f => f.act != null && f.clave === WIDGET.p).length);
  }
  return Math.max(1, DATOS.lonjas.filter(l => l.precios.some(f => f.act != null && f.clave === WIDGET.p)).length);
}
function codigoWidget() {
  const alto = 100 + filasWidget() * 52;
  return `<iframe src="${urlWidget()}" title="Precios de las lonjas · Lonjas CyL" width="100%" height="${alto}" style="max-width:420px;border:0" loading="lazy"></iframe>`;
}

function vistaDatos() {
  const activas = DATOS.lonjas.filter(l => l.estado !== "suspendida");
  if (WIDGET.lonja && !activas.some(l => l.id === WIDGET.lonja)) WIDGET.lonja = "";
  const claves = PRODUCTOS_CLAVE.filter(([c]) => todasLasFilas().some(f => f.clave === c && f.act != null && (!WIDGET.lonja || f.lonja.id === WIDGET.lonja)));
  if (WIDGET.p !== "principales" && !claves.some(([c]) => c === WIDGET.p)) WIDGET.p = WIDGET.lonja ? "principales" : (claves[0] || ["trigo"])[0];
  if (!WIDGET.lonja && WIDGET.p === "principales") WIDGET.p = "trigo";
  const opt = (v, t, sel) => `<option value="${esc(v)}"${v === sel ? " selected" : ""}>${esc(t)}</option>`;
  const desc = (n, f, t) => `<li><a href="data/abiertos/${f}" download>${n}</a> — ${t}</li>`;
  return `<section class="seccion metodo">
    <div class="cab-lonja"><button class="volver" type="button" data-ir="metodo">‹ Volver</button><h2>Datos abiertos y widget</h2>
      <div class="meta">Los precios de Lonjas CyL, listos para tu hoja de cálculo, tu programa o tu web. Se actualizan con cada pasada del robot.</div></div>

    <h3 class="sub">Descargar</h3>
    <ul class="lista">
      ${desc("precios.csv", "precios.csv", "última sesión de cada lonja, una fila por producto. Se abre directamente con Excel.")}
      ${desc("historial.csv", "historial.csv", "todas las sesiones guardadas por la app: lonja, producto, fecha y precio.")}
      ${desc("precios.json", "precios.json", "lo mismo que precios.csv, para programas (formato versión 1, números con punto).")}
    </ul>
    <p class="nota">CSV con «;» como separador, decimales con coma y UTF-8. Columnas de precios.csv: lonja, fecha de la sesión, mesa, producto, unidad, precio, anterior, variación, horquilla, si cotizó o no (con su último precio y fecha) y la fuente original.</p>

    <h3 class="sub">Licencia</h3>
    <ul class="lista">
      <li>Puedes reutilizar estos datos citando «Lonjas CyL» y la lonja de origen de cada precio (columna <i>fuente</i>).</li>
      <li>Los precios de la Lonja de Salamanca son datos abiertos de la Diputación de Salamanca, licencia <a href="https://creativecommons.org/licenses/by/4.0/deed.es" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>. El resto proceden de las publicaciones públicas de cada lonja, que conservan sus derechos.</li>
      <li>Son precios orientativos: no son una oferta ni una recomendación de compra o venta.</li>
    </ul>

    <h3 class="sub">Pon los precios en tu web</h3>
    <p class="nota">Una tabla pequeña que se actualiza sola. Elige qué mostrar, copia el código y pégalo en tu página (WordPress: bloque «HTML personalizado»).</p>
    <form class="widget-form" data-widget-form>
      <label class="campo"><span class="etiqueta">Qué mostrar</span><select name="lonja">${opt("", "Un producto en todas las lonjas", WIDGET.lonja)}${activas.map(l => opt(l.id, l.nombre, WIDGET.lonja)).join("")}</select></label>
      <label class="campo"><span class="etiqueta">Producto</span><select name="p">${WIDGET.lonja ? opt("principales", "Los principales", WIDGET.p) : ""}${claves.map(([c, n]) => opt(c, n, WIDGET.p)).join("")}</select></label>
      <label class="campo"><span class="etiqueta">Colores</span><select name="tema">${opt("claro", "Claros", WIDGET.tema)}${opt("oscuro", "Oscuros", WIDGET.tema)}</select></label>
    </form>
    <label class="campo"><span class="etiqueta">Código para tu web</span><textarea class="codigo" id="codigo-widget" readonly rows="4" spellcheck="false">${esc(codigoWidget())}</textarea></label>
    <div class="enlaces-pie"><button class="chip boton" type="button" data-copiar-widget>Copiar código</button><a class="chip auto" href="${esc(urlWidget())}" target="_blank" rel="noopener">Ver cómo queda ›</a></div>
    <p class="nota">El widget muestra siempre la fuente de cada precio y un enlace a Lonjas CyL.</p>
  </section>`;
}

document.addEventListener("change", e => {
  const f = e.target.closest("[data-widget-form]");
  if (!f) return;
  const k = e.target.name;
  if (k === "lonja") { WIDGET.lonja = e.target.value; WIDGET.p = WIDGET.lonja ? "principales" : "trigo"; }
  else if (k === "p") WIDGET.p = e.target.value;
  else if (k === "tema") WIDGET.tema = e.target.value === "oscuro" ? "oscuro" : "claro";
  router();
  const otra = document.querySelector(`[data-widget-form] [name="${k}"]`);
  if (otra) otra.focus();
});
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-copiar-widget]");
  if (!b) return;
  const area = document.getElementById("codigo-widget");
  try { await navigator.clipboard.writeText(area.value); b.textContent = "✓ Copiado"; }
  catch { area.focus(); area.select(); b.textContent = "Selecciona y copia (Ctrl+C)"; }
});

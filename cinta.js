/* Barra de cotizaciones (debajo de la cabecera, siempre visible): para cada producto principal, el mejor precio
   entre las lonjas que han cotizado en los últimos 14 días, qué lonja lo paga y su cambio; y el gasóleo B medio de
   Castilla y León. Desfila sola; se para al tocarla o al pasar el ratón; sin animación si el teléfono lo pide
   (prefers-reduced-motion), y entonces se desliza con el dedo. Cada cifra lleva a su comparativa. */
"use strict";

const CINTA_PRODUCTOS = [
  ["trigo", "Trigo"], ["cebada", "Cebada"], ["maiz", "Maíz"], ["centeno", "Centeno"], ["triticale", "Triticale"],
  ["avena", "Avena"], ["girasol", "Girasol"], ["alfalfa", "Alfalfa"], ["lechazo", "Lechazo"],
  ["cerdo-normal", "Cerdo"], ["lechones", "Lechones"],
];

function itemsCinta() {
  if (!DATOS) return [];
  const desde = new Date(Date.now() - 14 * 86400000).toISOString().slice(0, 10);
  const filas = todasLasFilas().filter(f => f.act != null && (f.lonja.fecha || "") >= desde);
  const out = [];
  for (const [clave, nombre] of CINTA_PRODUCTOS) {
    const de = filas.filter(f => f.clave === clave);
    if (!de.length) continue;
    // la unidad más habitual del producto (no se mezclan €/t con €/kg)
    const cuenta = {};
    de.forEach(f => { cuenta[f.unidad] = (cuenta[f.unidad] || 0) + 1; });
    const unidad = Object.keys(cuenta).sort((a, b) => cuenta[b] - cuenta[a])[0];
    const mejor = de.filter(f => f.unidad === unidad).sort((a, b) => b.act - a.act)[0];
    const v = variacion(mejor);
    out.push({
      href: `#comparar-${clave}`, nombre, valor: precio(mejor.act, unidad), unidad,
      cambio: v.clase === "s" || v.clase === "b" ? v.txt.replace("▲ ", "▲").replace("▼ ", "▼") : (v.txt === "=" ? "=" : ""),
      clase: v.clase, donde: mejor.lonja.nombre.replace("Lonja de ", ""),
      titulo: `${nombre}: mejor precio ${precio(mejor.act, unidad)} ${unidad} en ${mejor.lonja.nombre} (sesión del ${fechaCorta(mejor.lonja.fecha)})`,
    });
  }
  const g = typeof GASOLEO !== "undefined" && GASOLEO.datos;
  if (g && g.cyl) {
    const l = g.cyl.media.toLocaleString("es-ES", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
    out.push({ href: "#gasoleo", nombre: "Gasóleo B", valor: l, unidad: "€/l", cambio: "", clase: "i", donde: "media CyL",
               titulo: `Gasóleo agrícola (B): ${l} €/l de media en Castilla y León` });
  }
  return out;
}

function htmlCinta(items) {
  const uno = items.map(x => `<a class="cinta-item" href="${x.href}" title="${esc(x.titulo)}">
      <span class="ci-nombre">${esc(x.nombre)}</span>
      <span class="ci-valor num">${esc(x.valor)}<small> ${esc(x.unidad)}</small></span>
      ${x.cambio ? `<span class="ci-cambio ${x.clase === "s" ? "sube" : x.clase === "b" ? "baja" : ""}">${esc(x.cambio)}</span>` : ""}
      <span class="ci-donde">${esc(x.donde)}</span></a>`).join("");
  // Dos copias seguidas: al desplazar la mitad, el bucle no se nota. La segunda la ignoran los lectores de pantalla.
  return `<div class="cinta-pista">${uno}<span class="cinta-copia" aria-hidden="true">${uno.replace(/<a /g, '<a tabindex="-1" ')}</span></div>`;
}

function pintarCinta() {
  const caja = document.getElementById("cinta");
  if (!caja || !DATOS) return;
  const items = itemsCinta();
  caja.hidden = !items.length;
  if (items.length) {
    caja.innerHTML = htmlCinta(items);
    // velocidad según cuántas cifras haya (por código: la política de seguridad no deja estilos escritos en el HTML)
    caja.querySelector(".cinta-pista").style.setProperty("--dur", `${Math.max(20, items.length * 4.5)}s`);
  }
  // el gasóleo llega aparte: cuando esté, se vuelve a pintar (una sola vez)
  if (typeof GASOLEO !== "undefined" && !GASOLEO.datos && !GASOLEO.error && typeof cargarGasoleo === "function" && !pintarCinta.esperando) {
    pintarCinta.esperando = true;
    Promise.resolve(cargarGasoleo()).then(() => { pintarCinta.esperando = false; if (GASOLEO.datos) pintarCinta(); });
  }
}

/* Parar y seguir con un toque (en el móvil no hay «pasar el ratón») */
document.addEventListener("touchstart", e => {
  const c = e.target.closest?.("#cinta");
  if (c) c.classList.add("parada");
}, { passive: true });
document.addEventListener("touchend", e => {
  const c = e.target.closest?.("#cinta");
  if (c) setTimeout(() => c.classList.remove("parada"), 2500);
}, { passive: true });

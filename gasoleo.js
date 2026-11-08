/* Gasóleo agrícola (Gasóleo B): precio medio por provincia y gasolineras más baratas.
   Datos: data/gasoleo.json, que el robot saca del servicio oficial del Ministerio para la Transición Ecológica
   (el del Geoportal de gasolineras). Ruta #gasoleo y una tarjeta en Hoy. «Mi provincia» se guarda en el teléfono. */
"use strict";

const RUTA_GASOLEO = "data/gasoleo.json";
const GASOLEO = { datos: null, cargando: null, error: false };
const CLAVE_PROV = "lonjas-gasoleo-provincia";

function sanearGasoleo(c) {
  if (!c || !Array.isArray(c.provincias)) return null;
  const num = v => (typeof v === "number" && isFinite(v) ? v : null);
  const txt = v => (typeof v === "string" ? v.slice(0, 200) : "");
  const resumen = r => (r && num(r.media) != null ? { media: num(r.media), min: num(r.min), n: num(r.n) } : null);
  return {
    fecha: txt(c.fecha), fuente: txt(c.fuente), fuente_url: /^https:\/\//.test(c.fuente_url || "") ? c.fuente_url : "",
    espana: resumen(c.espana), cyl: resumen(c.cyl),
    provincias: c.provincias.filter(p => p && /^\d{2}$/.test(p.id) && num(p.media) != null).map(p => ({
      id: p.id, nombre: txt(p.nombre), cyl: !!p.cyl, n: num(p.n), media: num(p.media), min: num(p.min), max: num(p.max),
      descartados: num(p.descartados) || 0,
      baratas: (Array.isArray(p.baratas) ? p.baratas : []).slice(0, 3).filter(b => num(b.precio) != null).map(b => ({
        nombre: txt(b.nombre), precio: num(b.precio), direccion: txt(b.direccion), localidad: txt(b.localidad),
        horario: txt(b.horario), lat: num(b.lat), lon: num(b.lon) })),
    })),
  };
}

function cargarGasoleo() {
  if (GASOLEO.datos || GASOLEO.cargando) return GASOLEO.cargando;
  GASOLEO.cargando = fetch(RUTA_GASOLEO, { cache: "no-cache" })
    .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(c => { GASOLEO.datos = sanearGasoleo(c); GASOLEO.error = !GASOLEO.datos; })
    .catch(() => { GASOLEO.error = true; })
    .finally(() => {
      GASOLEO.cargando = null;
      const h = location.hash.slice(1) || "hoy";
      if (h === "hoy" || h === "gasoleo") router();
    });
  return GASOLEO.cargando;
}

const litro = v => v == null ? "—" : v.toLocaleString("es-ES", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
function miProvincia() { try { return localStorage.getItem(CLAVE_PROV) || ""; } catch { return ""; } }
function fechaHora(iso) {
  if (!iso) return "";
  const [d, h] = iso.split("T");
  return `${fechaCorta(d)}${h ? ", " + h.slice(0, 5) + " h" : ""}`;
}
function mapa(b) {
  return b.lat != null && b.lon != null
    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(b.lat + "," + b.lon)}` : "";
}

/* Tarjeta en Hoy */
function bloqueGasoleo() {
  const d = GASOLEO.datos;
  if (!d) { if (!GASOLEO.error) cargarGasoleo(); return ""; }
  const mia = d.provincias.find(p => p.id === miProvincia());
  const cyl = d.provincias.filter(p => p.cyl);
  const base = mia ? [mia] : cyl;
  if (!base.length) return "";
  const barata = base.flatMap(p => p.baratas.slice(0, 1).map(b => ({ ...b, prov: p.nombre }))).sort((a, b) => a.precio - b.precio)[0];
  const media = mia ? mia.media : d.cyl?.media;
  return `<section class="seccion">
    <button class="gasoleo-hoy" type="button" data-ir="gasoleo">
      <span class="etiqueta">Gasóleo agrícola (B) · hoy</span>
      <span class="gh-fila"><span><b class="num">${litro(media)}</b> <small>€/l de media en ${esc(mia ? mia.nombre : "Castilla y León")}</small></span>
      ${barata ? `<span class="gh-barata">Más barato: <b class="num">${litro(barata.precio)}</b> en ${esc(barata.localidad)}${mia ? "" : ` (${esc(barata.prov)})`}</span>` : ""}</span>
      <span class="gh-ver">Ver todas las provincias ›</span>
    </button>
  </section>`;
}

function tarjetaProvincia(p, abierta) {
  const filas = p.baratas.map((b, i) => `<li>
      <span class="gp-precio num">${litro(b.precio)}</span>
      <span class="gp-sitio"><b>${i === 0 ? "★ " : ""}${esc(b.nombre)}</b><small>${esc(b.localidad)}${b.direccion ? " · " + esc(b.direccion) : ""}</small>${b.horario ? `<small>${esc(b.horario)}</small>` : ""}</span>
      ${mapa(b) ? `<a class="gp-mapa" href="${esc(mapa(b))}" target="_blank" rel="noopener noreferrer">Cómo llegar</a>` : ""}
    </li>`).join("");
  return `<details class="gasoleo-prov"${abierta ? " open" : ""}>
    <summary>
      <span class="gp-nombre">${esc(p.nombre)}</span>
      <span class="gp-media"><b class="num">${litro(p.media)}</b> <small>€/l media</small></span>
      <span class="gp-min">más barato <b class="num">${litro(p.min)}</b> · ${p.n} gasolinera${p.n === 1 ? "" : "s"}</span>
    </summary>
    <ol class="gp-lista">${filas}</ol>
    ${p.descartados ? `<p class="gp-nota">No se cuenta${p.descartados === 1 ? "" : "n"} ${p.descartados} precio${p.descartados === 1 ? "" : "s"} que se aleja${p.descartados === 1 ? "" : "n"} más de un 20 % del habitual en la provincia (suelen ser datos sin actualizar).</p>` : ""}
  </details>`;
}

function vistaGasoleo() {
  const d = GASOLEO.datos;
  if (!d) {
    if (!GASOLEO.error) cargarGasoleo();
    return `<section class="seccion"><div class="titulo-seccion"><h2>Gasóleo agrícola (B)</h2></div>
      <div class="vacio">${GASOLEO.error ? "<b>No se han podido cargar los precios del gasóleo</b>Comprueba la conexión y vuelve a intentarlo." : "Cargando precios…"}</div></section>`;
  }
  const mia = miProvincia();
  const opciones = d.provincias.map(p => `<option value="${p.id}"${p.id === mia ? " selected" : ""}>${esc(p.nombre)}</option>`).join("");
  const pMia = d.provincias.find(p => p.id === mia);
  const cyl = d.provincias.filter(p => p.cyl && p.id !== mia);
  const resto = d.provincias.filter(p => !p.cyl && p.id !== mia);
  return `<section class="seccion">
    <div class="titulo-seccion"><h2>Gasóleo agrícola (B)</h2><span>Actualizado ${fechaHora(d.fecha)}</span></div>
    <p class="gasoleo-lead">Precio medio hoy: <b class="num">${litro(d.cyl?.media)}</b> €/l en Castilla y León y <b class="num">${litro(d.espana?.media)}</b> €/l en España. Abre una provincia para ver sus 3 gasolineras más baratas.</p>
    <label class="gasoleo-mia">Mi provincia
      <select id="gasoleo-provincia"><option value="">— elige para verla siempre primero —</option>${opciones}</select>
    </label>
    ${pMia ? `<h3 class="gasoleo-grupo">Mi provincia</h3>${tarjetaProvincia(pMia, true)}` : ""}
    <h3 class="gasoleo-grupo">Castilla y León</h3>
    ${cyl.map(p => tarjetaProvincia(p, false)).join("")}
    <details class="gasoleo-resto"><summary>Resto de España (${resto.length} provincias)</summary>${resto.map(p => tarjetaProvincia(p, false)).join("")}</details>
    <p class="nota">Precios que las gasolineras comunican al Ministerio para la Transición Ecológica (solo venta al público); pueden cambiar a lo largo del día. Fuente: ${d.fuente_url ? `<a href="${esc(d.fuente_url)}" target="_blank" rel="noopener noreferrer">${esc(d.fuente)}</a>` : esc(d.fuente)}. El gasóleo B solo puede usarse en los usos autorizados (maquinaria agrícola, entre otros).</p>
  </section>`;
}

document.addEventListener("change", e => {
  if (e.target.id !== "gasoleo-provincia") return;
  try { e.target.value ? localStorage.setItem(CLAVE_PROV, e.target.value) : localStorage.removeItem(CLAVE_PROV); } catch {}
  router();
});

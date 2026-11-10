/* Gasóleo agrícola (Gasóleo B): precio medio por provincia y gasolineras más baratas.
   Datos: data/gasoleo.json, que el robot saca del servicio oficial del Ministerio para la Transición Ecológica
   (el del Geoportal de gasolineras). Ruta #gasoleo y una tarjeta en Hoy. «Mi provincia» se guarda en el teléfono. */
"use strict";

const RUTA_GASOLEO = "data/gasoleo.json";
const GASOLEO = { datos: null, cargando: null, error: false };
const CLAVE_PROV = "lonjas-gasoleo-provincia";
let BUSQUEDA_GAS = "";

const numG = v => (typeof v === "number" && isFinite(v) ? v : null);
const txtG = v => (typeof v === "string" ? v.slice(0, 200) : "");
function estaciones(lista, max, prov) {
  return (Array.isArray(lista) ? lista : []).slice(0, max).filter(b => b && numG(b.precio) != null).map(b => ({
    id: /^\d{1,9}$/.test(b.id || "") ? b.id : "", nombre: txtG(b.nombre), precio: numG(b.precio), municipio: txtG(b.municipio || b.localidad),
    direccion: txtG(b.direccion), localidad: txtG(b.localidad), horario: txtG(b.horario), lat: numG(b.lat), lon: numG(b.lon),
    dudoso: b.dudoso === true, prov: txtG(prov.nombre) }));
}

function sanearGasoleo(c) {
  if (!c || !Array.isArray(c.provincias)) return null;
  const num = numG, txt = txtG;
  const resumen = r => (r && num(r.media) != null ? { media: num(r.media), min: num(r.min), n: num(r.n) } : null);
  return {
    fecha: txt(c.fecha), fuente: txt(c.fuente), fuente_url: /^https:\/\//.test(c.fuente_url || "") ? c.fuente_url : "",
    espana: resumen(c.espana), cyl: resumen(c.cyl),
    provincias: c.provincias.filter(p => p && /^\d{2}$/.test(p.id) && num(p.media) != null).map(p => ({
      id: p.id, nombre: txt(p.nombre), cyl: !!p.cyl, n: num(p.n), media: num(p.media), min: num(p.min), max: num(p.max),
      descartados: num(p.descartados) || 0,
      baratas: estaciones(p.baratas, 3, p),
      todas: Array.isArray(p.todas) ? estaciones(p.todas, 500, p) : null,
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
      if (h === "hoy" || h === "gasoleo" || h === "favoritos") router();
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

/* Gasolineras favoritas: id oficial (IDEESS) -> {nombre, localidad, prov} (para mostrarlas aunque un día no den precio) */
const CLAVE_GAS_FAV = "lonjas-gasolineras-favoritas";
function leerGasFav() {
  try { const o = JSON.parse(localStorage.getItem(CLAVE_GAS_FAV) || "{}"); return o && typeof o === "object" && !Array.isArray(o) ? o : {}; }
  catch { return {}; }
}
function guardarGasFav(o) { try { localStorage.setItem(CLAVE_GAS_FAV, JSON.stringify(o)); } catch {} }
function todasLasGasolineras() {
  const d = GASOLEO.datos, mapa = new Map();
  if (!d) return mapa;
  for (const p of d.provincias) for (const b of [...(p.todas || []), ...p.baratas]) if (b.id && !mapa.has(b.id)) mapa.set(b.id, b);
  return mapa;
}

function filaGasolinera(b, { destacar = false, conProvincia = false } = {}) {
  const fav = !!(b.id && leerGasFav()[b.id]);
  return `<li class="${destacar ? "mas-barata" : ""}${b.dudoso ? " dudosa" : ""}">
      <span class="gp-precio num">${litro(b.precio)}</span>
      <span class="gp-sitio"><b>${esc(b.nombre)}</b><small>${esc(b.municipio || b.localidad)}${conProvincia && b.prov ? ` (${esc(b.prov)})` : ""}${b.direccion ? " · " + esc(b.direccion) : ""}</small>${b.horario ? `<small>${esc(b.horario)}</small>` : ""}${destacar ? `<small class="gp-etq">La más barata</small>` : ""}${b.dudoso ? `<small class="gp-etq dud">Precio dudoso: se aleja más de un 20 % del habitual</small>` : ""}${mapa(b) ? `<a class="gp-mapa" href="${esc(mapa(b))}" target="_blank" rel="noopener noreferrer">Cómo llegar</a>` : ""}</span>
      ${b.id ? `<button class="gp-fav${fav ? " on" : ""}" type="button" data-fav-gas="${esc(b.id)}" aria-pressed="${fav}" aria-label="${fav ? "Quitar de" : "Añadir a"} favoritos: ${esc(b.nombre)}, ${esc(b.municipio || b.localidad)}">${fav ? "★" : "☆"}</button>` : ""}
    </li>`;
}

/* Favoritos -> «Mis gasolineras» */
function seccionGasolinerasFav() {
  const favs = leerGasFav(), ids = Object.keys(favs);
  if (!ids.length) return "";
  if (!GASOLEO.datos) {
    if (!GASOLEO.error) cargarGasoleo();
    return `<section class="seccion"><div class="titulo-seccion"><h2>Mis gasolineras</h2></div><div class="vacio">${GASOLEO.error ? "No se han podido cargar los precios del gasóleo." : "Cargando precios del gasóleo…"}</div></section>`;
  }
  const todas = todasLasGasolineras();
  const filas = ids.map(id => todas.get(id) || { id, ...favs[id], precio: null, sinPrecio: true })
    .sort((a, b) => (a.precio ?? 9) - (b.precio ?? 9));
  return `<section class="seccion">
    <div class="titulo-seccion"><h2>Mis gasolineras</h2><span>Gasóleo B · ${fechaHora(GASOLEO.datos.fecha)} · <button class="enlace" type="button" data-ir="gasoleo">ver todas</button></span></div>
    <ol class="gp-lista gp-favs">${filas.map(b => b.sinPrecio
      ? `<li><span class="gp-precio num">—</span><span class="gp-sitio"><b>${esc(b.nombre || "Gasolinera")}</b><small>${esc(b.localidad || "")} · hoy no ha comunicado precio</small></span>
         <button class="gp-fav on" type="button" data-fav-gas="${esc(b.id)}" aria-pressed="true" aria-label="Quitar de favoritos">★</button></li>`
      : filaGasolinera(b, { conProvincia: true })).join("")}</ol>
  </section>`;
}

function normalizar(t) { return (t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim(); }

/* Buscador de municipios (Castilla y León) */
function resultadosBusqueda(q) {
  const d = GASOLEO.datos;
  const n = normalizar(q);
  if (!d || n.length < 2) return "";
  const hits = d.provincias.filter(p => p.cyl).flatMap(p => p.todas || p.baratas)
    .filter(b => normalizar(`${b.municipio} ${b.localidad} ${b.nombre}`).includes(n))
    .sort((a, b) => (a.dudoso - b.dudoso) || a.precio - b.precio);
  if (!hits.length) return `<p class="gasoleo-sin">Ninguna gasolinera con gasóleo B en «${esc(q)}». Prueba con otro municipio o con parte del nombre.</p>`;
  return `<p class="gasoleo-cuenta">${hits.length} gasolinera${hits.length === 1 ? "" : "s"} en «${esc(q)}»</p>
    <ol class="gp-lista gp-busqueda">${hits.slice(0, 80).map((b, i) => filaGasolinera(b, { destacar: i === 0 && !b.dudoso, conProvincia: true })).join("")}</ol>`;
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
  const lista = p.todas || p.baratas;
  const primera = lista.findIndex(b => !b.dudoso);
  const filas = lista.map((b, i) => filaGasolinera(b, { destacar: i === primera })).join("");
  return `<details class="gasoleo-prov"${abierta ? " open" : ""}>
    <summary>
      <span class="gp-nombre">${esc(p.nombre)}</span>
      <span class="gp-media"><b class="num">${litro(p.media)}</b> <small>€/l media</small></span>
      <span class="gp-min">más barato <b class="num">${litro(p.min)}</b> · ${p.n} gasolinera${p.n === 1 ? "" : "s"}${p.todas ? " · ver todas" : ""}</span>
    </summary>
    ${p.todas ? "" : `<p class="gp-nota gp-nota-arriba">Las 3 más baratas de la provincia.</p>`}
    <ol class="gp-lista">${filas}</ol>
    ${p.descartados ? `<p class="gp-nota">${p.descartados} precio${p.descartados === 1 ? "" : "s"} se aleja${p.descartados === 1 ? "" : "n"} más de un 20 % del habitual en la provincia (suelen ser datos sin actualizar): no cuenta${p.descartados === 1 ? "" : "n"} para la media${p.todas ? " y salen marcados" : ""}.</p>` : ""}
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
    <p class="gasoleo-lead">Precio medio hoy: <b class="num">${litro(d.cyl?.media)}</b> €/l en Castilla y León y <b class="num">${litro(d.espana?.media)}</b> €/l en España. En Castilla y León, abre una provincia para ver todas sus gasolineras, o busca tu municipio. Toca ☆ para guardarla en Favoritos.</p>
    <label class="gasoleo-buscar">Buscar municipio en Castilla y León
      <input id="gasoleo-buscar" type="search" inputmode="search" autocomplete="off" placeholder="Ej.: Peñafiel, Roa, La Bañeza…" value="${esc(BUSQUEDA_GAS)}">
    </label>
    <div id="gasoleo-resultados">${resultadosBusqueda(BUSQUEDA_GAS)}</div>
    <div id="gasoleo-provincias"${normalizar(BUSQUEDA_GAS).length >= 2 ? " hidden" : ""}>
    <label class="gasoleo-mia">Mi provincia
      <select id="gasoleo-provincia"><option value="">— elige para verla siempre primero —</option>${opciones}</select>
    </label>
    ${pMia ? `<h3 class="gasoleo-grupo">Mi provincia</h3>${tarjetaProvincia(pMia, true)}` : ""}
    <h3 class="gasoleo-grupo">Castilla y León</h3>
    ${cyl.map(p => tarjetaProvincia(p, false)).join("")}
    <details class="gasoleo-resto"><summary>Resto de España (${resto.length} provincias · las 3 más baratas de cada una)</summary>${resto.map(p => tarjetaProvincia(p, false)).join("")}</details>
    </div>
    <p class="nota">Precios que las gasolineras comunican al Ministerio para la Transición Ecológica (solo venta al público); pueden cambiar a lo largo del día. Fuente: ${d.fuente_url ? `<a href="${esc(d.fuente_url)}" target="_blank" rel="noopener noreferrer">${esc(d.fuente)}</a>` : esc(d.fuente)}. El gasóleo B solo puede usarse en los usos autorizados (maquinaria agrícola, entre otros).</p>
  </section>`;
}

document.addEventListener("change", e => {
  if (e.target.id !== "gasoleo-provincia") return;
  try { e.target.value ? localStorage.setItem(CLAVE_PROV, e.target.value) : localStorage.removeItem(CLAVE_PROV); } catch {}
  router();
});

document.addEventListener("input", e => {
  if (e.target.id !== "gasoleo-buscar") return;
  BUSQUEDA_GAS = e.target.value.slice(0, 60);
  const res = document.getElementById("gasoleo-resultados"), prov = document.getElementById("gasoleo-provincias");
  if (res) res.innerHTML = resultadosBusqueda(BUSQUEDA_GAS);
  if (prov) prov.hidden = normalizar(BUSQUEDA_GAS).length >= 2;
});

document.addEventListener("click", e => {
  const bt = e.target.closest?.("[data-fav-gas]");
  if (!bt) return;
  e.preventDefault();
  const id = bt.dataset.favGas;
  if (!/^\d{1,9}$/.test(id)) return;
  const favs = leerGasFav();
  if (favs[id]) delete favs[id];
  else {
    const b = todasLasGasolineras().get(id);
    if (!b) return;
    favs[id] = { nombre: b.nombre, localidad: b.municipio || b.localidad, prov: b.prov };
  }
  guardarGasFav(favs);
  const on = !!favs[id];
  if ((location.hash.slice(1) || "hoy") === "favoritos") { router(); return; }
  document.querySelectorAll(`[data-fav-gas="${id}"]`).forEach(x => {
    x.classList.toggle("on", on); x.textContent = on ? "★" : "☆"; x.setAttribute("aria-pressed", String(on));
    x.setAttribute("aria-label", x.getAttribute("aria-label").replace(on ? "Añadir a" : "Quitar de", on ? "Quitar de" : "Añadir a"));
  });
  if (typeof aviso === "function") aviso(on ? "Gasolinera guardada en Favoritos" : "Gasolinera quitada de Favoritos");
});

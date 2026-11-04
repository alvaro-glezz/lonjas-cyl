"use strict";
const RUTA_DATOS = "data/precios.json";
// Formato válido de los identificadores. Debe ir arriba: leerFavs() lo usa al arrancar.
const RE_ID = /^[a-z0-9][a-z0-9-]{0,99}$/;
const PRODUCTOS_CLAVE = [
  ["trigo", "Trigo"], ["cebada", "Cebada"], ["maiz", "Maíz"], ["avena", "Avena"], ["centeno", "Centeno"],
  ["triticale", "Triticale"], ["girasol", "Girasol"], ["alfalfa", "Alfalfa"], ["paja", "Paja"],
  ["cerdo-normal", "Cerdo normal"], ["cerdo-selecto", "Cerdo selecto"], ["lechones", "Lechones"], ["lechazo", "Lechazo"],
];
const RESUMEN = ["trigo", "cebada", "maiz", "cerdo-normal", "lechones", "lechazo"];
const $ = (s, el = document) => el.querySelector(s);
let DATOS = null;
let estado = { cat: "Todas", texto: "", clave: "trigo" };

/* ---------- almacenamiento local (favoritos) ---------- */
function leerFavs() {
  try {
    const l = JSON.parse(localStorage.getItem("lonjas-favoritos") || "[]");
    return new Set(Array.isArray(l) ? l.filter(x => typeof x === "string" && RE_ID.test(x)).slice(0, 500) : []);
  } catch { return new Set(); }
}
function guardarFavs(s) { try { localStorage.setItem("lonjas-favoritos", JSON.stringify([...s])); } catch {} }
let FAVS = leerFavs();

/* ---------- formato ---------- */
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
function fechaCorta(iso) { if (!iso) return "—"; const [a, m, d] = iso.split("-").map(Number); return `${d} ${MESES[m - 1]}`; }
function fechaLarga(iso) { if (!iso) return "—"; const f = new Date(iso + "T12:00:00"); return `${DIAS[f.getDay()]} ${f.getDate()} ${MESES[f.getMonth()]} ${f.getFullYear()}`; }
function decimales(v, unidad) {
  if (/€\/t/.test(unidad) || Math.abs(v) >= 100) return Number.isInteger(v) ? 0 : 2;
  const s = String(v).split(".")[1] || "";
  return Math.max(2, Math.min(s.length, 5));
}
function precio(v, unidad) {
  if (v == null) return "S/C";
  return v.toLocaleString("es-ES", { minimumFractionDigits: decimales(v, unidad), maximumFractionDigits: decimales(v, unidad) });
}
function variacion(f) {
  if (f.act == null || f.ant == null) return { txt: f.act == null ? "" : "nuevo", clase: "i", d: 0 };
  const d = Math.round((f.act - f.ant) * 100000) / 100000;
  if (d === 0) return { txt: "=", clase: "i", d };
  const dec = decimales(Math.abs(d) < 1 ? f.act : d, f.unidad);
  const txt = (d > 0 ? "▲ +" : "▼ −") + Math.abs(d).toLocaleString("es-ES", { minimumFractionDigits: Math.min(dec, 3), maximumFractionDigits: 3 });
  return { txt, clase: d > 0 ? "s" : "b", d };
}
function diasDesde(iso) { return Math.floor((Date.now() - new Date(iso + "T12:00:00")) / 86400000); }
function estadoLonja(l) {
  if (l.estado === "suspendida") return { txt: "Sin cotizar", clase: "p-off" };
  if (l.error && diasDesde(l.fecha) > 8) return { txt: "Revisar fuente", clase: "p-err" };
  if (!l.fecha) return { txt: "Sin datos", clase: "p-off" };
  return diasDesde(l.fecha) <= 7 ? { txt: "Al día", clase: "p-dia" } : { txt: "Pendiente", clase: "p-pend" };
}
const esc = s => String(s ?? "").replace(/[&<>"'`]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;" }[c]));
const icoEstrella = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.9z"/></svg>';

/* ---------- validación de los datos recibidos ----------
   precios.json lo genera un proceso automático que lee webs y PDF de terceros, y la app guarda una copia en
   el teléfono. Nada de eso se da por bueno: se reconstruye un objeto limpio con tipos y formatos comprobados,
   y lo que no encaja se descarta. Así un dato corrupto o manipulado no puede inyectar HTML ni romper la app. */
const RE_FECHA = /^\d{4}-\d{2}-\d{2}$/;
const texto = (v, max) => typeof v === "string" ? v.replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, max) : "";
const num = v => (typeof v === "number" && Number.isFinite(v) && Math.abs(v) < 1e7) ? v : null;
function fechaOk(v) {
  if (typeof v !== "string" || !RE_FECHA.test(v)) return null;
  const [a, m, d] = v.split("-").map(Number), f = new Date(Date.UTC(a, m - 1, d));
  return (f.getUTCFullYear() === a && f.getUTCMonth() === m - 1 && f.getUTCDate() === d) ? v : null;
}
function urlHttps(v) {
  try { const u = new URL(v); return u.protocol === "https:" ? u.href : null; } catch { return null; }
}
function sanear(crudo) {
  if (!crudo || typeof crudo !== "object" || !Array.isArray(crudo.lonjas)) throw new Error("Formato de datos no válido");
  const out = { generado: typeof crudo.generado === "string" && !isNaN(new Date(crudo.generado)) ? crudo.generado : null, lonjas: [], historial: {} };
  for (const l of crudo.lonjas.slice(0, 50)) {
    if (!l || typeof l.id !== "string" || !RE_ID.test(l.id)) continue;
    const precios = [];
    for (const f of (Array.isArray(l.precios) ? l.precios : []).slice(0, 1000)) {
      if (!f || typeof f.id !== "string" || !RE_ID.test(f.id)) continue;
      const fila = { id: f.id, cat: texto(f.cat, 60) || "General", producto: texto(f.producto, 120), unidad: texto(f.unidad, 24),
        ant: num(f.ant), act: num(f.act) };
      if (!fila.producto) continue;
      if (typeof f.rango === "string") fila.rango = texto(f.rango, 40);
      if (typeof f.clave === "string" && RE_ID.test(f.clave)) fila.clave = f.clave;
      precios.push(fila);
    }
    out.lonjas.push({
      id: l.id, nombre: texto(l.nombre, 80) || l.id, provincia: texto(l.provincia, 60), dia: texto(l.dia, 20),
      estado: l.estado === "suspendida" ? "suspendida" : "activa", nota: texto(l.nota, 200) || null,
      fuente: urlHttps(l.fuente), fecha: fechaOk(l.fecha), origen: texto(l.origen, 60), error: l.error ? true : null, precios,
    });
  }
  if (crudo.historial && typeof crudo.historial === "object") {
    for (const [id, serie] of Object.entries(crudo.historial).slice(0, 5000)) {
      if (!RE_ID.test(id) || !Array.isArray(serie)) continue;
      out.historial[id] = serie.slice(-1500).filter(p => Array.isArray(p) && fechaOk(p[0]) && num(p[1]) !== null).map(p => [p[0], p[1]]);
    }
  }
  return out;
}

/* ---------- datos ---------- */
function todasLasFilas() { return DATOS.lonjas.flatMap(l => l.precios.map(f => ({ ...f, lonja: l }))); }
function buscarFila(id) { return todasLasFilas().find(f => f.id === id); }

async function cargar(forzar = false) {
  const btn = $("#recargar"); btn.classList.add("girando");
  try {
    const r = await fetch(RUTA_DATOS + (forzar ? "?t=" + Date.now() : ""), { cache: forzar ? "no-store" : "no-cache" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const crudo = await r.text();
    if (crudo.length > 8e6) throw new Error("Respuesta demasiado grande");
    DATOS = sanear(JSON.parse(crudo));
    try { localStorage.setItem("lonjas-copia", JSON.stringify(DATOS)); } catch {}
    DATOS.__sinRed = false;
  } catch (e) {
    let copia = null;
    try { const c = JSON.parse(localStorage.getItem("lonjas-copia") || "null"); copia = c ? sanear(c) : null; } catch {}
    if (copia) { DATOS = copia; DATOS.__sinRed = true; }
    else if (!DATOS) { $("#vista").innerHTML = `<div class="vacio"><b>No se han podido cargar las cotizaciones</b>Comprueba la conexión y pulsa el botón de actualizar, arriba a la derecha.</div>`; }
  } finally { btn.classList.remove("girando"); }
  if (DATOS) { pintarCabecera(); router(); }
}

function pintarCabecera() {
  const g = DATOS.generado ? new Date(DATOS.generado) : null;
  $("#actualizado").textContent = (DATOS.__sinRed ? "Sin conexión · " : "") +
    (g ? `Revisado ${g.getDate()} ${MESES[g.getMonth()]}, ${String(g.getHours()).padStart(2, "0")}:${String(g.getMinutes()).padStart(2, "0")} h` : "");
}

/* ---------- vistas ---------- */
function vistaHoy() {
  const filas = todasLasFilas();
  const fichas = RESUMEN.map(clave => {
    const nombre = PRODUCTOS_CLAVE.find(p => p[0] === clave)[1];
    const v = filas.filter(f => f.clave === clave && f.act != null);
    if (!v.length) return "";
    const media = v.reduce((s, f) => s + f.act, 0) / v.length;
    const min = Math.min(...v.map(f => f.act)), max = Math.max(...v.map(f => f.act));
    const subidas = v.filter(f => variacion(f).d > 0).length, bajadas = v.filter(f => variacion(f).d < 0).length;
    const tend = bajadas > subidas ? '<span class="pastilla p-baja">▼ baja</span>' : subidas > bajadas ? '<span class="pastilla p-sube">▲ sube</span>' : '<span class="pastilla p-igual">= estable</span>';
    return `<button class="ficha" type="button" data-clave="${esc(clave)}">
      <span class="nombre">${nombre}</span>
      <span class="valor num">${precio(Math.round(media * 1000) / 1000, v[0].unidad)}<small>${esc(v[0].unidad)}</small></span>
      <span class="rango">${v.length > 1 ? `media de ${v.length} lonjas · ${precio(min, v[0].unidad)}–${precio(max, v[0].unidad)}` : `solo ${esc(v[0].lonja.nombre.replace("Lonja de ", ""))}`}</span>
      ${tend}</button>`;
  }).join("");
  return `
    ${DATOS.__sinRed ? '<p class="aviso-red">Estás sin conexión. Se muestran los últimos precios guardados en este teléfono.</p>' : ""}
    <section class="seccion">
      <div class="titulo-seccion"><h2>Pizarra de la semana</h2><span>Toca un producto para comparar</span></div>
      <div class="pizarra">${fichas}</div>
    </section>
    <section class="seccion">
      <div class="titulo-seccion"><h2>Lonjas</h2><span>Última sesión de cada una</span></div>
      ${listaLonjas()}
    </section>
    <p class="nota">Precios orientativos publicados por cada lonja. Cada lonja cotiza en sus propias condiciones (calidad, punto de entrega, peso), así que los valores no siempre son comparables entre sí.</p>`;
}

function listaLonjas() {
  const orden = [...DATOS.lonjas].sort((a, b) => (b.estado !== "suspendida") - (a.estado !== "suspendida") || (b.fecha || "").localeCompare(a.fecha || ""));
  return `<div class="lonjas">${orden.map(l => {
    const e = estadoLonja(l);
    if (l.estado === "suspendida") {
      return `<div class="lonja apagada"><div><h3>${esc(l.nombre)}</h3><div class="meta">${esc(l.nota || "Sin cotizaciones activas")}</div></div><span class="pastilla ${e.clase}">${e.txt}</span></div>`;
    }
    const subes = l.precios.filter(f => variacion(f).d > 0).length, bajas = l.precios.filter(f => variacion(f).d < 0).length;
    const iguales = l.precios.filter(f => f.act != null && variacion(f).d === 0 && f.ant != null).length;
    return `<button class="lonja" type="button" data-lonja="${esc(l.id)}">
      <div><h3>${esc(l.nombre)}</h3><div class="meta">Sesión del ${fechaLarga(l.fecha)} · cotiza los ${esc(l.dia).toLowerCase()}</div></div>
      <span class="pastilla ${e.clase}">${e.txt}</span>
      <div class="cifras"><span class="pastilla p-sube">▲ ${subes}</span><span class="pastilla p-baja">▼ ${bajas}</span><span class="pastilla p-igual">= ${iguales}</span><span class="pastilla p-igual">${l.precios.length} precios</span></div>
    </button>`;
  }).join("")}</div>`;
}

function vistaLonjas() {
  return `<section class="seccion"><div class="titulo-seccion"><h2>Todas las lonjas</h2><span>Castilla y León</span></div>${listaLonjas()}</section>`;
}

function filaHTML(f, conLonja = false) {
  const v = variacion(f);
  const fav = FAVS.has(f.id);
  return `<div class="fila" role="button" tabindex="0" data-fila="${esc(f.id)}">
    <button class="estrella" type="button" data-fav="${esc(f.id)}" aria-pressed="${fav}" aria-label="${fav ? "Quitar de" : "Añadir a"} favoritos">${icoEstrella}</button>
    <span class="prod"><b>${esc(f.producto)}</b><small>${conLonja ? esc(f.lonja.nombre.replace("Lonja de ", "")) + " · " : ""}${esc(f.unidad)}${f.rango ? " · " + esc(f.rango) : ""}</small></span>
    <span class="precio num ${f.act == null ? "sc" : ""}">${precio(f.act, f.unidad)}</span>
    <span class="var ${v.clase}">${v.txt}</span>
  </div>`;
}

function vistaLonja(id) {
  const l = DATOS.lonjas.find(x => x.id === id);
  if (!l) return vistaHoy();
  const cats = ["Todas", ...new Set(l.precios.map(f => f.cat))];
  if (!cats.includes(estado.cat)) estado.cat = "Todas";
  const t = estado.texto.trim().toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const visibles = l.precios.filter(f => (estado.cat === "Todas" || f.cat === estado.cat) &&
    (!t || f.producto.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").includes(t)));
  let cuerpo = "", catActual = null;
  for (const f of visibles) {
    if (f.cat !== catActual) { catActual = f.cat; cuerpo += `<h3 class="mesa">${esc(f.cat)}</h3>`; }
    cuerpo += filaHTML(f);
  }
  const e = estadoLonja(l);
  return `
    <section class="seccion">
      <div class="cab-lonja">
        <button class="volver" type="button" data-ir="hoy">‹ Volver</button>
        <h2>${esc(l.nombre)}</h2>
        <div class="meta"><span class="pastilla ${e.clase}">${e.txt}</span> &nbsp;Sesión del ${fechaLarga(l.fecha)}</div>
      </div>
      <div class="filtros" role="group" aria-label="Mesas">${cats.map(c => `<button class="chip" type="button" data-cat="${esc(c)}" aria-pressed="${c === estado.cat}">${esc(c)}</button>`).join("")}</div>
      <input id="buscar-producto" class="buscar" type="search" placeholder="Buscar producto (trigo, cordero, vacas…)" value="${esc(estado.texto)}" aria-label="Buscar producto">
      <div class="tablilla">${cuerpo || '<div class="vacio sin-borde"><b>Nada coincide</b>Prueba con otra palabra o elige «Todas».</div>'}</div>
      <p class="fuente">Fuente: ${l.fuente ? `<a href="${esc(l.fuente)}" target="_blank" rel="noopener noreferrer">publicación oficial de la lonja</a>` : "lonja"}${l.origen === "carga manual" ? " · cargado a mano" : ""}${l.error ? " · La última lectura automática falló; se muestran los precios de la sesión indicada." : ""}</p>
    </section>`;
}

function vistaComparar() {
  const filas = todasLasFilas();
  const disponibles = PRODUCTOS_CLAVE.filter(([c]) => filas.some(f => f.clave === c));
  const v = filas.filter(f => f.clave === estado.clave);
  const conPrecio = v.filter(f => f.act != null);
  const max = Math.max(...conPrecio.map(f => f.act), 0);
  const mejor = conPrecio.length ? Math.max(...conPrecio.map(f => f.act)) : null;
  const filasCmp = [...v].sort((a, b) => (b.act ?? -1) - (a.act ?? -1)).map(f => {
    const va = variacion(f);
    return `<div class="cmp-fila" role="button" tabindex="0" data-fila="${esc(f.id)}">
      <span><b>${esc(f.lonja.nombre.replace("Lonja de ", ""))}</b><br><small class="etiqueta">${fechaCorta(f.lonja.fecha)}</small></span>
      <div class="barra-cmp" aria-hidden="true"><i class="${f.act === mejor ? "mejor" : ""}" data-w="${f.act == null || !max ? 0 : Math.round(Math.max(4, f.act / max * 100))}"></i></div>
      <span class="cmp-valor num">${precio(f.act, f.unidad)}<small class="var ${va.clase}">${va.txt}</small></span>
      <span class="q">${esc(f.producto)} · ${esc(f.unidad)}</span>
    </div>`;
  }).join("");
  return `
    <section class="seccion">
      <div class="titulo-seccion"><h2>Comparar lonjas</h2><span>Mismo producto, distintas lonjas</span></div>
      <div class="filtros" role="group" aria-label="Producto">${disponibles.map(([c, n]) => `<button class="chip" type="button" data-clave-cmp="${esc(c)}" aria-pressed="${c === estado.clave}">${n}</button>`).join("")}</div>
      <div class="comparativa">${filasCmp || '<div class="vacio sin-borde">No hay cotizaciones de este producto ahora mismo.</div>'}</div>
      <p class="nota">La barra dorada marca el precio más alto. Fíjate en la descripción bajo cada lonja: un «trigo pienso» en almacén y un «trigo tipo III» en origen no son exactamente el mismo producto.</p>
    </section>`;
}

function vistaFavoritos() {
  const filas = todasLasFilas().filter(f => FAVS.has(f.id));
  return `<section class="seccion">
    <div class="titulo-seccion"><h2>Mis precios</h2><span>${filas.length} guardado${filas.length === 1 ? "" : "s"}</span></div>
    ${filas.length ? `<div class="tablilla">${filas.map(f => filaHTML(f, true)).join("")}</div>` :
      `<div class="vacio"><b>Aún no tienes precios guardados</b>Abre una lonja y toca la estrella junto a los productos que vendes o compras. Aparecerán aquí, juntos.</div>`}
  </section>`;
}

/* ---------- detalle con gráfico ---------- */
function grafico(serie, unidad) {
  if (serie.length < 2) return '<p class="nota">El histórico se irá llenando cada semana con las nuevas sesiones.</p>';
  const W = 420, H = 200, mi = { l: 50, r: 12, t: 12, b: 28 };
  const vals = serie.map(p => p[1]);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.15 || Math.abs(hi) * 0.02 || 1; lo -= pad; hi += pad;
  const t0 = new Date(serie[0][0]).getTime(), t1 = new Date(serie.at(-1)[0]).getTime();
  const x = t => mi.l + (new Date(t).getTime() - t0) / (t1 - t0 || 1) * (W - mi.l - mi.r);
  const y = v => mi.t + (hi - v) / (hi - lo) * (H - mi.t - mi.b);
  const pts = serie.map(p => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
  const area = `${mi.l},${H - mi.b} ${pts} ${x(serie.at(-1)[0]).toFixed(1)},${H - mi.b}`;
  const ticks = [lo + pad, (lo + hi) / 2, hi - pad];
  const u = serie.at(-1);
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Evolución del precio">
    ${ticks.map(v => `<line x1="${mi.l}" x2="${W - mi.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--linea)" stroke-width="1"/>
      <text x="${mi.l - 8}" y="${y(v) + 4}" text-anchor="end" font-size="13" fill="var(--tenue)" font-family="var(--cifra)">${precio(Math.round(v * 1000) / 1000, unidad)}</text>`).join("")}
    <polygon points="${area}" fill="var(--pino)" opacity=".12"/>
    <polyline points="${pts}" fill="none" stroke="var(--pino)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
    ${serie.map(p => `<circle cx="${x(p[0])}" cy="${y(p[1])}" r="3" fill="var(--hoja)" stroke="var(--pino)" stroke-width="1.5"/>`).join("")}
    <circle cx="${x(u[0])}" cy="${y(u[1])}" r="6" fill="var(--paja)" stroke="var(--hoja)" stroke-width="2"/>
    <text x="${mi.l}" y="${H - 8}" font-size="13" fill="var(--tenue)">${fechaCorta(serie[0][0])}</text>
    <text x="${W - mi.r}" y="${H - 8}" font-size="13" fill="var(--tenue)" text-anchor="end">${fechaCorta(u[0])}</text>
  </svg>`;
}

function abrirDetalle(id) {
  const f = buscarFila(id); if (!f) return;
  const serie = (DATOS.historial?.[id] || []).filter(p => p[0] && p[1] != null);
  const vals = serie.map(p => p[1]);
  const v = variacion(f);
  const velo = $("#velo");
  velo.innerHTML = `<div class="hoja-detalle" role="dialog" aria-modal="true" aria-labelledby="det-titulo">
    <header><div><div class="etiqueta">${esc(f.lonja.nombre)} · ${esc(f.cat)}</div><h3 id="det-titulo">${esc(f.producto)}</h3></div>
      <button class="cerrar" type="button" data-cerrar aria-label="Cerrar">✕</button></header>
    <div class="datos-det">
      <div><span class="etiqueta">Actual</span><b class="num">${precio(f.act, f.unidad)}</b><small>${esc(f.unidad)}</small></div>
      <div><span class="etiqueta">Anterior</span><b class="num">${precio(f.ant, f.unidad)}</b><small class="var ${v.clase}">${v.txt}</small></div>
      <div><span class="etiqueta">${serie.length > 1 ? "Mín · máx" : "Sesión"}</span><b class="num chico">${serie.length > 1 ? precio(Math.min(...vals), f.unidad) + " · " + precio(Math.max(...vals), f.unidad) : fechaCorta(f.lonja.fecha)}</b><small>${serie.length > 1 ? serie.length + " sesiones" : ""}</small></div>
    </div>
    <div class="grafico">${grafico(serie, f.unidad)}</div>
    ${serie.length > 1 ? `<div class="serie">${[...serie].reverse().map(p => `<div><span>${fechaLarga(p[0])}</span><b class="num">${precio(p[1], f.unidad)}</b></div>`).join("")}</div>` : ""}
    <button class="chip auto" type="button" data-fav="${esc(f.id)}" aria-pressed="${FAVS.has(f.id)}">${FAVS.has(f.id) ? "★ En favoritos" : "☆ Añadir a favoritos"}</button>
  </div>`;
  velo.hidden = false;
  $(".cerrar", velo).focus();
}
function cerrarDetalle() { const v = $("#velo"); v.hidden = true; v.innerHTML = ""; }

/* ---------- navegación ---------- */
function router() {
  if (!DATOS) return;
  const h = location.hash.slice(1) || "hoy";
  let html, seccion = h;
  if (h.startsWith("lonja-")) { html = vistaLonja(h.slice(6)); seccion = "lonjas"; }
  else if (h === "lonjas") html = vistaLonjas();
  else if (h === "comparar") html = vistaComparar();
  else if (h === "favoritos") html = vistaFavoritos();
  else { html = vistaHoy(); seccion = "hoy"; }
  $("#vista").innerHTML = html;
  document.querySelectorAll("[data-w]").forEach(el => { el.style.width = Math.min(100, Math.max(0, Number(el.dataset.w) || 0)) + "%"; });
  document.querySelectorAll(".navegacion a").forEach(a => a.dataset.vista === seccion ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
}
function ir(h) { if (location.hash.slice(1) === h) router(); else location.hash = h; window.scrollTo(0, 0); }

document.addEventListener("click", e => {
  const t = e.target;
  const fav = t.closest("[data-fav]");
  if (fav) {
    e.stopPropagation();
    const id = fav.dataset.fav;
    FAVS.has(id) ? FAVS.delete(id) : FAVS.add(id); guardarFavs(FAVS);
    if (!$("#velo").hidden) abrirDetalle(id);
    router(); return;
  }
  if (t.closest("[data-cerrar]") || t === $("#velo")) return cerrarDetalle();
  const lj = t.closest("[data-lonja]"); if (lj) { estado.cat = "Todas"; estado.texto = ""; return ir("lonja-" + lj.dataset.lonja); }
  const cl = t.closest("[data-clave]"); if (cl) { estado.clave = cl.dataset.clave; return ir("comparar"); }
  const cc = t.closest("[data-clave-cmp]"); if (cc) { estado.clave = cc.dataset.claveCmp; return router(); }
  const cat = t.closest("[data-cat]"); if (cat) { estado.cat = cat.dataset.cat; return router(); }
  const v = t.closest("[data-ir]"); if (v) return ir(v.dataset.ir);
  const fila = t.closest("[data-fila]"); if (fila) return abrirDetalle(fila.dataset.fila);
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !$("#velo").hidden) cerrarDetalle();
  if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-fila]")) { e.preventDefault(); abrirDetalle(e.target.dataset.fila); }
});
document.addEventListener("input", e => {
  if (e.target.id === "buscar-producto") {
    estado.texto = e.target.value; const pos = e.target.selectionStart;
    router(); const b = $("#buscar-producto"); if (b) { b.focus(); b.setSelectionRange(pos, pos); }
  }
});
$("#recargar").addEventListener("click", () => { ultimaCarga = Date.now(); cargar(true); });
window.addEventListener("hashchange", router);
let ultimaCarga = Date.now();
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && DATOS && Date.now() - ultimaCarga > 60000) { ultimaCarga = Date.now(); cargar(); }
});

if ("serviceWorker" in navigator && location.protocol === "https:" && !/claude|anthropic/.test(location.hostname)) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
cargar();

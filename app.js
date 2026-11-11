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
/* Campo con un número no válido: borde rojo y el motivo justo debajo; se quita al volver a escribir. */
function marcarInvalido(input, motivo) {
  input.setAttribute("aria-invalid", "true");
  let m = input.parentElement.querySelector(".motivo-err");
  if (!m) { m = document.createElement("small"); m.className = "motivo-err"; m.id = "err-" + Math.random().toString(36).slice(2, 8); input.parentElement.append(m); }
  m.textContent = motivo; input.setAttribute("aria-describedby", m.id);
  input.focus();
}
document.addEventListener("input", e => {
  if (e.target.getAttribute?.("aria-invalid") === "true") {
    e.target.removeAttribute("aria-invalid"); e.target.parentElement.querySelector(".motivo-err")?.remove();
  }
});

/* Lee un número escrito a la española: «228,5», «1.500» (con miles=true), «1,143». Los campos son de texto con teclado
   numérico porque un <input type="number"> descarta la coma en muchos navegadores («228,5» se leía como 2285).
   Sin miles, el punto es decimal («1.143» €/kg). Devuelve NaN si no es un número. */
function numero(v, miles = false) {
  let t = String(v ?? "").trim().replace(/\s|€/g, "");
  if (!t) return NaN;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  else if (miles && /^\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, "");
  return /^-?\d*\.?\d+$/.test(t) ? Number(t) : NaN;
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
  if (l.error && ((l.fallos || 0) >= 2 || diasDesde(l.fecha) > 8)) return { txt: "Revisar fuente", clase: "p-err" };
  if (!l.fecha) return { txt: "Sin datos", clase: "p-off" };
  return diasDesde(l.fecha) <= 7 ? { txt: "Al día", clase: "p-dia" } : { txt: "Pendiente", clase: "p-pend" };
}
/* ---------- próxima sesión ----------
   Cada lonja cotiza un día fijo de la semana. Se busca ese día después de la última sesión publicada; si ya pasó
   hace pocos días es que aún no se ha publicado, y si pasó hace más (un festivo sin sesión) se mira la siguiente. */
const DIA_NUM = { domingo: 0, lunes: 1, martes: 2, miércoles: 3, miercoles: 3, jueves: 4, viernes: 5, sábado: 6, sabado: 6 };
function hoyISO() { const h = new Date(); return `${h.getFullYear()}-${String(h.getMonth() + 1).padStart(2, "0")}-${String(h.getDate()).padStart(2, "0")}`; }
function sumarDias(iso, n) { const f = new Date(iso + "T12:00:00"); f.setDate(f.getDate() + n); return `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, "0")}-${String(f.getDate()).padStart(2, "0")}`; }
function difDias(a, b) { return Math.round((new Date(a + "T12:00:00") - new Date(b + "T12:00:00")) / 86400000); }
function proximaSesion(l, hoy = hoyISO()) {
  if (l.estado === "suspendida") return null;
  const n = DIA_NUM[(l.dia || "").toLowerCase()];
  if (n == null) return null;
  let c = sumarDias(l.fecha || sumarDias(hoy, -1), 1);
  while (new Date(c + "T12:00:00").getDay() !== n) c = sumarDias(c, 1);
  while (difDias(hoy, c) > 3) c = sumarDias(c, 7);
  return { fecha: c, dias: difDias(c, hoy) };
}
function textoProxima(l) {
  const p = proximaSesion(l);
  if (!p) return "";
  if (p.dias < 0) return `Sesión del ${DIAS[new Date(p.fecha + "T12:00:00").getDay()]} ${fechaCorta(p.fecha)}: pendiente de publicar`;
  if (p.dias === 0) return "Hoy hay sesión · aún sin publicar";
  if (p.dias === 1) return `Mañana hay sesión (${fechaCorta(p.fecha)})`;
  return `Próxima sesión: ${DIAS[new Date(p.fecha + "T12:00:00").getDay()]} ${fechaCorta(p.fecha)}`;
}
/** Lonja que lleva más de una semana sin sesión nueva: explica que es la lonja la que no ha publicado (no un fallo
    de la app) y cuándo la revisó el robot por última vez. */
function notaPendiente(l) {
  const saltadas = [];
  for (let f = sumarDias(l.fecha, 7); f < hoyISO(); f = sumarDias(f, 7)) saltadas.push(`${DIAS[new Date(f + "T12:00:00").getDay()]} ${fechaCorta(f)}`);
  if (!saltadas.length) return "";
  const lect = l.ultimaLectura ? new Date(l.ultimaLectura) : null;
  const cuando = lect && !isNaN(lect) ? ` La última vez, ${fechaCorta(hoyISO()) === fechaCorta(`${lect.getFullYear()}-${String(lect.getMonth() + 1).padStart(2, "0")}-${String(lect.getDate()).padStart(2, "0")}`) ? "hoy" : "el " + lect.getDate() + " " + MESES[lect.getMonth()]} a las ${String(lect.getHours()).padStart(2, "0")}:${String(lect.getMinutes()).padStart(2, "0")} h.` : "";
  return `<p class="aviso-red">La lonja no ha publicado en su web ${saltadas.length === 1 ? "la sesión del " + saltadas[0] : "las sesiones del " + saltadas.join(" y ")}: puede que no la hubiera (un festivo, por ejemplo) o que aún no la haya subido. El robot revisa su web tres veces al día.${cuando} <a href="${esc(l.fuente || l.origen || "#")}" target="_blank" rel="noopener noreferrer">Ver su web</a></p>`;
}
/** «último 2,80 · 29 oct» para un producto que no cotizó en la última sesión. */
function textoUltimo(f) { return f.act == null && f.ult ? `último ${precio(f.ult[1], f.unidad)} (${fechaCorta(f.ult[0])})` : ""; }

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
/** Fecha y hora ISO ('2026-11-05T13:40+01:00') válida, o null. */
function fechaHoraOk(v) {
  return typeof v === "string" && v.length <= 40 && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v) && !isNaN(new Date(v)) ? v : null;
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
      // Producto que no cotizó en esta sesión: su último precio conocido y la fecha
      if (fila.act == null && Array.isArray(f.ult) && fechaOk(f.ult[0]) && num(f.ult[1]) !== null) fila.ult = [f.ult[0], f.ult[1]];
      precios.push(fila);
    }
    out.lonjas.push({
      id: l.id, nombre: texto(l.nombre, 80) || l.id, provincia: texto(l.provincia, 60), dia: texto(l.dia, 20),
      estado: l.estado === "suspendida" ? "suspendida" : "activa", nota: texto(l.nota, 200) || null,
      fuente: urlHttps(l.fuente), fecha: fechaOk(l.fecha), origen: texto(l.origen, 200), error: l.error ? (texto(l.error, 120) || "Error de lectura") : null,
      ultimaLectura: fechaHoraOk(l.ultima_lectura ?? l.ultimaLectura), falloDesde: fechaHoraOk(l.fallo_desde ?? l.falloDesde),
      fallos: Number.isInteger(l.fallos) && l.fallos >= 0 && l.fallos < 10000 ? l.fallos : 0, precios,
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
  if (DATOS) { pintarCabecera(); router(); if (typeof trasCargarDatos === "function") trasCargarDatos(); }
}

function pintarCabecera() {
  const g = DATOS.generado ? new Date(DATOS.generado) : null;
  $("#actualizado").textContent = (DATOS.__sinRed ? "Sin conexión · " : "") +
    (g ? `Revisado ${g.getDate()} ${MESES[g.getMonth()]}, ${String(g.getHours()).padStart(2, "0")}:${String(g.getMinutes()).padStart(2, "0")} h` : "");
}

/* La media de la pizarra, con los decimales con que cotizan las lonjas: 30,17 €/ud (no 30,167), 1,143 €/kg. */
function redondearMedia(media, valores) {
  const dec = Math.max(...valores.map(x => (String(x).split(".")[1] || "").length));
  const d = Math.max(2, Math.min(3, dec));
  return Math.round(media * 10 ** d) / 10 ** d;
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
      <span class="valor num">${precio(redondearMedia(media, v.map(f => f.act)), v[0].unidad)}<small>${esc(v[0].unidad)}</small></span>
      <span class="rango">${v.length > 1 ? `media de ${v.length} lonjas · ${precio(min, v[0].unidad)}–${precio(max, v[0].unidad)}` : `solo ${esc(v[0].lonja.nombre.replace("Lonja de ", ""))}`}</span>
      ${tend}</button>`;
  }).join("");
  return `
    ${DATOS.__sinRed ? '<p class="aviso-red">Estás sin conexión. Se muestran los últimos precios guardados en este teléfono.</p>' : ""}
    ${typeof bloqueAvisosCumplidos === "function" ? bloqueAvisosCumplidos() : ""}
    ${seccionMiPizarra()}
    <section class="seccion">
      <div class="titulo-seccion"><h2>Pizarra de la semana</h2><span>Toca un producto para comparar</span></div>
      <div class="pizarra">${fichas}</div>
    </section>
    ${typeof seccionHerramientas === "function" ? seccionHerramientas() : ""}
    ${typeof seccionTitulares === "function" ? seccionTitulares() : ""}
    ${typeof bloquePlazos === "function" ? bloquePlazos() : ""}
    ${typeof bloqueGasoleo === "function" ? bloqueGasoleo() : ""}
    ${typeof bloqueComentario === "function" ? bloqueComentario() : ""}
    <section class="seccion">
      <div class="titulo-seccion"><h2>Lonjas</h2><span>Última sesión de cada una</span></div>
      ${listaLonjas()}
    </section>
    <p class="nota">Precios orientativos publicados por cada lonja. Cada lonja cotiza en sus propias condiciones (calidad, punto de entrega, peso), así que los valores no siempre son comparables entre sí. <a href="#metodo">Fuentes y método</a>.</p>`;
}

/* «Mi pizarra»: como la Pizarra de la semana, pero con los productos que el usuario ha marcado con ★.
   Una ficha por favorito (producto de una lonja concreta), en el orden en que los guardó. Al tocarla, su detalle. */
function seccionMiPizarra(dondeFavoritos = false) {
  const filas = [...FAVS].map(buscarFila).filter(Boolean);
  if (!filas.length) {
    return dondeFavoritos ? "" : `<section class="seccion mi-pizarra-vacia">
      <p><b>Crea tu pizarra.</b> Toca la ★ de los productos que vendes o compras y los tendrás aquí arriba, juntos, cada vez que abras la app.</p>
    </section>`;
  }
  const fichas = filas.map(f => {
    const v = variacion(f);
    const lonja = f.lonja.nombre.replace("Lonja de ", "");
    const pastilla = f.act == null
      ? `<span class="pastilla p-igual">sin cotizar${f.ult ? ` · último ${precio(f.ult[1], f.unidad)}` : ""}</span>`
      : v.clase === "s" ? `<span class="pastilla p-sube">${v.txt}</span>`
      : v.clase === "b" ? `<span class="pastilla p-baja">${v.txt}</span>`
      : `<span class="pastilla p-igual">${v.txt === "nuevo" ? "nuevo" : "= repite"}</span>`;
    return `<button class="ficha ficha-fav${f.act == null ? " sin-cot" : ""}" type="button" data-fila="${esc(f.id)}" aria-label="${esc(f.producto)}, ${esc(lonja)}">
      <span class="nombre">${esc(f.producto)}</span>
      <span class="valor num">${f.act == null ? "—" : precio(f.act, f.unidad)}<small>${esc(f.unidad)}</small></span>
      <span class="rango">${esc(lonja)} · ${fechaCorta(f.lonja.fecha)}</span>
      ${pastilla}</button>`;
  }).join("");
  const suben = filas.filter(f => variacion(f).d > 0).length, bajan = filas.filter(f => variacion(f).d < 0).length;
  return `<section class="seccion mi-pizarra">
    <div class="titulo-seccion"><h2>Mi pizarra</h2><span>${filas.length} favorito${filas.length === 1 ? "" : "s"} · ${suben} ▲ · ${bajan} ▼${dondeFavoritos ? "" : ` · <button class="enlace" type="button" data-ir="favoritos">editar</button>`}</span></div>
    <div class="pizarra">${fichas}</div>
  </section>`;
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
    const cotizados = l.precios.filter(f => f.act != null).length, sinCot = l.precios.length - cotizados;
    const prox = textoProxima(l);
    return `<button class="lonja" type="button" data-lonja="${esc(l.id)}">
      <div><h3>${esc(l.nombre)}</h3><div class="meta">Sesión del ${fechaLarga(l.fecha)} · cotiza los ${esc(l.dia).toLowerCase()}</div>${prox ? `<div class="prox">${esc(prox)}</div>` : ""}</div>
      <span class="pastilla ${e.clase}">${e.txt}</span>
      <div class="cifras"><span class="pastilla p-sube">▲ ${subes}</span><span class="pastilla p-baja">▼ ${bajas}</span><span class="pastilla p-igual">= ${iguales}</span><span class="pastilla p-igual">${cotizados} precios</span>${sinCot ? `<span class="pastilla p-off">${sinCot} sin cotizar</span>` : ""}</div>
    </button>`;
  }).join("")}</div>`;
}

function vistaLonjas() {
  return `<section class="seccion"><div class="titulo-seccion"><h2>Todas las lonjas</h2><span>Castilla y León</span></div>${listaLonjas()}
    <div class="enlaces-pie"><button class="chip auto" type="button" data-ir="fuentes">Estado de las fuentes ›</button><button class="chip auto" type="button" data-ir="metodo">Fuentes y método ›</button><button class="chip auto" type="button" data-ir="datos">Datos abiertos y widget ›</button></div>
    <p class="nota">Las sesiones pueden cambiar de día en semanas con festivo.</p></section>`;
}

/* ---------- estado de las fuentes: ¿se están leyendo bien las lonjas? ---------- */
function cuando(iso) {
  if (!iso) return "—";
  const f = new Date(iso), d = Math.round((new Date().setHours(0, 0, 0, 0) - new Date(f).setHours(0, 0, 0, 0)) / 86400000);
  const h = `${String(f.getHours()).padStart(2, "0")}:${String(f.getMinutes()).padStart(2, "0")} h`;
  return d === 0 ? `hoy, ${h}` : d === 1 ? `ayer, ${h}` : `${f.getDate()} ${MESES[f.getMonth()]} ${f.getFullYear()}`;
}
function tipoOrigen(l) {
  const o = (l.origen || "").toLowerCase();
  if (o === "carga manual") return "Cargado a mano";
  if (o === "carga inicial") return "Carga inicial (a mano, al crear la app)";
  if (o.includes("datosabiertos")) return "Datos abiertos oficiales";
  if (o.endsWith(".pdf")) return "Boletín en PDF";
  return o ? "Web de la lonja" : "—";
}
function estadoFuente(l) {
  if (l.estado === "suspendida") return { txt: "Sin cotizar", clase: "p-off" };
  if ((l.fallos || 0) >= 2) return { txt: "Falla", clase: "p-err" };
  if ((l.fallos || 0) === 1) return { txt: "Reintentando", clase: "p-pend" };
  return { txt: "Funciona", clase: "p-dia" };
}
function vistaFuentes() {
  const activas = DATOS.lonjas.filter(l => l.estado !== "suspendida");
  const conFallo = activas.filter(l => (l.fallos || 0) >= 2);
  const ultima = activas.map(l => l.ultimaLectura).filter(Boolean).sort().at(-1);
  let hist = "";
  if (typeof HIST !== "undefined") {
    if (!HIST.indice && !HIST.cargando && !HIST.error) cargarHistorico().then(() => { if (location.hash === "#fuentes") router(); });
    const imp = HIST.indice ? HIST.indice.archivos.filter(a => a.importado) : [];
    const u = imp.at(-1);
    hist = `<div class="fuente-fila">
        <div class="fuente-cab"><h3>Histórico oficial · Junta de Castilla y León</h3><span class="pastilla ${HIST.error ? "p-err" : u ? "p-dia" : "p-off"}">${HIST.error ? "No disponible" : u ? "Funciona" : "Cargando…"}</span></div>
        <dl>${u ? `<dt>Última semana importada</dt><dd>semana ${u.semana} de ${u.anio}</dd><dt>Archivos</dt><dd>${imp.length} Excel semanales · <a href="#historico-fuentes">ver lista</a></dd>` : ""}
          <dt>Origen</dt><dd>Excel semanales de la Junta (con unas semanas de retraso)</dd></dl></div>`;
  }
  return `<section class="seccion">
    <div class="cab-lonja"><button class="volver" type="button" data-ir="lonjas">‹ Volver</button><h2>Estado de las fuentes</h2>
      <div class="meta">El robot lee las lonjas 3 veces al día, de lunes a sábado.${ultima ? ` Última lectura correcta: ${cuando(ultima)}.` : ""}</div></div>
    ${conFallo.length ? `<div class="aviso-red"><b>${conFallo.length === 1 ? "Una lonja no se está pudiendo leer" : `${conFallo.length} lonjas no se están pudiendo leer`}.</b> La app sigue mostrando sus últimos precios buenos. Al responsable de la app le llega un aviso automático.</div>` : `<div class="aviso-ok">Todas las lonjas activas se están leyendo correctamente.</div>`}
    <div class="fuentes">${DATOS.lonjas.map(l => {
      const e = estadoFuente(l);
      return `<div class="fuente-fila${l.estado === "suspendida" ? " apagada" : ""}">
        <div class="fuente-cab"><h3>${esc(l.nombre)}</h3><span class="pastilla ${e.clase}">${e.txt}</span></div>
        ${l.estado === "suspendida" ? `<p class="nota">${esc(l.nota || "Sin cotizaciones activas")}</p>` : `<dl>
          <dt>Última sesión</dt><dd>${l.fecha ? fechaLarga(l.fecha) : "—"}${l.dia ? ` · cotiza los ${esc(l.dia).toLowerCase()}` : ""}</dd>
          ${textoProxima(l) ? `<dt>Próxima</dt><dd>${esc(textoProxima(l).replace(/^Próxima sesión: /, ""))}</dd>` : ""}
          <dt>Última lectura correcta</dt><dd>${cuando(l.ultimaLectura)}</dd>
          <dt>Origen</dt><dd>${tipoOrigen(l)}${l.fuente ? ` · <a href="${esc(l.fuente)}" target="_blank" rel="noopener noreferrer">${l.nota ? esc(l.nota) : "ver fuente"}</a>` : ""}</dd>
          ${l.error ? `<dt>Problema</dt><dd class="err">${esc(l.error)}${l.fallos ? ` · ${l.fallos >= 3 ? "3 o más intentos seguidos" : l.fallos === 1 ? "1 intento" : `${l.fallos} intentos seguidos`}${l.falloDesde ? `, desde ${cuando(l.falloDesde)}` : ""}` : ""}</dd>` : ""}
        </dl>`}</div>`;
    }).join("")}${hist}</div>
    <p class="nota">Si una lonja cambia su web o deja de publicar, el robot conserva los últimos precios buenos y avisa. Los precios se pueden cargar a mano mientras se adapta el lector.</p>
    <button class="chip auto" type="button" data-ir="metodo">Cómo se obtienen los precios ›</button>
  </section>`;
}

/* ---------- fuentes y método: de dónde sale cada precio y qué hace la app con él ---------- */
const METODO_LONJAS = {
  salamanca: "Datos abiertos de la Diputación de Salamanca: el archivo oficial de cotizaciones de la Lonja, en formato reutilizable y con licencia CC BY 4.0.",
  leon: "Web de la Lonja de León. Cada mesa publica su día, así que la app junta la última publicación de cada mesa de los 10 días anteriores: en una misma sesión puede haber mesas de días distintos.",
  segovia: "Boletín semanal en PDF de la Federación Empresarial Segoviana (FES). El robot lee el PDF y traduce cada producto a su nombre en la app; un producto que no conoce no se publica hasta revisarlo.",
  lerma: "Tabla de cotizaciones de la web del Ayuntamiento de Lerma (sesión actual y anterior).",
};
function vistaMetodo() {
  const lonjas = DATOS.lonjas.map(l => `<div class="fuente-fila${l.estado === "suspendida" ? " apagada" : ""}">
      <div class="fuente-cab"><h3>${esc(l.nombre)}</h3>${l.dia ? `<span class="pastilla p-igual">${l.estado === "suspendida" ? "Sin cotizar" : esc(l.dia)}</span>` : ""}</div>
      <p class="nota">${l.estado === "suspendida" ? esc(l.nota || "Sin cotizaciones activas.") : esc(METODO_LONJAS[l.id] || tipoOrigen(l) + ".")}</p>
      ${l.fuente && l.estado !== "suspendida" ? `<p class="fuente"><a href="${esc(l.fuente)}" target="_blank" rel="noopener noreferrer">Ver la fuente original</a></p>` : ""}
    </div>`).join("");
  return `<section class="seccion metodo">
    <div class="cab-lonja"><button class="volver" type="button" data-ir="lonjas">‹ Volver</button><h2>Fuentes y método</h2>
      <div class="meta">Los precios salen de las publicaciones oficiales de cada lonja. La app no cambia ningún precio: los lee, los ordena y los compara.</div></div>

    <h3 class="sub">De dónde sale cada lonja</h3>
    <div class="fuentes">${lonjas}</div>

    <h3 class="sub">Cada cuánto se actualiza</h3>
    <ul class="lista">
      <li>Un robot revisa todas las fuentes de lunes a sábado, hacia las 13:40, 17:40 y 21:40 (una hora más tarde en verano). La hora de la última revisión aparece arriba, junto al título.</li>
      <li>Cada lonja cotiza un día fijo de la semana. La «próxima sesión» se calcula con ese día, así que una semana con festivo la sesión puede adelantarse o retrasarse.</li>
      <li>Si una fuente falla, la app conserva los últimos precios buenos y avisa en <a href="#fuentes">Estado de las fuentes</a>.</li>
    </ul>

    <h3 class="sub">Cómo se tratan los precios</h3>
    <ul class="lista">
      <li><b>Anterior y variación.</b> «Anterior» es el precio de la sesión previa de esa lonja. ▲ ▼ = indican la diferencia con él, en la unidad de la lonja.</li>
      <li><b>Horquillas.</b> Cuando la lonja da un mínimo y un máximo, se muestra el punto medio, con la horquilla debajo del nombre.</li>
      <li><b>Sin cotizar.</b> Si un producto no sale en la última sesión, no se borra: aparece al final de su mesa con su último precio y la fecha, durante 6 meses.</li>
      <li><b>Pizarra de la semana.</b> Es la media simple de las lonjas que cotizan ese producto, con el precio más bajo y el más alto. No pondera por volumen.</li>
      <li><b>Unidades.</b> Se respetan las de cada lonja (€/t, €/kg vivo, €/kg canal, €/ud…). Solo se comparan precios en la misma unidad.</li>
      <li><b>Comprobaciones.</b> Solo se publica una lectura con fecha válida, al menos 4 precios y valores razonables. Las webs y PDF se descargan solo de las direcciones de cada lonja.</li>
    </ul>

    <h3 class="sub">Histórico oficial</h3>
    <ul class="lista">
      <li>El histórico 2025–2026 son los Excel semanales que publica la Junta de Castilla y León con los precios de lonjas y mercados, que llegan con unas semanas de retraso. <a href="#historico-fuentes">Ver los archivos importados</a>.</li>
      <li>La Junta publica los cereales y forrajes en €/100 kg; la app los pasa a €/t (× 10) para que coincidan con las lonjas.</li>
      <li>Los valores que parecen una errata (un pico aislado o una fila desplazada en el Excel) se marcan como «dudoso» y no entran en gráficos ni medias.</li>
    </ul>

    <h3 class="sub">Licencias y uso</h3>
    <ul class="lista">
      <li>Lonja de Salamanca: datos abiertos de la Diputación de Salamanca, licencia <a href="https://creativecommons.org/licenses/by/4.0/deed.es" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>.</li>
      <li>Resto de lonjas e histórico: publicaciones públicas de cada lonja y de la Junta de Castilla y León. La app cita y enlaza siempre la fuente original.</li>
      <li>Lonjas CyL es una app independiente: no es una lonja ni habla en nombre de ninguna.</li>
      <li>Los precios se pueden descargar en CSV y JSON, y poner en otras webs con un widget: <a href="#datos">Datos abiertos y widget</a>.</li>
    </ul>

    <h3 class="sub">Privacidad</h3>
    <ul class="lista">
      <li>La app no usa cookies ni pide registrarse. Favoritos, avisos, ofertas y tu explotación se guardan solo en tu teléfono.</li>
      <li>Para saber cuánta gente la usa se cuentan las visitas de forma anónima: qué sección se ve, de qué web se llega, si es móvil u ordenador y el país. Para no contar dos veces a la misma persona en un día se usa un resumen cifrado que cambia cada día; tu dirección IP no se guarda. Los recuentos se borran a los 400 días.</li>
      <li>Si tu navegador pide «no rastrear», no se cuenta nada.</li>
      <li>El robot de Telegram guarda tu número de chat solo si creas avisos; «/borrar todos» lo elimina.</li>
    </ul>

    <p class="aviso-red"><b>Precios orientativos.</b> Cada lonja cotiza en sus propias condiciones (calidad, punto de entrega, peso). Estos precios sirven para informarse y comparar; no son una oferta de compra ni una recomendación de compra o venta. Antes de cerrar una operación, confírmalo con tu lonja o tu comprador.</p>
  </section>`;
}

function filaHTML(f, conLonja = false) {
  const v = variacion(f);
  const fav = FAVS.has(f.id);
  const ult = textoUltimo(f);
  // La fila entera se puede tocar; para teclado y lectores de pantalla, el botón es el nombre (la estrella va aparte:
  // un botón dentro de otro no se puede usar con el teclado).
  return `<div class="fila${f.act == null ? " sin-cot" : ""}" data-fila="${esc(f.id)}">
    <button class="estrella" type="button" data-fav="${esc(f.id)}" aria-pressed="${fav}" aria-label="${fav ? "Quitar" : "Añadir"} ${esc(f.producto)} ${fav ? "de" : "a"} favoritos">${icoEstrella}</button>
    <button type="button" class="prod" aria-label="${esc(f.producto)}: ${esc(precio(f.act, f.unidad))} ${esc(f.unidad)}${v.txt ? ", " + esc(v.txt) : ""}. Ver ficha"><b>${esc(f.producto)}</b><small>${conLonja ? esc(f.lonja.nombre.replace("Lonja de ", "")) + " · " : ""}${esc(f.unidad)}${f.rango ? " · " + esc(f.rango) : ""}</small>${f.act == null ? `<small class="ult">Sin cotizar${ult ? ` · ${esc(ult)}` : " en esta sesión"}</small>` : ""}</button>
    <span class="precio num ${f.act == null ? "sc" : ""}" ${f.act == null ? 'title="Sin cotización"' : ""}>${precio(f.act, f.unidad)}</span>
    <span class="var ${v.clase}">${v.txt}</span>
  </div>`;
}

/* Buscador de productos. Cada palabra tiene que aparecer en el nombre o en la mesa, o alguno de sus sinónimos:
   las lonjas usan sus propios nombres («lechazo» y no «cordero lechal», «porcino» y no «cerdo»). */
const SINONIMOS = [            // grupos estrechos: «garbanzo» no debe traer también las lentejas
  ["cordero", "lechazo", "lechal", "ternasco", "ovino", "oveja", "recental"],
  ["cerdo", "porcino", "cerda", "cerdas", "marrano", "cochino"],
  ["lechon", "lechones", "cochinillo", "cochinillos", "toston", "tostones"],
  ["vaca", "vacas", "vacuno", "bovino"],
  ["ternera", "terneras", "ternero", "terneros", "añojo", "añojos", "anojo", "anojos", "novillo", "novillos"],
  ["legumbre", "legumbres", "leguminosa", "leguminosas"],
  ["forraje", "forrajes", "heno"],
  ["girasol", "pipa", "pipas"],
  ["patata", "patatas", "papa", "papas"],
  ["cereal", "cereales", "grano"],
  ["cebada", "maltera"],
];
const sinTilde = x => String(x || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
function buscadorProductos(texto) {
  const palabras = sinTilde(texto).split(/[^a-z0-9ñ]+/).filter(w => w.length > 1 && !["de", "del", "la", "el", "los", "las", "y", "kg"].includes(w));
  if (!palabras.length) return () => true;
  const grupos = palabras.map(w => {
    const g = SINONIMOS.find(gr => gr.some(s => { const n = sinTilde(s); return n === w || (w.length >= 4 && n.startsWith(w)); }));
    return [...new Set([w, ...(g || []).map(sinTilde)])];
  });
  return f => { const donde = sinTilde(f.producto + " " + f.cat); return grupos.every(g => g.some(w => donde.includes(w))); };
}

function vistaLonja(id) {
  const l = DATOS.lonjas.find(x => x.id === id);
  if (!l) return vistaHoy();
  const cats = ["Todas", ...new Set(l.precios.map(f => f.cat))];
  if (!cats.includes(estado.cat)) estado.cat = "Todas";
  const coincide = buscadorProductos(estado.texto);
  const filtradas = l.precios.filter(f => (estado.cat === "Todas" || f.cat === estado.cat) && coincide(f));
  // Por mesas en el orden de la lonja; dentro de cada mesa, los que no cotizaron van al final
  const ordenCat = [...new Set(l.precios.map(f => f.cat))];
  const visibles = filtradas.map((f, i) => ({ f, i })).sort((a, b) =>
    ordenCat.indexOf(a.f.cat) - ordenCat.indexOf(b.f.cat) || (a.f.act == null) - (b.f.act == null) || a.i - b.i).map(x => x.f);
  const sinCot = l.precios.filter(f => f.act == null).length;
  const prox = textoProxima(l);
  let cuerpo = "", catActual = null;
  for (const f of visibles) {
    if (f.cat !== catActual) { catActual = f.cat; cuerpo += `<h3 class="mesa">${esc(f.cat)}</h3>`; }
    cuerpo += filaHTML(f);
  }
  const e = estadoLonja(l);
  if (!l.precios.length) return `
    <section class="seccion">
      <div class="cab-lonja">
        <button class="volver" type="button" data-ir="lonjas">‹ Volver</button>
        <h2>${esc(l.nombre)}</h2>
        <div class="meta"><span class="pastilla ${e.clase}">${e.txt}</span></div>
      </div>
      <div class="vacio"><b>Esta lonja no está publicando precios</b>${esc(l.nota || "Ha dejado de cotizar por ahora.")} Cuando vuelva a publicar, aparecerán aquí solos.</div>
      <p class="nota">Mientras tanto, mira <a href="#comparar">qué pagan las demás lonjas</a> o su histórico en <a href="#historico">Histórico</a>.</p>
    </section>`;
  return `
    <section class="seccion">
      <div class="cab-lonja">
        <button class="volver" type="button" data-ir="hoy">‹ Volver</button>
        <h2>${esc(l.nombre)}</h2>
        <div class="meta"><span class="pastilla ${e.clase}">${e.txt}</span> &nbsp;Sesión del ${fechaLarga(l.fecha)}</div>
        ${prox ? `<div class="prox">${esc(prox)}</div>` : ""}
      </div>
      ${e.txt === "Pendiente" ? notaPendiente(l) : ""}
      ${sinCot ? `<p class="nota">${sinCot === 1 ? "Un producto no cotizó" : `${sinCot} productos no cotizaron`} en esta sesión: se muestran al final de su mesa con su último precio.</p>` : ""}
      <div class="filtros" role="group" aria-label="Mesas">${cats.map(c => `<button class="chip" type="button" data-cat="${esc(c)}" aria-pressed="${c === estado.cat}">${esc(c)}</button>`).join("")}</div>
      <input id="buscar-producto" class="buscar" type="search" placeholder="Buscar producto (trigo, cordero, vacas…)" value="${esc(estado.texto)}" aria-label="Buscar producto">
      <div class="tablilla">${cuerpo || '<div class="vacio sin-borde"><b>Nada coincide</b>Prueba con otra palabra o elige «Todas».</div>'}</div>
      <p class="fuente">Fuente: ${l.fuente ? `<a href="${esc(l.fuente)}" target="_blank" rel="noopener noreferrer">${l.nota ? esc(l.nota) : "publicación oficial de la lonja"}</a>` : "lonja"}${l.origen === "carga manual" ? " · cargado a mano" : ""}${l.error ? " · La última lectura automática falló; se muestran los precios de la sesión indicada." : ""} · <a href="#fuentes">Estado de las fuentes</a> · <a href="#metodo">Fuentes y método</a></p>
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
      <span class="q">${esc(f.producto)} · ${esc(f.unidad)}${f.act == null ? ` · sin cotizar${f.ult ? `, ${esc(textoUltimo(f))}` : ""}` : ""}</span>
    </div>`;
  }).join("");
  return `
    <section class="seccion">
      <div class="titulo-seccion"><h2>Comparar lonjas</h2><span>Mismo producto, distintas lonjas</span></div>
      <div class="filtros" role="group" aria-label="Producto">${disponibles.map(([c, n]) => `<button class="chip" type="button" data-clave-cmp="${esc(c)}" aria-pressed="${c === estado.clave}">${n}</button>`).join("")}</div>
      <div class="comparativa">${filasCmp || '<div class="vacio sin-borde">No hay cotizaciones de este producto ahora mismo.</div>'}</div>
      <p class="nota">La barra dorada marca el precio más alto. Fíjate en la descripción bajo cada lonja: un «trigo pienso» en almacén y un «trigo tipo III» en origen no son exactamente el mismo producto.</p>
      ${CLAVE_A_JUNTA[estado.clave] ? `<button class="chip auto" type="button" data-h-abrir="${esc(estado.clave)}">Ver su evolución en el histórico 2025–2026</button>` : ""}
    </section>
    ${typeof bloqueDiferencias === "function" ? bloqueDiferencias(estado.clave) : ""}`;
}

/* Redes de la app: un toque para seguirlas o unirse al canal de Telegram (abre la app de cada red si está instalada). */
const REDES = [
  { id: "telegram", nombre: "Canal de Telegram", usuario: "t.me/lonjas_cyl", url: "https://t.me/lonjas_cyl", accion: "Unirme", ico: "✈️",
    txt: "Cada sesión nueva de cada lonja, al momento." },
  { id: "robot", nombre: "Robot de Telegram", usuario: "@lonjascyl_bot", url: "https://t.me/lonjascyl_bot", accion: "Abrir", ico: "🤖",
    txt: "Pregúntale un precio o crea avisos: /aviso trigo salamanca 240." },
  { id: "instagram", nombre: "Instagram", usuario: "@lonjas.cyl", url: "https://www.instagram.com/lonjas.cyl/", accion: "Seguir", ico: "📸",
    txt: "Precios del día, reels y comparativas." },
  { id: "facebook", nombre: "Facebook", usuario: "Lonjas CyL", url: "https://www.facebook.com/1368079503066363", accion: "Seguir", ico: "👍",
    txt: "Lo mismo que en Instagram, en Facebook." },
];

function seccionRedes() {
  return `<details class="redes-app seccion">
    <summary><span class="ayuda-ico" aria-hidden="true">📣</span><span><b>Síguenos en redes y Telegram</b><small>Un toque para seguir la app o unirte al canal</small></span></summary>
    <div class="redes-lista">${REDES.map(r => `<a class="red red-${r.id}" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" data-red="${r.id}">
        <span class="red-ico" aria-hidden="true">${r.ico}</span>
        <span class="red-txt"><b>${esc(r.nombre)}</b><small>${esc(r.usuario)} · ${esc(r.txt)}</small></span>
        <span class="red-boton">${esc(r.accion)}</span></a>`).join("")}</div>
  </details>`;
}

function vistaFavoritos() {
  const filas = todasLasFilas().filter(f => FAVS.has(f.id));
  return `${seccionMiPizarra(true)}${typeof seccionGasolinerasFav === "function" ? seccionGasolinerasFav() : ""}${seccionRedes()}${typeof seccionAvisos === "function" ? seccionAvisos() : ""}<section class="seccion">
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
  if (window.LonjasUso) window.LonjasUso.contar("detalle");
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
    ${f.act == null ? `<p class="aviso-red">No cotizó en la sesión del ${fechaLarga(f.lonja.fecha)}.${f.ult ? ` Último precio: <b class="num">${precio(f.ult[1], f.unidad)}</b> ${esc(f.unidad)}, el ${fechaLarga(f.ult[0])}.` : ""}</p>` : ""}
    <div class="grafico">${grafico(serie, f.unidad)}</div>
    <div id="det-aviso" class="det-aviso"></div>
    <div id="det-hist" class="det-hist"></div>
    ${serie.length > 1 ? `<div class="serie">${[...serie].reverse().map(p => `<div><span>${fechaLarga(p[0])}</span><b class="num">${precio(p[1], f.unidad)}</b></div>`).join("")}</div>` : ""}
    <button class="chip auto" type="button" data-fav="${esc(f.id)}" aria-pressed="${FAVS.has(f.id)}">${FAVS.has(f.id) ? "★ En favoritos" : "☆ Añadir a favoritos"}</button>
  </div>`;
  if (velo.hidden) {
    // Con la ficha abierta, el botón «atrás» del móvil la cierra en vez de salir de la pantalla de debajo.
    detalleDesde = document.activeElement;
    history.pushState({ detalle: true }, "", location.href);
  }
  velo.hidden = false;
  $(".cerrar", velo).focus();
  if (typeof pintarAvisoDetalle === "function") pintarAvisoDetalle(f);
  pintarHistDetalle(f);
}
let detalleDesde = null;
function cerrarDetalle(porHistorial = false) {
  const v = $("#velo");
  if (v.hidden) return;
  v.hidden = true; v.innerHTML = "";
  if (!porHistorial && history.state?.detalle) history.back();     // quita la entrada que puso abrirDetalle
  if (detalleDesde?.isConnected) detalleDesde.focus({ preventScroll: true });   // el foco vuelve a la fila
  detalleDesde = null;
}
window.addEventListener("popstate", () => { if (!$("#velo").hidden) cerrarDetalle(true); });

/* ---------- navegación ---------- */
function router() {
  if (!DATOS) return;
  const h = location.hash.slice(1) || "hoy";
  let html, seccion = h;
  if (h.startsWith("lonja-")) { html = vistaLonja(h.slice(6)); seccion = "lonjas"; }
  else if (h === "lonjas") html = vistaLonjas();
  else if (h === "fuentes") { html = vistaFuentes(); seccion = "lonjas"; }
  else if (h === "metodo") { html = vistaMetodo(); seccion = "lonjas"; }
  else if (h === "ayuda" && typeof vistaAyuda === "function") { html = vistaAyuda(); seccion = "hoy"; }
  else if (h === "plazos" && typeof vistaPlazos === "function") { html = vistaPlazos(); seccion = "hoy"; }
  else if (h === "gasoleo" && typeof vistaGasoleo === "function") { html = vistaGasoleo(); seccion = "hoy"; }
  else if (h === "datos" && typeof vistaDatos === "function") { html = vistaDatos(); seccion = "lonjas"; }
  else if (h === "calculadora" && typeof vistaCalculadora === "function") { html = vistaCalculadora(); seccion = "hoy"; }
  else if (h === "oferta" && typeof vistaOferta === "function") { html = vistaOferta(); seccion = "hoy"; }
  else if (h === "explotacion" && typeof vistaExplotacion === "function") { html = vistaExplotacion(); seccion = "hoy"; }
  else if (h === "termometro" && typeof vistaTermometro === "function") { html = vistaTermometro(); seccion = "hoy"; }
  else if (h === "comparar") html = vistaComparar();
  else if (h.startsWith("comparar-")) { estado.clave = h.slice(9); html = vistaComparar(); seccion = "comparar"; }  // enlace directo desde las páginas de precios
  else if (h === "favoritos") html = vistaFavoritos();
  else if (h === "historico") html = vistaHistorico();
  else if (h === "historico-fuentes") { html = vistaFuentesHist(); seccion = "historico"; }
  else { html = vistaHoy(); seccion = "hoy"; }
  $("#vista").innerHTML = html;
  // En pantallas anchas (ordenador) estas pantallas usan dos columnas; las de mucho texto siguen en una (estilos.css).
  const vista = h.startsWith("lonja-") ? "lonja" : h.startsWith("comparar") ? "comparar" : h;
  $("#vista").dataset.vista = vista;
  $("#vista").toggleAttribute("data-ancho", ["hoy", "lonja", "lonjas", "comparar", "favoritos", "gasoleo"].includes(vista));
  // Al cambiar de pantalla: arriba del todo y el título de la pestaña con el nombre de la pantalla (no al repintar la misma).
  if (h !== router.ultimaPintada) {
    if (router.ultimaPintada !== undefined) window.scrollTo(0, 0);
    router.ultimaPintada = h;
    const t = h === "hoy" ? "" : $("#vista h2")?.textContent.trim();
    document.title = (t ? t + " · " : "") + "Lonjas CyL · Precios de las lonjas de Castilla y León hoy";
  }
  document.querySelectorAll("[data-w]").forEach(el => { el.style.width = Math.min(100, Math.max(0, Number(el.dataset.w) || 0)) + "%"; });
  document.querySelectorAll(".navegacion a").forEach(a => a.dataset.vista === seccion ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
  if (typeof trasPintar === "function") trasPintar(h);
  if (typeof trasPintarHerramientas === "function") trasPintarHerramientas(h);
  // Se cuenta al cambiar de sección, no cada vez que se repinta (al terminar de cargar plazos o histórico)
  if (window.LonjasUso && h !== router.ultimaContada) {
    router.ultimaContada = h;
    window.LonjasUso.contar(/^(lonja-[a-z0-9-]+|comparar-[a-z0-9-]+)$/.test(h) ? h : h.split("-")[0]);
  }
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
window.addEventListener("hashchange", () => { if (!$("#velo").hidden) cerrarDetalle(true); router(); });
let ultimaCarga = Date.now();
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && DATOS && Date.now() - ultimaCarga > 60000) { ultimaCarga = Date.now(); cargar(); }
});

if ("serviceWorker" in navigator && location.protocol === "https:" && !/claude|anthropic/.test(location.hostname)) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
// Se espera a que estén cargados todos los archivos de la app (historico.js, agricultor.js): si los precios
// llegasen antes, la primera pantalla se pintaría sin sus secciones.
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => cargar(), { once: true });
else cargar();

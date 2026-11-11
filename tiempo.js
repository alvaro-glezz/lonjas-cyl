/* Tiempo del campo y ventana de tratamientos (#tiempo + tarjeta en Hoy).
   Previsión hora a hora de AEMET a través de /api/tiempo (la clave de AEMET vive solo en el servidor). Si AEMET no
   responde o aún no hay clave configurada, se usa Open-Meteo como reserva (gratis para uso no comercial, CC BY 4.0).
   Cada hora de luz se califica para tratar (buena / regular / mala) según viento, rachas, lluvia, temperatura y
   humedad, con límites que el usuario puede cambiar. Es orientativo: manda la etiqueta del producto.
   El municipio elegido y los límites se guardan solo en el teléfono. */
"use strict";

const TIEMPO = { lugar: null, prevision: null, cargando: null, error: "", hora: null, buscando: null, resultados: null };
const CLAVE_LUGAR = "lonjas-tiempo-lugar";
const CLAVE_UMBRALES = "lonjas-tratamientos-umbrales";
const UMBRALES_DEF = { viento: 15, rachas: 25, tmin: 5, tmax: 25, hmin: 50, horasSinLluvia: 4 };
const METEO = "https://api.open-meteo.com/v1/forecast";
const GEO = "https://geocoding-api.open-meteo.com/v1/search";

function leerJSON(clave, def) { try { const v = JSON.parse(localStorage.getItem(clave) || "null"); return v ?? def; } catch { return def; } }
function guardarJSON(clave, v) { try { localStorage.setItem(clave, JSON.stringify(v)); } catch {} }
function umbrales() {
  const u = { ...UMBRALES_DEF, ...leerJSON(CLAVE_UMBRALES, {}) };
  for (const k of Object.keys(UMBRALES_DEF)) if (typeof u[k] !== "number" || !isFinite(u[k])) u[k] = UMBRALES_DEF[k];
  return u;
}
function lugarGuardado() {
  const l = leerJSON(CLAVE_LUGAR, null);
  if (!l || typeof l.nombre !== "string") return null;
  const conCodigo = typeof l.c === "string" && /^\d{5}$/.test(l.c);
  const conCoord = typeof l.lat === "number" && typeof l.lon === "number";
  return conCodigo || conCoord ? l : null;
}

/* ---------- municipios de Castilla y León (lista de AEMET, guardada 30 días en el teléfono) ---------- */
const MUNI = { lista: null, cargando: null, sinAemet: false };
const CLAVE_MUNI = "lonjas-municipios-cyl-2";   // «-2»: la primera lista pudo guardarse con tildes mal leídas
function listaMunicipios() {
  if (MUNI.lista) return Promise.resolve(MUNI.lista);
  const c = leerJSON(CLAVE_MUNI, null);
  if (c && Array.isArray(c.l) && c.l.length > 100 && Date.now() - c.t < 30 * 864e5) return Promise.resolve(MUNI.lista = c.l);
  if (MUNI.sinAemet) return Promise.resolve(null);
  if (!MUNI.cargando) {
    MUNI.cargando = fetch("api/tiempo?lista=2")
      .then(r => (r.ok ? r.json() : null))
      .then(j => {
        const l = j && Array.isArray(j.municipios) ? j.municipios.filter(m => m && /^\d{5}$/.test(m.c) && typeof m.n === "string") : [];
        if (l.length < 100) { MUNI.sinAemet = true; return null; }
        guardarJSON(CLAVE_MUNI, { t: Date.now(), l });
        return (MUNI.lista = l);
      })
      .catch(() => { MUNI.sinAemet = true; return null; })
      .finally(() => { MUNI.cargando = null; });
  }
  return MUNI.cargando;
}
const sinTildes = s => String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
function cercano(lista, lat, lon) {
  let mejor = null, dm = Infinity;
  const k = Math.cos(lat * Math.PI / 180);
  for (const m of lista) {
    if (typeof m.la !== "number" || typeof m.lo !== "number") continue;
    const d = (m.la - lat) ** 2 + ((m.lo - lon) * k) ** 2;
    if (d < dm) { dm = d; mejor = m; }
  }
  return dm < 0.25 ? mejor : null;      // a menos de unos 50 km: si no, está fuera de Castilla y León
}

/* ---------- datos ---------- */
const valida = d => d && d.hourly && Array.isArray(d.hourly.time) && d.hourly.time.length && d.daily && Array.isArray(d.daily.time);
async function pedirPrevision(l) {
  // Lugar sin código (elegido antes o con «mi ubicación»): se busca el municipio de AEMET más cercano
  if (!l.c && typeof l.lat === "number") {
    const lista = await listaMunicipios();
    const m = lista && cercano(lista, l.lat, l.lon);
    if (m) { l.c = m.c; if (l.nombre === "Mi ubicación") l.nombre = m.n; l.prov = m.p; guardarJSON(CLAVE_LUGAR, l); }
  }
  if (l.c) {
    try {
      const r = await fetch(`api/tiempo?m=${encodeURIComponent(l.c)}`);
      if (r.ok) { const d = await r.json(); if (valida(d) && d.fuente === "aemet") return d; }
    } catch { /* reserva */ }
  }
  if (typeof l.lat !== "number") throw new Error("sin previsión");
  const q = new URLSearchParams({
    latitude: l.lat, longitude: l.lon, timezone: "Europe/Madrid", forecast_days: "5", wind_speed_unit: "kmh",
    hourly: "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,wind_speed_10m,wind_gusts_10m,weather_code,is_day",
    daily: "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,weather_code",
  });
  const r = await fetch(`${METEO}?${q}`);
  if (!r.ok) throw new Error("HTTP " + r.status);
  const d = await r.json();
  if (!valida(d)) throw new Error("formato");
  d.fuente = "open-meteo";
  return d;
}
const claveLugar = l => l.c || `${l.lat},${l.lon}`;
function cargarPrevision(forzar = false) {
  const l = TIEMPO.lugar || (TIEMPO.lugar = lugarGuardado());
  if (!l) return null;
  const cache = leerJSON("lonjas-tiempo-cache", null);
  if (!forzar && !TIEMPO.prevision && cache && cache.clave === claveLugar(l) && Date.now() - cache.t < 30 * 60e3 && valida(cache.datos)) {
    TIEMPO.prevision = cache.datos;
  }
  if ((TIEMPO.prevision && !forzar) || TIEMPO.cargando) return TIEMPO.cargando;
  TIEMPO.error = "";
  TIEMPO.cargando = pedirPrevision(l)
    .then(d => {
      TIEMPO.prevision = d;
      guardarJSON("lonjas-tiempo-cache", { clave: claveLugar(l), t: Date.now(), datos: d });
    })
    .catch(() => { TIEMPO.error = "No se ha podido cargar la previsión. Comprueba la conexión."; })
    .finally(() => {
      TIEMPO.cargando = null;
      const h = location.hash.slice(1) || "hoy";
      if (h === "hoy" || h === "tiempo") router();
    });
  return TIEMPO.cargando;
}

/* ---------- calificar cada hora ---------- */
function calificarHoras(d, u = umbrales()) {
  const H = d.hourly, n = H.time.length, horas = [];
  for (let i = 0; i < n; i++) {
    const hora = +H.time[i].slice(11, 13);
    const x = {
      i, t: H.time[i], dia: H.time[i].slice(0, 10), hora, luz: H.is_day?.[i] === 1 || (hora >= 7 && hora <= 19),
      temp: H.temperature_2m[i], hum: H.relative_humidity_2m[i], lluvia: H.precipitation[i] ?? 0,
      prob: H.precipitation_probability?.[i] ?? 0, viento: H.wind_speed_10m[i], rachas: H.wind_gusts_10m[i], codigo: H.weather_code?.[i],
    };
    // lluvia en las horas siguientes (el producto necesita unas horas sin lluvia después de aplicarlo)
    let sig = 0, probSig = 0;
    for (let k = i + 1; k <= Math.min(n - 1, i + u.horasSinLluvia); k++) { sig += H.precipitation[k] || 0; probSig = Math.max(probSig, H.precipitation_probability?.[k] || 0); }
    const malos = [], regulares = [];
    if (x.viento > u.viento + 5 || x.rachas > u.rachas + 10) malos.push(`viento ${Math.round(x.viento)} km/h, rachas ${Math.round(x.rachas)}`);
    else if (x.viento > u.viento || x.rachas > u.rachas) regulares.push(`viento ${Math.round(x.viento)} km/h, rachas ${Math.round(x.rachas)}`);
    else if (x.viento < 2) regulares.push("calma total (puede haber inversión térmica)");
    if (x.lluvia > 0.1) malos.push(`llueve (${num1(x.lluvia)} mm)`);
    else if (sig > 0.5 || probSig >= 60) malos.push(`lluvia en las ${u.horasSinLluvia} h siguientes`);
    else if (probSig >= 30 || x.prob >= 30) regulares.push(`posible lluvia (${Math.max(probSig, x.prob)} %)`);
    if (x.temp < u.tmin || x.temp > u.tmax + 3) malos.push(`${Math.round(x.temp)} °C`);
    else if (x.temp > u.tmax || x.temp < u.tmin + 2) regulares.push(`${Math.round(x.temp)} °C`);
    if (x.hum < u.hmin - 15) malos.push(`humedad ${Math.round(x.hum)} %`);
    else if (x.hum < u.hmin) regulares.push(`humedad ${Math.round(x.hum)} %`);
    else if (x.hum > 95) regulares.push(`humedad ${Math.round(x.hum)} % (rocío)`);
    x.nota = malos.length ? "mala" : regulares.length ? "regular" : "buena";
    x.motivos = malos.length ? malos : regulares;
    horas.push(x);
  }
  return horas;
}
const num1 = v => (Math.round(v * 10) / 10).toLocaleString("es-ES");

/* Tramos seguidos de horas buenas (de luz) de un día: [[desde, hasta], ...] */
function ventanas(horasDia) {
  const out = []; let ini = null;
  for (const h of horasDia) {
    if (h.luz && h.nota === "buena") { if (ini === null) ini = h.hora; }
    else if (ini !== null) { out.push([ini, h.hora]); ini = null; }
  }
  if (ini !== null) out.push([ini, horasDia[horasDia.length - 1].hora + 1]);
  return out.sort((a, b) => (b[1] - b[0]) - (a[1] - a[0]));
}
const textoVentana = v => `de ${v[0]} a ${v[1]} h`;

function porDias(horas) {
  const m = new Map();
  for (const h of horas) { if (!m.has(h.dia)) m.set(h.dia, []); m.get(h.dia).push(h); }
  return [...m.entries()];
}

const CIELO = c => c == null ? "" : c === 0 ? "☀️ Despejado" : c <= 2 ? "🌤️ Poco nuboso" : c === 3 ? "☁️ Nublado" : c <= 48 ? "🌫️ Niebla"
  : c <= 57 ? "🌦️ Llovizna" : c <= 67 ? "🌧️ Lluvia" : c <= 77 ? "🌨️ Nieve" : c <= 82 ? "🌧️ Chubascos" : c <= 86 ? "🌨️ Chubascos de nieve" : "⛈️ Tormenta";
const DIA_SEM = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
function nombreDia(iso, k) {
  if (k === 0) return "Hoy";
  if (k === 1) return "Mañana";
  const f = new Date(iso + "T12:00:00");
  return `${DIA_SEM[f.getDay()]} ${f.getDate()}`;
}

/* ---------- Hoy ---------- */
function bloqueTiempo() {
  const l = TIEMPO.lugar || (TIEMPO.lugar = lugarGuardado());
  if (!l) {
    return `<section class="seccion"><button class="tiempo-hoy" type="button" data-ir="tiempo">
      <span class="etiqueta">Tiempo y tratamientos</span>
      <b>¿Cuándo puedes tratar esta semana?</b>
      <small>Elige tu municipio y te marcamos las horas buenas según viento, lluvia, temperatura y humedad.</small>
      <span class="gh-ver">Elegir municipio ›</span></button></section>`;
  }
  if (!TIEMPO.prevision) { cargarPrevision(); return ""; }
  const dias = porDias(calificarHoras(TIEMPO.prevision)).slice(0, 2);
  const [hoy, man] = dias.map(([, hs]) => ventanas(hs.filter(h => h.hora >= new Date().getHours() || h.dia !== dias[0][0])));
  const d0 = TIEMPO.prevision.daily;
  let frase;
  if (hoy && hoy.length) frase = `Hoy, buenas horas para tratar <b>${textoVentana(hoy[0])}</b>.`;
  else if (man && man.length) frase = `Hoy no quedan buenas horas; mañana, <b>${textoVentana(man[0])}</b>.`;
  else frase = "Hoy y mañana no hay buenas horas para tratar.";
  return `<section class="seccion"><button class="tiempo-hoy" type="button" data-ir="tiempo">
    <span class="etiqueta">Tiempo y tratamientos · ${esc(l.nombre)}</span>
    <span class="th-fila"><span>${CIELO(d0.weather_code?.[0])} <b class="num">${Math.round(d0.temperature_2m_max[0])}°</b> / ${Math.round(d0.temperature_2m_min[0])}°</span>
    <small>${num1(d0.precipitation_sum[0])} mm · viento hasta ${Math.round(d0.wind_speed_10m_max[0])} km/h</small></span>
    <span class="th-frase">${frase}</span>
    <span class="gh-ver">Ver los próximos días ›</span></button></section>`;
}

/* ---------- vista ---------- */
function fechaElab(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(String(s));
  return m ? `${+m[3]}/${+m[2]} a las ${m[4]}:${m[5]}` : "";
}
function vistaTiempo() {
  const l = TIEMPO.lugar || (TIEMPO.lugar = lugarGuardado());
  const u = umbrales();
  const buscador = `<div class="tiempo-lugar">
      <label class="gasoleo-buscar">${l ? "Cambiar de municipio" : "Tu municipio"}
        <input id="tiempo-buscar" type="search" autocomplete="off" placeholder="Ej.: Peñafiel, Medina de Rioseco…" value="${esc(TIEMPO.buscando || "")}">
      </label>
      <button class="boton-sec" type="button" data-tiempo-ubicacion>📍 Usar mi ubicación</button>
      <div id="tiempo-resultados">${resultadosLugar()}</div>
    </div>`;
  const cab = `<div class="titulo-seccion"><h2>Tiempo y tratamientos</h2><span>${l ? esc(l.nombre) + (l.prov ? ` (${esc(l.prov)})` : "") : "Elige tu municipio"}</span></div>`;
  const P = TIEMPO.prevision;
  const fuente = P && P.fuente === "open-meteo"
    ? `Previsión: <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo</a> (CC BY 4.0), porque AEMET no ha respondido.`
    : `Fuente: <a href="https://www.aemet.es/" target="_blank" rel="noopener noreferrer">AEMET</a>. Información elaborada utilizando, entre otras, la obtenida de la Agencia Estatal de Meteorología${P && P.elaborado ? ` (previsión del ${esc(fechaElab(P.elaborado))})` : ""}.`;
  const pie = `<p class="nota">Orientativo: sigue siempre la etiqueta del producto y la normativa de uso de fitosanitarios (no tratar con viento que provoque deriva). ${fuente} El municipio y los límites se guardan solo en tu teléfono.</p>`;
  if (!l) return `<section class="seccion">${cab}<p class="gasoleo-lead">Busca tu municipio y te marcamos, hora a hora y para los próximos días, cuándo hay buenas condiciones para tratar.</p>${buscador}${pie}</section>`;
  if (!TIEMPO.prevision) {
    cargarPrevision();
    return `<section class="seccion">${cab}<div class="vacio">${TIEMPO.error ? esc(TIEMPO.error) : "Cargando la previsión…"}</div>${buscador}${pie}</section>`;
  }
  const dias = porDias(calificarHoras(TIEMPO.prevision, u));
  const D = TIEMPO.prevision.daily;
  const ahora = new Date(), hoyIso = `${ahora.getFullYear()}-${String(ahora.getMonth() + 1).padStart(2, "0")}-${String(ahora.getDate()).padStart(2, "0")}`;
  const bloques = dias.map(([dia, hs], k) => {
    const visibles = hs.filter(h => h.hora >= 6 && h.hora <= 21);
    const futuras = dia === hoyIso ? visibles.filter(h => h.hora >= ahora.getHours()) : visibles;
    const v = ventanas(futuras);
    const celdas = visibles.map(h => `<button type="button" class="hora h-${h.nota}${h.luz ? "" : " noche"}${dia === hoyIso && h.hora < ahora.getHours() ? " pasada" : ""}${TIEMPO.hora === h.t ? " sel" : ""}" data-tiempo-hora="${esc(h.t)}" aria-label="${h.hora} h: ${h.nota}">${h.hora}</button>`).join("");
    const sel = TIEMPO.hora && TIEMPO.hora.startsWith(dia) ? hs.find(h => h.t === TIEMPO.hora) : null;
    const j = D.time.indexOf(dia);
    return `<article class="tiempo-dia">
      <header><b>${nombreDia(dia, k)}</b><span>${j >= 0 ? `${CIELO(D.weather_code?.[j])} · ${Math.round(D.temperature_2m_max[j])}° / ${Math.round(D.temperature_2m_min[j])}° · ${num1(D.precipitation_sum[j])} mm · viento hasta ${Math.round(D.wind_speed_10m_max[j])} km/h` : ""}</span></header>
      <p class="tiempo-ventana ${v.length ? "si" : "no"}">${v.length ? `✅ Mejor ventana para tratar: <b>${textoVentana(v[0])}</b>${v[1] ? ` · también ${textoVentana(v[1])}` : ""}` : "❌ Sin horas buenas para tratar"}</p>
      <div class="horas">${celdas}</div>
      ${sel ? `<p class="hora-detalle"><b>${sel.hora}:00 h · ${sel.nota}</b> — ${Math.round(sel.temp)} °C, humedad ${Math.round(sel.hum)} %, viento ${Math.round(sel.viento)} km/h (rachas ${Math.round(sel.rachas)}), lluvia ${num1(sel.lluvia)} mm (${sel.prob} %).${sel.motivos.length ? ` <span>Motivo: ${esc(sel.motivos.join("; "))}.</span>` : ""}</p>` : ""}
    </article>`;
  }).join("");
  const campo = (k, txt, min, max, paso) => `<label>${txt}<input type="number" data-umbral="${k}" value="${u[k]}" min="${min}" max="${max}" step="${paso}" inputmode="numeric"></label>`;
  return `<section class="seccion">${cab}
    <p class="leyenda"><span class="h-buena">buena</span><span class="h-regular">regular</span><span class="h-mala">mala</span> Toca una hora para ver el detalle.</p>
    ${bloques}
    <details class="tiempo-ajustes"><summary>Ajustar los límites (${u.viento} km/h de viento, ${u.tmin}–${u.tmax} °C, humedad ≥ ${u.hmin} %, ${u.horasSinLluvia} h sin lluvia)</summary>
      <div class="ajustes-rejilla">
        ${campo("viento", "Viento máximo (km/h)", 3, 40, 1)}${campo("rachas", "Rachas máximas (km/h)", 5, 60, 1)}
        ${campo("tmin", "Temperatura mínima (°C)", -5, 20, 1)}${campo("tmax", "Temperatura máxima (°C)", 10, 40, 1)}
        ${campo("hmin", "Humedad mínima (%)", 0, 100, 5)}${campo("horasSinLluvia", "Horas sin lluvia después", 0, 24, 1)}
      </div>
      <button class="enlace" type="button" data-umbrales-def>Volver a los valores por defecto</button>
    </details>
    ${buscador}${pie}</section>`;
}

/* ---------- buscar municipio ---------- */
function resultadosLugar() {
  if (TIEMPO.resultados === "cargando") return `<p class="gasoleo-cuenta">Buscando…</p>`;
  if (!Array.isArray(TIEMPO.resultados)) return "";
  if (!TIEMPO.resultados.length) return `<p class="gasoleo-sin">No se ha encontrado ese municipio.</p>`;
  return `<ul class="tiempo-opciones">${TIEMPO.resultados.map((r, k) => `<li><button type="button" data-tiempo-lugar="${k}">${esc(r.nombre)}<small>${esc(r.prov || "")}</small></button></li>`).join("")}</ul>`;
}
let temporizadorGeo = null, busquedaN = 0, temporizadorUmbral = null;
function buscarLugar(q) {
  clearTimeout(temporizadorGeo);
  const n = ++busquedaN;
  TIEMPO.buscando = q;
  if (q.trim().length < 3) { TIEMPO.resultados = null; pintarResultados(); return; }
  temporizadorGeo = setTimeout(async () => {
    TIEMPO.resultados = "cargando"; pintarResultados();
    let res = [];
    try {
      const lista = await listaMunicipios();
      if (lista) {
        // Municipios de AEMET (solo Castilla y León): primero los que empiezan por lo escrito
        const t = sinTildes(q.trim());
        const emp = [], con = [];
        for (const m of lista) { const x = sinTildes(m.n); if (x.startsWith(t)) emp.push(m); else if (x.includes(t)) con.push(m); }
        res = [...emp, ...con].slice(0, 8).map(m => ({ nombre: m.n, prov: m.p, c: m.c, lat: m.la, lon: m.lo }));
      } else {
        const r = await fetch(`${GEO}?${new URLSearchParams({ name: q.trim(), count: "8", language: "es", countryCode: "ES", format: "json" })}`);
        const d = await r.json();
        res = (d.results || []).filter(r => typeof r.latitude === "number").map(r => ({
          nombre: String(r.name || "").slice(0, 80), prov: [r.admin2, r.admin1].filter(Boolean).join(", ").slice(0, 80), cyl: r.admin1 === "Castilla y León",
          lat: Math.round(r.latitude * 100) / 100, lon: Math.round(r.longitude * 100) / 100 }));
        res.sort((a, b) => b.cyl - a.cyl);
      }
    } catch { res = []; }
    if (n === busquedaN) { TIEMPO.resultados = res; pintarResultados(); }
  }, 250);
}
function pintarResultados() {
  const el = document.getElementById("tiempo-resultados");
  if (!el || !el.isConnected) return;
  try { el.innerHTML = resultadosLugar(); } catch { /* la vista ya cambió */ }
}
function elegirLugar(l) {
  clearTimeout(temporizadorGeo); busquedaN++;
  TIEMPO.lugar = l; TIEMPO.prevision = null; TIEMPO.resultados = null; TIEMPO.buscando = ""; TIEMPO.hora = null;
  guardarJSON(CLAVE_LUGAR, l);
  try { localStorage.removeItem("lonjas-tiempo-cache"); } catch {}
  cargarPrevision(true);
  router();
}

document.addEventListener("input", e => {
  if (e.target.id === "tiempo-buscar") buscarLugar(e.target.value.slice(0, 60));
});
document.addEventListener("change", e => {
  const k = e.target.dataset?.umbral;
  if (!k) return;
  const v = parseFloat(e.target.value);
  if (!isFinite(v)) return;
  const u = { ...leerJSON(CLAVE_UMBRALES, {}), [k]: v };
  guardarJSON(CLAVE_UMBRALES, u);
  // Redibujar después del evento: si se quita el campo con el foco dentro, el navegador lanza otro «change»
  clearTimeout(temporizadorUmbral);
  temporizadorUmbral = setTimeout(() => { router(); document.querySelector(".tiempo-ajustes")?.setAttribute("open", ""); }, 0);
});
document.addEventListener("click", e => {
  const t = e.target.closest?.("[data-tiempo-hora],[data-tiempo-lugar],[data-tiempo-ubicacion],[data-umbrales-def]");
  if (!t) return;
  if (t.dataset.tiempoHora) { TIEMPO.hora = TIEMPO.hora === t.dataset.tiempoHora ? null : t.dataset.tiempoHora; router(); return; }
  if (t.dataset.tiempoLugar != null) {
    const r = Array.isArray(TIEMPO.resultados) ? TIEMPO.resultados[+t.dataset.tiempoLugar] : null;
    if (r) elegirLugar({ nombre: r.nombre, prov: String(r.prov || "").split(",")[0], ...(r.c ? { c: r.c } : {}),
                         ...(typeof r.lat === "number" ? { lat: r.lat, lon: r.lon } : {}) });
    return;
  }
  if (t.hasAttribute("data-umbrales-def")) { try { localStorage.removeItem(CLAVE_UMBRALES); } catch {} router(); return; }
  if (t.hasAttribute("data-tiempo-ubicacion")) {
    if (!navigator.geolocation) { TIEMPO.error = "Este teléfono no permite usar la ubicación."; router(); return; }
    t.textContent = "Buscando tu ubicación…";
    navigator.geolocation.getCurrentPosition(
      p => elegirLugar({ nombre: "Mi ubicación", prov: "", lat: Math.round(p.coords.latitude * 100) / 100, lon: Math.round(p.coords.longitude * 100) / 100 }),
      () => { t.textContent = "📍 No se pudo: busca tu municipio"; },
      { timeout: 10000, maximumAge: 3600e3 });
  }
});

/* Fila del módulo «En el campo» de Hoy */
function filaCampoTiempo() {
  const l = TIEMPO.lugar || (TIEMPO.lugar = lugarGuardado());
  const ico = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M7 17a4 4 0 1 1 1-7.9A5 5 0 0 1 18 10a3.5 3.5 0 0 1 0 7z"/><path d="M9 20l1-2M13 20l1-2"/></svg>';
  if (!l) {
    return `<button class="fila-mod" type="button" data-ir="tiempo"><span class="fm-ico">${ico}</span>
      <span><b>Tiempo para tratar</b><small>Elige tu municipio y te marcamos las horas buenas</small></span><span class="fm-ir" aria-hidden="true">›</span></button>`;
  }
  if (!TIEMPO.prevision) { cargarPrevision(); return ""; }
  const dias = porDias(calificarHoras(TIEMPO.prevision)).slice(0, 2);
  const ahora = new Date().getHours();
  const [hoy, man] = dias.map(([, hs], k) => ventanas(hs.filter(h => k > 0 || h.hora >= ahora)));
  let dato, frase, clase;
  if (hoy && hoy.length) { dato = "Sí"; clase = "s"; frase = `Hoy, buenas horas ${textoVentana(hoy[0])}`; }
  else if (man && man.length) { dato = "Mañana"; clase = ""; frase = `Hoy ya no; mañana ${textoVentana(man[0])}`; }
  else { dato = "No"; clase = "b"; frase = "Hoy y mañana sin horas buenas"; }
  return `<button class="fila-mod" type="button" data-ir="tiempo"><span class="fm-ico">${ico}</span>
    <span><b>Tratamientos · ${esc(l.nombre)}</b><small>${esc(frase)}</small></span><span class="fm-dato ${clase}">${dato}</span></button>`;
}

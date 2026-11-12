"use strict";
/* Previsión de AEMET para «Tiempo y tratamientos» (/api/tiempo). La clave de AEMET OpenData va SOLO en la variable
   de entorno AEMET_API_KEY de Vercel: nunca llega al teléfono ni al código público.
     GET /api/tiempo?m=47114   previsión horaria del municipio (código INE de 5 cifras, solo Castilla y León)
     GET /api/tiempo?lista=1   municipios de Castilla y León con su código y coordenadas (para buscar y «mi ubicación»)
   La respuesta de la previsión tiene la misma forma que la que ya usaba la app (hourly/daily), para no tocar el cálculo
   de las horas buenas. La CDN de Vercel guarda cada respuesta (30 min la previsión, 7 días la lista): así se hacen
   muy pocas llamadas a AEMET aunque haya muchos usuarios.
   Condiciones de AEMET: se permite el uso comercial citando la fuente y la fecha de elaboración. */

const BASE = "https://opendata.aemet.es/opendata/api";
const PROVINCIAS = { "05": "Ávila", "09": "Burgos", "24": "León", "34": "Palencia", "37": "Salamanca", "40": "Segovia", "42": "Soria", "47": "Valladolid", "49": "Zamora" };
const ESPERA = 9000;

function clave() {
  const k = String(process.env.AEMET_API_KEY || "").trim();
  return /^[A-Za-z0-9._-]{20,1000}$/.test(k) ? k : "";
}

async function conTiempo(url, op = {}) {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), ESPERA);
  try { return await fetch(url, { ...op, signal: c.signal }); } finally { clearTimeout(t); }
}

/* AEMET responde en dos pasos: primero un JSON con la dirección de los datos («datos»), luego los datos (en ISO-8859-15). */
async function pedirAemet(ruta, k) {
  const r = await conTiempo(`${BASE}${ruta}`, { headers: { api_key: k, accept: "application/json", "cache-control": "no-cache" } });
  const sobre = await r.json().catch(() => null);
  if (Array.isArray(sobre)) return sobre;                            // algunos maestros vienen ya en el primer paso
  if (!sobre || sobre.estado !== 200 || typeof sobre.datos !== "string" || !/^https:\/\/opendata\.aemet\.es\//.test(sobre.datos)) {
    const e = new Error("aemet " + (sobre && sobre.estado)); e.estado = sobre && sobre.estado; throw e;
  }
  const d = await conTiempo(sobre.datos);
  if (!d.ok) throw new Error("datos " + d.status);
  const buf = await d.arrayBuffer();
  // AEMET dice que manda ISO-8859-15, pero a veces llega en UTF-8: primero UTF-8 estricto y, si falla, ISO-8859-15
  let txt;
  try { txt = new TextDecoder("utf-8", { fatal: true }).decode(buf); }
  catch { try { txt = new TextDecoder("iso-8859-15").decode(buf); } catch { txt = Buffer.from(buf).toString("latin1"); } }
  return JSON.parse(txt);
}

/* ---------- convertir la previsión horaria de AEMET ---------- */
const n = v => { const x = parseFloat(String(v ?? "").replace(",", ".")); return isFinite(x) ? x : null; };
const lluvia = v => (String(v).trim().toLowerCase() === "ip" ? 0.05 : n(v));      // «Ip» = inapreciable

/* Código de cielo de AEMET (11…83, con «n» de noche) -> código WMO, el que ya pinta la app */
function cieloWmo(c) {
  const x = parseInt(String(c || ""), 10);
  if (!x) return null;
  if (x === 11) return 0;
  if (x === 12) return 1;
  if (x === 13 || x === 17) return 2;
  if (x >= 14 && x <= 16) return 3;
  if (x >= 81) return 45;
  if (x >= 43 && x <= 46) return 51;
  if (x >= 23 && x <= 26) return 61;
  if ((x >= 33 && x <= 36) || (x >= 71 && x <= 74)) return 71;
  if ((x >= 51 && x <= 54) || (x >= 61 && x <= 64)) return 95;
  return 3;
}
const horaDe = p => { const h = parseInt(String(p || "").slice(0, 2), 10); return h >= 0 && h <= 23 ? h : null; };
const aMin = s => { const m = /^(\d{1,2}):(\d{2})/.exec(String(s || "")); return m ? +m[1] * 60 + +m[2] : null; };

/** Lista de [hora, valor] de un campo horario de AEMET ({value, periodo:"07"}). */
function porHora(lista, f = x => n(x.value)) {
  const m = new Map();
  for (const x of Array.isArray(lista) ? lista : []) { const h = horaDe(x.periodo); if (h !== null && String(x.periodo).length === 2) m.set(h, f(x)); }
  return m;
}
/** Probabilidad por tramos («0208», «0814»…) -> probabilidad de cada hora. */
function probPorHora(lista) {
  const m = new Map();
  for (const x of Array.isArray(lista) ? lista : []) {
    const p = String(x.periodo || "");
    if (!/^\d{4}$/.test(p)) continue;
    const a = +p.slice(0, 2), b = +p.slice(2, 4), v = n(x.value);
    if (v === null) continue;
    for (let h = a; h !== b; h = (h + 1) % 24) m.set(h, v);
  }
  return m;
}

function normalizar(json, ahora = new Date()) {
  const p = Array.isArray(json) ? json[0] : json;
  const dias = p && p.prediccion && Array.isArray(p.prediccion.dia) ? p.prediccion.dia : null;
  if (!dias) throw new Error("formato");
  const H = { time: [], temperature_2m: [], relative_humidity_2m: [], precipitation: [], precipitation_probability: [],
              wind_speed_10m: [], wind_gusts_10m: [], weather_code: [], is_day: [] };
  for (const d of dias) {
    const fecha = String(d.fecha || "").slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(fecha)) continue;
    const temp = porHora(d.temperatura), hum = porHora(d.humedadRelativa), pre = porHora(d.precipitacion, x => lluvia(x.value));
    const cielo = porHora(d.estadoCielo, x => String(x.value || "")), prob = probPorHora(d.probPrecipitacion);
    const viento = new Map(), racha = new Map();
    for (const x of Array.isArray(d.vientoAndRachaMax) ? d.vientoAndRachaMax : []) {
      const h = horaDe(x.periodo);
      if (h === null) continue;
      if (Array.isArray(x.velocidad)) viento.set(h, n(x.velocidad[0]));
      else if (x.value != null) racha.set(h, n(x.value));
    }
    const orto = aMin(d.orto), ocaso = aMin(d.ocaso);
    for (const h of [...temp.keys()].sort((a, b) => a - b)) {
      if (temp.get(h) === null) continue;
      const v = viento.get(h) ?? 0;
      H.time.push(`${fecha}T${String(h).padStart(2, "0")}:00`);
      H.temperature_2m.push(temp.get(h));
      H.relative_humidity_2m.push(hum.get(h) ?? 70);
      H.precipitation.push(pre.get(h) ?? 0);
      H.precipitation_probability.push(prob.get(h) ?? 0);
      H.wind_speed_10m.push(v);
      H.wind_gusts_10m.push(Math.max(racha.get(h) ?? 0, v));
      H.weather_code.push(cieloWmo(cielo.get(h)));
      const c = cielo.get(h) || "";
      H.is_day.push(orto !== null && ocaso !== null ? (h * 60 + 30 >= orto && h * 60 + 30 <= ocaso ? 1 : 0) : (c.endsWith("n") ? 0 : 1));
    }
  }
  // Días que solo traen horas de noche (el último suele acabar a las 6 h): fuera, no sirven para tratar
  const conLuz = new Set(H.time.filter(t => { const h = +t.slice(11, 13); return h >= 9 && h <= 17; }).map(t => t.slice(0, 10)));
  for (let i = H.time.length - 1; i >= 0; i--) if (!conLuz.has(H.time[i].slice(0, 10))) for (const k of Object.keys(H)) H[k].splice(i, 1);
  if (!H.time.length) throw new Error("sin horas");
  // Resumen de cada día con las horas que da AEMET
  const D = { time: [], temperature_2m_max: [], temperature_2m_min: [], precipitation_sum: [], precipitation_probability_max: [],
              wind_speed_10m_max: [], weather_code: [] };
  const grav = c => (c === null ? -1 : c === 45 ? 2.5 : c);
  for (let i = 0; i < H.time.length; i++) {
    const dia = H.time[i].slice(0, 10);
    let j = D.time.indexOf(dia);
    if (j < 0) {
      j = D.time.push(dia) - 1;
      D.temperature_2m_max.push(-99); D.temperature_2m_min.push(99); D.precipitation_sum.push(0);
      D.precipitation_probability_max.push(0); D.wind_speed_10m_max.push(0); D.weather_code.push(null);
    }
    D.temperature_2m_max[j] = Math.max(D.temperature_2m_max[j], H.temperature_2m[i]);
    D.temperature_2m_min[j] = Math.min(D.temperature_2m_min[j], H.temperature_2m[i]);
    D.precipitation_sum[j] = Math.round((D.precipitation_sum[j] + H.precipitation[i]) * 10) / 10;
    D.precipitation_probability_max[j] = Math.max(D.precipitation_probability_max[j], H.precipitation_probability[i]);
    D.wind_speed_10m_max[j] = Math.max(D.wind_speed_10m_max[j], H.wind_speed_10m[i]);
    const h = +H.time[i].slice(11, 13);
    if (h >= 7 && h <= 20 && grav(H.weather_code[i]) > grav(D.weather_code[j])) D.weather_code[j] = H.weather_code[i];
  }
  return { fuente: "aemet", municipio: String(p.nombre || "").slice(0, 80), provincia: String(p.provincia || "").slice(0, 40),
           elaborado: String(p.elaborado || "").slice(0, 19), hourly: H, daily: D };
}

/* ---------- días que AEMET aún no da por horas (predicción diaria por tramos) ---------- */
/** Resumen de las horas de luz de los días que faltan hasta completar 5 (los que la horaria no cubre). */
function resumenDiario(json, diasConHoras, hasta = 5) {
  const p = Array.isArray(json) ? json[0] : json;
  const dias = p && p.prediccion && Array.isArray(p.prediccion.dia) ? p.prediccion.dia : [];
  const per = x => String(x.periodo || "00-24");
  const lleno = x => x && x.value !== "" && x.value != null;
  // Prefiere los tramos de día (06-12, 12-18); si no hay, mañana/tarde (00-12, 12-24); si no, el día entero
  const diurnos = (lista, ok = lleno) => {
    const l = Array.isArray(lista) ? lista : [];
    for (const pref of [["06-12", "12-18"], ["00-12", "12-24"], ["00-24"]]) {
      const s = l.filter(x => pref.includes(per(x)) && ok(x));
      if (s.length) return s;
    }
    return [];
  };
  const max = xs => (xs.length ? Math.max(...xs) : null);
  const out = [];
  const total = diasConHoras.length;
  for (const d of dias) {
    const fecha = String(d.fecha || "").slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(fecha) || diasConHoras.includes(fecha)) continue;
    if (diasConHoras.length && fecha < diasConHoras[0]) continue;
    if (total + out.length >= hasta) break;
    const prob = max(diurnos(d.probPrecipitacion).map(x => n(x.value)).filter(v => v !== null));
    const viento = max(diurnos(d.viento, x => Array.isArray(x.velocidad) || x.velocidad != null)
      .map(x => n(Array.isArray(x.velocidad) ? x.velocidad[0] : x.velocidad)).filter(v => v !== null));
    const racha = max(diurnos(d.rachaMax).map(x => n(x.value)).filter(v => v !== null));
    const cielos = Array.isArray(d.estadoCielo) ? d.estadoCielo.filter(lleno) : [];
    const cielo = (cielos.find(x => ["12-18", "12-24"].includes(per(x))) || cielos.find(x => per(x) === "00-24") || cielos[0] || {}).value;
    const t = d.temperatura || {}, hr = d.humedadRelativa || {};
    out.push({ fecha, tmax: n(t.maxima), tmin: n(t.minima), hmin: n(hr.minima), prob, viento, racha, cielo: cieloWmo(cielo) });
  }
  return out;
}

/* ---------- municipios de Castilla y León ---------- */
function municipios(lista) {
  const out = [];
  for (const m of Array.isArray(lista) ? lista : []) {
    const c = String(m.id || "").replace(/^id/, "");
    if (!/^\d{5}$/.test(c) || !PROVINCIAS[c.slice(0, 2)]) continue;
    const la = n(m.latitud_dec ?? m.lat), lo = n(m.longitud_dec ?? m.lon);
    out.push({ c, n: String(m.nombre || "").slice(0, 80), p: PROVINCIAS[c.slice(0, 2)],
               la: la === null ? null : Math.round(la * 1000) / 1000, lo: lo === null ? null : Math.round(lo * 1000) / 1000 });
  }
  return out.sort((a, b) => a.n.localeCompare(b.n, "es"));
}

async function manejador(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "solo GET" });
  const k = clave();
  if (!k) { res.setHeader("Cache-Control", "no-store"); return res.status(503).json({ error: "sin-clave" }); }
  const q = req.query || {};
  try {
    if (q.lista === "1" || q.lista === "2") {
      const l = municipios(await pedirAemet("/maestro/municipios", k));
      if (l.length < 100) throw new Error("lista corta");
      res.setHeader("Cache-Control", "public, max-age=86400, s-maxage=604800, stale-while-revalidate=604800");
      return res.status(200).json({ fuente: "aemet", municipios: l });
    }
    const m = String(q.m || "");
    if (!/^\d{5}$/.test(m) || !PROVINCIAS[m.slice(0, 2)]) return res.status(400).json({ error: "municipio" });
    const [hor, dia] = await Promise.allSettled([
      pedirAemet(`/prediccion/especifica/municipio/horaria/${m}`, k),
      pedirAemet(`/prediccion/especifica/municipio/diaria/${m}`, k)]);
    if (hor.status !== "fulfilled") throw hor.reason;
    const d = normalizar(hor.value);
    // Hasta completar 5 días, los que AEMET aún no da por horas van como resumen del día
    if (dia.status === "fulfilled") { try { d.resumen = resumenDiario(dia.value, d.daily.time); } catch { /* sin resumen */ } }
    res.setHeader("Cache-Control", "public, max-age=600, s-maxage=1800, stale-while-revalidate=3600");
    return res.status(200).json({ ...d, codigo: m });
  } catch (e) {
    res.setHeader("Cache-Control", "no-store");
    return res.status(e.estado === 404 ? 404 : 502).json({ error: e.estado === 429 ? "aemet-limite" : "aemet" });
  }
}

module.exports = manejador;
module.exports.normalizar = normalizar;
module.exports.municipios = municipios;
module.exports.cieloWmo = cieloWmo;
module.exports.resumenDiario = resumenDiario;

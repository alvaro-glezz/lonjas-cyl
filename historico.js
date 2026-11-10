"use strict";
/* ============================================================================================
   Histórico oficial 2025–2026 (Junta de Castilla y León)
   Lee data/historico/indice.json y data/historico/<año>.json, que genera scraper/importar_jcyl.py
   a partir de los Excel semanales de la Junta. Se carga solo al abrir la pantalla «Histórico» o el
   detalle de un producto, para no hacer más lento el arranque de la app.
   Usa utilidades de app.js ($, esc, precio, fechaCorta, fechaLarga, texto, num, fechaOk, urlHttps, RE_ID, ir, router).
   ============================================================================================ */
const RUTA_HIST = "data/historico/";
const RE_SEM = /^\d{4}-W\d{2}$/;
const SECTORES_HIST = ["Cereales y forrajes", "Porcino", "Vacuno", "Ovino y caprino", "Aves y conejos"];
// La Junta publica los cereales y forrajes en €/100 kg; en el campo se habla de €/t. Se convierten al mostrarlos
// (los archivos de data/historico/ se quedan tal como los publica la Junta).
const CONVERSION_UNIDAD = { "€/100 kg": { u: "€/t", factor: 10 } };
const HIST = { indice: null, puntos: {}, grupos: new Map(), cache: new Map(), cargando: null, error: null };
const estHist = { ambito: "cyl", sector: "Cereales y forrajes", grupo: null, lonja: null, provincia: "Todas", periodo: "2026", todas: false, extra: [], ampliado: false };

// Productos clave de la app -> producto del cuadro de la Junta (misma lonja; la unidad es la que publica la Junta)
const CLAVE_A_JUNTA = {
  trigo: "Cereales y forrajes|Trigo|€/t",
  cebada: "Cereales y forrajes|Cebada (+64)|€/t",
  maiz: "Cereales y forrajes|Maiz seco nac|€/t",
  avena: "Cereales y forrajes|Avena|€/t",
  centeno: "Cereales y forrajes|Centeno|€/t",
  girasol: "Cereales y forrajes|Pipa de girasol|€/t",
  alfalfa: "Cereales y forrajes|Alfalfa rama|€/t",
  "cerdo-normal": "Porcino|Cebo · normal|€/kg vivo",
  "cerdo-selecto": "Porcino|Cebo · selecto|€/kg vivo",
  lechazo: "Ovino y caprino|Lechazos · 10-12 Kgs.|€/kg vivo",
};

/* ---------- validación (los datos vienen de Excel de terceros: nada se da por bueno) ---------- */
function sanearIndice(c) {
  if (!c || typeof c !== "object" || !c.series || typeof c.series !== "object" || !c.lonjas || typeof c.lonjas !== "object") {
    throw new Error("Formato de histórico no válido");
  }
  const out = { fuente: urlHttps(c.fuente), generado: typeof c.generado === "string" ? c.generado.slice(0, 40) : null,
    anios: [], lonjas: {}, series: {}, archivos: [] };
  out.anios = (Array.isArray(c.anios) ? c.anios : []).filter(a => Number.isInteger(a) && a >= 2000 && a <= 2100).slice(0, 20);
  for (const [id, l] of Object.entries(c.lonjas).slice(0, 200)) {
    if (!RE_ID.test(id) || !l || typeof l !== "object") continue;
    out.lonjas[id] = { nombre: texto(l.nombre, 80) || id, ambito: l.ambito === "cyl" ? "cyl" : "nacional",
      provincia: texto(l.provincia, 40) || "—", app: typeof l.app === "string" && RE_ID.test(l.app) ? l.app : null };
  }
  for (const [id, s] of Object.entries(c.series).slice(0, 5000)) {
    if (!RE_ID.test(id) || !s || typeof s !== "object" || !out.lonjas[s.l]) continue;
    const p = texto(s.p, 120), u = texto(s.u, 24), sec = texto(s.s, 40);
    if (!p || !u || !sec) continue;
    const conv = CONVERSION_UNIDAD[u];
    out.series[id] = { l: s.l, s: sec, p, u: conv ? conv.u : u, factor: conv ? conv.factor : 1, uJunta: u, dudosos: num(s.dudosos) || 0 };
  }
  for (const a of (Array.isArray(c.archivos) ? c.archivos : []).slice(0, 300)) {
    if (!a || !Number.isInteger(a.anio) || !Number.isInteger(a.semana)) continue;
    out.archivos.push({ anio: a.anio, semana: a.semana, archivo: texto(a.archivo, 60), importado: a.importado === true,
      registros: num(a.registros) || 0, motivo: texto(a.motivo, 160) });
  }
  return out;
}
function sanearAnio(c, indice) {
  const out = {};
  if (!c || typeof c !== "object" || !c.series || typeof c.series !== "object") return out;
  const conv = (v, k) => v == null ? null : Math.round(v * k * 1e4) / 1e4;
  for (const [id, serie] of Object.entries(c.series)) {
    if (!indice.series[id] || !Array.isArray(serie)) continue;
    const k = indice.series[id].factor || 1;
    out[id] = serie.slice(0, 80).filter(p => Array.isArray(p) && typeof p[1] === "string" && RE_SEM.test(p[1]) && num(p[2]) !== null)
      .map(p => ({ f: fechaOk(p[0]), w: p[1], a: conv(p[2], k), b: conv(num(p[3]), k), dud: p[4] === 1 }));
  }
  return out;
}

/* ---------- carga ---------- */
function cargarHistorico() {
  if (HIST.indice) return Promise.resolve();
  if (HIST.cargando) return HIST.cargando;
  HIST.error = null;
  const leer = async ruta => {
    const r = await fetch(ruta, { cache: "no-cache" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const t = await r.text();
    if (t.length > 8e6) throw new Error("Respuesta demasiado grande");
    return JSON.parse(t);
  };
  HIST.cargando = (async () => {
    const indice = sanearIndice(await leer(RUTA_HIST + "indice.json"));
    const anios = await Promise.all(indice.anios.map(a => leer(`${RUTA_HIST}${a}.json`)));
    const puntos = {};
    anios.forEach(d => {
      for (const [id, pts] of Object.entries(sanearAnio(d, indice))) (puntos[id] ||= []).push(...pts);
    });
    HIST.puntos = puntos; HIST.indice = indice; HIST.cache.clear();
    construirGrupos();
  })().catch(e => { HIST.error = e; }).finally(() => { HIST.cargando = null; });
  return HIST.cargando;
}

function lunesISO(w) {
  const [a, s] = w.split("-W").map(Number);
  const d = new Date(Date.UTC(a, 0, 4));
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() || 7) - 1) + (s - 1) * 7);
  return d.toISOString().slice(0, 10);
}
const anioDe = p => Number(p.w.slice(0, 4));
const semDe = p => Number(p.w.slice(6));
const media = v => v.reduce((s, x) => s + x, 0) / v.length;
const pct = (a, b) => (a == null || b == null || !b) ? null : (a - b) / Math.abs(b) * 100;

/** Puntos de una serie, ordenados por fecha. v = precio, o el centro de la horquilla mín–máx. */
function puntosSerie(id) {
  if (HIST.cache.has(id)) return HIST.cache.get(id);
  const pts = (HIST.puntos[id] || []).map(p => ({ ...p, v: p.b != null ? Math.round((p.a + p.b) / 2 * 1e5) / 1e5 : p.a,
    fecha: p.f || lunesISO(p.w), sinFecha: !p.f }))
    .sort((x, y) => x.fecha.localeCompare(y.fecha) || x.w.localeCompare(y.w));
  HIST.cache.set(id, pts);
  return pts;
}

/** Agrupa las series por producto: mismo sector, mismo nombre en el cuadro de la Junta y misma unidad.
    Así un gráfico o una comparativa nunca mezcla productos ni unidades distintos. */
function construirGrupos() {
  HIST.grupos = new Map();
  for (const [id, s] of Object.entries(HIST.indice.series)) {
    const k = `${s.s}|${s.p}|${s.u}`;
    if (!HIST.grupos.has(k)) HIST.grupos.set(k, { clave: k, sector: s.s, producto: s.p, unidad: s.u, series: [] });
    HIST.grupos.get(k).series.push(id);
  }
}
const lonjaH = id => HIST.indice.lonjas[id];
const enAmbito = id => estHist.ambito === "todas" || lonjaH(HIST.indice.series[id].l).ambito === "cyl";
const conDatos = id => puntosSerie(id).some(p => !p.dud);

/* ---------- cálculos ---------- */
function enPeriodo(pts, periodo) {
  if (periodo === "todo" || periodo === "comparar") return pts;
  return pts.filter(p => anioDe(p) === Number(periodo));
}
function ultimo(pts) { for (let i = pts.length - 1; i >= 0; i--) if (!pts[i].dud) return pts[i]; return null; }
/** Punto del año anterior en la misma semana ISO (o la vecina más cercana, como mucho a una semana). */
function mismaSemanaAnterior(pts, p) {
  if (!p) return null;
  const a = anioDe(p) - 1, s = semDe(p);
  let mejor = null;
  for (const q of pts) {
    if (q.dud || anioDe(q) !== a) continue;
    const d = Math.abs(semDe(q) - s);
    if (d <= 1 && (!mejor || d < mejor.d)) mejor = { q, d };
  }
  return mejor && mejor.q;
}
/** Media de las semanas que tienen dato en los dos años, hasta la última semana con dato del año actual. */
function mismoPeriodo(pts, anio) {
  const act = new Map(), ant = new Map();
  for (const p of pts) {
    if (p.dud) continue;
    if (anioDe(p) === anio) act.set(semDe(p), p.v);
    if (anioDe(p) === anio - 1) ant.set(semDe(p), p.v);
  }
  if (!act.size) return null;
  const hasta = Math.max(...act.keys());
  const comunes = [...act.keys()].filter(s => s <= hasta && ant.has(s));
  if (comunes.length < 4) return null;
  const mA = media(comunes.map(s => act.get(s))), mB = media(comunes.map(s => ant.get(s)));
  return { semanas: comunes.length, desde: Math.min(...comunes), hasta, act: mA, ant: mB, var: pct(mA, mB) };
}
/** Tendencia de las últimas 4 sesiones válidas: más de un 1 % arriba o abajo. */
function tendencia(pts) {
  const v = pts.filter(p => !p.dud).slice(-4);
  if (v.length < 3) return null;
  const d = pct(v.at(-1).v, v[0].v);
  const sube = v.slice(1).filter((p, i) => p.v > v[i].v).length, baja = v.slice(1).filter((p, i) => p.v < v[i].v).length;
  if (d > 1) return { txt: "▲ Alcista", clase: "p-sube", d, sube, baja };
  if (d < -1) return { txt: "▼ Bajista", clase: "p-baja", d, sube, baja };
  return { txt: "= Estable", clase: "p-igual", d, sube, baja };
}
/** Precio de hace unas 4 semanas (el punto más reciente que tenga al menos 21 días menos). */
function hace4(pts, p) {
  if (!p) return null;
  const lim = new Date(p.fecha + "T12:00:00"); lim.setDate(lim.getDate() - 21);
  const tope = lim.toISOString().slice(0, 10);
  for (let i = pts.length - 1; i >= 0; i--) if (!pts[i].dud && pts[i].fecha <= tope) return pts[i];
  return null;
}
function txtPct(v, dec = 1) {
  if (v == null || !Number.isFinite(v)) return { txt: "—", clase: "i" };
  const r = Math.round(v * 10 ** dec) / 10 ** dec;
  if (r === 0) return { txt: "0 %", clase: "i" };
  return { txt: (r > 0 ? "+" : "−") + Math.abs(r).toLocaleString("es-ES", { minimumFractionDigits: dec, maximumFractionDigits: dec }) + " %", clase: r > 0 ? "s" : "b" };
}
const valorTxt = (p, u) => p.b != null ? `${precio(p.a, u)}–${precio(p.b, u)}` : precio(p.a, u);

/* ---------- gráficos ----------
   Un gráfico se calcula una vez como «modelo» (lista de trazos: líneas, áreas, puntos y textos) y de ahí se
   dibuja en pantalla (SVG) o en una imagen PNG para descargar (canvas). Así los dos salen idénticos y la
   imagen no necesita relajar la política de seguridad (CSP) de la app.
   Todas las líneas de un gráfico tienen la MISMA unidad. */
const COLORES_LINEA = ["pino", "paja", "s3", "s4", "s5"];
const MAX_LONJAS_GRAFICO = 5;
const MESES_C = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
// Colores fijos (tema claro) para la imagen descargada: se comparte por WhatsApp o se imprime, mejor sobre blanco.
const PALETA_PNG = { hoja: "#ffffff", fondo: "#eef1ea", tinta: "#18241d", tenue: "#5b6a60", linea: "#d6ddd2",
  pino: "#24503c", paja: "#b9861f", s3: "#2f6db5", s4: "#8a4fb0", s5: "#c0365f" };
const GRAFS = new Map();
let nGraf = 0;

const fmtNum = (v, d) => v.toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });
function pasoBonito(rango, n) {
  const bruto = rango / Math.max(1, n), e = 10 ** Math.floor(Math.log10(bruto)), f = bruto / e;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * e;
}
function decimalesPaso(paso) {
  let d = 0;
  while (d < 4 && Math.abs(Math.round(paso * 10 ** d) - paso * 10 ** d) > 1e-6) d++;
  return d;
}
/** Semana ISO de una fecha 'AAAA-MM-DD' -> 'AAAA-Www' (para poner las sesiones recientes en el eje de semanas). */
function semanaISO(iso) {
  const d = new Date(iso + "T12:00:00Z"), dia = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dia);
  const a = d.getUTCFullYear(), s = Math.ceil(((d - Date.UTC(a, 0, 1)) / 86400000 + 1) / 7);
  return `${a}-W${String(s).padStart(2, "0")}`;
}

/** Tamaño del dibujo: tan ancho como el hueco real, para que los textos se lean a su tamaño (12 px). */
function medidasGrafico(contexto) {
  // Con «letra grande» la pantalla se amplía: se dibuja para el ancho real que queda, así el texto también crece
  const z = typeof factorLetra === "function" ? factorLetra() : 1;
  const w = (window.innerWidth || 390) / z, h = (window.innerHeight || 800) / z;
  if (contexto === "png") return { W: 720, H: 360 };
  if (contexto === "ampliado") {
    const W = Math.round(Math.max(300, Math.min(w - 40, 1400)));
    return { W, H: Math.round(Math.max(220, Math.min(h - 250, W * 0.62))) };
  }
  const W = Math.round(Math.max(280, Math.min(w - (contexto === "detalle" ? 40 : 64), 728)));
  return { W, H: Math.round(Math.max(200, Math.min(W * 0.6, 330))) };
}

/**
 * lineas: [{ nombre, color, pts, recientes?, discontinua? }]  (pts sin valores dudosos, ordenados)
 * o: { eje: "fecha" | "semana", unidad, banda, media, W, H }
 */
function construirGrafico(lineas, o) {
  const W = o.W, H = o.H, mi = { l: 46, r: 14, t: 26, b: 26 };
  const vis = lineas.filter(l => l.pts.length || (l.recientes || []).length);
  const todos = vis.flatMap(l => [...l.pts, ...(l.recientes || [])]);
  if (todos.length < 2) return null;
  const xv = p => o.eje === "semana" ? semDe(p) : Date.parse(p.fecha + "T12:00:00Z");
  let x0 = Math.min(...todos.map(xv)), x1 = Math.max(...todos.map(xv));
  if (o.eje === "semana") { x0 = 1; x1 = Math.max(x1, 52); }
  if (x1 === x0) x1 = x0 + (o.eje === "semana" ? 1 : 86400000);
  const conBanda = o.banda && vis.length === 1 && vis[0].pts.some(p => p.b != null);
  const vals = todos.flatMap(p => conBanda && p.b != null ? [p.a, p.b] : [p.v]);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi === lo) { const d = Math.abs(hi) * 0.05 || 1; lo -= d; hi += d; }
  const paso = pasoBonito(hi - lo, H >= 280 ? 6 : 4);
  lo = Math.floor(lo / paso - 1e-9) * paso; hi = Math.ceil(hi / paso + 1e-9) * paso;
  const dec = decimalesPaso(paso);
  const X = v => mi.l + (v - x0) / (x1 - x0) * (W - mi.l - mi.r);
  const Y = v => mi.t + (hi - v) / (hi - lo) * (H - mi.t - mi.b);
  const P = [];

  // Eje vertical: valores redondos y la unidad arriba
  for (let v = lo; v <= hi + paso / 2; v += paso) {
    const vy = Y(v);
    P.push({ k: "line", x1: mi.l, x2: W - mi.r, y1: vy, y2: vy, c: "linea", w: 1 });
    P.push({ k: "text", x: mi.l - 6, y: vy + 4, txt: fmtNum(Math.round(v * 1e6) / 1e6, dec), c: "tenue", size: 12, anchor: "end", font: "cifra" });
  }
  P.push({ k: "text", x: 4, y: 13, txt: o.unidad, c: "tenue", size: 11.5, anchor: "start", font: "texto", weight: 600 });

  // Eje horizontal: meses (y separador de año)
  const base = H - mi.b;
  if (o.eje === "semana") {
    const cada = W < 420 ? 2 : 1;
    for (let m = 0; m < 12; m += cada) {
      const xs = X(1 + m * 52 / 12);
      P.push({ k: "line", x1: xs, x2: xs, y1: base, y2: base + 4, c: "linea", w: 1 });
      P.push({ k: "text", x: xs + 2, y: H - 8, txt: MESES_C[m], c: "tenue", size: 12, anchor: "start", font: "texto" });
    }
  } else {
    const f0 = new Date(x0), f1 = new Date(x1);
    const a0 = f0.getUTCFullYear(), m0 = f0.getUTCMonth();
    const nM = (f1.getUTCFullYear() - a0) * 12 + f1.getUTCMonth() - m0 + 1;
    const maxEt = Math.max(3, Math.floor((W - mi.l - mi.r) / 44));
    const cada = [1, 2, 3, 4, 6, 12].find(s => Math.ceil(nM / s) <= maxEt) || 12;
    const DIA = 86400000;
    let ultimaEt = -Infinity;
    for (let k = 0; k <= nM; k++) {
      const a = a0 + Math.floor((m0 + k) / 12), m = (m0 + k) % 12, t = Date.UTC(a, m, 1);
      if (t < x0 - 20 * DIA || t > x1) continue;   // el mes en que empieza la serie también se rotula
      const xs = X(Math.max(t, x0));
      if (m === 0 && t > x0 + 21 * DIA) {          // separador de año (no si la serie empieza en los últimos días de diciembre)
        P.push({ k: "line", x1: xs, x2: xs, y1: mi.t, y2: base, c: "tenue", w: 1, dash: "3 3" });
        P.push({ k: "text", x: xs + 4, y: mi.t + 12, txt: String(a), c: "tenue", size: 12, anchor: "start", font: "cifra", weight: 600 });
      }
      if (m % cada === 0 && xs <= W - mi.r - 18 && xs - ultimaEt >= 30) {
        ultimaEt = xs;
        P.push({ k: "line", x1: xs, x2: xs, y1: base, y2: base + 4, c: "linea", w: 1 });
        P.push({ k: "text", x: xs + 2, y: H - 8, txt: MESES_C[m], c: "tenue", size: 12, anchor: "start", font: "texto" });
      }
    }
  }
  P.push({ k: "line", x1: mi.l, x2: W - mi.r, y1: base, y2: base, c: "tenue", w: 1 });

  const salto = o.eje === "semana" ? 4 : 35 * 86400000; // huecos largos (sin sesiones) no se unen con una línea
  const tramos = pts => {
    const seg = []; let act = [];
    pts.forEach((p, i) => { if (i && xv(p) - xv(pts[i - 1]) > salto) { seg.push(act); act = []; } act.push(p); });
    if (act.length) seg.push(act);
    return seg;
  };

  // Horquilla mínimo–máximo (solo con una lonja, cuando la publica)
  if (conBanda) {
    for (const s of tramos(vis[0].pts.filter(p => p.b != null))) {
      if (s.length < 2) continue;
      P.push({ k: "area", c: vis[0].color, op: 0.16,
        pts: [...s.map(p => [X(xv(p)), Y(p.a)]), ...[...s].reverse().map(p => [X(xv(p)), Y(p.b)])] });
    }
  }
  // Media del periodo (solo con una lonja)
  let valorMedia = null;
  if (o.media && vis.length === 1 && vis[0].pts.length > 2) {
    valorMedia = media(vis[0].pts.map(p => p.v));
    const ym = Y(valorMedia);
    P.push({ k: "line", x1: mi.l, x2: W - mi.r, y1: ym, y2: ym, c: "tenue", w: 1.2, dash: "6 4" });
    const dm = valorMedia >= 100 ? 0 : decimalesPaso(paso) + 1;
    P.push({ k: "text", x: W - mi.r - 2, y: ym - 5, txt: "media " + fmtNum(valorMedia, Math.min(dm, 3)), c: "tenue", size: 12, anchor: "end", font: "cifra", weight: 600 });
  }
  // Líneas
  vis.forEach(l => {
    for (const s of tramos(l.pts)) {
      if (s.length > 1) P.push({ k: "path", pts: s.map(p => [X(xv(p)), Y(p.v)]), c: l.color, w: l.grosor || 2.5, dash: l.discontinua ? "5 4" : null });
      else P.push({ k: "circle", x: X(xv(s[0])), y: Y(s[0].v), r: 2.5, fill: l.color });
    }
    // Sesiones recientes de la propia lonja: línea de puntos que continúa la oficial
    const rec = l.recientes || [];
    if (rec.length) {
      const desde = l.pts.at(-1);
      const cadena = (desde && xv(rec[0]) - xv(desde) <= salto * 2 ? [desde] : []).concat(rec);
      if (cadena.length > 1) P.push({ k: "path", pts: cadena.map(p => [X(xv(p)), Y(p.v)]), c: l.color, w: 2, dash: "2 4" });
      rec.forEach(p => P.push({ k: "circle", x: X(xv(p)), y: Y(p.v), r: 3.2, fill: "hoja", stroke: l.color, sw: 2 }));
    }
    const ult = rec.at(-1) || l.pts.at(-1);   // marcador final: lleno si es oficial, hueco si es dato reciente de la lonja
    if (ult) P.push(ult.reciente ? { k: "circle", x: X(xv(ult)), y: Y(ult.v), r: 4.8, fill: "hoja", stroke: l.color, sw: 2.6 }
      : { k: "circle", x: X(xv(ult)), y: Y(ult.v), r: 4.5, fill: l.color, stroke: "hoja", sw: 2 });
  });

  // Columnas para consultar al tocar. Con varias lonjas se agrupa por semana: cada lonja cotiza un día distinto.
  const porSemana = o.eje === "semana" || vis.length > 1;
  const cols = new Map();
  vis.forEach(l => [...l.pts, ...(l.recientes || [])].forEach(p => {
    const k = o.eje === "semana" ? semDe(p) : porSemana ? p.w : p.fecha;
    if (!cols.has(k)) cols.set(k, { fecha: p.fecha, w: p.w, sinFecha: !!p.sinFecha, porSemana, items: [] });
    const c = cols.get(k), i = lineas.indexOf(l);
    if (c.items.some(it => it.i === i)) return;
    c.items.push({ i, x: X(xv(p)), y: Y(p.v), txt: valorTxt(p, o.unidad), reciente: !!p.reciente, fecha: p.fecha, sinFecha: !!p.sinFecha });
  }));
  const columnas = [...cols.values()].map(c => ({ ...c, x: media(c.items.map(it => it.x)) })).sort((a, b) => a.x - b.x);
  return { W, H, mi, P, columnas, valorMedia, conBanda };
}

/* Dibujo en SVG */
const colorVar = c => `var(--${c})`;
function svgDe(P) {
  const n = v => Math.round(v * 10) / 10;
  return P.map(p => {
    if (p.k === "line") return `<line x1="${n(p.x1)}" x2="${n(p.x2)}" y1="${n(p.y1)}" y2="${n(p.y2)}" stroke="${colorVar(p.c)}" stroke-width="${p.w}"${p.dash ? ` stroke-dasharray="${p.dash}"` : ""}/>`;
    if (p.k === "path") return `<polyline points="${p.pts.map(([x, y]) => n(x) + "," + n(y)).join(" ")}" fill="none" stroke="${colorVar(p.c)}" stroke-width="${p.w}" stroke-linejoin="round" stroke-linecap="round"${p.dash ? ` stroke-dasharray="${p.dash}"` : ""}/>`;
    if (p.k === "area") return `<polygon points="${p.pts.map(([x, y]) => n(x) + "," + n(y)).join(" ")}" fill="${colorVar(p.c)}" fill-opacity="${p.op}" stroke="none"/>`;
    if (p.k === "circle") return `<circle cx="${n(p.x)}" cy="${n(p.y)}" r="${p.r}" fill="${p.fill ? colorVar(p.fill) : "none"}"${p.stroke ? ` stroke="${colorVar(p.stroke)}" stroke-width="${p.sw || 1}"` : ""}/>`;
    if (p.k === "text") return `<text x="${n(p.x)}" y="${n(p.y)}" font-size="${p.size}" fill="${colorVar(p.c)}" text-anchor="${p.anchor}" font-family="${p.font === "cifra" ? "var(--cifra)" : "var(--texto)"}"${p.weight ? ` font-weight="${p.weight}"` : ""}>${esc(p.txt)}</text>`;
    return "";
  }).join("");
}
/* Dibujo en canvas (imagen descargable) */
function canvasDe(ctx, P, col) {
  for (const p of P) {
    ctx.save();
    if (p.k === "line" || p.k === "path") {
      ctx.strokeStyle = col(p.c); ctx.lineWidth = p.w || 1; ctx.lineJoin = "round"; ctx.lineCap = "round";
      ctx.setLineDash(p.dash ? p.dash.split(" ").map(Number) : []);
      const pts = p.k === "line" ? [[p.x1, p.y1], [p.x2, p.y2]] : p.pts;
      ctx.beginPath(); pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.stroke();
    } else if (p.k === "area") {
      ctx.globalAlpha = p.op; ctx.fillStyle = col(p.c);
      ctx.beginPath(); p.pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.closePath(); ctx.fill();
    } else if (p.k === "circle") {
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      if (p.fill) { ctx.fillStyle = col(p.fill); ctx.fill(); }
      if (p.stroke) { ctx.strokeStyle = col(p.stroke); ctx.lineWidth = p.sw || 1; ctx.stroke(); }
    } else if (p.k === "text") {
      ctx.fillStyle = col(p.c);
      ctx.font = `${p.weight || 500} ${p.size}px ${p.font === "cifra" ? '"Barlow Condensed", "Arial Narrow", sans-serif' : '"Public Sans", system-ui, sans-serif'}`;
      ctx.textAlign = p.anchor === "end" ? "right" : p.anchor === "middle" ? "center" : "left";
      ctx.fillText(p.txt, p.x, p.y);
    }
    ctx.restore();
  }
}

function leyendaHTML(lineas, m) {
  const items = lineas.filter(l => l.pts.length || (l.recientes || []).length)
    .map(l => `<span><i class="c-${l.color}${l.discontinua ? " disc" : ""}"></i>${esc(l.nombre)}</span>`);
  if (lineas.some(l => (l.recientes || []).length)) items.push('<span><i class="rec"></i>Sesiones recientes (publicadas por la lonja)</span>');
  if (m.conBanda) items.push(`<span><i class="banda c-${lineas[0].color}"></i>Horquilla mínimo–máximo</span>`);
  if (m.valorMedia != null) items.push('<span><i class="media"></i>Media del periodo</span>');
  return items.length > 1 ? `<div class="leyenda">${items.join("")}</div>` : "";
}

/**
 * Gráfico interactivo. o: { eje, unidad, etiqueta, banda, media, contexto ("normal" | "ampliado" | "detalle"),
 * titulo, subtitulo, archivo } — titulo/subtitulo/archivo se usan al descargar.
 */
function graficoHist(lineas, o = {}) {
  const opts = { eje: "fecha", unidad: "", etiqueta: "Evolución del precio", ...o };
  const m = construirGrafico(lineas, { ...opts, ...medidasGrafico(opts.contexto) });
  if (!m) return '<p class="nota">No hay suficientes sesiones en este periodo para dibujar la evolución.</p>';
  const id = "g" + (++nGraf);
  GRAFS.set(id, { lineas, o: opts, m });
  while (GRAFS.size > 24) GRAFS.delete(GRAFS.keys().next().value);
  const guia = `<g class="guia" display="none"><line x1="0" x2="0" y1="${m.mi.t}" y2="${m.H - m.mi.b}" stroke="var(--tinta)" stroke-width="1" stroke-dasharray="3 3" opacity=".55"/>${lineas.map((l, i) => `<circle data-i="${i}" r="5.5" cx="0" cy="0" fill="${colorVar(l.color)}" stroke="var(--hoja)" stroke-width="2"/>`).join("")}</g>`;
  return `<div class="graf" data-graf="${id}">
      <svg viewBox="0 0 ${m.W} ${m.H}" role="img" tabindex="0" aria-label="${esc(opts.etiqueta)}. Toca el gráfico o usa las flechas del teclado para ver el precio de cada sesión.">${svgDe(m.P)}${guia}</svg>
      <div class="graf-tip" role="status" aria-live="polite" hidden></div>
    </div>${leyendaHTML(lineas, m)}`;
}

/* ---------- consultar un punto (tocar, arrastrar, ratón o flechas) ---------- */
function ocultarPunto(caja) {
  const cajas = caja ? [caja] : document.querySelectorAll(".graf[data-idx]");
  cajas.forEach(c => {
    delete c.dataset.idx;
    c.querySelector(".guia")?.setAttribute("display", "none");
    const tip = c.querySelector(".graf-tip"); if (tip) tip.hidden = true;
  });
}
function mostrarPunto(caja, idx) {
  const g = GRAFS.get(caja.dataset.graf), svg = caja.querySelector("svg");
  if (!g || !svg || !g.m.columnas.length) return;
  idx = Math.max(0, Math.min(g.m.columnas.length - 1, idx));
  caja.dataset.idx = idx;
  const c = g.m.columnas[idx], guia = svg.querySelector(".guia");
  guia.setAttribute("display", "inline");
  const ln = guia.querySelector("line"); ln.setAttribute("x1", c.x); ln.setAttribute("x2", c.x);
  guia.querySelectorAll("circle").forEach(ci => {
    const it = c.items.find(t => t.i === Number(ci.dataset.i));
    if (it) { ci.setAttribute("cx", it.x); ci.setAttribute("cy", it.y); ci.setAttribute("display", "inline"); }
    else ci.setAttribute("display", "none");
  });
  const semana = g.o.eje === "semana" || c.porSemana;
  const cab = g.o.eje === "semana" ? `Semana ${Number(c.w.slice(6))}` : semana || c.sinFecha ? `Semana ${Number(c.w.slice(6))} de ${c.w.slice(0, 4)}` : fechaLarga(c.fecha);
  const tip = caja.querySelector(".graf-tip");
  tip.innerHTML = `<b>${esc(cab)}</b>` + c.items.map(it => {
    const l = g.lineas[it.i];
    const extra = [semana && !it.sinFecha ? fechaCorta(it.fecha) : "", it.reciente ? "dato de la lonja" : ""].filter(Boolean).join(" · ");
    return `<span><i class="c-${l.color}"></i><em>${esc(l.nombre)}${extra ? ` <small>${esc(extra)}</small>` : ""}</em><b class="num">${esc(it.txt)}</b></span>`;
  }).join("");
  tip.hidden = false;
  // Medidas en píxeles CSS de la caja (con letra grande la pantalla está ampliada y getBoundingClientRect no coincide)
  const ancho = svg.clientWidth || svg.getBoundingClientRect().width, px = c.x * ancho / g.m.W, tw = tip.offsetWidth;
  let left = px + 14;
  if (left + tw > ancho) left = px - tw - 14;
  if (left < 0) left = Math.max(0, Math.min(ancho - tw, px - tw / 2));
  tip.style.left = Math.round(left) + "px";
}
function puntoEn(svg, clientX) {
  const caja = svg.closest(".graf"), g = caja && GRAFS.get(caja.dataset.graf);
  if (!g || !g.m.columnas.length) return;
  const r = svg.getBoundingClientRect(), vx = (clientX - r.left) / r.width * g.m.W;
  let mejor = 0, d = Infinity;
  g.m.columnas.forEach((c, i) => { const dd = Math.abs(c.x - vx); if (dd < d) { d = dd; mejor = i; } });
  mostrarPunto(caja, mejor);
}

/* ---------- descargas: imagen PNG (o compartir en el móvil) y CSV para Excel ---------- */
function nombreArchivo(g, ext) {
  return `lonjas-${slugTxt(g.o.archivo || g.o.titulo || "grafico")}.${ext}`;
}
const slugTxt = t => String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || "grafico";
function descargarBlob(blob, nombre) {
  const u = URL.createObjectURL(blob), a = document.createElement("a");
  a.href = u; a.download = nombre; a.rel = "noopener";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(u), 5000);
}
async function exportarPNG(id) {
  const g = GRAFS.get(id); if (!g) return;
  const m = construirGrafico(g.lineas, { ...g.o, ...medidasGrafico("png") });
  if (!m) return;
  const col = c => PALETA_PNG[c] || PALETA_PNG.tinta;
  const items = g.lineas.filter(l => l.pts.length || (l.recientes || []).length);
  const cab = 64, filasLey = Math.ceil((items.length + (items.some(l => (l.recientes || []).length) ? 1 : 0)) / 3), pie = 26 + filasLey * 20;
  const W = m.W + 32, H = cab + m.H + pie;
  const cv = document.createElement("canvas"); cv.width = W * 2; cv.height = H * 2;
  const ctx = cv.getContext("2d"); ctx.scale(2, 2);
  try { await document.fonts?.ready; } catch {}
  ctx.fillStyle = col("hoja"); ctx.fillRect(0, 0, W, H);
  const texto = (t, x, y, size, color, peso = 600, fuente = "texto", alinea = "left") => {
    ctx.fillStyle = col(color); ctx.textAlign = alinea;
    ctx.font = `${peso} ${size}px ${fuente === "cifra" ? '"Barlow Condensed", "Arial Narrow", sans-serif' : '"Public Sans", system-ui, sans-serif'}`;
    ctx.fillText(t, x, y);
  };
  texto(g.o.titulo || "Lonjas CyL", 16, 30, 22, "tinta", 700, "cifra");
  texto(g.o.subtitulo || "", 16, 52, 13, "tenue", 500);
  ctx.save(); ctx.translate(16, cab); canvasDe(ctx, m.P, col); ctx.restore();
  // leyenda
  const ley = items.map(l => ({ c: l.color, t: l.nombre, disc: l.discontinua }));
  if (items.some(l => (l.recientes || []).length)) ley.push({ c: "tenue", t: "Puntos huecos: últimas sesiones", disc: true });
  ley.forEach((it, i) => {
    const x = 16 + (i % 3) * ((W - 32) / 3), y = cab + m.H + 18 + Math.floor(i / 3) * 20;
    ctx.save(); ctx.strokeStyle = col(it.c); ctx.lineWidth = 3; ctx.setLineDash(it.disc ? [4, 3] : []);
    ctx.beginPath(); ctx.moveTo(x, y - 4); ctx.lineTo(x + 18, y - 4); ctx.stroke(); ctx.restore();
    texto(it.t.length > 34 ? it.t.slice(0, 33) + "…" : it.t, x + 24, y, 12, "tinta", 500);
  });
  texto("Fuente: Junta de Castilla y León y lonjas · Lonjas CyL", W - 16, H - 8, 11, "tenue", 500, "texto", "right");
  const blob = await new Promise(r => cv.toBlob(r, "image/png"));
  if (!blob) return;
  const nombre = nombreArchivo(g, "png");
  // En el móvil se ofrece compartir (WhatsApp, correo…); si no se puede, se descarga
  if (window.matchMedia?.("(pointer: coarse)").matches && typeof File === "function" && navigator.canShare) {
    const file = new File([blob], nombre, { type: "image/png" });
    if (navigator.canShare({ files: [file] })) {
      try { await navigator.share({ files: [file], title: g.o.titulo || "Lonjas CyL" }); return; }
      catch (e) { if (e && e.name === "AbortError") return; }
    }
  }
  descargarBlob(blob, nombre);
}
function exportarCSV(id) {
  const g = GRAFS.get(id); if (!g) return;
  const n = v => v == null ? "" : v.toLocaleString("es-ES", { useGrouping: false, maximumFractionDigits: 4 });
  const campo = v => /[;"\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : v;
  const filas = [["Fecha", "Semana", "Lonja", "Provincia", "Producto", "Unidad", "Precio", "Mínimo", "Máximo", "Dudoso", "Origen"]];
  for (const l of g.lineas) {
    for (const p of [...(l.csv || l.pts), ...(l.recientes || [])]) {
      filas.push([p.sinFecha ? "" : p.fecha, p.w || "", l.lonja || l.nombre, l.provincia || "", l.producto || "", g.o.unidad,
        n(p.v), p.b != null ? n(p.a) : "", p.b != null ? n(p.b) : "", p.dud ? "sí" : "no",
        p.reciente ? "Lonja (lectura de la app)" : "Junta de Castilla y León"]);
    }
  }
  const txt = "﻿" + filas.map(f => f.map(v => campo(String(v))).join(";")).join("\r\n");
  descargarBlob(new Blob([txt], { type: "text/csv;charset=utf-8" }), nombreArchivo(g, "csv"));
}

/* ---------- selección ---------- */
function gruposVisibles() {
  return [...HIST.grupos.values()].filter(g => g.series.some(id => enAmbito(id) && conDatos(id)));
}
function normalizarSeleccion() {
  const visibles = gruposVisibles();
  const sectores = SECTORES_HIST.filter(s => visibles.some(g => g.sector === s));
  if (!sectores.includes(estHist.sector)) estHist.sector = sectores[0];
  const delSector = visibles.filter(g => g.sector === estHist.sector)
    .sort((a, b) => b.series.filter(enAmbito).length - a.series.filter(enAmbito).length || a.producto.localeCompare(b.producto, "es"));
  if (!delSector.some(g => g.clave === estHist.grupo)) {
    // Por defecto, el producto de referencia del sector (trigo, cebo normal, lechazo…) si tiene datos
    const pref = Object.values(CLAVE_A_JUNTA).find(k => delSector.some(g => g.clave === k));
    estHist.grupo = pref || delSector[0]?.clave || null;
  }
  const g = HIST.grupos.get(estHist.grupo);
  const series = g ? g.series.filter(id => enAmbito(id) && conDatos(id)) : [];
  const provincias = [...new Set(series.map(id => lonjaH(HIST.indice.series[id].l).provincia))].sort((a, b) => a.localeCompare(b, "es"));
  if (estHist.provincia !== "Todas" && !provincias.includes(estHist.provincia)) estHist.provincia = "Todas";
  const filtradas = series.filter(id => estHist.provincia === "Todas" || lonjaH(HIST.indice.series[id].l).provincia === estHist.provincia);
  if (!filtradas.includes(estHist.lonja)) {
    // Por defecto, la lonja con más sesiones
    estHist.lonja = [...filtradas].sort((a, b) => puntosSerie(b).length - puntosSerie(a).length)[0] || null;
  }
  // Lonjas añadidas al gráfico: del mismo producto y filtro, sin repetir la principal
  estHist.extra = estHist.extra.filter(x => x !== estHist.lonja && filtradas.includes(x)).slice(0, MAX_LONJAS_GRAFICO - 1);
  return { sectores, delSector, g, provincias, filtradas };
}

/** Abre el histórico ya filtrado para un producto clave de la app (desde «Comparar» o el detalle). */
function abrirHistoricoDe(clave, lonjaApp) {
  estHist.grupo = CLAVE_A_JUNTA[clave] || estHist.grupo;
  estHist.sector = (estHist.grupo || "").split("|")[0] || estHist.sector;
  estHist.provincia = "Todas"; estHist.lonja = null; estHist.ambito = "cyl"; estHist.extra = [];
  if (lonjaApp && HIST.indice) estHist.lonja = serieDeApp(clave, lonjaApp);
  ir("historico");
}
function serieDeApp(clave, lonjaApp) {
  const g = HIST.grupos.get(CLAVE_A_JUNTA[clave]);
  if (!g) return null;
  return g.series.find(id => lonjaH(HIST.indice.series[id].l).app === lonjaApp && conDatos(id)) || null;
}

/* ---------- vista ---------- */
function vistaHistorico() {
  if (!HIST.indice) {
    if (!HIST.cargando && !HIST.error) cargarHistorico().then(() => { if (location.hash === "#historico") router(); });
    return `<section class="seccion"><div class="titulo-seccion"><h2>Histórico</h2><span>2025–2026</span></div>
      ${HIST.error ? `<div class="vacio"><b>No se ha podido cargar el histórico</b>Comprueba la conexión y vuelve a intentarlo.<br><button class="chip auto" type="button" data-h-reintentar>Reintentar</button></div>`
        : '<div class="vacio"><b>Cargando el histórico…</b>Cotizaciones semanales de 2025 y 2026.</div>'}</section>`;
  }
  const { sectores, delSector, g, provincias, filtradas } = normalizarSeleccion();
  if (!g) return '<section class="seccion"><div class="vacio"><b>Sin datos</b>No hay series para este filtro.</div></section>';
  const ser = estHist.lonja && HIST.indice.series[estHist.lonja];
  const pts = ser ? puntosSerie(estHist.lonja) : [];
  const anios = HIST.indice.anios;
  const periodos = [...anios.map(a => [String(a), String(a)]), ["todo", `${anios[0]}–${anios.at(-1)}`], ...(anios.length > 1 ? [["comparar", `Comparar ${anios.at(-2)} y ${anios.at(-1)}`]] : [])];
  if (!periodos.some(p => p[0] === estHist.periodo)) estHist.periodo = String(anios.at(-1));
  const chips = (lista, actual, attr) => lista.map(([v, t]) => `<button class="chip" type="button" ${attr}="${esc(v)}" aria-pressed="${v === actual}">${esc(t)}</button>`).join("");

  return `
    <section class="seccion">
      <div class="titulo-seccion"><h2>Histórico</h2><span>Cotizaciones semanales · Junta de Castilla y León</span></div>
      <div class="panel-filtros">
        <div class="filtros" role="group" aria-label="Ámbito">${chips([["cyl", "Castilla y León"], ["todas", "Toda España"]], estHist.ambito, "data-h-ambito")}</div>
        <div class="filtros" role="group" aria-label="Categoría">${chips(sectores.map(s => [s, s]), estHist.sector, "data-h-sector")}</div>
        <label class="campo"><span class="etiqueta">Producto</span>
          <select id="h-producto">${delSector.map(x => `<option value="${esc(x.clave)}"${x.clave === g.clave ? " selected" : ""}>${esc(x.producto)} · ${esc(x.unidad)}</option>`).join("")}</select></label>
        ${provincias.length > 1 ? `<div class="filtros" role="group" aria-label="Provincia">${chips([["Todas", "Todas las provincias"], ...provincias.map(p => [p, p])], estHist.provincia, "data-h-provincia")}</div>` : ""}
        <label class="campo"><span class="etiqueta">Lonja</span>
          <select id="h-lonja">${filtradas.map(id => `<option value="${esc(id)}"${id === estHist.lonja ? " selected" : ""}>${esc(lonjaH(HIST.indice.series[id].l).nombre)} (${esc(lonjaH(HIST.indice.series[id].l).provincia)})</option>`).join("")}</select></label>
        <div class="filtros" role="group" aria-label="Periodo">${chips(periodos, estHist.periodo, "data-h-periodo")}</div>
      </div>
    </section>
    ${ser ? panelSerie(estHist.lonja, pts, g, filtradas) : ""}
    ${panelLonjas(g, filtradas)}
    ${ser ? panelSemanal(pts, g) : ""}
    <p class="nota">Fuente: ${HIST.indice.fuente ? `<a href="${esc(HIST.indice.fuente)}" target="_blank" rel="noopener noreferrer">Junta de Castilla y León, precios de lonjas y mercados</a>` : "Junta de Castilla y León"}.
      Valores tal como se publican, en la unidad de cada producto, salvo cereales y forrajes: la Junta los da en €/100 kg y aquí se muestran en €/t (multiplicados por 10).
      Los puntos huecos al final de una línea son sesiones más recientes que la app ha leído de la propia lonja y que la Junta aún no ha publicado. Cuando la lonja da una horquilla (mínimo–máximo) se usa el centro para gráficos y medias.
      Los valores marcados como «dudoso» se apartan mucho del resto de la serie o son un pico aislado que vuelve a su nivel la semana siguiente (casi siempre, una errata o una fila desplazada en el Excel original) y no se usan en gráficos ni cálculos.
      <a href="#historico-fuentes">Archivos importados</a>.</p>`;
}

/* ---------- sesiones recientes que la app ya ha leído de la propia lonja ----------
   La Junta publica su cuadro con unas semanas de retraso; el robot de la app lee cada lonja el mismo día.
   Se añaden al final de la serie oficial SOLO si es la misma lonja, el mismo producto clave (trigo, cebada…),
   la misma unidad, y el primer valor no se aparta más de un 15 % del último oficial (si no, no son comparables). */
const normU = u => String(u || "").toLowerCase().replace(/\s+/g, " ").trim();
function recientesDe(id) {
  if (typeof DATOS === "undefined" || !DATOS || !Array.isArray(DATOS.lonjas)) return [];
  const s = HIST.indice.series[id], l = lonjaH(s.l);
  if (!l.app) return [];
  const clave = Object.keys(CLAVE_A_JUNTA).find(k => CLAVE_A_JUNTA[k] === `${s.s}|${s.p}|${s.u}`);
  const lonjaApp = clave && DATOS.lonjas.find(x => x.id === l.app);
  const oficial = lonjaApp && ultimo(puntosSerie(id));
  if (!oficial) return [];
  let mejor = null;
  for (const f of lonjaApp.precios.filter(f => f.clave === clave && normU(f.unidad) === normU(s.u))) {
    const serie = (DATOS.historial?.[f.id] || []).filter(p => p[0] > oficial.fecha && num(p[1]) !== null && p[1] > 0);
    if (!serie.length) continue;
    const dif = Math.abs(serie[0][1] - oficial.v) / Math.abs(oficial.v);
    if (dif <= 0.15 && (!mejor || dif < mejor.dif)) mejor = { dif, serie };
  }
  return mejor ? mejor.serie.slice(-12).map(([fecha, v]) => ({ fecha, w: semanaISO(fecha), v, a: v, b: null, reciente: true, sinFecha: false, dud: false })) : [];
}
const nombreCorto = id => lonjaH(HIST.indice.series[id].l).nombre.replace(/^Lonja de(l)? /, "");
/** Una línea del gráfico para una serie y un periodo (sin dudosos; con las sesiones recientes del periodo). */
function lineaDe(id, per, color) {
  const s = HIST.indice.series[id], l = lonjaH(s.l), enP = enPeriodo(puntosSerie(id), per);
  const rec = recientesDe(id).filter(p => per === "todo" || per === "comparar" || anioDe(p) === Number(per));
  return { nombre: nombreCorto(id), color, pts: enP.filter(p => !p.dud), csv: enP, recientes: rec, lonja: l.nombre, provincia: l.provincia, producto: s.p };
}

function panelSerie(id, pts, g, filtradas) {
  const s = HIST.indice.series[id], u = s.u, per = estHist.periodo, lonjaN = lonjaH(s.l).nombre;
  const anios = HIST.indice.anios, anioAct = per === "todo" || per === "comparar" ? anios.at(-1) : Number(per);
  const vis = enPeriodo(pts, per).filter(p => !p.dud);
  const ult = ultimo(enPeriodo(pts, per));
  const perTxt = per === "todo" ? `${anios[0]}–${anios.at(-1)}` : per === "comparar" ? `${anios.at(-2)} frente a ${anios.at(-1)}` : per;
  const base = { unidad: u, contexto: estHist.ampliado ? "ampliado" : "normal", subtitulo: `${u} · ${perTxt} · cotizaciones semanales` };
  let lineas, opts;
  if (per === "comparar") {
    const rec = recientesDe(id);
    lineas = anios.slice(-2).map((a, i, arr) => {
      const actual = i === arr.length - 1, todos = pts.filter(p => anioDe(p) === a);
      return { nombre: String(a), color: actual ? "pino" : "paja", discontinua: !actual, pts: todos.filter(p => !p.dud), csv: todos,
        recientes: actual ? rec.filter(p => anioDe(p) === a) : [], lonja: lonjaN, provincia: lonjaH(s.l).provincia, producto: s.p };
    });
    opts = { ...base, eje: "semana", etiqueta: `Precio por semana del año, ${anios.slice(-2).join(" frente a ")}`,
      titulo: `${s.p} · ${lonjaN}`, archivo: `${s.p}-${nombreCorto(id)}-${anios.slice(-2).join("-")}` };
  } else {
    lineas = [id, ...estHist.extra].map((sid, i) => lineaDe(sid, per, COLORES_LINEA[i]));
    const varias = lineas.length > 1;
    opts = { ...base, banda: !varias, media: !varias,
      etiqueta: varias ? `Evolución de ${s.p} en ${lineas.map(l => l.nombre).join(", ")}` : `Evolución de ${s.p} en ${lonjaN}`,
      titulo: varias ? `${s.p} · ${lineas.length} lonjas` : `${s.p} · ${lonjaN}`,
      archivo: `${s.p}-${varias ? lineas.map(l => l.nombre).join("-") : nombreCorto(id)}-${per}` };
  }
  const grafico = graficoHist(lineas, opts);
  const gid = grafico.includes(`data-graf="g${nGraf}"`) ? "g" + nGraf : null;
  const principal = per === "comparar" ? lineas.at(-1) : lineas[0];
  const rec = principal.recientes;

  const vals = vis.map(p => p.v);
  const ia = mismaSemanaAnterior(pts, ult), mp = mismoPeriodo(pts, anioAct), t = tendencia(enPeriodo(pts, per));
  const primero = vis[0];
  const vAnio = primero && ult && primero !== ult ? txtPct(pct(ult.v, primero.v)) : null;
  const vIa = txtPct(ia ? pct(ult.v, ia.v) : null), vMp = txtPct(mp ? mp.var : null);
  const nDud = enPeriodo(pts, per).filter(p => p.dud).length;
  const redondeo = v => u === "€/t" ? Math.round(v * 100) / 100 : Math.round(v * 1000) / 1000;

  const otras = filtradas.filter(x => x !== id);
  const lleno = estHist.extra.length >= MAX_LONJAS_GRAFICO - 1;
  const chipsExtra = per === "comparar"
    ? (otras.length ? `<p class="nota">Para ver varias lonjas en el mismo gráfico, elige un año o ${anios[0]}–${anios.at(-1)}.</p>` : "")
    : otras.length ? `<div class="extra-lonjas" role="group" aria-label="Añadir lonjas al gráfico"><span class="etiqueta">Añadir al gráfico (hasta ${MAX_LONJAS_GRAFICO} lonjas)</span>
        <div class="filtros envolver">${otras.map(x => {
          const i = estHist.extra.indexOf(x);
          return `<button class="chip" type="button" data-h-extra="${esc(x)}" aria-pressed="${i >= 0}"${i < 0 && lleno ? " disabled" : ""}>${i >= 0 ? `<i class="punto c-${COLORES_LINEA[i + 1]}"></i>` : "+ "}${esc(nombreCorto(x))}</button>`;
        }).join("")}</div></div>` : "";
  const acciones = gid ? `<div class="graf-acciones">
      <button class="chip" type="button" data-h-ampliar aria-pressed="${estHist.ampliado}">${estHist.ampliado ? "✕ Cerrar" : "⤢ Ampliar"}</button>
      <button class="chip" type="button" data-h-png="${gid}">⇩ Imagen</button>
      <button class="chip" type="button" data-h-csv="${gid}">⇩ Excel (CSV)</button></div>` : "";
  const notaRec = rec.length ? `<p class="nota">Puntos huecos al final: ${rec.length === 1 ? "la última sesión publicada" : `las ${rec.length} últimas sesiones publicadas`} por la propia lonja (${fechaCorta(rec.at(-1).fecha)}: <b class="num">${valorTxt(rec.at(-1), u)}</b>). La Junta aún no las ha recogido en su cuadro.</p>` : "";

  return `
    <section class="seccion">
      <div class="tarjeta-hist${estHist.ampliado ? " ampliado" : ""}"${estHist.ampliado ? ' role="dialog" aria-modal="true" aria-label="Gráfico ampliado"' : ""}>
        <div class="cab-hist"><div><div class="etiqueta">${esc(lonjaN)} · ${esc(s.s)}</div><h3>${esc(s.p)}</h3><small>${esc(u)} · ${esc(perTxt)}</small></div>
          ${t ? `<span class="pastilla ${t.clase}" title="Últimas 4 sesiones: ${t.sube} subidas, ${t.baja} bajadas">${t.txt}</span>` : ""}</div>
        <div class="datos-det cuatro">
          <div><span class="etiqueta">Último</span><b class="num">${ult ? valorTxt(ult, u) : "—"}</b><small>${ult ? (ult.sinFecha ? "semana " + semDe(ult) + " de " + anioDe(ult) : fechaLarga(ult.fecha)) : ""}</small></div>
          <div><span class="etiqueta">Media${per === "comparar" ? " " + anios.join("–") : ""}</span><b class="num">${vals.length ? precio(redondeo(media(vals)), u) : "—"}</b><small>${vals.length} sesiones</small></div>
          <div><span class="etiqueta">Mín · máx</span><b class="num chico">${vals.length ? precio(Math.min(...vals), u) + " · " + precio(Math.max(...vals), u) : "—"}</b><small>${vAnio ? `<span class="var ${vAnio.clase}">${vAnio.txt}</span> en el periodo` : ""}</small></div>
          <div><span class="etiqueta">Interanual</span><b class="num chico var ${vIa.clase}">${vIa.txt}</b><small>${ia ? `vs ${valorTxt(ia, u)} (sem. ${semDe(ia)} de ${anioDe(ia)})` : "sin dato del año anterior"}</small></div>
        </div>
        ${mp ? `<p class="mismo-periodo">Media de ${anioAct} entre las semanas ${mp.desde} y ${mp.hasta}: <b class="num">${precio(redondeo(mp.act), u)}</b>, frente a <b class="num">${precio(redondeo(mp.ant), u)}</b> en las mismas ${mp.semanas} semanas de ${anioAct - 1} (<span class="var ${vMp.clase}">${vMp.txt}</span>).</p>` : ""}
        <div class="grafico">${grafico}</div>
        ${acciones}
        ${chipsExtra}
        ${notaRec}
        ${nDud ? `<p class="nota">${nDud} valor${nDud === 1 ? "" : "es"} dudoso${nDud === 1 ? "" : "s"} fuera del gráfico (ver tabla semanal).</p>` : ""}
      </div>
    </section>`;
}

/** Entre lonjas: cada lonja como un punto sobre una escala ajustada a los precios, con la media marcada.
    Las barras desde cero escondían diferencias de 5–10 €/t, que son justo las que importan para vender. */
function panelLonjas(g, filtradas) {
  const per = estHist.periodo, u = g.unidad;
  const filas = filtradas.map(id => {
    const pts = puntosSerie(id), ul = ultimo(enPeriodo(pts, per));
    return { id, s: HIST.indice.series[id], u: ul, h4: hace4(pts, ul), ia: mismaSemanaAnterior(pts, ul) };
  }).filter(f => f.u);
  if (!filas.length) return "";
  const masNueva = filas.reduce((m, f) => f.u.fecha > m ? f.u.fecha : m, "");
  const lim = new Date(masNueva + "T12:00:00Z"); lim.setUTCDate(lim.getUTCDate() - 21);
  const tope = lim.toISOString().slice(0, 10);
  filas.forEach(f => { f.viejo = f.u.fecha < tope; });
  const actuales = filas.filter(f => !f.viejo);
  const med = media(actuales.map(f => f.u.v));
  filas.sort((a, b) => (a.viejo - b.viejo) || b.u.v - a.u.v);
  let lo = Math.min(...filas.map(f => f.u.v), med), hi = Math.max(...filas.map(f => f.u.v), med);
  const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.03 || 1; lo -= pad; hi += pad;
  const pos = v => Math.round((10 + (v - lo) / (hi - lo) * 180) * 10) / 10;
  const red = v => u === "€/t" ? Math.round(v) : Math.round(v * 1000) / 1000;
  const enGraf = estHist.periodo === "comparar" ? [estHist.lonja] : [estHist.lonja, ...estHist.extra];
  return `
    <section class="seccion">
      <div class="titulo-seccion"><h2>Entre lonjas</h2><span>${esc(g.producto)} · ${esc(u)}</span></div>
      <p class="nota">${actuales.length > 1 ? `Media de las ${actuales.length} lonjas con sesión en las 3 últimas semanas: <b class="num">${precio(red(med), u)}</b>. La raya marca la media; cada punto, el último precio de la lonja.` : "Último precio de cada lonja en el periodo elegido."}</p>
      <div class="comparativa">${filas.map(f => {
        const v4 = txtPct(f.h4 ? pct(f.u.v, f.h4.v) : null), via = txtPct(f.ia ? pct(f.u.v, f.ia.v) : null);
        const i = enGraf.indexOf(f.id), color = i >= 0 ? COLORES_LINEA[i] : "tenue";
        const d = red(f.u.v - med), dTxt = f.viejo || actuales.length < 2 ? "" : d === 0 ? "= media" : `${d > 0 ? "+" : "−"}${precio(Math.abs(d), u)} vs media`;
        return `<div class="cmp-fila${f.viejo ? " viejo" : ""}" role="button" tabindex="0" data-h-lonja="${esc(f.id)}"${f.id === estHist.lonja ? ' aria-current="true"' : ""}>
          <span><b>${esc(nombreCorto(f.id))}</b><br><small class="etiqueta">${f.u.sinFecha ? "sem. " + semDe(f.u) : fechaCorta(f.u.fecha)} ${anioDe(f.u)}</small></span>
          <svg class="tira" viewBox="0 0 200 20" aria-hidden="true"><line x1="10" x2="190" y1="10" y2="10" stroke="var(--linea)" stroke-width="5" stroke-linecap="round"/>${actuales.length > 1 ? `<line x1="${pos(med)}" x2="${pos(med)}" y1="1" y2="19" stroke="var(--tenue)" stroke-width="2"/>` : ""}<circle cx="${pos(f.u.v)}" cy="10" r="${i >= 0 ? 7 : 6}" fill="${f.viejo ? "var(--hoja)" : colorVar(color)}" stroke="${colorVar(color)}" stroke-width="2.5"/></svg>
          <span class="cmp-valor num">${valorTxt(f.u, u)}<small class="var ${d > 0 ? "s" : d < 0 ? "b" : "i"}">${dTxt}</small></span>
          <span class="q">${esc(lonjaH(f.s.l).provincia)} · 4 sem. <span class="var ${v4.clase}">${v4.txt}</span> · interanual <span class="var ${via.clase}">${via.txt}</span>${f.viejo ? " · sin sesión reciente (no cuenta en la media)" : ""}</span>
        </div>`;
      }).join("")}</div>
      <p class="nota">Toca una lonja para verla arriba. Cada lonja cotiza en sus propias condiciones (origen, almacén, calidad), así que las diferencias no siempre son de mercado.</p>
    </section>`;
}

function panelSemanal(pts, g) {
  const per = estHist.periodo;
  const lista = enPeriodo(pts, per);
  if (!lista.length) return "";
  let previo = null;
  const filas = lista.map(p => {
    const d = !p.dud && previo ? p.v - previo.v : null;
    const fila = { p, d, pc: !p.dud && previo ? pct(p.v, previo.v) : null };
    if (!p.dud) previo = p;
    return fila;
  }).reverse();
  const visibles = estHist.todas ? filas : filas.slice(0, 20);
  return `
    <section class="seccion">
      <div class="titulo-seccion"><h2>Semana a semana</h2><span>${lista.length} sesiones</span></div>
      <div class="tabla-hist" role="table" aria-label="Precios por semana">
        <div class="th" role="row"><span role="columnheader">Sesión</span><span role="columnheader">Precio</span><span role="columnheader">Variación</span></div>
        ${visibles.map(({ p, d, pc }) => {
          const v = d == null ? { txt: "", clase: "i" } : txtPct(pc);
          return `<div class="tr${p.dud ? " dudoso" : ""}" role="row">
            <span role="cell">${p.sinFecha ? `Semana ${semDe(p)} de ${anioDe(p)}` : fechaLarga(p.fecha)}<small>sem. ${semDe(p)}</small></span>
            <span role="cell" class="num">${valorTxt(p, g.unidad)}</span>
            <span role="cell" class="var ${p.dud ? "i" : v.clase}">${p.dud ? "dudoso" : (d == null ? "—" : (d === 0 ? "=" : v.txt))}</span>
          </div>`;
        }).join("")}
      </div>
      ${filas.length > 20 ? `<button class="chip auto" type="button" data-h-todas>${estHist.todas ? "Ver solo las 20 últimas" : `Ver las ${filas.length} sesiones`}</button>` : ""}
    </section>`;
}

function vistaFuentesHist() {
  if (!HIST.indice) { if (!HIST.cargando) cargarHistorico().then(() => { if (location.hash === "#historico-fuentes") router(); }); return '<div class="vacio"><b>Cargando…</b></div>'; }
  const a = HIST.indice.archivos;
  const reg = a.reduce((s, x) => s + x.registros, 0);
  return `<section class="seccion">
    <div class="cab-lonja"><button class="volver" type="button" data-ir="historico">‹ Volver</button><h2>Archivos importados</h2>
      <div class="meta">${a.filter(x => x.importado).length} Excel semanales · ${reg.toLocaleString("es-ES")} cotizaciones</div></div>
    <div class="serie larga">${a.map(x => `<div><span>${x.anio} · semana ${x.semana}</span><b class="num">${x.importado ? x.registros + " precios" : esc(x.motivo || "no importado")}</b></div>`).join("")}</div>
  </section>`;
}

/* ---------- histórico dentro de la hoja de detalle de un producto ---------- */
async function pintarHistDetalle(f) {
  const caja = document.getElementById("det-hist");
  if (!caja || !f.clave || !CLAVE_A_JUNTA[f.clave]) return;
  caja.innerHTML = '<p class="nota">Cargando el histórico oficial…</p>';
  await cargarHistorico();
  if (!document.body.contains(caja)) return;
  const id = HIST.indice && serieDeApp(f.clave, f.lonja.id);
  if (!id) { caja.innerHTML = ""; return; }
  const s = HIST.indice.series[id], pts = puntosSerie(id).filter(p => !p.dud), u = ultimo(pts), ia = mismaSemanaAnterior(pts, u);
  const via = txtPct(ia ? pct(u.v, ia.v) : null);
  const linea = lineaDe(id, "todo", "pino");
  caja.innerHTML = `<div class="etiqueta">Histórico oficial ${HIST.indice.anios[0]}–${HIST.indice.anios.at(-1)} · Junta de CyL</div>
    <p class="nota">${esc(s.p)} · ${esc(s.u)}${s.factor !== 1 ? ` (la Junta lo publica en ${esc(s.uJunta)})` : ""}. Último: <b class="num">${valorTxt(u, s.u)}</b> · interanual <span class="var ${via.clase}">${via.txt}</span></p>
    ${typeof lineaTermometro === "function" ? lineaTermometro(id) : ""}
    <div class="grafico">${graficoHist([linea], { unidad: s.u, contexto: "detalle", banda: true, etiqueta: `Histórico de ${s.p} en ${lonjaH(s.l).nombre}`,
      titulo: `${s.p} · ${lonjaH(s.l).nombre}`, subtitulo: `${s.u} · histórico oficial`, archivo: `${s.p}-${nombreCorto(id)}-historico` })}</div>
    <button class="chip auto" type="button" data-h-abrir="${esc(f.clave)}" data-h-lonja-app="${esc(f.lonja.id)}">Ver en Histórico</button>`;
}

/* ---------- eventos ---------- */
function reabrirAmpliado() {
  router();
  document.querySelector("[data-h-ampliar]")?.focus({ preventScroll: true });
}
document.addEventListener("click", e => {
  const t = e.target;
  const q = sel => t.closest(sel);
  let el;
  if ((el = q("[data-h-ambito]"))) { estHist.ambito = el.dataset.hAmbito; estHist.lonja = null; return router(); }
  if ((el = q("[data-h-sector]"))) { estHist.sector = el.dataset.hSector; estHist.grupo = null; estHist.lonja = null; estHist.extra = []; return router(); }
  if ((el = q("[data-h-provincia]"))) { estHist.provincia = el.dataset.hProvincia; estHist.lonja = null; return router(); }
  if ((el = q("[data-h-periodo]"))) { estHist.periodo = el.dataset.hPeriodo; return router(); }
  if ((el = q("[data-h-extra]"))) {
    const id = el.dataset.hExtra, i = estHist.extra.indexOf(id);
    if (i >= 0) estHist.extra.splice(i, 1); else if (estHist.extra.length < MAX_LONJAS_GRAFICO - 1) estHist.extra.push(id);
    const y = window.scrollY; router(); window.scrollTo(0, y);
    return document.querySelector(`[data-h-extra="${CSS.escape(id)}"]`)?.focus({ preventScroll: true });
  }
  if (q("[data-h-ampliar]")) { estHist.ampliado = !estHist.ampliado; return reabrirAmpliado(); }
  if ((el = q("[data-h-png]"))) { exportarPNG(el.dataset.hPng).catch(() => {}); return; }
  if ((el = q("[data-h-csv]"))) { exportarCSV(el.dataset.hCsv); return; }
  if ((el = q("[data-h-lonja]"))) {
    estHist.lonja = el.dataset.hLonja; estHist.ampliado = false; router();
    return document.getElementById("h-lonja")?.scrollIntoView({ block: "center" });
  }
  if (q("[data-h-todas]")) { estHist.todas = !estHist.todas; return router(); }
  if (q("[data-h-reintentar]")) { HIST.error = null; return router(); }
  if ((el = q("[data-h-abrir]"))) { cerrarDetalle(true); return abrirHistoricoDe(el.dataset.hAbrir, el.dataset.hLonjaApp || null); }
});
document.addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-h-lonja]")) { e.preventDefault(); e.target.click(); return; }
  const svg = e.target.closest?.(".graf svg");
  if (svg) {
    const caja = svg.closest(".graf"), g = GRAFS.get(caja.dataset.graf);
    if (!g) return;
    const n = g.m.columnas.length, act = caja.dataset.idx != null ? Number(caja.dataset.idx) : n;
    const nuevo = { ArrowRight: act >= n ? n - 1 : act + 1, ArrowLeft: act >= n ? n - 1 : act - 1, Home: 0, End: n - 1 }[e.key];
    if (nuevo != null) { e.preventDefault(); return mostrarPunto(caja, nuevo); }
    if (e.key === "Escape" && caja.dataset.idx != null) { e.preventDefault(); return ocultarPunto(caja); }
  }
  if (e.key === "Escape" && estHist.ampliado && location.hash === "#historico") { estHist.ampliado = false; reabrirAmpliado(); }
});
document.addEventListener("change", e => {
  if (e.target.id === "h-producto") { estHist.grupo = e.target.value; estHist.lonja = null; estHist.provincia = "Todas"; estHist.extra = []; router(); }
  if (e.target.id === "h-lonja") { estHist.lonja = e.target.value; router(); }
});
// Consultar el gráfico: con el ratón al pasar, con el dedo al tocar o arrastrar en horizontal
document.addEventListener("pointermove", e => {
  const svg = e.target.closest?.(".graf svg");
  if (svg && (e.pointerType !== "touch" || e.buttons)) puntoEn(svg, e.clientX);
});
document.addEventListener("pointerdown", e => {
  const svg = e.target.closest?.(".graf svg");
  if (svg) puntoEn(svg, e.clientX);
  else if (!e.target.closest?.(".graf-tip")) ocultarPunto();
});
document.addEventListener("pointerout", e => {
  if (e.pointerType !== "mouse") return;
  const caja = e.target.closest?.(".graf");
  if (caja && !caja.contains(e.relatedTarget)) ocultarPunto(caja);
});
// El gráfico se dibuja al ancho real de la pantalla: al girar el móvil o cambiar la ventana, se redibuja
let tRedim = null, anchoPrevio = window.innerWidth;
window.addEventListener("resize", () => {
  clearTimeout(tRedim);
  tRedim = setTimeout(() => {
    if (Math.abs(window.innerWidth - anchoPrevio) < 30 && !estHist.ampliado) return;
    anchoPrevio = window.innerWidth;
    if (location.hash.startsWith("#historico") && HIST.indice) { const y = window.scrollY; router(); window.scrollTo(0, y); }
  }, 250);
});

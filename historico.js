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
const HIST = { indice: null, puntos: {}, grupos: new Map(), cache: new Map(), cargando: null, error: null };
const estHist = { ambito: "cyl", sector: "Cereales y forrajes", grupo: null, lonja: null, provincia: "Todas", periodo: "2026", todas: false };

// Productos clave de la app -> producto del cuadro de la Junta (misma lonja; la unidad es la que publica la Junta)
const CLAVE_A_JUNTA = {
  trigo: "Cereales y forrajes|Trigo|€/100 kg",
  cebada: "Cereales y forrajes|Cebada (+64)|€/100 kg",
  maiz: "Cereales y forrajes|Maiz seco nac|€/100 kg",
  avena: "Cereales y forrajes|Avena|€/100 kg",
  centeno: "Cereales y forrajes|Centeno|€/100 kg",
  girasol: "Cereales y forrajes|Pipa de girasol|€/100 kg",
  alfalfa: "Cereales y forrajes|Alfalfa rama|€/100 kg",
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
    out.series[id] = { l: s.l, s: sec, p, u, dudosos: num(s.dudosos) || 0 };
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
  for (const [id, serie] of Object.entries(c.series)) {
    if (!indice.series[id] || !Array.isArray(serie)) continue;
    out[id] = serie.slice(0, 80).filter(p => Array.isArray(p) && typeof p[1] === "string" && RE_SEM.test(p[1]) && num(p[2]) !== null)
      .map(p => ({ f: fechaOk(p[0]), w: p[1], a: p[2], b: num(p[3]), dud: p[4] === 1 }));
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

/* ---------- gráfico de líneas (una o varias series de la MISMA unidad) ---------- */
function graficoHist(lineas, { eje = "fecha", unidad = "", etiqueta = "Evolución del precio" } = {}) {
  const todos = lineas.flatMap(l => l.pts);
  if (todos.length < 2) return '<p class="nota">No hay suficientes sesiones en este periodo para dibujar la evolución.</p>';
  const W = 420, H = 210, mi = { l: 50, r: 12, t: 12, b: 30 };
  const xv = p => eje === "semana" ? semDe(p) : new Date(p.fecha + "T12:00:00").getTime();
  let x0 = Math.min(...todos.map(xv)), x1 = Math.max(...todos.map(xv));
  if (eje === "semana") { x0 = 1; x1 = Math.max(x1, 52); }
  const vals = todos.map(p => p.v);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.15 || Math.abs(hi) * 0.02 || 1; lo -= pad; hi += pad;
  const x = v => mi.l + (v - x0) / (x1 - x0 || 1) * (W - mi.l - mi.r);
  const y = v => mi.t + (hi - v) / (hi - lo) * (H - mi.t - mi.b);
  const ticks = [lo + pad, (lo + hi) / 2, hi - pad];
  const salto = eje === "semana" ? 4 : 35 * 86400000; // huecos largos (sin sesiones) no se unen con una línea
  const trazos = l => {
    const seg = []; let act = [];
    l.pts.forEach((p, i) => {
      if (i && xv(p) - xv(l.pts[i - 1]) > salto) { seg.push(act); act = []; }
      act.push(`${x(xv(p)).toFixed(1)},${y(p.v).toFixed(1)}`);
    });
    seg.push(act);
    return seg.map(s => s.length > 1
      ? `<polyline points="${s.join(" ")}" fill="none" stroke="${l.color}" stroke-width="${l.grosor || 2.5}" stroke-linejoin="round" stroke-linecap="round"${l.discontinua ? ' stroke-dasharray="5 4"' : ""}/>`
      : `<circle cx="${s[0].split(",")[0]}" cy="${s[0].split(",")[1]}" r="2.5" fill="${l.color}"/>`).join("");
  };
  let etX;
  if (eje === "semana") {
    etX = [1, 13, 26, 39, 52].map(s => `<text x="${x(s)}" y="${H - 9}" font-size="12" fill="var(--tenue)" text-anchor="middle">S${s}</text>`).join("");
  } else {
    const f0 = new Date(x0), f1 = new Date(x1);
    etX = `<text x="${mi.l}" y="${H - 9}" font-size="12" fill="var(--tenue)">${fechaCorta(f0.toISOString().slice(0, 10))} ${f0.getFullYear()}</text>
      <text x="${W - mi.r}" y="${H - 9}" font-size="12" fill="var(--tenue)" text-anchor="end">${fechaCorta(f1.toISOString().slice(0, 10))} ${f1.getFullYear()}</text>`;
    // Separador de año
    for (let a = f0.getFullYear() + 1; a <= f1.getFullYear(); a++) {
      const xa = x(Date.UTC(a, 0, 1));
      etX += `<line x1="${xa}" x2="${xa}" y1="${mi.t}" y2="${H - mi.b}" stroke="var(--linea)" stroke-dasharray="3 3"/>
        <text x="${xa + 4}" y="${mi.t + 11}" font-size="12" fill="var(--tenue)">${a}</text>`;
    }
  }
  const ult = lineas.map(l => l.pts.at(-1) && `<circle cx="${x(xv(l.pts.at(-1)))}" cy="${y(l.pts.at(-1).v)}" r="5" fill="${l.color}" stroke="var(--hoja)" stroke-width="2"/>`).join("");
  const leyenda = lineas.length > 1 ? `<div class="leyenda">${lineas.map(l => `<span><i class="${l.clase}"></i>${esc(l.nombre)}</span>`).join("")}</div>` : "";
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(etiqueta)}">
    ${ticks.map(v => `<line x1="${mi.l}" x2="${W - mi.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--linea)" stroke-width="1"/>
      <text x="${mi.l - 8}" y="${y(v) + 4}" text-anchor="end" font-size="13" fill="var(--tenue)" font-family="var(--cifra)">${precio(Math.round(v * 1000) / 1000, unidad)}</text>`).join("")}
    ${etX}${lineas.map(trazos).join("")}${ult}
  </svg>${leyenda}`;
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
  return { sectores, delSector, g, provincias, filtradas };
}

/** Abre el histórico ya filtrado para un producto clave de la app (desde «Comparar» o el detalle). */
function abrirHistoricoDe(clave, lonjaApp) {
  estHist.grupo = CLAVE_A_JUNTA[clave] || estHist.grupo;
  estHist.sector = (estHist.grupo || "").split("|")[0] || estHist.sector;
  estHist.provincia = "Todas"; estHist.lonja = null; estHist.ambito = "cyl";
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
    ${ser ? panelSerie(estHist.lonja, pts, g) : ""}
    ${panelLonjas(g, filtradas)}
    ${ser ? panelSemanal(pts, g) : ""}
    <p class="nota">Fuente: ${HIST.indice.fuente ? `<a href="${esc(HIST.indice.fuente)}" target="_blank" rel="noopener noreferrer">Junta de Castilla y León, precios de lonjas y mercados</a>` : "Junta de Castilla y León"}.
      Valores tal como se publican, en la unidad de cada producto. Cuando la lonja da una horquilla (mínimo–máximo) se usa el centro para gráficos y medias.
      Los valores marcados como «dudoso» se apartan mucho del resto de la serie (casi siempre, una fila desplazada en el Excel original) y no se usan en los cálculos.
      <a href="#historico-fuentes">Archivos importados</a>.</p>`;
}

function panelSerie(id, pts, g) {
  const s = HIST.indice.series[id], u = s.u, per = estHist.periodo;
  const anios = HIST.indice.anios, anioAct = per === "todo" || per === "comparar" ? anios.at(-1) : Number(per);
  const vis = enPeriodo(pts, per).filter(p => !p.dud);
  const ult = ultimo(enPeriodo(pts, per));
  let grafico;
  if (per === "comparar") {
    const lineas = anios.slice(-2).map((a, i, arr) => ({ nombre: String(a), pts: pts.filter(p => !p.dud && anioDe(p) === a),
      color: i === arr.length - 1 ? "var(--pino)" : "var(--paja)", clase: i === arr.length - 1 ? "l-act" : "l-ant", discontinua: i !== arr.length - 1 }));
    grafico = graficoHist(lineas, { eje: "semana", unidad: u, etiqueta: `Precio por semana del año, ${anios.slice(-2).join(" frente a ")}` });
  } else {
    grafico = graficoHist([{ nombre: s.p, pts: vis, color: "var(--pino)", clase: "l-act" }], { unidad: u, etiqueta: `Evolución de ${s.p} en ${lonjaH(s.l).nombre}` });
  }
  const vals = vis.map(p => p.v);
  const ia = mismaSemanaAnterior(pts, ult), mp = mismoPeriodo(pts, anioAct), t = tendencia(enPeriodo(pts, per));
  const primero = vis[0];
  const vAnio = primero && ult && primero !== ult ? txtPct(pct(ult.v, primero.v)) : null;
  const vIa = txtPct(ia ? pct(ult.v, ia.v) : null), vMp = txtPct(mp ? mp.var : null);
  const nDud = enPeriodo(pts, per).filter(p => p.dud).length;
  return `
    <section class="seccion">
      <div class="tarjeta-hist">
        <div class="cab-hist"><div><div class="etiqueta">${esc(lonjaH(s.l).nombre)} · ${esc(s.s)}</div><h3>${esc(s.p)}</h3><small>${esc(u)}</small></div>
          ${t ? `<span class="pastilla ${t.clase}" title="Últimas 4 sesiones: ${t.sube} subidas, ${t.baja} bajadas">${t.txt}</span>` : ""}</div>
        <div class="datos-det cuatro">
          <div><span class="etiqueta">Último</span><b class="num">${ult ? valorTxt(ult, u) : "—"}</b><small>${ult ? (ult.sinFecha ? "semana " + semDe(ult) + " de " + anioDe(ult) : fechaLarga(ult.fecha)) : ""}</small></div>
          <div><span class="etiqueta">Media${per === "comparar" ? " " + anios.join("–") : ""}</span><b class="num">${vals.length ? precio(Math.round(media(vals) * 1000) / 1000, u) : "—"}</b><small>${vals.length} sesiones</small></div>
          <div><span class="etiqueta">Mín · máx</span><b class="num chico">${vals.length ? precio(Math.min(...vals), u) + " · " + precio(Math.max(...vals), u) : "—"}</b><small>${vAnio ? `<span class="var ${vAnio.clase}">${vAnio.txt}</span> en el periodo` : ""}</small></div>
          <div><span class="etiqueta">Interanual</span><b class="num chico var ${vIa.clase}">${vIa.txt}</b><small>${ia ? `vs ${valorTxt(ia, u)} (sem. ${semDe(ia)} de ${anioDe(ia)})` : "sin dato del año anterior"}</small></div>
        </div>
        ${mp ? `<p class="mismo-periodo">Media de ${anioAct} entre las semanas ${mp.desde} y ${mp.hasta}: <b class="num">${precio(Math.round(mp.act * 1000) / 1000, u)}</b>, frente a <b class="num">${precio(Math.round(mp.ant * 1000) / 1000, u)}</b> en las mismas ${mp.semanas} semanas de ${anioAct - 1} (<span class="var ${vMp.clase}">${vMp.txt}</span>).</p>` : ""}
        <div class="grafico">${grafico}</div>
        ${nDud ? `<p class="nota">${nDud} valor${nDud === 1 ? "" : "es"} dudoso${nDud === 1 ? "" : "s"} fuera del gráfico (ver tabla semanal).</p>` : ""}
      </div>
    </section>`;
}

function panelLonjas(g, filtradas) {
  const per = estHist.periodo;
  const filas = filtradas.map(id => {
    const pts = puntosSerie(id), u = ultimo(enPeriodo(pts, per));
    return { id, s: HIST.indice.series[id], u, h4: hace4(pts, u), ia: mismaSemanaAnterior(pts, u) };
  }).filter(f => f.u).sort((a, b) => b.u.v - a.u.v);
  if (!filas.length) return "";
  const max = Math.max(...filas.map(f => f.u.v));
  return `
    <section class="seccion">
      <div class="titulo-seccion"><h2>Entre lonjas</h2><span>${esc(g.producto)} · ${esc(g.unidad)}</span></div>
      <div class="comparativa">${filas.map(f => {
        const v4 = txtPct(f.h4 ? pct(f.u.v, f.h4.v) : null), via = txtPct(f.ia ? pct(f.u.v, f.ia.v) : null);
        return `<div class="cmp-fila" role="button" tabindex="0" data-h-lonja="${esc(f.id)}"${f.id === estHist.lonja ? ' aria-current="true"' : ""}>
          <span><b>${esc(lonjaH(f.s.l).nombre.replace(/^Lonja de(l)? /, ""))}</b><br><small class="etiqueta">${f.u.sinFecha ? "sem. " + semDe(f.u) : fechaCorta(f.u.fecha)} ${anioDe(f.u)}</small></span>
          <div class="barra-cmp" aria-hidden="true"><i class="${f.id === estHist.lonja ? "mejor" : ""}" data-w="${Math.round(Math.max(4, f.u.v / max * 100))}"></i></div>
          <span class="cmp-valor num">${valorTxt(f.u, g.unidad)}<small class="var ${v4.clase}">${v4.txt} 4 sem.</small></span>
          <span class="q">${esc(lonjaH(f.s.l).provincia)} · interanual <span class="var ${via.clase}">${via.txt}</span></span>
        </div>`;
      }).join("")}</div>
      <p class="nota">Último precio de cada lonja en el periodo elegido. Cada lonja cotiza en sus propias condiciones, así que las diferencias no siempre son de mercado.</p>
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
  caja.innerHTML = `<div class="etiqueta">Histórico oficial ${HIST.indice.anios[0]}–${HIST.indice.anios.at(-1)} · Junta de CyL</div>
    <p class="nota">${esc(s.p)} · ${esc(s.u)} (unidad de la Junta). Último: <b class="num">${valorTxt(u, s.u)}</b> · interanual <span class="var ${via.clase}">${via.txt}</span></p>
    <div class="grafico">${graficoHist([{ nombre: s.p, pts, color: "var(--pino)", clase: "l-act" }], { unidad: s.u })}</div>
    <button class="chip auto" type="button" data-h-abrir="${esc(f.clave)}" data-h-lonja-app="${esc(f.lonja.id)}">Ver en Histórico</button>`;
}

/* ---------- eventos ---------- */
document.addEventListener("click", e => {
  const t = e.target;
  const q = sel => t.closest(sel);
  let el;
  if ((el = q("[data-h-ambito]"))) { estHist.ambito = el.dataset.hAmbito; estHist.lonja = null; return router(); }
  if ((el = q("[data-h-sector]"))) { estHist.sector = el.dataset.hSector; estHist.grupo = null; estHist.lonja = null; return router(); }
  if ((el = q("[data-h-provincia]"))) { estHist.provincia = el.dataset.hProvincia; estHist.lonja = null; return router(); }
  if ((el = q("[data-h-periodo]"))) { estHist.periodo = el.dataset.hPeriodo; return router(); }
  if ((el = q("[data-h-lonja]"))) { estHist.lonja = el.dataset.hLonja; router(); return document.getElementById("h-lonja")?.scrollIntoView({ block: "center" }); }
  if (q("[data-h-todas]")) { estHist.todas = !estHist.todas; return router(); }
  if (q("[data-h-reintentar]")) { HIST.error = null; return router(); }
  if ((el = q("[data-h-abrir]"))) { cerrarDetalle(); return abrirHistoricoDe(el.dataset.hAbrir, el.dataset.hLonjaApp || null); }
});
document.addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-h-lonja]")) { e.preventDefault(); e.target.click(); }
});
document.addEventListener("change", e => {
  if (e.target.id === "h-producto") { estHist.grupo = e.target.value; estHist.lonja = null; estHist.provincia = "Todas"; router(); }
  if (e.target.id === "h-lonja") { estHist.lonja = e.target.value; router(); }
});

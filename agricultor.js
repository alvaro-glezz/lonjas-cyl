"use strict";
/* ============================================================================================
   Herramientas para el agricultor: avisos de precio, titulares y resumen de la semana, calculadora de venta
   y letra grande. Todo se guarda en este teléfono (la app no tiene cuentas ni servidor).
   Usa utilidades de app.js ($, esc, precio, fechaCorta, fechaLarga, variacion, buscarFila, todasLasFilas,
   PRODUCTOS_CLAVE, RE_ID, DATOS, router, ir, abrirDetalle).
   ============================================================================================ */
const CACHE_AJUSTES = "lonjas-ajustes";          // la lee el service worker para avisar en segundo plano
const MAX_AVISOS = 30;
const ZOOM_LETRA = 1.18;
const leerLS = (k, def) => { try { const v = JSON.parse(localStorage.getItem(k) || "null"); return v ?? def; } catch { return def; } };
const guardarLS = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} };
const nombreClave = c => (PRODUCTOS_CLAVE.find(p => p[0] === c) || [c, c])[1];
const corto = l => l.nombre.replace(/^Lonja de(l)? /, "");
const euros = v => v.toLocaleString("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
/** Precios de sesiones recientes (lo de hace más de 3 semanas no se compara con lo de hoy). */
const reciente = l => l.fecha && diasDesde(l.fecha) <= 21 && l.estado !== "suspendida";

/* ---------- ajustes (letra grande, resumen de los lunes) ---------- */
function leerAjustes() {
  const a = leerLS("lonjas-ajustes", {});
  return { letraGrande: a.letraGrande === true, resumenLunes: a.resumenLunes === true };
}
function guardarAjustes(a) { guardarLS("lonjas-ajustes", a); espejarParaSW(); }
function aplicarLetra() {
  const g = leerAjustes().letraGrande;
  document.documentElement.classList.toggle("letra-grande", g);
  const b = $("#letra");
  if (b) { b.setAttribute("aria-pressed", String(g)); b.title = b.ariaLabel = g ? "Letra normal" : "Letra más grande"; }
}
/** Factor de ampliación actual (lo usa el histórico para dibujar los gráficos a su tamaño). */
function factorLetra() { return document.documentElement.classList.contains("letra-grande") ? ZOOM_LETRA : 1; }

/* ---------- avisos de precio ---------- */
function leerAvisos() {
  const l = leerLS("lonjas-avisos", []);
  return (Array.isArray(l) ? l : []).filter(a => a && typeof a.id === "string" && /^a\d{6,16}$/.test(a.id) && typeof a.fila === "string" && RE_ID.test(a.fila)
    && (a.tipo === "sube" || a.tipo === "baja") && typeof a.umbral === "number" && Number.isFinite(a.umbral) && a.umbral > 0)
    .map(a => ({ id: a.id, fila: a.fila, tipo: a.tipo, umbral: a.umbral, notificado: a.notificado === true,
      sesion: typeof a.sesion === "string" && /^\d{4}-\d{2}-\d{2}$/.test(a.sesion) ? a.sesion : null }))
    .slice(0, MAX_AVISOS);
}
function guardarAvisos(l) { guardarLS("lonjas-avisos", l.slice(0, MAX_AVISOS)); espejarParaSW(); }
/** Copia de avisos y ajustes donde el service worker pueda leerlos (no tiene acceso a localStorage). */
function espejarParaSW() {
  if (!("caches" in window)) return;
  const cuerpo = JSON.stringify({ avisos: leerAvisos(), ajustes: leerAjustes() });
  caches.open(CACHE_AJUSTES).then(c => c.put("ajustes/avisos.json", new Response(cuerpo, { headers: { "Content-Type": "application/json" } }))).catch(() => {});
}
/** Si el service worker ya avisó en segundo plano, no se repite al abrir la app. */
async function traerDelSW() {
  try {
    if (!("caches" in window)) return;
    const r = await (await caches.open(CACHE_AJUSTES)).match("ajustes/avisos.json");
    if (!r) return;
    const sw = await r.json(), locales = leerAvisos();
    let cambio = false;
    for (const a of locales) {
      const b = (sw.avisos || []).find(x => x && x.id === a.id);
      if (b && typeof b.sesion === "string" && /^\d{4}-\d{2}-\d{2}$/.test(b.sesion) && (!a.sesion || b.sesion > a.sesion)) {
        a.sesion = b.sesion; a.notificado = b.notificado === true; cambio = true;
      }
    }
    if (cambio) guardarLS("lonjas-avisos", locales);
  } catch {}
}
function estadoAviso(a) {
  const f = buscarFila(a.fila);
  if (!f) return { f: null, cumple: false };
  return { f, cumple: f.act != null && (a.tipo === "sube" ? f.act >= a.umbral : f.act <= a.umbral) };
}
const textoCondicion = (a, u) => `${a.tipo === "sube" ? "suba a" : "baje a"} ${precio(a.umbral, u)} ${u} ${a.tipo === "sube" ? "o más" : "o menos"}`;
function puedeNotificar() { return "Notification" in window && Notification.permission === "granted"; }
async function notificar(titulo, cuerpo, etiqueta) {
  try {
    const reg = "serviceWorker" in navigator ? await navigator.serviceWorker.getRegistration() : null;
    const opts = { body: cuerpo, tag: etiqueta, icon: "icons/icono-192.png", badge: "icons/icono-192.png", data: { url: "./#favoritos" } };
    if (reg) await reg.showNotification(titulo, opts); else new Notification(titulo, opts);
  } catch {}
}
/** Se llama cada vez que llegan precios. Un aviso suena al CRUZAR el precio (no cada semana mientras siga
    por encima); se rearma solo cuando el precio vuelve al otro lado. */
async function comprobarAvisos() {
  await traerDelSW();
  const avisos = leerAvisos();
  const nuevos = [];
  let cambio = false;
  for (const a of avisos) {
    const { f, cumple } = estadoAviso(a);
    if (!f) continue;
    if (cumple && !a.notificado) { a.notificado = true; nuevos.push({ a, f }); cambio = true; }
    else if (!cumple && a.notificado) { a.notificado = false; cambio = true; }
    if (a.sesion !== f.lonja.fecha) { a.sesion = f.lonja.fecha; cambio = true; }
  }
  if (cambio) guardarAvisos(avisos);
  if (!nuevos.length) return;
  if (puedeNotificar() && !DATOS.__sinRed) {
    for (const { a, f } of nuevos) {
      await notificar(`${f.producto} · ${corto(f.lonja)}: ${precio(f.act, f.unidad)} ${f.unidad}`,
        `Se cumple tu aviso: que ${textoCondicion(a, f.unidad)}. Sesión del ${fechaLarga(f.lonja.fecha)}.`, a.id);
    }
  }
  if (location.hash === "" || location.hash === "#hoy" || location.hash === "#favoritos") router();
}
async function pedirPermisoYProgramar() {
  if (!("Notification" in window)) return "sin-soporte";
  let p = Notification.permission;
  if (p === "default") { try { p = await Notification.requestPermission(); } catch { p = "denied"; } }
  if (p === "granted") {
    // Android con la app instalada: el teléfono la despierta de vez en cuando para comprobar avisos con la app cerrada
    try {
      // getRegistration (no «ready»): si no hay service worker, «ready» no termina nunca
      const reg = await navigator.serviceWorker?.getRegistration();
      if (reg && "periodicSync" in reg) {
        const st = await navigator.permissions.query({ name: "periodic-background-sync" });
        if (st.state === "granted") await reg.periodicSync.register("comprobar-avisos", { minInterval: 6 * 3600 * 1000 });
      }
    } catch {}
  }
  return p;
}
function textoPermiso() {
  if (!("Notification" in window)) return "Este navegador no permite notificaciones: verás los avisos cumplidos al abrir la app.";
  if (Notification.permission === "denied") return "Las notificaciones de esta app están bloqueadas en el teléfono: verás los avisos al abrir la app (puedes activarlas en los ajustes del navegador).";
  if (Notification.permission === "default") return "Al crear el primer aviso, el teléfono te preguntará si permites notificaciones.";
  return "Te llegará una notificación cuando se cumpla, al actualizarse los precios. Con la app instalada en Android también con la app cerrada; en iPhone, al abrirla.";
}

/** Bloque de avisos dentro de la hoja de detalle de un producto. */
function pintarAvisoDetalle(f) {
  const caja = document.getElementById("det-aviso");
  if (!caja || !f) return;
  const propios = leerAvisos().filter(a => a.fila === f.id);
  const base = f.act ?? f.ant;
  caja.innerHTML = `<div class="etiqueta">Avisarme del precio</div>
    ${propios.map(a => { const { cumple } = estadoAviso(a); return `<div class="aviso-linea"><span>🔔 Cuando ${esc(textoCondicion(a, f.unidad))}${cumple ? ' · <b class="var s">cumplido</b>' : ""}</span>
      <button class="chip" type="button" data-aviso-borrar="${esc(a.id)}" aria-label="Borrar aviso">Quitar</button></div>`; }).join("")}
    <form class="aviso-form" data-aviso-fila="${esc(f.id)}">
      <label class="campo"><span class="etiqueta">Cuando</span><select name="tipo"><option value="sube">suba a</option><option value="baja">baje a</option></select></label>
      <label class="campo"><span class="etiqueta">Precio (${esc(f.unidad || "€")})</span><input name="umbral" type="number" inputmode="decimal" step="any" min="0" required value="${base != null ? esc(String(base)) : ""}"></label>
      <button class="chip boton" type="submit">Crear aviso</button>
    </form>
    <p class="nota">${esc(textoPermiso())}</p>
    ${f.clave ? `<button class="chip auto" type="button" data-calc="${esc(f.clave)}">Calcular cuánto me pagan</button>` : ""}`;
}

/** Sección «Mis avisos» (en Favoritos). */
function seccionAvisos() {
  const avisos = leerAvisos();
  if (!avisos.length) {
    return `<section class="seccion"><div class="titulo-seccion"><h2>Mis avisos</h2><span>0</span></div>
      <div class="vacio"><b>Sin avisos de precio</b>Abre cualquier producto y pon el precio al que quieres vender o comprar: la app te avisa cuando la lonja llegue a él.</div></section>`;
  }
  return `<section class="seccion"><div class="titulo-seccion"><h2>Mis avisos</h2><span>${avisos.length}</span></div>
    <div class="tablilla">${avisos.map(a => {
      const { f, cumple } = estadoAviso(a);
      if (!f) return `<div class="aviso-fila"><span class="prod"><b>Producto no disponible</b><small>La lonja ya no publica este precio</small></span><span></span><button class="chip" type="button" data-aviso-borrar="${esc(a.id)}">Quitar</button></div>`;
      return `<div class="aviso-fila${cumple ? " cumplido" : ""}">
        <span class="prod" role="button" tabindex="0" data-fila="${esc(f.id)}"><b>${esc(f.producto)}</b><small>${esc(corto(f.lonja))} · cuando ${esc(textoCondicion(a, f.unidad))}</small></span>
        <span class="estado-aviso">${cumple ? '<span class="pastilla p-sube">✓ Cumplido</span>' : `<span class="pastilla p-igual">Ahora ${precio(f.act, f.unidad)}</span>`}</span>
        <button class="chip" type="button" data-aviso-borrar="${esc(a.id)}" aria-label="Quitar aviso de ${esc(f.producto)}">Quitar</button>
      </div>`;
    }).join("")}</div>
    <p class="nota">${esc(textoPermiso())}</p></section>`;
}
/** Avisos cumplidos, arriba del todo en «Hoy». */
function bloqueAvisosCumplidos() {
  const c = leerAvisos().map(a => ({ a, ...estadoAviso(a) })).filter(x => x.cumple);
  if (!c.length) return "";
  return `<section class="seccion"><div class="avisos-cumplidos"><b>🔔 ${c.length === 1 ? "Se cumple uno de tus avisos" : `Se cumplen ${c.length} avisos`}</b>
    ${c.slice(0, 4).map(({ a, f }) => `<button type="button" class="linea-aviso" data-fila="${esc(f.id)}">${esc(f.producto)} en ${esc(corto(f.lonja))}: <b class="num">${precio(f.act, f.unidad)}</b> ${esc(f.unidad)} <small>(tu aviso: ${a.tipo === "sube" ? "≥" : "≤"} ${precio(a.umbral, f.unidad)})</small></button>`).join("")}
    <button class="chip auto" type="button" data-ir="favoritos">Ver mis avisos</button></div></section>`;
}

/* ---------- titulares y resumen de la semana ---------- */
const ORDINAL = ["", "", "segunda", "tercera", "cuarta", "quinta", "sexta"];
function rachaDe(id) {
  const s = (DATOS.historial?.[id] || []).filter(p => p[1] != null);
  let n = 0, dir = 0;
  for (let i = s.length - 1; i > 0; i--) {
    const d = Math.sign(s[i][1] - s[i - 1][1]);
    if (!d || (dir && d !== dir)) break;
    dir = d; n++;
  }
  return { n, dir };
}
function generarTitulares() {
  const filas = todasLasFilas().filter(f => f.clave && f.act != null && reciente(f.lonja) && PRODUCTOS_CLAVE.some(p => p[0] === f.clave));
  const tit = [];
  // 1) Rachas: tres o más semanas seguidas en la misma dirección
  for (const f of filas) {
    const r = rachaDe(f.id);
    if (r.n >= 2) tit.push({ peso: 10 + r.n, clave: f.clave, txt: `${nombreClave(f.clave)} ${r.dir > 0 ? "sube" : "baja"} por ${ORDINAL[r.n] ? ORDINAL[r.n] + " semana seguida" : r.n + " semanas seguidas"} en ${corto(f.lonja)}`, valor: `${precio(f.act, f.unidad)} ${f.unidad}`, dir: r.dir, fila: f.id });
  }
  // 2) Movimientos fuertes de la última sesión (2 % o más)
  for (const f of filas) {
    if (f.ant == null || !f.ant) continue;
    const p = (f.act - f.ant) / f.ant * 100;
    if (Math.abs(p) >= 2) tit.push({ peso: Math.min(9, Math.abs(p)), clave: f.clave, txt: `${nombreClave(f.clave)} en ${corto(f.lonja)}: ${p > 0 ? "+" : "−"}${Math.abs(p).toLocaleString("es-ES", { maximumFractionDigits: 1 })} % en una semana`, valor: `${precio(f.ant, f.unidad)} → ${precio(f.act, f.unidad)} ${f.unidad}`, dir: Math.sign(p), fila: f.id });
  }
  // 3) Quién paga más (con 3 lonjas o más que cotizan en la misma unidad)
  for (const [c] of PRODUCTOS_CLAVE) {
    const v = filas.filter(f => f.clave === c);
    const u = v[0]?.unidad, mismas = v.filter(f => f.unidad === u);
    if (mismas.length < 3) continue;
    const mejor = mismas.reduce((m, f) => f.act > m.act ? f : m), med = mismas.reduce((s, f) => s + f.act, 0) / mismas.length;
    const dif = mejor.act - med;
    if (dif / med < 0.01) continue;
    tit.push({ peso: 8, clave: c, txt: `${corto(mejor.lonja)} paga el ${nombreClave(c).toLowerCase()} más caro`, valor: `${precio(mejor.act, u)} ${u}, ${precio(Math.round(dif * 100) / 100, u)} sobre la media de ${mismas.length} lonjas`, dir: 0, fila: mejor.id });
  }
  // Un titular por producto (el de más peso) y como mucho 5
  const vistos = new Set();
  return tit.sort((a, b) => b.peso - a.peso).filter(t => !vistos.has(t.clave + t.dir) && vistos.add(t.clave + t.dir)).slice(0, 5);
}
function resumenSemana() {
  const filas = todasLasFilas().filter(f => reciente(f.lonja) && f.act != null && f.ant != null && f.ant > 0);
  const cambios = filas.map(f => ({ f, p: (f.act - f.ant) / f.ant * 100 })).filter(x => x.p !== 0);
  const fechas = DATOS.lonjas.filter(reciente).map(l => l.fecha).sort();
  return {
    desde: fechas[0], hasta: fechas.at(-1), total: filas.length,
    suben: cambios.filter(x => x.p > 0).length, bajan: cambios.filter(x => x.p < 0).length,
    subidas: cambios.filter(x => x.p > 0).sort((a, b) => b.p - a.p).slice(0, 3),
    bajadas: cambios.filter(x => x.p < 0).sort((a, b) => a.p - b.p).slice(0, 3),
  };
}
const pctTxt = p => `${p > 0 ? "+" : "−"}${Math.abs(p).toLocaleString("es-ES", { maximumFractionDigits: 1 })} %`;
function seccionTitulares() {
  const t = generarTitulares(), r = resumenSemana();
  if (!r.total) return "";
  const aj = leerAjustes();
  const linea = x => `<button type="button" class="mov" data-fila="${esc(x.f.id)}"><span>${esc(x.f.producto)} <small>${esc(corto(x.f.lonja))}</small></span><b class="var ${x.p > 0 ? "s" : "b"}">${pctTxt(x.p)}</b></button>`;
  return `<section class="seccion">
    <div class="titulo-seccion"><h2>Resumen de la semana</h2><span>${r.desde ? `${fechaCorta(r.desde)} – ${fechaCorta(r.hasta)}` : ""}</span></div>
    <div class="resumen">
      ${t.length ? `<ul class="titulares">${t.map(x => `<li><button type="button" data-fila="${esc(x.fila)}"><span class="flecha ${x.dir > 0 ? "s" : x.dir < 0 ? "b" : "i"}" aria-hidden="true">${x.dir > 0 ? "▲" : x.dir < 0 ? "▼" : "★"}</span><span><b>${esc(x.txt)}</b><small>${esc(x.valor)}</small></span></button></li>`).join("")}</ul>` : ""}
      <p class="balance"><span class="pastilla p-sube">▲ ${r.suben} suben</span><span class="pastilla p-baja">▼ ${r.bajan} bajan</span><span class="pastilla p-igual">= ${r.total - r.suben - r.bajan} igual</span></p>
      ${r.subidas.length || r.bajadas.length ? `<div class="movs"><div><span class="etiqueta">Más suben</span>${r.subidas.map(linea).join("") || '<p class="nota">—</p>'}</div><div><span class="etiqueta">Más bajan</span>${r.bajadas.map(linea).join("") || '<p class="nota">—</p>'}</div></div>` : ""}
      <div class="graf-acciones">
        <button class="chip" type="button" data-compartir-resumen>⇪ Compartir resumen</button>
        ${"Notification" in window ? `<button class="chip" type="button" data-resumen-lunes aria-pressed="${aj.resumenLunes}">${aj.resumenLunes ? "🔔 Aviso de los lunes activado" : "🔔 Avisarme los lunes"}</button>` : ""}
        <button class="chip" type="button" data-ir="calculadora">🧮 Calculadora de venta</button>
      </div>
    </div></section>`;
}
function textoResumen() {
  const t = generarTitulares(), r = resumenSemana();
  const l = [`Lonjas CyL · semana del ${fechaCorta(r.desde)} al ${fechaCorta(r.hasta)}`, ""];
  t.forEach(x => l.push(`• ${x.txt} (${x.valor})`));
  l.push("", `Suben ${r.suben} precios, bajan ${r.bajan}.`);
  if (r.subidas.length) l.push("Más suben: " + r.subidas.map(x => `${x.f.producto} ${corto(x.f.lonja)} ${pctTxt(x.p)}`).join("; "));
  if (r.bajadas.length) l.push("Más bajan: " + r.bajadas.map(x => `${x.f.producto} ${corto(x.f.lonja)} ${pctTxt(x.p)}`).join("; "));
  return l.join("\n");
}
async function compartirResumen(boton) {
  const texto = textoResumen(), url = location.origin + location.pathname;
  try {
    if (navigator.share) { await navigator.share({ title: "Resumen de la semana · Lonjas CyL", text: texto, url }); return; }
  } catch (e) { if (e && e.name === "AbortError") return; }
  try { await navigator.clipboard.writeText(texto + "\n" + url); boton.textContent = "✓ Copiado: pégalo en WhatsApp"; }
  catch { boton.textContent = "No se pudo copiar"; }
}

/* ---------- calculadora de venta ---------- */
const UNIDAD_CALC = [[/€\/t/, "toneladas", "t"], [/€\/kg/, "kilos", "kg"], [/€\/ud/, "cabezas", "ud"], [/€\/litro/, "litros", "l"]];
function leerCalc() {
  const c = leerLS("lonjas-calculadora", {});
  const portes = {};
  for (const [k, v] of Object.entries(c.portes && typeof c.portes === "object" ? c.portes : {}).slice(0, 50)) {
    if (RE_ID.test(k) && typeof v === "number" && v >= 0 && v < 1e5) portes[k] = v;
  }
  return { clave: typeof c.clave === "string" && PRODUCTOS_CLAVE.some(p => p[0] === c.clave) ? c.clave : "trigo",
    cantidad: typeof c.cantidad === "number" && c.cantidad > 0 && c.cantidad < 1e7 ? c.cantidad : 25, portes };
}
function filasCalc(clave) {
  const v = todasLasFilas().filter(f => f.clave === clave && f.act != null && reciente(f.lonja));
  const cuenta = {}; v.forEach(f => { cuenta[f.unidad] = (cuenta[f.unidad] || 0) + 1; });
  const unidad = Object.keys(cuenta).sort((a, b) => cuenta[b] - cuenta[a])[0] || "";
  return { unidad, filas: v.filter(f => f.unidad === unidad), otras: v.filter(f => f.unidad !== unidad) };
}
function vistaCalculadora() {
  const c = leerCalc();
  const disponibles = PRODUCTOS_CLAVE.filter(([k]) => filasCalc(k).filas.length);
  if (!disponibles.some(([k]) => k === c.clave) && disponibles.length) c.clave = disponibles[0][0];
  const { unidad, filas, otras } = filasCalc(c.clave);
  const [, nombreCant, abrev] = UNIDAD_CALC.find(([re]) => re.test(unidad)) || [null, "unidades", "ud"];
  return `<section class="seccion">
    <div class="cab-lonja"><button class="volver" type="button" data-ir="hoy">‹ Volver</button><h2>Calculadora de venta</h2>
      <div class="meta">Cuánto te pagaría cada lonja por tu partida, con su último precio y descontando el porte.</div></div>
    <div class="panel-filtros calc-form">
      <label class="campo"><span class="etiqueta">Producto</span><select id="calc-clave">${disponibles.map(([k, n]) => `<option value="${esc(k)}"${k === c.clave ? " selected" : ""}>${esc(n)}</option>`).join("")}</select></label>
      <label class="campo"><span class="etiqueta">Cantidad (${esc(nombreCant)})</span><input id="calc-cantidad" type="number" inputmode="decimal" min="0" step="any" value="${esc(String(c.cantidad))}"></label>
    </div>
    ${filas.length ? `<div class="calc-tabla" role="table" aria-label="Importe por lonja">
      <div class="th" role="row"><span role="columnheader">Lonja</span><span role="columnheader">Precio</span><span role="columnheader">Porte (${esc(unidad)})</span><span role="columnheader">Te pagan</span></div>
      ${filas.map(f => `<div class="tr" role="row" data-calc-fila="${esc(f.id)}" data-precio="${f.act}">
        <span role="cell"><b>${esc(corto(f.lonja))}</b><small>${esc(f.producto)} · ${fechaCorta(f.lonja.fecha)}</small></span>
        <span role="cell" class="num">${precio(f.act, f.unidad)}</span>
        <span role="cell"><input class="porte" type="number" inputmode="decimal" min="0" step="any" aria-label="Porte hasta ${esc(corto(f.lonja))}" data-porte="${esc(f.lonja.id)}" value="${c.portes[f.lonja.id] ?? ""}" placeholder="0"></span>
        <span role="cell" class="total"><b class="num" data-total></b><small data-dif></small></span>
      </div>`).join("")}</div>
      <p class="nota">Lo que te pagan = (precio − porte) × cantidad. Son precios orientativos de cada lonja en sus propias condiciones (calidad, punto de entrega): sirven para comparar, no son una oferta.${otras.length ? ` No se incluyen ${otras.length} precio${otras.length === 1 ? "" : "s"} en otra unidad.` : ""}</p>`
      : '<div class="vacio"><b>Sin precios recientes</b>Ninguna lonja ha cotizado este producto en las últimas tres semanas.</div>'}
  </section>`;
}
/** Recalcula los importes sin redibujar la pantalla (así no se pierde lo que se está escribiendo). */
function recalcular() {
  const cant = Number($("#calc-cantidad")?.value) || 0;
  const filas = [...document.querySelectorAll("[data-calc-fila]")].map(tr => {
    const porte = Number(tr.querySelector("[data-porte]").value) || 0;
    return { tr, neto: Number(tr.dataset.precio) - porte };
  });
  if (!filas.length) return;
  const mejor = Math.max(...filas.map(x => x.neto * cant));
  for (const { tr, neto } of filas) {
    const total = neto * cant;
    tr.querySelector("[data-total]").textContent = cant ? euros(total) : "—";
    const d = tr.querySelector("[data-dif]");
    d.textContent = !cant ? "" : total === mejor ? "la que más paga" : `${euros(mejor - total)} menos que la mejor`;
    tr.classList.toggle("mejor", !!cant && total === mejor);
  }
  const grupo = [...document.querySelector(".calc-tabla").children].slice(1).sort((a, b) =>
    (Number(b.dataset.precio) - (Number(b.querySelector("[data-porte]").value) || 0)) - (Number(a.dataset.precio) - (Number(a.querySelector("[data-porte]").value) || 0)));
  if (document.activeElement?.closest?.(".calc-tabla") == null) grupo.forEach(tr => tr.parentNode.appendChild(tr));
}
function guardarCalcDesdePantalla() {
  const c = leerCalc();
  c.clave = $("#calc-clave")?.value || c.clave;
  const q = Number($("#calc-cantidad")?.value); if (q > 0 && q < 1e7) c.cantidad = q;
  document.querySelectorAll("[data-porte]").forEach(i => { const v = Number(i.value); if (i.value === "") delete c.portes[i.dataset.porte]; else if (v >= 0 && v < 1e5) c.portes[i.dataset.porte] = v; });
  guardarLS("lonjas-calculadora", c);
}

/* ---------- enganches con app.js ---------- */
/** Lo llama app.js cada vez que llegan precios nuevos (o la copia sin conexión). */
function trasCargarDatos() { comprobarAvisos(); }
/** Lo llama el router después de pintar cada pantalla. */
function trasPintar(h) { if (h === "calculadora") recalcular(); }

document.addEventListener("submit", async e => {
  const form = e.target.closest?.("[data-aviso-fila]");
  if (!form) return;
  e.preventDefault();
  const umbral = Number(form.umbral.value), fila = form.dataset.avisoFila;
  if (!(umbral > 0) || !RE_ID.test(fila)) { form.umbral.focus(); return; }
  const avisos = leerAvisos();
  if (avisos.length >= MAX_AVISOS) { form.insertAdjacentHTML("afterend", `<p class="nota err">Como mucho ${MAX_AVISOS} avisos: quita alguno antes.</p>`); return; }
  const f = buscarFila(fila);
  const a = { id: "a" + Date.now(), fila, tipo: form.tipo.value === "baja" ? "baja" : "sube", umbral, notificado: false, sesion: f ? f.lonja.fecha : null };
  // Si ya se cumple al crearlo no se notifica (se ve en pantalla); sonará cuando vuelva a cruzar el precio
  if (f && estadoAviso(a).cumple) a.notificado = true;
  avisos.push(a); guardarAvisos(avisos);
  if (f) abrirDetalle(f.id);
  router();
  // El permiso de notificaciones se pide después de mostrar el aviso creado (sin bloquear la pantalla)
  pedirPermisoYProgramar().then(() => { if (f && !$("#velo").hidden) pintarAvisoDetalle(f); });
});
document.addEventListener("click", e => {
  const t = e.target;
  let el;
  if ((el = t.closest("[data-aviso-borrar]"))) {
    e.stopPropagation();
    guardarAvisos(leerAvisos().filter(a => a.id !== el.dataset.avisoBorrar));
    const det = document.getElementById("det-aviso");
    if (det) pintarAvisoDetalle(buscarFila(det.querySelector("[data-aviso-fila]")?.dataset.avisoFila));
    return router();
  }
  if ((el = t.closest("[data-calc]"))) {
    const c = leerCalc(); c.clave = el.dataset.calc; guardarLS("lonjas-calculadora", c);
    if (!$("#velo").hidden) cerrarDetalle();
    return ir("calculadora");
  }
  if ((el = t.closest("[data-compartir-resumen]"))) { compartirResumen(el); return; }
  if ((el = t.closest("[data-resumen-lunes]"))) {
    const aj = leerAjustes(); aj.resumenLunes = !aj.resumenLunes; guardarAjustes(aj);
    if (aj.resumenLunes) pedirPermisoYProgramar().then(() => router()); else router();
    return;
  }
  if (t.closest("#letra")) {
    const aj = leerAjustes(); aj.letraGrande = !aj.letraGrande; guardarAjustes(aj);
    aplicarLetra(); return router();
  }
});
document.addEventListener("input", e => {
  if (e.target.id === "calc-cantidad" || e.target.matches?.("[data-porte]")) { guardarCalcDesdePantalla(); recalcular(); }
});
document.addEventListener("change", e => {
  if (e.target.id === "calc-clave") { guardarCalcDesdePantalla(); router(); }
  if (e.target.matches?.("[data-porte]")) recalcular();
});
aplicarLetra();
espejarParaSW();

"use strict";
/* Herramientas para decidir (sin servidor; lo que escribe el agricultor se queda en su teléfono):
   1. ¿Me están pagando bien?  (#oferta)       su oferta frente a las lonjas de esta semana
   2. Mi explotación           (#explotacion)  lo que vale lo que tiene almacenado y cuánto ha cambiado
   3. ¿Caro o barato?          (#termometro)   el precio de hoy frente a todas las semanas del histórico oficial
   4. Diferencias entre lonjas (en Comparar)   cuánto suele pagar de más una lonja que otra
   Usa funciones de app.js, agricultor.js (filasCalc, leerLS…) e historico.js (series oficiales). */

const MAX_PARTIDAS = 30;
const VENTANA_DIAS = 730;          // «¿caro o barato?» y diferencias: como mucho los dos últimos años
const MIN_SEMANAS_TERMO = 26;      // con menos de medio año de datos no se da veredicto
const MIN_SEMANAS_DIF = 12;

const unidadCant = u => UNIDAD_CALC.find(([re]) => re.test(u)) || [null, "unidades", "ud"];
const redondeoU = (v, u) => /€\/t/.test(u) ? Math.round(v) : Math.round(v * 1000) / 1000;
const conSigno = (v, u) => `${v > 0 ? "+" : v < 0 ? "−" : "±"}${precio(Math.abs(redondeoU(v, u)), u)}`;
const mediaDe = v => v.reduce((s, x) => s + x, 0) / v.length;
/** «5 €/t menos que» / «3 €/t más que» / «lo mismo que». */
const relTxt = (d, u) => { const r = redondeoU(d, u); return r === 0 ? "lo mismo que" : `${precio(Math.abs(r), u)} ${u} ${r > 0 ? "más" : "menos"} que`; };
const euroSigno = v => `${v > 0 ? "+" : v < 0 ? "−" : ""}${euros(Math.abs(v))}`;

/* =====================================================================================
   1. ¿Me están pagando bien?
   ===================================================================================== */
function leerOferta() {
  const o = leerLS("lonjas-oferta", {});
  return { clave: typeof o.clave === "string" && PRODUCTOS_CLAVE.some(p => p[0] === o.clave) ? o.clave : "trigo",
    precio: typeof o.precio === "number" && o.precio > 0 && o.precio < 1e6 ? o.precio : null,
    cantidad: typeof o.cantidad === "number" && o.cantidad > 0 && o.cantidad < 1e7 ? o.cantidad : null };
}
function vistaOferta() {
  const o = leerOferta();
  const disp = PRODUCTOS_CLAVE.filter(([k]) => filasCalc(k).filas.length);
  if (!disp.some(([k]) => k === o.clave) && disp.length) o.clave = disp[0][0];
  const { unidad, filas } = filasCalc(o.clave);
  const [, nombreCant] = unidadCant(unidad);
  const med = filas.length ? redondeoU(mediaDe(filas.map(f => f.act)), unidad) : null;
  return `<section class="seccion herramienta">
    <div class="cab-lonja"><button class="volver" type="button" data-ir="hoy">‹ Volver</button><h2>¿Me están pagando bien?</h2>
      <div class="meta">Escribe lo que te ofrece tu almacén, cooperativa o tratante y compáralo con lo que han pagado las lonjas esta semana.</div></div>
    ${disp.length ? `<div class="panel-filtros calc-form">
      <label class="campo"><span class="etiqueta">Producto</span><select id="of-clave">${disp.map(([k, n]) => `<option value="${esc(k)}"${k === o.clave ? " selected" : ""}>${esc(n)}</option>`).join("")}</select></label>
      <label class="campo"><span class="etiqueta">Te ofrecen (${esc(unidad)})</span><input id="of-precio" type="text" inputmode="decimal" autocomplete="off" min="0" step="any" value="${o.precio ?? ""}" placeholder="${med != null ? esc(String(med)) : ""}"></label>
      <label class="campo"><span class="etiqueta">Cantidad (${esc(nombreCant)}, opcional)</span><input id="of-cantidad" type="text" inputmode="decimal" autocomplete="off" min="0" step="any" value="${o.cantidad ?? ""}"></label>
    </div>
    <div id="of-resultado" aria-live="polite"></div>
    <p class="nota">Las lonjas dan un precio de referencia en sus propias condiciones (calidad, punto de entrega, quién paga el porte). Tenlo en cuenta al comparar: una oferta en tu almacén y un precio «sobre camión» en otra provincia no son lo mismo.</p>`
    : '<div class="vacio"><b>Sin precios recientes</b>Ninguna lonja ha cotizado en las últimas tres semanas.</div>'}
  </section>`;
}
function veredictoOferta(oferta, vals) {
  const med = mediaDe(vals), max = Math.max(...vals), min = Math.min(...vals), p = (oferta - med) / med * 100;
  if (oferta >= max) return { clase: "bien", titulo: "Buena oferta", texto: "Te pagan lo mismo o más que la lonja que más ha pagado esta semana." };
  if (p >= 1) return { clase: "bien", titulo: "Por encima de la media", texto: "Te ofrecen más que la media de las lonjas, aunque alguna paga más." };
  if (p > -1) return { clase: "igual", titulo: "En la media", texto: "Te ofrecen lo mismo que la media de las lonjas." };
  if (oferta >= min) return { clase: "mal", titulo: "Por debajo de la media", texto: "Te ofrecen menos que la media de las lonjas." };
  return { clase: "mal", titulo: "Oferta baja", texto: "Te ofrecen menos que todas las lonjas esta semana." };
}
function pintarOferta() {
  const caja = document.getElementById("of-resultado");
  if (!caja) return;
  const o = leerOferta();
  const { unidad, filas } = filasCalc(o.clave);
  if (!filas.length) { caja.innerHTML = ""; return; }
  const vals = filas.map(f => f.act), med = mediaDe(vals), max = Math.max(...vals);
  if (o.precio == null) {
    caja.innerHTML = `<p class="nota">Esta semana: media de ${filas.length} lonja${filas.length === 1 ? "" : "s"} <b class="num">${precio(redondeoU(med, unidad), unidad)} ${esc(unidad)}</b>, la más alta <b class="num">${precio(max, unidad)}</b>. Escribe tu oferta para compararla.</p>`;
    return;
  }
  const v = veredictoOferta(o.precio, vals), [, , abrev] = unidadCant(unidad);
  const dMed = o.precio - med, dMax = o.precio - max, mejor = filas.find(f => f.act === max);
  const cant = o.cantidad;
  const enDinero = cant ? `<p>En ${cant.toLocaleString("es-ES")} ${esc(abrev)}: <b>${euroSigno(dMed * cant)}</b> frente a la media${dMax < 0 ? ` y <b>${euroSigno(dMax * cant)}</b> frente a ${esc(corto(mejor.lonja))}` : ""}.</p>` : "";
  caja.innerHTML = `<div class="veredicto ${v.clase}">
      <b>${v.titulo}</b>
      <p>${v.texto} Tu oferta, <b class="num">${precio(o.precio, unidad)} ${esc(unidad)}</b>, es ${esc(relTxt(dMed, unidad))} la media${dMax < 0 ? ` y ${esc(relTxt(dMax, unidad))} ${esc(corto(mejor.lonja))}` : ""}.</p>
      ${enDinero}
    </div>
    <div class="oferta-tabla">${[...filas].sort((a, b) => b.act - a.act).map(f => {
      const d = o.precio - f.act;
      return `<div class="oferta-fila" role="button" tabindex="0" data-fila="${esc(f.id)}">
        <span class="prod"><b>${esc(corto(f.lonja))}</b><small>${esc(f.producto)} · ${fechaCorta(f.lonja.fecha)}</small></span>
        <span class="precio num">${precio(f.act, f.unidad)}</span>
        <span class="var ${d > 0 ? "s" : d < 0 ? "b" : "i"}" title="Tu oferta menos el precio de la lonja">${d === 0 ? "igual" : conSigno(d, unidad)}</span></div>`;
    }).join("")}</div>
    <p class="nota">Verde: tu oferta paga más que esa lonja. Rojo: paga menos.</p>`;
}
function guardarOfertaPantalla() {
  const o = leerOferta();
  o.clave = document.getElementById("of-clave")?.value || o.clave;
  const p = numero(document.getElementById("of-precio")?.value), q = numero(document.getElementById("of-cantidad")?.value, true);
  o.precio = p > 0 && p < 1e6 ? p : null;
  o.cantidad = q > 0 && q < 1e7 ? q : null;
  guardarLS("lonjas-oferta", o);
}

/* =====================================================================================
   2. Mi explotación
   ===================================================================================== */
const NUEVA = { clave: null };
function leerPartidas() {
  const l = leerLS("lonjas-explotacion", []);
  return (Array.isArray(l) ? l : []).filter(p => p && typeof p.id === "string" && /^p\d{1,16}$/.test(p.id)
    && PRODUCTOS_CLAVE.some(c => c[0] === p.clave) && typeof p.cantidad === "number" && p.cantidad > 0 && p.cantidad < 1e7
    && (p.valorar === "media" || p.valorar === "max" || RE_ID.test(p.valorar))).slice(0, MAX_PARTIDAS);
}
/** Precio con el que se valora una partida ahora y en la sesión anterior de esas mismas lonjas. */
function valorPartida(p) {
  const { unidad, filas } = filasCalc(p.clave);
  if (!filas.length) return null;
  const prev = f => f.ant ?? f.act;
  let ref, act, ant, fecha;
  if (p.valorar === "media") {
    act = mediaDe(filas.map(f => f.act)); ant = mediaDe(filas.map(prev));
    ref = filas.length === 1 ? corto(filas[0].lonja) : `media de ${filas.length} lonjas`;
    fecha = filas.map(f => f.lonja.fecha).sort().at(-1);
  } else if (p.valorar === "max") {
    const f = filas.reduce((a, b) => (b.act > a.act ? b : a));
    act = f.act; ant = Math.max(...filas.map(prev)); ref = `la que más paga: ${corto(f.lonja)}`; fecha = f.lonja.fecha;
  } else {
    const f = filas.find(x => x.lonja.id === p.valorar);
    if (!f) return null;
    act = f.act; ant = prev(f); ref = corto(f.lonja); fecha = f.lonja.fecha;
  }
  return { unidad, act, ant, ref, fecha, valor: act * p.cantidad, cambio: (act - ant) * p.cantidad };
}
function totalExplotacion() {
  const vs = leerPartidas().map(valorPartida).filter(Boolean);
  if (!vs.length) return null;
  return { valor: vs.reduce((s, v) => s + v.valor, 0), cambio: vs.reduce((s, v) => s + v.cambio, 0), n: vs.length };
}
function vistaExplotacion() {
  const partidas = leerPartidas();
  const disp = PRODUCTOS_CLAVE.filter(([k]) => filasCalc(k).filas.length);
  if (!NUEVA.clave || !disp.some(([k]) => k === NUEVA.clave)) NUEVA.clave = (disp[0] || ["trigo"])[0];
  const { unidad, filas } = filasCalc(NUEVA.clave);
  const [, nombreCant] = unidadCant(unidad);
  const tot = totalExplotacion();
  const filasP = partidas.map(p => {
    const v = valorPartida(p), nombre = nombreClave(p.clave);
    if (!v) return `<div class="partida apagada"><span class="prod"><b>${esc(nombre)}</b><small>${p.cantidad.toLocaleString("es-ES")} · sin precio reciente para valorarlo</small></span>
      <button class="chip" type="button" data-partida-borrar="${esc(p.id)}" aria-label="Quitar ${esc(nombre)}">Quitar</button></div>`;
    const [, , abrev] = unidadCant(v.unidad);
    return `<div class="partida">
      <span class="prod"><b>${esc(nombre)} · ${p.cantidad.toLocaleString("es-ES")} ${esc(abrev)}</b><small>a ${precio(redondeoU(v.act, v.unidad), v.unidad)} ${esc(v.unidad)} (${esc(v.ref)}, ${fechaCorta(v.fecha)})</small></span>
      <span class="valor-partida"><b class="num">${euros(v.valor)}</b><small class="var ${v.cambio > 0 ? "s" : v.cambio < 0 ? "b" : "i"}">${v.cambio ? euroSigno(v.cambio) : "="}</small></span>
      <button class="chip" type="button" data-partida-borrar="${esc(p.id)}" aria-label="Quitar ${esc(nombre)}">Quitar</button>
    </div>`;
  }).join("");
  const ganado = /€\/kg/.test(unidad) && /vivo|canal/.test(unidad);
  return `<section class="seccion herramienta">
    <div class="cab-lonja"><button class="volver" type="button" data-ir="hoy">‹ Volver</button><h2>Mi explotación</h2>
      <div class="meta">Apunta lo que tienes almacenado o en la granja y mira cuánto vale con los precios de esta semana. Se guarda solo en este teléfono.</div></div>
    ${tot ? `<div class="veredicto ${tot.cambio > 0 ? "bien" : tot.cambio < 0 ? "mal" : "igual"}">
        <span class="etiqueta">Vale esta semana</span><b class="num grande">${euros(tot.valor)}</b>
        <p>${tot.cambio ? `${euroSigno(tot.cambio)} desde la sesión anterior de cada lonja.` : "Igual que en la sesión anterior."}</p>
      </div>` : ""}
    ${filasP ? `<div class="partidas">${filasP}</div>` : '<div class="vacio sin-borde">Aún no has apuntado nada. Añade tu primera partida abajo.</div>'}
    <h3 class="sub-h">Añadir una partida</h3>
    ${partidas.length >= MAX_PARTIDAS ? `<p class="nota">Como mucho ${MAX_PARTIDAS} partidas.</p>` : `<form class="panel-filtros calc-form" data-partida-form>
      <label class="campo"><span class="etiqueta">Producto</span><select name="clave" id="ex-clave">${disp.map(([k, n]) => `<option value="${esc(k)}"${k === NUEVA.clave ? " selected" : ""}>${esc(n)}</option>`).join("")}</select></label>
      <label class="campo"><span class="etiqueta">Cantidad (${esc(nombreCant)}${ganado ? " en total" : ""})</span><input name="cantidad" type="text" inputmode="decimal" autocomplete="off" min="0" step="any" required></label>
      <label class="campo"><span class="etiqueta">Valorar con</span><select name="valorar">
        <option value="media">La media de las lonjas</option><option value="max">La lonja que más paga</option>
        ${filas.map(f => `<option value="${esc(f.lonja.id)}">${esc(f.lonja.nombre)}</option>`).join("")}</select></label>
      <button class="chip boton" type="submit">Añadir</button>
    </form>
    ${ganado ? `<p class="nota">El ganado se valora por kilo (${esc(unidad)}): pon los kilos de todos los animales juntos. Por ejemplo, 300 lechazos de 11 kg son 3.300 kg.</p>` : ""}`}
    <p class="nota">Es una valoración orientativa con el precio de referencia de las lonjas, no lo que te pagarían: no descuenta portes, comisiones ni diferencias de calidad. Para comparar una oferta concreta usa <a href="#oferta">¿Me están pagando bien?</a>.</p>
  </section>`;
}

/* =====================================================================================
   3. ¿Caro o barato?  (histórico oficial de la Junta + sesiones recientes de la app)
   ===================================================================================== */
const restarDias = (iso, n) => { const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10); };
/** Serie semanal de una lonja: puntos oficiales (sin dudosos) y, detrás, las sesiones recientes de la app. */
function serieCompleta(id) {
  const of = puntosSerie(id).filter(p => !p.dud);
  const rec = recientesDe(id);
  const vistas = new Set(of.map(p => p.w));
  return [...of, ...rec.filter(p => !vistas.has(p.w))].sort((a, b) => a.fecha.localeCompare(b.fecha));
}
function termometro(id) {
  const pts = serieCompleta(id);
  const ult = pts.at(-1);
  if (!ult || diasDesde(ult.fecha) > 45) return null;
  const ventana = pts.filter(p => p.fecha >= restarDias(ult.fecha, VENTANA_DIAS));
  if (ventana.length < MIN_SEMANAS_TERMO) return null;
  const otros = ventana.slice(0, -1).map(p => p.v);
  const p = (otros.filter(x => x < ult.v).length + otros.filter(x => x === ult.v).length / 2) / otros.length;
  const pMin = ventana.reduce((a, b) => (b.v < a.v ? b : a)), pMax = ventana.reduce((a, b) => (b.v > a.v ? b : a));
  const hace1 = restarDias(ult.fecha, 365);
  const cerca = pts.filter(x => Math.abs(new Date(x.fecha) - new Date(hace1)) <= 17 * 86400000);
  const anioPasado = cerca.length ? mediaDe(cerca.map(x => x.v)) : null;
  const desde = new Date(ventana[0].fecha + "T12:00:00"); desde.setDate(desde.getDate() + 6);
  return { id, v: ult.v, fecha: ult.fecha, reciente: !!ult.reciente, p, n: ventana.length, desde: desde.toISOString().slice(0, 10), min: pMin, max: pMax,
    anioPasado, varAnio: anioPasado ? (ult.v - anioPasado) / anioPasado * 100 : null, u: HIST.indice.series[id].u };
}
function veredictoTermo(p) {
  if (p >= 0.8) return { txt: "Alto", clase: "alto" };
  if (p >= 0.6) return { txt: "Algo alto", clase: "algo-alto" };
  if (p > 0.4) return { txt: "Normal", clase: "normal" };
  if (p > 0.2) return { txt: "Algo bajo", clase: "algo-bajo" };
  return { txt: "Bajo", clase: "bajo" };
}
const mesAnio = iso => { const [a, m] = iso.split("-").map(Number); return `${MESES[m - 1]} ${a}`; };
function fraseTermo(t) {
  const pct = Math.round(t.p * 100);
  return pct >= 50 ? `Más alto que en el ${pct} % de las semanas desde ${mesAnio(t.desde)}.`
    : `Más bajo que en el ${100 - pct} % de las semanas desde ${mesAnio(t.desde)}.`;
}
function filaTermo(t, titulo, sub, clave, lonjaApp) {
  const v = veredictoTermo(t.p);
  const via = t.varAnio == null ? "" : `${t.varAnio > 0 ? "+" : "−"}${Math.abs(t.varAnio).toLocaleString("es-ES", { maximumFractionDigits: 1 })} % que hace un año`;
  return `<button class="termo-fila" type="button" data-h-abrir="${esc(clave)}" data-h-lonja-app="${esc(lonjaApp)}">
    <span class="prod"><b>${esc(titulo)}</b><small>${esc(sub)}</small></span>
    <span class="precio num">${precio(redondeoU(t.v, t.u), t.u)}<small>${esc(t.u)}</small></span>
    <span class="termo" aria-hidden="true"><i class="${v.clase}" data-w="${Math.round(4 + t.p * 96)}"></i></span>
    <span class="pastilla termo-${v.clase}">${v.txt}</span>
    <span class="termo-texto">${fraseTermo(t)} Mín. ${precio(redondeoU(t.min.v, t.u), t.u)} (${mesAnio(t.min.fecha)}) · máx. ${precio(redondeoU(t.max.v, t.u), t.u)} (${mesAnio(t.max.fecha)})${via ? ` · ${via}` : ""}</span>
  </button>`;
}
/** Avisa a la vista cuando el histórico termina de cargar (lo comparten «¿caro o barato?» y las diferencias). */
function asegurarHistorico(rutas) {
  if (HIST.indice) return true;
  if (!HIST.cargando && !HIST.error) cargarHistorico().then(() => { if (rutas.includes(location.hash.slice(1) || "hoy")) router(); });
  return false;
}
function lonjasAppActivas() { return DATOS.lonjas.filter(l => l.estado !== "suspendida"); }
function vistaTermometro() {
  const cab = `<div class="cab-lonja"><button class="volver" type="button" data-ir="hoy">‹ Volver</button><h2>¿Caro o barato?</h2>
    <div class="meta">El último precio de cada lonja comparado con todas las semanas del histórico oficial de la Junta de Castilla y León y las sesiones recientes.</div></div>`;
  if (!asegurarHistorico(["termometro"])) {
    return `<section class="seccion herramienta">${cab}${HIST.error ? '<div class="vacio"><b>No se ha podido cargar el histórico</b>Comprueba la conexión y vuelve a intentarlo.</div>' : '<div class="vacio sin-borde">Cargando el histórico oficial…</div>'}</section>`;
  }
  const bloques = PRODUCTOS_CLAVE.filter(([c]) => CLAVE_A_JUNTA[c]).map(([clave, nombre]) => {
    const filas = lonjasAppActivas().map(l => {
      const id = serieDeApp(clave, l.id);
      const t = id && termometro(id);
      return t ? filaTermo(t, corto(l), `${HIST.indice.series[id].p} · ${t.reciente ? "sesión del " : "semana del "}${fechaCorta(t.fecha)}`, clave, l.id) : "";
    }).join("");
    return filas ? `<h3 class="sub-h">${esc(nombre)}</h3><div class="termos">${filas}</div>` : "";
  }).join("");
  return `<section class="seccion herramienta">${cab}
    ${bloques || '<div class="vacio sin-borde">No hay suficientes datos recientes para comparar.</div>'}
    <p class="nota">«Alto» o «bajo» dice cómo está el precio comparado con lo que ha sido desde ${HIST.indice.anios[0]}; no es una previsión de lo que va a pasar. El histórico oficial empieza en ${HIST.indice.anios[0]}, así que con cada año que pase la comparación será más sólida. Toca una fila para ver su gráfico.</p>
  </section>`;
}
/** Línea para el detalle de un producto (debajo de su histórico oficial). */
function lineaTermometro(id) {
  const t = termometro(id);
  if (!t) return "";
  const v = veredictoTermo(t.p);
  return `<p class="nota termo-detalle"><span class="pastilla termo-${v.clase}">${v.txt}</span> ${fraseTermo(t)} <a href="#termometro">¿Caro o barato?</a></p>`;
}

/* =====================================================================================
   4. Diferencias entre lonjas
   ===================================================================================== */
function diferencias(clave) {
  const series = lonjasAppActivas().map(l => {
    const id = serieDeApp(clave, l.id);
    if (!id) return null;
    const pts = serieCompleta(id);
    if (!pts.length) return null;
    const ult = pts.at(-1);
    return { lonja: l, id, u: HIST.indice.series[id].u, porSemana: new Map(pts.map(p => [p.w, p])), ult: diasDesde(ult.fecha) <= 21 ? ult : null };
  }).filter(Boolean);
  const out = [];
  for (let i = 0; i < series.length; i++) for (let j = i + 1; j < series.length; j++) {
    let a = series[i], b = series[j];
    if (a.u !== b.u) continue;
    const ref = [a.ult, b.ult].filter(Boolean).map(p => p.fecha).sort().at(-1) || hoyISO();
    const desde = restarDias(ref, VENTANA_DIAS);
    let difs = [...a.porSemana].filter(([w, p]) => b.porSemana.has(w) && p.fecha >= desde).map(([w, p]) => p.v - b.porSemana.get(w).v);
    if (difs.length < MIN_SEMANAS_DIF) continue;
    let med = mediaDe(difs);
    if (med < 0) { [a, b] = [b, a]; difs = difs.map(d => -d); med = -med; }
    const sd = Math.sqrt(mediaDe(difs.map(d => (d - med) ** 2)));
    const actual = a.ult && b.ult ? a.ult.v - b.ult.v : null;
    const umbral = /€\/t/.test(a.u) ? 0.5 : 0.002;
    out.push({ a: a.lonja, b: b.lonja, u: a.u, n: difs.length, media: med, casiIgual: med < (/€\/t/.test(a.u) ? 1 : 0.005),
      mas: difs.filter(d => d > umbral).length / difs.length, menos: difs.filter(d => d < -umbral).length / difs.length, actual,
      fuera: actual == null || sd === 0 ? 0 : actual > med + sd ? 1 : actual < med - sd ? -1 : 0 });
  }
  return out.sort((x, y) => y.media - x.media);
}
function bloqueDiferencias(clave) {
  if (!CLAVE_A_JUNTA[clave]) return "";
  const titulo = '<div class="titulo-seccion"><h2>Diferencias habituales</h2><span>Lonja contra lonja, semana a semana</span></div>';
  if (!asegurarHistorico(["comparar"])) return HIST.error ? "" : `<section class="seccion">${titulo}<div class="vacio sin-borde">Calculando con el histórico oficial…</div></section>`;
  const lista = diferencias(clave);
  if (!lista.length) return "";
  return `<section class="seccion">${titulo}
    <div class="difs">${lista.map(d => {
      const A = esc(corto(d.a)), Bn = esc(corto(d.b)), pc = x => Math.round(x * 100);
      const texto = d.casiIgual
        ? `${A} y ${Bn} pagan casi lo mismo de media (menos de ${/€\/t/.test(d.u) ? "1 €/t" : "0,005 " + esc(d.u)} de diferencia): más ${A} en ${pc(d.mas)} de cada 100 semanas, más ${Bn} en ${pc(d.menos)} e igual en ${pc(1 - d.mas - d.menos)} (${d.n} semanas comparadas).`
        : `${A} paga de media <b class="num">${precio(redondeoU(d.media, d.u), d.u)} ${esc(d.u)}</b> más que ${Bn}: más en ${pc(d.mas)} de cada 100 semanas (${d.n} semanas comparadas).`;
      const r = d.actual == null ? null : redondeoU(d.actual, d.u);
      const ahoraTxt = r == null ? "" : r === 0 ? "Esta semana pagan lo mismo" : `Esta semana: ${r > 0 ? A : Bn} paga ${precio(Math.abs(r), d.u)} ${esc(d.u)} más`;
      const marca = r == null || d.casiIgual ? "" : d.fuera > 0 ? " · más de lo habitual" : d.fuera < 0 ? (r < 0 ? " · al revés de lo habitual" : " · menos de lo habitual") : " · lo habitual";
      const ahora = r == null ? "" : `<span class="dif-ahora ${d.fuera > 0 ? "s" : d.fuera < 0 ? "b" : "i"}">${ahoraTxt}${marca}</span>`;
      return `<div class="dif"><p>${texto}</p>${ahora}</div>`;
    }).join("")}</div>
    <p class="nota">Calculado con las semanas en que cotizaron las dos lonjas, en el histórico oficial de la Junta (desde ${HIST.indice.anios[0]}) y las sesiones recientes. Cada lonja describe el producto a su manera (calidad, punto de entrega): parte de la diferencia viene de ahí.</p>
  </section>`;
}

/* =====================================================================================
   Tarjeta de «Hoy» y enganches
   ===================================================================================== */
function seccionHerramientas() {
  const tot = totalExplotacion();
  const boton = (ruta, titulo, texto) => `<button class="herr" type="button" data-ir="${ruta}"><b>${titulo}</b><small>${texto}</small></button>`;
  return `<section class="seccion">
    <div class="titulo-seccion"><h2>Para decidir</h2><span>Tus herramientas</span></div>
    <div class="herrs">
      ${boton("explotacion", "Mi explotación", tot ? `Vale <b class="num">${euros(tot.valor)}</b> <span class="var ${tot.cambio > 0 ? "s" : tot.cambio < 0 ? "b" : "i"}">${tot.cambio ? euroSigno(tot.cambio) : "="}</span>` : "Lo que vale lo que tienes almacenado")}
      ${boton("oferta", "¿Me están pagando bien?", "Tu oferta frente a las lonjas")}
      ${boton("termometro", "¿Caro o barato?", "El precio de hoy frente a otros años")}
      ${boton("calculadora", "Calculadora de venta", "Cuánto te pagaría cada lonja")}
    </div>
  </section>`;
}
function trasPintarHerramientas(h) {
  if (h === "oferta") pintarOferta();
}

document.addEventListener("input", e => {
  if (e.target.id === "of-precio" || e.target.id === "of-cantidad") { guardarOfertaPantalla(); pintarOferta(); }
});
document.addEventListener("change", e => {
  if (e.target.id === "of-clave") { const o = leerOferta(); o.clave = e.target.value; o.precio = null; guardarLS("lonjas-oferta", o); router(); }
  if (e.target.id === "ex-clave") { NUEVA.clave = e.target.value; router(); }
});
document.addEventListener("submit", e => {
  const f = e.target.closest?.("[data-partida-form]");
  if (!f) return;
  e.preventDefault();
  const cantidad = numero(f.cantidad.value, true), clave = f.clave.value, valorar = f.valorar.value;
  if (!(cantidad > 0 && cantidad < 1e7)) { marcarInvalido(f.cantidad, "Escribe una cantidad mayor que 0, por ejemplo 60 o 12,5."); return; }
  if (!PRODUCTOS_CLAVE.some(p => p[0] === clave) || !(valorar === "media" || valorar === "max" || RE_ID.test(valorar))) return;
  const l = leerPartidas();
  if (l.length >= MAX_PARTIDAS) return;
  l.push({ id: "p" + Date.now(), clave, cantidad, valorar });
  guardarLS("lonjas-explotacion", l);
  router();
});
document.addEventListener("click", e => {
  const b = e.target.closest("[data-partida-borrar]");
  if (!b) return;
  guardarLS("lonjas-explotacion", leerPartidas().filter(p => p.id !== b.dataset.partidaBorrar));
  router();
});

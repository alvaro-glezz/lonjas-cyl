"use strict";
/* Plazos del campo (PAC): tarjeta con cuenta atrás en «Hoy» y página #plazos.
   Lee data/plazos.json, que se edita a mano con las fechas oficiales y su fuente. Como el resto de datos,
   se valida antes de usarlo: fechas reales, textos acotados y enlaces solo https. */
const RUTA_PLAZOS = "data/plazos.json";
const PLAZOS = { lista: null, actualizado: null, cargando: null, error: false };

function sanearPlazos(crudo) {
  if (!crudo || typeof crudo !== "object" || !Array.isArray(crudo.plazos)) throw new Error("Formato de plazos no válido");
  const lista = [];
  for (const p of crudo.plazos.slice(0, 100)) {
    if (!p || typeof p.id !== "string" || !RE_ID.test(p.id)) continue;
    const inicio = fechaOk(p.inicio), fin = fechaOk(p.fin);
    const titulo = texto(p.titulo, 120);
    if (!inicio || !fin || fin < inicio || !titulo) continue;
    lista.push({ id: p.id, titulo, inicio, fin, tipo: p.tipo === "tramite" ? "tramite" : "cobro", confirmado: p.confirmado !== false,
      detalle: texto(p.detalle, 600), fuente: urlHttps(p.fuente), fuenteNombre: texto(p.fuente_nombre, 160) });
  }
  return { lista, actualizado: fechaOk(crudo.actualizado) };
}

function cargarPlazos() {
  if (PLAZOS.lista || PLAZOS.cargando) return PLAZOS.cargando;
  PLAZOS.cargando = fetch(RUTA_PLAZOS, { cache: "no-cache" })
    .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(j => { Object.assign(PLAZOS, sanearPlazos(j)); PLAZOS.error = false; })
    .catch(() => { PLAZOS.error = true; })
    .finally(() => {
      PLAZOS.cargando = null;
      const h = location.hash.slice(1) || "hoy";
      if (h === "hoy" || h === "plazos") router();
    });
  return PLAZOS.cargando;
}

/** Fase de un plazo respecto a hoy: en curso (días hasta el fin), próximo (días hasta el inicio) o pasado. */
function fasePlazo(p, hoy = hoyISO()) {
  if (hoy < p.inicio) return { fase: "proximo", dias: difDias(p.inicio, hoy) };
  if (hoy <= p.fin) return { fase: "activo", dias: difDias(p.fin, hoy), total: difDias(p.fin, p.inicio) + 1, hechos: difDias(hoy, p.inicio) + 1 };
  return { fase: "pasado", dias: difDias(hoy, p.fin) };
}
function plazosOrdenados(hoy = hoyISO()) {
  const conFase = (PLAZOS.lista || []).map(p => ({ p, f: fasePlazo(p, hoy) }));
  const vivos = conFase.filter(x => x.f.fase !== "pasado")
    .sort((a, b) => (a.f.fase === "activo" ? a.p.fin : a.p.inicio).localeCompare(b.f.fase === "activo" ? b.p.fin : b.p.inicio));
  const pasados = conFase.filter(x => x.f.fase === "pasado").sort((a, b) => b.p.fin.localeCompare(a.p.fin));
  return { vivos, pasados };
}
function cuentaAtras(f) {
  if (f.fase === "activo") return f.dias === 0 ? "Último día" : f.dias === 1 ? "Termina mañana" : `Quedan ${f.dias} días`;
  if (f.fase === "proximo") return f.dias === 1 ? "Empieza mañana" : `Empieza en ${f.dias} días`;
  return `Terminó hace ${f.dias} día${f.dias === 1 ? "" : "s"}`;
}
function fechasPlazo(p) { return `${fechaCorta(p.inicio)} ${p.inicio.slice(0, 4) !== p.fin.slice(0, 4) ? p.inicio.slice(0, 4) + " " : ""}– ${fechaCorta(p.fin)} ${p.fin.slice(0, 4)}`; }
function tarjetaPlazo({ p, f }, enlace) {
  const urgente = f.fase === "activo" && f.dias <= 7;
  const pct = f.fase === "activo" ? Math.round(f.hechos / f.total * 100) : 0;
  return `<${enlace ? 'button type="button" data-ir="plazos"' : "div"} class="plazo${f.fase === "activo" ? " activo" : ""}${urgente ? " urgente" : ""}">
    <span class="plazo-cab"><b>${esc(p.titulo)}</b><span class="pastilla ${f.fase === "activo" ? (urgente ? "p-err" : "p-dia") : f.fase === "proximo" ? "p-pend" : "p-off"}">${cuentaAtras(f)}</span></span>
    <span class="plazo-fechas">${p.tipo === "cobro" ? "Cobro" : "Trámite"} · ${fechasPlazo(p)}${p.confirmado ? "" : " · fecha prevista"}</span>
    ${f.fase === "activo" ? `<span class="plazo-barra" aria-hidden="true"><i data-w="${pct}"></i></span>` : ""}
  </${enlace ? "button" : "div"}>`;
}

/** Tarjeta de «Hoy»: los dos plazos más cercanos (en curso o próximos). */
function bloquePlazos() {
  if (!PLAZOS.lista) { if (!PLAZOS.error) cargarPlazos(); return ""; }
  const { vivos } = plazosOrdenados();
  if (!vivos.length) return "";
  return `<section class="seccion">
    <div class="titulo-seccion"><h2>Plazos del campo</h2><span>PAC · cuenta atrás</span></div>
    <div class="plazos">${vivos.slice(0, 2).map(x => tarjetaPlazo(x, true)).join("")}</div>
  </section>`;
}

function vistaPlazos() {
  if (!PLAZOS.lista) {
    if (!PLAZOS.error) { cargarPlazos(); return '<div class="vacio"><b>Cargando…</b></div>'; }
    return '<div class="vacio"><b>No se ha podido cargar el calendario</b>Comprueba la conexión y vuelve a intentarlo.</div>';
  }
  const { vivos, pasados } = plazosOrdenados();
  const ficha = x => `<div class="fuente-fila">${tarjetaPlazo(x, false)}
      ${x.p.detalle ? `<p class="nota">${esc(x.p.detalle)}</p>` : ""}
      ${x.p.fuente ? `<p class="fuente">Fuente: <a href="${esc(x.p.fuente)}" target="_blank" rel="noopener noreferrer">${esc(x.p.fuenteNombre || "documento oficial")}</a></p>` : ""}
    </div>`;
  return `<section class="seccion">
    <div class="cab-lonja"><button class="volver" type="button" data-ir="hoy">‹ Volver</button><h2>Plazos del campo</h2>
      <div class="meta">Cobros y trámites de la PAC con su cuenta atrás.${PLAZOS.actualizado ? ` Calendario revisado el ${fechaLarga(PLAZOS.actualizado)}.` : ""}</div></div>
    ${vivos.length ? `<div class="fuentes">${vivos.map(ficha).join("")}</div>` : '<div class="vacio sin-borde">No hay plazos próximos en el calendario.</div>'}
    ${pasados.length ? `<h3 class="mesa-suelta">Ya pasados</h3><div class="fuentes">${pasados.map(ficha).join("")}</div>` : ""}
    <p class="nota">Fechas generales de la PAC en España. Las marcadas como «fecha prevista» son el plazo habitual y aún no se han publicado para ese año. Cada pago depende de la Junta de Castilla y León y de tu expediente: consulta tu caso con tu entidad colaboradora.</p>
  </section>`;
}

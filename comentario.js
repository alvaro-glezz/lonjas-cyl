/* Comentario semanal del mercado: pestaña «Comentario» (#comentario) y tarjeta en Hoy.
   Lee data/informes/ultimo.json (scraper/informe.py, cada sábado): el comentario escrito como un artículo
   («redaccion»), con el audio de la voz y enlace al archivo de semanas anteriores (mercado/). */
"use strict";

const COMENTARIO = { datos: null, cargando: null, error: false };
const cTexto = (v, max) => String(v ?? "").slice(0, max);

function cargarComentario() {
  if (COMENTARIO.datos || COMENTARIO.cargando || COMENTARIO.error) return;
  COMENTARIO.cargando = fetch("data/informes/ultimo.json", { cache: "no-cache" })
    .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(c => {
      if (!c || !/^\d{4}-W\d{2}$/.test(c.semana || "") || typeof c.titular !== "string") throw new Error("formato");
      const fecha = v => (/^\d{4}-\d{2}-\d{2}$/.test(v || "") ? v : "");
      const red = Array.isArray(c.redaccion) ? c.redaccion.filter(x => x && typeof x.p === "string").slice(0, 30)
        .map(x => ({ t: cTexto(x.t, 80), p: cTexto(x.p, 3000) })) : [];
      // Informes antiguos sin redacción: se montan con el resumen y las secciones
      const secciones = Array.isArray(c.secciones) ? c.secciones.slice(0, 12).map(s => ({ t: cTexto(s && s.titulo, 80),
        p: (Array.isArray(s && s.lineas) ? s.lineas : []).map(l => cTexto(l, 600)).join(" ") })) : [];
      COMENTARIO.datos = {
        semana: c.semana, titular: cTexto(c.titular, 160), titulo: cTexto(c.titulo, 160),
        resumen: Array.isArray(c.resumen) ? cTexto(c.resumen[0], 300) : "",
        redaccion: red.length ? red : [{ t: "", p: (Array.isArray(c.resumen) ? c.resumen : []).map(x => cTexto(x, 400)).join(" ") }, ...secciones],
        audio: typeof c.audio === "string" && /^audio\/informe-\d{4}-W\d{2}\.mp3$/.test(c.audio) ? c.audio : "",
        audioSeg: Number.isFinite(c.audio_seg) ? c.audio_seg : 0,
        desde: fecha(c.desde), hasta: fecha(c.hasta),
        fuentes: Array.isArray(c.fuentes) ? c.fuentes.slice(0, 6).map(f => cTexto(f, 200)) : [],
      };
    })
    .catch(() => { COMENTARIO.error = true; })
    .finally(() => {
      COMENTARIO.cargando = null;
      const h = location.hash.slice(1) || "hoy";
      if (h === "comentario" || (h === "hoy" && COMENTARIO.datos)) router();
    });
}

const comentarioReciente = c => !c.hasta || (Date.now() - new Date(c.hasta + "T12:00:00")) / 864e5 <= 10;

function bloqueComentario() {
  const c = COMENTARIO.datos;
  if (!c) { cargarComentario(); return ""; }
  if (!comentarioReciente(c)) return "";
  return `<section class="seccion">
    <a class="comentario-hoy" href="#comentario">
      <span class="etiqueta">Comentario de la semana${c.audio ? " · 🎧 con audio" : ""}</span>
      <b>${esc(c.titular)}</b>
      <small>${esc(c.resumen)}</small>
      <span class="gh-ver">Leer el comentario ›</span>
    </a>
  </section>`;
}

function vistaComentario() {
  const c = COMENTARIO.datos;
  const cab = `<div class="titulo-seccion"><h2>Comentario de la semana</h2><span>Mercado agrario de Castilla y León</span></div>`;
  if (!c) {
    cargarComentario();
    return `<section class="seccion">${cab}<div class="vacio">${COMENTARIO.error
      ? "<b>Aún no hay comentario</b>Se publica cada sábado por la mañana con lo que ha pasado en las lonjas."
      : "Cargando el comentario…"}</div></section>`;
  }
  const fl = iso => { const f = new Date(iso + "T12:00:00"); return isNaN(f) ? "" : f.toLocaleDateString("es-ES", { day: "numeric", month: "long" }); };
  const dur = c.audioSeg ? (c.audioSeg < 90 ? `${c.audioSeg} segundos` : `${Math.round(c.audioSeg / 60)} minutos`) : "un par de minutos";
  const parrafos = c.redaccion.map((x, k) => `${x.t ? `<h4>${esc(x.t)}</h4>` : ""}<p${k === 0 ? ' class="entradilla"' : ""}>${esc(x.p)}</p>`).join("");
  return `<section class="seccion">${cab}
    <article class="comentario-art">
      <p class="comentario-fecha">${c.titulo.includes(" · semana ") ? `Semana ${esc(c.titulo.split(" · semana ")[1])}` : c.desde && c.hasta ? `Semana del ${esc(fl(c.desde))} al ${esc(fl(c.hasta))}` : esc(c.titulo)}${comentarioReciente(c) ? "" : " · el próximo sale el sábado"}</p>
      <h3 class="comentario-titular">${esc(c.titular)}</h3>
      ${c.audio ? `<figure class="comentario-audio"><figcaption>🎧 Escúchalo en ${esc(dur)} <small>(voz generada por ordenador)</small></figcaption>
        <audio controls preload="none" src="${esc(c.audio)}"></audio></figure>` : ""}
      ${parrafos}
      <p class="nota">Fuentes: ${esc(c.fuentes.join("; "))}. Precios orientativos; no es una recomendación de compra ni de venta.</p>
      <p class="comentario-mas"><a href="mercado/">Comentarios de semanas anteriores ›</a></p>
    </article>
  </section>`;
}

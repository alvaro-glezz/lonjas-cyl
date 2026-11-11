/* Tarjeta «Comentario de la semana» en Hoy: lee data/informes/ultimo.json (scraper/informe.py, cada sábado)
   y enlaza a su página (mercado/<semana>/), que tiene el texto completo y el audio. */
"use strict";

const COMENTARIO = { datos: null, cargando: null, error: false };

function cargarComentario() {
  if (COMENTARIO.datos || COMENTARIO.cargando || COMENTARIO.error) return;
  COMENTARIO.cargando = fetch("data/informes/ultimo.json", { cache: "no-cache" })
    .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(c => {
      if (!c || !/^\d{4}-W\d{2}$/.test(c.semana || "") || typeof c.titular !== "string") throw new Error("formato");
      COMENTARIO.datos = { semana: c.semana, titular: c.titular.slice(0, 160), titulo: String(c.titulo || "").slice(0, 160),
                           resumen: Array.isArray(c.resumen) ? String(c.resumen[0] || "").slice(0, 300) : "", audio: !!c.audio,
                           hasta: /^\d{4}-\d{2}-\d{2}$/.test(c.hasta || "") ? c.hasta : "" };
    })
    .catch(() => { COMENTARIO.error = true; })
    .finally(() => { COMENTARIO.cargando = null; if ((location.hash.slice(1) || "hoy") === "hoy" && COMENTARIO.datos) router(); });
}

function bloqueComentario() {
  const c = COMENTARIO.datos;
  if (!c) { cargarComentario(); return ""; }
  // Solo si es reciente (de los últimos 10 días)
  if (c.hasta && (Date.now() - new Date(c.hasta + "T12:00:00")) / 864e5 > 10) return "";
  return `<section class="seccion">
    <a class="comentario-hoy" href="mercado/${c.semana.toLowerCase()}/">
      <span class="etiqueta">Comentario de la semana${c.audio ? " · 🎧 con audio" : ""}</span>
      <b>${esc(c.titular)}</b>
      <small>${esc(c.resumen)}</small>
      <span class="gh-ver">Leer el comentario completo ›</span>
    </a>
  </section>`;
}

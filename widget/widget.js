"use strict";
/* Widget de Lonjas CyL para insertar en otras webs:
     <iframe src="https://…/widget/?lonja=salamanca&p=trigo,cebada" …></iframe>   precios de una lonja
     <iframe src="https://…/widget/?p=trigo" …></iframe>                           un producto en todas las lonjas
   Parámetros: lonja (id), p (claves de producto separadas por comas), tema=oscuro, max (filas, 1-20).
   Solo lee data/precios.json de esta misma web. Todo lo que pinta se valida y se escapa. */
(function () {
  const RE_ID = /^[a-z0-9][a-z0-9-]{0,99}$/;
  const NOMBRES = { trigo: "Trigo", cebada: "Cebada", maiz: "Maíz", avena: "Avena", centeno: "Centeno", triticale: "Triticale",
    girasol: "Girasol", alfalfa: "Alfalfa", paja: "Paja", "cerdo-normal": "Cerdo normal", "cerdo-selecto": "Cerdo selecto",
    lechones: "Lechones", lechazo: "Lechazo", "cerdo-graso": "Cerdo graso", "cerda-extra": "Cerda extra",
    cochinillo: "Cochinillo sin hierro" };
  const PRINCIPALES = ["trigo", "cebada", "maiz", "girasol", "cerdo-normal", "lechones", "lechazo"];
  const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const caja = document.getElementById("w");
  const q = new URLSearchParams(location.search);
  const lonjaId = RE_ID.test(q.get("lonja") || "") ? q.get("lonja") : null;
  const claves = (q.get("p") || "").split(",").map(s => s.trim()).filter(s => NOMBRES[s]).slice(0, 13);
  const max = Math.min(20, Math.max(1, parseInt(q.get("max"), 10) || 8));
  if (q.get("tema") === "oscuro") document.documentElement.dataset.tema = "oscuro";

  const esc = s => String(s ?? "").replace(/[&<>"'`]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;" }[c]));
  const num = v => (typeof v === "number" && Number.isFinite(v) && Math.abs(v) < 1e7) ? v : null;
  const fecha = iso => (typeof iso === "string" && /^\d{4}-\d{2}-\d{2}$/.test(iso)) ? `${+iso.slice(8)} ${MESES[+iso.slice(5, 7) - 1]}` : "";
  const txt = (v, n) => typeof v === "string" ? v.slice(0, n) : "";
  function precio(v, u) {
    const dec = /€\/t/.test(u) || Math.abs(v) >= 100 ? (Number.isInteger(v) ? 0 : 2) : Math.max(2, Math.min(((String(v).split(".")[1]) || "").length, 4));
    return v.toLocaleString("es-ES", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  }
  function variacion(f) {
    if (f.ant == null) return { t: "", c: "i" };
    const d = Math.round((f.act - f.ant) * 1e5) / 1e5;
    if (!d) return { t: "=", c: "i" };
    return { t: (d > 0 ? "▲ +" : "▼ −") + Math.abs(d).toLocaleString("es-ES", { maximumFractionDigits: 3 }), c: d > 0 ? "s" : "b" };
  }
  function web() { return new URL("../", location.href).href; }
  function fila(f, sub) {
    const v = variacion(f);
    return `<tr><td>${esc(f.producto)}<small>${esc(sub)}</small></td><td class="n">${precio(f.act, f.unidad)}</td><td class="v ${v.c}">${esc(v.t)}</td></tr>`;
  }
  function pintar(d) {
    const lonjas = (Array.isArray(d.lonjas) ? d.lonjas : []).filter(l => l && RE_ID.test(l.id) && l.estado !== "suspendida").map(l => ({
      id: l.id, nombre: txt(l.nombre, 80), fecha: l.fecha, precios: (Array.isArray(l.precios) ? l.precios : []).map(p => ({
        producto: txt(p && p.producto, 80), unidad: txt(p && p.unidad, 20), clave: p && p.clave, act: num(p && p.act), ant: num(p && p.ant) }))
        .filter(p => p.producto && p.act !== null) }));
    let titulo, sub, filas, fuentes;
    if (lonjaId) {
      const l = lonjas.find(x => x.id === lonjaId);
      if (!l) throw new Error("Lonja no encontrada");
      const elegidas = claves.length ? claves : PRINCIPALES;
      let ps = l.precios.filter(p => elegidas.includes(p.clave)).sort((a, b) => elegidas.indexOf(a.clave) - elegidas.indexOf(b.clave));
      if (!ps.length) ps = l.precios;
      titulo = l.nombre; sub = `Sesión del ${fecha(l.fecha)}`; fuentes = l.nombre;
      filas = ps.slice(0, max).map(p => fila(p, p.unidad));
    } else {
      const c = claves[0] || "trigo";
      const ps = lonjas.flatMap(l => l.precios.filter(p => p.clave === c).map(p => ({ ...p, lonja: l })));
      const u = ps.length ? ps[0].unidad : "";
      const mismas = ps.filter(p => p.unidad === u).sort((a, b) => b.act - a.act);
      const art = { cebada: "de la", avena: "de la", alfalfa: "de la", paja: "de la", lechones: "de los" }[c] || "del";
      titulo = `Precio ${art} ${NOMBRES[c].toLowerCase()}`;
      sub = `Lonjas de Castilla y León · ${u}`; fuentes = mismas.map(p => p.lonja.nombre.replace("Lonja de ", "")).join(", ");
      filas = mismas.slice(0, max).map(p => fila({ ...p, producto: p.lonja.nombre.replace("Lonja de ", "") }, `${p.producto} · ${fecha(p.lonja.fecha)}`));
    }
    caja.innerHTML = `<header class="cab"><h1>${esc(titulo)}</h1><p>${esc(sub)}</p></header>
      ${filas.length ? `<table>${filas.join("")}</table>` : '<p class="error">Sin cotizaciones recientes.</p>'}
      <footer class="pie"><span>Fuente: ${esc(fuentes)} · orientativo</span><a href="${esc(web())}" target="_blank" rel="noopener">Lonjas CyL ›</a></footer>`;
  }
  fetch("../data/precios.json", { cache: "no-cache" })
    .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(pintar)
    .catch(() => { caja.innerHTML = `<p class="error">No se han podido cargar los precios. <a href="${esc(web())}" target="_blank" rel="noopener">Ver en Lonjas CyL</a></p>`; });
})();

"use strict";
/* Panel de visitas de Lonjas CyL: lee /api/estadisticas con la contraseña del panel y lo pinta.
   La contraseña se guarda solo en esta pestaña (o en este dispositivo si se marca «Recordar»). */
(function () {
  const $ = id => document.getElementById(id);
  const API = "../api/estadisticas";
  const SECCIONES = { hoy: "Hoy", lonjas: "Lonjas", comparar: "Comparar", historico: "Histórico", favoritos: "Favoritos",
    calculadora: "Calculadora de venta", oferta: "¿Me están pagando bien?", explotacion: "Mi explotación", termometro: "¿Caro o barato?",
    plazos: "Plazos de la PAC", datos: "Datos abiertos y widget", metodo: "Fuentes y método", fuentes: "Estado de las fuentes",
    detalle: "Ficha de un producto", widget: "Widget en otras webs" };
  const ORIGENES = { directo: "Directo o app instalada", google: "Google", bing: "Bing", duckduckgo: "DuckDuckGo", telegram: "Telegram",
    whatsapp: "WhatsApp", instagram: "Instagram", facebook: "Facebook", x: "X (Twitter)", "web-antigua": "Dirección antigua (github.io)",
    interno: "Desde la propia web", otras: "Otras webs", widget: "Widget en otras webs" };
  const APARATOS = { movil: "Móvil", ordenador: "Ordenador", tableta: "Tableta" };
  const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
  let paises;
  try { paises = new Intl.DisplayNames(["es"], { type: "region" }); } catch { paises = null; }
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const n = v => (v ?? 0).toLocaleString("es-ES");
  const fecha = iso => `${+iso.slice(8)} ${MESES[+iso.slice(5, 7) - 1]}`;
  const fechaDia = iso => `${DIAS[new Date(iso + "T12:00:00").getDay()]} ${fecha(iso)}`;

  function nombreSeccion(k) {
    if (SECCIONES[k]) return SECCIONES[k];
    if (k.startsWith("lonja-")) return "Lonja de " + k.slice(6).replace(/^\w/, c => c.toUpperCase());
    if (k.startsWith("comparar-")) return "Comparar · " + k.slice(9);
    if (k.startsWith("web:")) {
      const w = k.slice(4), cap = s => s.replace(/-/g, " ").replace(/^\w/, c => c.toUpperCase());
      if (w === "precios") return "Índice de precios";
      if (w === "plazos") return "Calendario de la PAC";
      if (w.startsWith("precio-")) return "Precio: " + cap(w.slice(7)).replace("Maiz", "Maíz");
      if (w.startsWith("lonja-")) return "Lonja de " + cap(w.slice(6)).replace("Leon", "León");
      return cap(w);
    }
    return k;
  }

  let clave = "";
  try { clave = sessionStorage.getItem("panel-clave") || localStorage.getItem("panel-clave") || ""; } catch { /* sin almacenamiento */ }
  let datos = null, medida = "personas";

  async function cargar() {
    $("error").textContent = "";
    const r = await fetch(`${API}?dias=${encodeURIComponent($("dias").value)}`, { headers: { authorization: "Bearer " + clave }, cache: "no-store" });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || `Error ${r.status}`);
    return j;
  }
  async function entrar() {
    try {
      datos = await cargar();
      $("acceso").hidden = true; $("controles").hidden = false; $("panel").hidden = false;
      pintar();
    } catch (e) {
      $("acceso").hidden = false; $("panel").hidden = true; $("controles").hidden = true;
      $("error").textContent = e.message === "Failed to fetch" ? "No hay conexión con la web." : e.message;
    }
  }

  function tile(titulo, valor, sub) {
    return `<div class="tile"><span>${esc(titulo)}</span><b>${valor}</b>${sub ? `<small>${sub}</small>` : ""}</div>`;
  }
  function lista(titulo, items, nombre, total, vacia) {
    const max = Math.max(1, ...items.map(x => x.v));
    return `<section class="caja"><h2>${esc(titulo)}</h2>${items.length ? `<ul class="lista">${items.map(x => `<li>
        <span title="${esc(nombre(x.k))}">${esc(nombre(x.k))}</span><b>${n(x.v)}${total ? ` <small>· ${Math.round(x.v / total * 100)} %</small>` : ""}</b>
        <i><em data-w="${(x.v / max * 100).toFixed(1)}"></em></i></li>`).join("")}</ul>` : `<p class="vacia">${esc(vacia || "Sin datos todavía.")}</p>`}</section>`;
  }

  /** Barras por día de una sola medida (personas, visitas o vistas), con eje en cero y aviso al pasar el dedo. */
  function grafico(porDia, campo) {
    // Se dibuja al ancho real de la caja (en el móvil no se encoge el texto)
    const W = Math.max(280, Math.round(($("panel").clientWidth || 1000) - 34)), H = W < 600 ? 200 : 260, m = { t: 12, r: 8, b: 26, l: 34 };
    const vals = porDia.map(d => d[campo] || 0);
    const max = Math.max(4, ...vals);
    const paso = Math.pow(10, Math.floor(Math.log10(max))) * (max / Math.pow(10, Math.floor(Math.log10(max))) > 5 ? 2 : 1);
    const tope = Math.ceil(max / paso) * paso;
    const y = v => m.t + (H - m.t - m.b) * (1 - v / tope);
    const bw = (W - m.l - m.r) / porDia.length, gap = Math.min(2, bw * 0.2);
    let s = "";
    for (let v = 0; v <= tope; v += paso) s += `<line class="rejilla" x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/><text class="eje" x="${m.l - 6}" y="${y(v) + 4}" text-anchor="end">${n(v)}</text>`;
    const cadaX = Math.ceil(porDia.length / Math.max(3, Math.floor(W / 110)));
    porDia.forEach((d, i) => {
      const x = m.l + i * bw, h = H - m.b - y(vals[i]);
      if (vals[i] > 0) {
        const r = Math.min(4, (bw - gap) / 2, h);
        const x0 = x + gap / 2, x1 = x + bw - gap / 2, y0 = y(vals[i]), yb = H - m.b;
        s += `<path class="barra" data-i="${i}" d="M${x0},${yb} V${y0 + r} Q${x0},${y0} ${x0 + r},${y0} H${x1 - r} Q${x1},${y0} ${x1},${y0 + r} V${yb} Z"/>`;
      }
      const ultimo = i === porDia.length - 1 && (porDia.length - 1) % cadaX >= cadaX / 2;
      if (i % cadaX === 0 || ultimo) s += `<text class="eje" x="${x + bw / 2}" y="${H - 8}" text-anchor="middle">${fecha(d.fecha)}</text>`;
      s += `<rect class="golpe" data-i="${i}" x="${x}" y="${m.t}" width="${bw}" height="${H - m.t - m.b}"/>`;
    });
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(campo)} por día">${s}</svg><div class="tooltip" id="tip"></div>`;
  }
  const MEDIDAS = { personas: "Personas", visitas: "Visitas", vistas: "Páginas vistas" };

  function pintar() {
    const d = datos, r = d.resumen, hoy = d.porDia.at(-1) || {};
    const ayer = d.porDia.at(-2) || {};
    const totalOrigen = d.origenes.reduce((s, x) => s + x.v, 0);
    const totalAparato = d.aparatos.reduce((s, x) => s + x.v, 0);
    const app = d.rutas.filter(x => !x.k.startsWith("web:") && x.k !== "widget");
    const web = d.rutas.filter(x => x.k.startsWith("web:"));
    const sinDatos = r.vistas_periodo === 0 && r.bot_mensajes_periodo === 0 && r.tg_canal == null;
    $("panel").innerHTML = `
      ${sinDatos ? '<p class="nota">Todavía no hay datos: el contador empieza a sumar en cuanto alguien visita la web de Vercel (no cuenta las visitas a github.io ni las tuyas en pruebas locales).</p>' : ""}
      <div class="tiles">
        ${tile("Personas hoy", n(hoy.personas), `ayer ${n(ayer.personas)}`)}
        ${tile("Personas · 7 días", n(r.personas_7), "distintas, sin repetir")}
        ${tile(`Personas · ${d.dias} días`, n(r.personas_periodo), `${n(r.visitas_periodo)} visitas · ${n(r.vistas_periodo)} páginas`)}
        ${tile("Con la app instalada", n(r.instalada_periodo), `visitas en ${d.dias} días`)}
        ${tile("Canal de Telegram", r.tg_canal == null ? "—" : n(r.tg_canal), "miembros (último recuento)")}
        ${tile("Robot de Telegram", n(r.bot_personas_periodo), `personas · ${n(r.bot_mensajes_periodo)} mensajes · ${n(r.avisos_personas)} con avisos`)}
      </div>
      <section class="caja">
        <div class="caja-cab"><h2>${MEDIDAS[medida]} por día</h2>
          <div class="selector" role="group" aria-label="Medida">${Object.entries(MEDIDAS).map(([k, t]) => `<button type="button" data-medida="${k}" aria-pressed="${k === medida}">${t}</button>`).join("")}</div></div>
        <div class="grafico" id="graf">${grafico(d.porDia, medida)}</div>
        <details class="tabla"><summary>Ver los datos en tabla</summary><table><thead><tr><th>Día</th><th>Personas</th><th>Visitas</th><th>Páginas</th><th>App instalada</th><th>Robot (personas)</th><th>Canal</th></tr></thead>
          <tbody>${[...d.porDia].reverse().map(x => `<tr><td>${fechaDia(x.fecha)}</td><td>${n(x.personas)}</td><td>${n(x.visitas)}</td><td>${n(x.vistas)}</td><td>${n(x.instalada)}</td><td>${n(x.bot_personas)}</td><td>${x.tg_canal == null ? "—" : n(x.tg_canal)}</td></tr>`).join("")}</tbody></table></details>
      </section>
      <div class="rejilla2">
        ${lista("De dónde llegan", d.origenes, k => ORIGENES[k] || k, totalOrigen, "Aún no hay visitas.")}
        ${lista("Qué usan en la app", app, nombreSeccion, 0)}
        ${lista("Páginas de Google más vistas", web, nombreSeccion, 0, "Aún nadie ha llegado a las páginas de precios.")}
        ${lista("Otras webs que envían visitas", d.webs, k => k, 0, "Ninguna todavía.")}
        ${lista("Webs con el widget", d.widget, k => k, 0, "Ninguna web ha puesto el widget todavía.")}
        ${lista("Aparatos", d.aparatos, k => APARATOS[k] || k, totalAparato)}
        ${lista("Países", d.paises, k => (k === "XX" ? "Desconocido" : (paises ? paises.of(k) : k)), 0)}
      </div>
      <p class="pie">«Personas» cuenta navegadores distintos cada día sin guardar ningún dato que identifique a nadie; la misma persona en el móvil y en el ordenador cuenta dos veces. No cuenta a quien pide «no rastrear» ni a los buscadores. Actualizado ${new Date(d.generado).toLocaleString("es-ES")}.</p>`;
    document.querySelectorAll("[data-w]").forEach(el => { el.style.width = el.dataset.w + "%"; });
  }

  // Aviso al pasar el ratón o el dedo por una barra
  document.addEventListener("pointermove", e => {
    const g = e.target.closest(".golpe"), tip = $("tip");
    if (!tip) return;
    document.querySelectorAll(".barra.activa").forEach(b => b.classList.remove("activa"));
    if (!g) { tip.classList.remove("ver"); return; }
    const i = +g.dataset.i, d = datos.porDia[i], caja = $("graf").getBoundingClientRect(), rr = g.getBoundingClientRect();
    document.querySelector(`.barra[data-i="${i}"]`)?.classList.add("activa");
    const sing = { personas: "persona", visitas: "visita", vistas: "página vista" }[medida];
    tip.innerHTML = `<b>${fechaDia(d.fecha)}</b> · ${n(d[medida])} ${d[medida] === 1 ? sing : MEDIDAS[medida].toLowerCase()}`;
    tip.style.left = (rr.left + rr.width / 2 - caja.left) + "px";
    tip.style.top = (rr.top - caja.top + 20) + "px";
    tip.classList.add("ver");
  });
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-medida]");
    if (b) { medida = b.dataset.medida; pintar(); }
  });
  $("acceso").addEventListener("submit", e => {
    e.preventDefault();
    clave = $("clave").value;
    try { sessionStorage.setItem("panel-clave", clave); if ($("recordar").checked) localStorage.setItem("panel-clave", clave); } catch { /* nada */ }
    entrar();
  });
  $("dias").addEventListener("change", entrar);
  $("salir").addEventListener("click", () => {
    try { sessionStorage.removeItem("panel-clave"); localStorage.removeItem("panel-clave"); } catch { /* nada */ }
    clave = ""; datos = null; $("clave").value = ""; $("panel").hidden = true; $("controles").hidden = true; $("acceso").hidden = false;
  });
  let espera;
  window.addEventListener("resize", () => { clearTimeout(espera); espera = setTimeout(() => { if (datos && !$("panel").hidden) pintar(); }, 200); });
  if (clave) entrar();
})();

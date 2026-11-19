"use strict";
/* Estudio · «Mis reels»: fichas guardadas en /api/estudio (contraseña del panel) y editor con vista previa 9:16. */
(() => {
  const $ = id => document.getElementById(id);
  const API = "../api/estudio";
  const MAX = 6;
  let clave = "", fichas = [], publicados = new Set(), actual = null, vista = 0;
  try { clave = sessionStorage.getItem("panel-clave") || localStorage.getItem("panel-clave") || ""; } catch { /* sin almacenamiento */ }

  const el = (tag, props = {}, ...hijos) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v);
    }
    hijos.flat().forEach(h => h != null && e.append(h));
    return e;
  };
  const error = t => { $("fichas-error").textContent = t || ""; };
  const fechaBonita = iso => iso ? new Date(iso + "T12:00:00").toLocaleDateString("es-ES", { weekday: "short", day: "numeric", month: "short" }) : "sin fecha";

  async function api(metodo, cuerpo) {
    const r = await fetch(API, { method: metodo, cache: "no-store", headers: { authorization: "Bearer " + clave, ...(cuerpo ? { "content-type": "application/json" } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined });
    const j = await r.json().catch(() => ({}));
    if (r.status === 401) { salir(); throw new Error("Contraseña incorrecta"); }
    if (!r.ok) throw new Error(j.error || "No se ha podido hacer");
    return j;
  }
  function salir() {
    clave = "";
    try { sessionStorage.removeItem("panel-clave"); localStorage.removeItem("panel-clave"); } catch { /* nada */ }
    $("fichas-acceso").hidden = false; $("nueva-ficha").hidden = true; $("fichas-lista").textContent = ""; $("editor").hidden = true;
  }

  async function cargar() {
    if (!clave) { $("fichas-acceso").hidden = false; return; }
    error("");
    try {
      const [j, est] = await Promise.all([api("GET"), fetch("../data/instagram.json", { cache: "no-store" }).then(r => r.ok ? r.json() : {}).catch(() => ({}))]);
      publicados = new Set((est.registro || []).map(x => String(x.id || "")).filter(x => x.includes("-ficha-")).map(x => x.split("-ficha-")[1]));
      fichas = j.fichas || [];
      $("fichas-acceso").hidden = true; $("nueva-ficha").hidden = false;
      pintarLista();
    } catch (e) { error(e.message === "Failed to fetch" ? "Sin conexión." : e.message); }
  }

  function pintarLista() {
    const caja = $("fichas-lista");
    caja.textContent = "";
    if (!fichas.length) { caja.append(el("p", { class: "nota", text: "Aún no tienes reels propios. Pulsa «Nuevo reel»." })); return; }
    for (const f of fichas) {
      const est = publicados.has(f.id) ? ["bien", "Publicado"] : f.estado === "programado" ? ["aviso", "Programado"] : ["", "Borrador"];
      caja.append(el("div", { class: "ficha" },
        el("span", { class: "que" }, el("b", { text: f.titulo }), el("small", { text: `${fechaBonita(f.fecha)} · ${f.escenas.length} escena${f.escenas.length > 1 ? "s" : ""}` })),
        el("span", { class: "p " + est[0], text: est[1] }),
        el("button", { type: "button", class: "sec", text: "Editar", onclick: () => abrir(f) }),
        el("button", { type: "button", class: "sec", text: "Vista previa", onclick: () => previa(f) }),
        el("button", { type: "button", class: "sec", text: "Borrar", onclick: () => borrar(f) })));
    }
  }

  async function previa(f) {
    try { await api("POST", { accion: "previa", id: f.id }); error(""); alertaSuave(`Vista previa de «${f.titulo}» pedida: te llega a Telegram en 15–30 minutos.`); }
    catch (e) { error(e.message); }
  }
  async function borrar(f) {
    if (!window.confirm(`¿Borrar «${f.titulo}»? No se puede deshacer.`)) return;
    try { await api("POST", { accion: "borrar", id: f.id }); fichas = fichas.filter(x => x.id !== f.id); pintarLista(); } catch (e) { error(e.message); }
  }
  function alertaSuave(t) { $("fichas-error").textContent = ""; const n = el("p", { class: "nota", role: "status", text: "✓ " + t }); $("fichas-lista").prepend(n); setTimeout(() => n.remove(), 8000); }

  // ---------- editor ----------
  function abrir(f) {
    actual = f ? JSON.parse(JSON.stringify(f)) : { titulo: "", subtitulo: "", escenas: [{ titulo: "", texto: "" }], guion: "", copy: "", etiquetas: "", fecha: "", estado: "borrador" };
    $("f-titulo").value = actual.titulo; $("f-subtitulo").value = actual.subtitulo || ""; $("f-guion").value = actual.guion || "";
    $("f-copy").value = actual.copy || ""; $("f-etiquetas").value = actual.etiquetas || ""; $("f-fecha").value = actual.fecha || "";
    $("f-programar").checked = actual.estado === "programado";
    vista = 0; pintarEscenas(); $("editor").hidden = false; $("nueva-ficha").hidden = true; $("f-titulo").focus();
  }
  function leerEditor() {
    actual.titulo = $("f-titulo").value; actual.subtitulo = $("f-subtitulo").value; actual.guion = $("f-guion").value;
    actual.copy = $("f-copy").value; actual.etiquetas = $("f-etiquetas").value; actual.fecha = $("f-fecha").value;
    actual.estado = $("f-programar").checked ? "programado" : "borrador";
  }
  function pintarEscenas() {
    const ol = $("f-escenas");
    ol.textContent = "";
    actual.escenas.forEach((e, i) => {
      const titulo = el("input", { maxlength: "50", placeholder: "Título de la escena", "aria-label": `Título de la escena ${i + 1}` });
      const texto = el("textarea", { maxlength: "160", rows: "2", placeholder: "Texto en pantalla", "aria-label": `Texto de la escena ${i + 1}` });
      titulo.value = e.titulo; texto.value = e.texto;
      titulo.addEventListener("input", () => { e.titulo = titulo.value; vista = i + 1; pintarPantalla(); });
      texto.addEventListener("input", () => { e.texto = texto.value; vista = i + 1; pintarPantalla(); });
      const mover = d => () => { const j = i + d; if (j < 0 || j >= actual.escenas.length) return; [actual.escenas[i], actual.escenas[j]] = [actual.escenas[j], actual.escenas[i]]; vista = j + 1; pintarEscenas(); };
      ol.append(el("li", {}, titulo, texto, el("div", { class: "acciones" },
        el("button", { type: "button", class: "sec", text: "↑", "aria-label": "Subir escena", onclick: mover(-1) }),
        el("button", { type: "button", class: "sec", text: "↓", "aria-label": "Bajar escena", onclick: mover(1) }),
        el("button", { type: "button", class: "sec", text: "Ver", onclick: () => { vista = i + 1; pintarPantalla(); } }),
        el("button", { type: "button", class: "sec", text: "Quitar", onclick: () => { if (actual.escenas.length > 1) { actual.escenas.splice(i, 1); vista = 0; pintarEscenas(); } } }))));
    });
    $("f-mas-escena").hidden = actual.escenas.length >= MAX;
    pintarPantalla();
  }
  function pintarPantalla() {
    const p = $("f-pantalla"), n = actual.escenas.length;
    vista = Math.max(0, Math.min(vista, n));
    p.textContent = "";
    if (vista === 0) {
      p.className = "pantalla portada";
      p.append(el("div", { class: "marca", text: "Lonjas CyL" }), el("div", { class: "t", text: $("f-titulo").value || "Título" }),
        el("div", { class: "x", text: $("f-subtitulo").value || "Lonjas CyL · Castilla y León" }));
    } else {
      const e = actual.escenas[vista - 1];
      p.className = "pantalla";
      p.append(el("div", { class: "banda" }, el("div", { class: "marca" }, el("span", { text: "Lonjas CyL" }), el("span", { text: `${vista}/${n}` })),
        el("div", { class: "t", text: e.titulo || " " })), el("div", { class: "x", text: e.texto || " " }));
    }
    $("f-cual").textContent = vista === 0 ? "Portada" : `Escena ${vista} de ${n}`;
    const palabras = ($("f-guion").value.trim() || [$("f-titulo").value, ...actual.escenas.map(e => `${e.titulo} ${e.texto}`)].join(" ")).split(/\s+/).filter(Boolean).length;
    const seg = Math.max(5 + 3 * n, Math.round(palabras / 2.5) + 1);
    $("f-duracion").textContent = `Duración aproximada: ${seg} s` + (seg > 90 ? " · Instagram recomienda menos de 90 s: acorta el texto." : "");
  }

  $("f-mas-escena").addEventListener("click", () => { if (actual.escenas.length < MAX) { actual.escenas.push({ titulo: "", texto: "" }); vista = actual.escenas.length; pintarEscenas(); } });
  ["f-titulo", "f-subtitulo", "f-guion"].forEach(id => $(id).addEventListener("input", () => { if (id !== "f-guion") vista = 0; pintarPantalla(); }));
  $("f-ant").addEventListener("click", () => { vista--; pintarPantalla(); });
  $("f-sig").addEventListener("click", () => { vista++; pintarPantalla(); });
  $("f-cancelar").addEventListener("click", () => { $("editor").hidden = true; $("nueva-ficha").hidden = false; actual = null; });
  $("nueva-ficha").addEventListener("click", () => abrir(null));
  $("f-fecha").addEventListener("change", () => { if (!$("f-fecha").value) $("f-programar").checked = false; });
  $("f-programar").addEventListener("change", () => { if ($("f-programar").checked && !$("f-fecha").value) { $("f-programar").checked = false; error("Elige antes el día de publicación."); } });
  $("editor").addEventListener("submit", async ev => {
    ev.preventDefault();
    leerEditor();
    try {
      const { ficha } = await api("POST", { accion: "guardar", ficha: actual });
      fichas = [ficha, ...fichas.filter(x => x.id !== ficha.id)];
      $("editor").hidden = true; $("nueva-ficha").hidden = false; actual = null; pintarLista();
      alertaSuave(ficha.estado === "programado" ? `Guardado. Se publica el ${fechaBonita(ficha.fecha)} a las 18:37.` : "Guardado como borrador.");
    } catch (e) { error(e.message); }
  });
  $("fichas-acceso").addEventListener("submit", ev => {
    ev.preventDefault();
    clave = $("fichas-clave").value;
    try { sessionStorage.setItem("panel-clave", clave); } catch { /* nada */ }
    cargar();
  });
  cargar();
})();

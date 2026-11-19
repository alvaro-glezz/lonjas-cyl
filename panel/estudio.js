"use strict";
/* Estudio de Reels (fase 2, solo lectura): lee datos públicos del propio sitio, sin claves ni servidores externos. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
  const NOMBRES = { "cerdo-normal": "cerdo cebado", maiz: "maíz" };
  const nombre = k => NOMBRES[k] || k;
  const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

  function lunes(hoy) {
    const d = new Date(hoy); d.setHours(12, 0, 0, 0);
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    return d;
  }

  // Lo que el robot intentará publicar (redes.elegir): el producto previsto puede cambiar si ese día no hay precios.
  function previsto(franja, dia, plan) {
    if (franja === "reel") {
      const k = nombre(plan.producto_reel[dia]);
      return dia % 2 === 0 ? `Ranking de ${k} (o movimientos de la semana)` : `Movimientos de la semana (o ranking de ${k})`;
    }
    if (franja === "manana") return `Precios de ${nombre(plan.producto_dia[dia])} o sesión de lonja`;
    if (franja === "hortalizas") return "Precios de las patatas de la sesión del miércoles";
    if (franja === "tarde") return "Sesión de lonja o comparativa semanal";
    return ["Gasóleo B por provincia", "Cereales: la lonja que más paga", "Ganado: precios de la semana",
      "¿Cuánto cambia según la lonja?", "Ocho semanas de mercado"][dia] || "";
  }

  function pintarSemana(plan, estado, hoy) {
    const base = lunes(hoy), hecho = estado.franjas || {}, hoyIso = iso(hoy);
    let html = "";
    for (let dia = 0; dia < 6; dia++) {
      const d = new Date(base); d.setDate(base.getDate() + dia);
      const f = iso(d), hechas = hecho[f] || [];
      const filas = plan.franjas.filter(x => x.dias.includes(dia)).map(x => {
        const ok = hechas.includes(x.id);
        const est = ok ? ["bien", "Publicado"] : f < hoyIso ? ["mal", "No consta"] : ["aviso", "Programado"];
        return `<li><span class="hora">${esc(x.hora)}</span><span class="que"><b>${esc(x.nombre)}</b><small>${esc(previsto(x.id, dia, plan))}</small></span><span class="p ${est[0]}">${est[1]}</span></li>`;
      }).join("");
      const extra = hechas.filter(x => x.startsWith("especial:")).map(x => `<li><span class="hora">—</span><span class="que"><b>Reel especial</b><small>${esc(x.slice(9))}</small></span><span class="p bien">Publicado</span></li>`).join("");
      html += `<div class="dia${f === hoyIso ? " hoy" : ""}"><h3>${DIAS[dia]} ${d.getDate()}${f === hoyIso ? " · hoy" : ""}</h3><ul>${filas}${extra}</ul></div>`;
    }
    $("semana").innerHTML = html;
  }

  function pintarRegistro(estado) {
    const r = (estado.registro || []).slice(-15).reverse();
    if (!r.length) { $("registro").textContent = "Aún no hay publicaciones registradas."; return; }
    $("registro").innerHTML = `<ul class="lista">${r.map(x => {
      const [f, h] = String(x.fecha || "").split("T");
      const redes = ["Instagram", x.facebook ? "Facebook" : ""].filter(Boolean).join(" + ");
      return `<li><span class="hora">${esc(f)} ${esc(h || "")}</span><span class="que"><b>${esc(x.id)}</b><small>${esc(redes)}</small></span></li>`;
    }).join("")}</ul><p class="nota">Horas UTC, tal como las guarda el robot.</p>`;
  }

  function pintarHerramientas(plan, estado) {
    $("herramientas").innerHTML = `<ul class="lista">${plan.herramientas.map(h => {
      const est = h.estado === "activo" ? ["bien", "Activo"] : ["aviso", "Pendiente"];
      return `<li><span class="que"><b>${esc(h.nombre)}</b><small>${esc(h.donde)} · ${esc(h.nota)}</small></span><span class="p ${est[0]}">${est[1]}</span></li>`;
    }).join("")}</ul>${estado.token_renovado ? `<p class="nota">Token de Instagram renovado el ${esc(estado.token_renovado)}.</p>` : ""}`;
  }

  async function cargar() {
    try {
      const [plan, estado] = await Promise.all(["../data/estudio-plan.json", "../data/instagram.json"].map(async u => {
        const r = await fetch(u, { cache: "no-store" });
        if (!r.ok) throw new Error(`No se ha podido leer ${u.split("/").pop()}`);
        return r.json();
      }));
      const hoy = new Date();
      pintarSemana(plan, estado, hoy);
      pintarRegistro(estado);
      pintarHerramientas(plan, estado);
    } catch (e) {
      $("error").textContent = e.message === "Failed to fetch" ? "No hay conexión con la web." : e.message;
    }
  }
  cargar();
})();

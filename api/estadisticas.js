"use strict";
/* Datos del panel de visitas (/api/estadisticas?dias=30). Solo con la contraseña del panel:
   cabecera «Authorization: Bearer <PANEL_CLAVE>» (variable de entorno de Vercel, 12 caracteres o más).
   Devuelve recuentos por día y totales del periodo; nunca datos de personas concretas. */
const crypto = require("crypto");
const { config, pipeline, hoyMadrid } = require("./_almacen");

function igual(a, b) {
  const x = Buffer.from(String(a)), y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}
function diasAtras(n, hoy) {
  const out = [];
  const base = new Date(hoy + "T12:00:00Z");
  for (let i = n - 1; i >= 0; i--) out.push(new Date(base.getTime() - i * 86400000).toISOString().slice(0, 10));
  return out;
}
const aObjeto = plano => {
  const o = {};
  if (Array.isArray(plano)) for (let i = 0; i + 1 < plano.length; i += 2) o[plano[i]] = Number(plano[i + 1]) || 0;
  return o;
};
const sumar = (dst, src) => { for (const [k, v] of Object.entries(src)) dst[k] = (dst[k] || 0) + v; return dst; };
const top = (o, n) => Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, n).map(([k, v]) => ({ k, v }));

async function manejador(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "GET") return res.status(405).json({ error: "solo GET" });
  const clave = process.env.PANEL_CLAVE || "";
  const dada = String(req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (clave.length < 12) return res.status(503).json({ error: "Falta la variable PANEL_CLAVE en Vercel" });
  if (!igual(dada, clave)) {
    await new Promise(r => setTimeout(r, 600));               // frena a quien pruebe contraseñas
    return res.status(401).json({ error: "Contraseña incorrecta" });
  }
  if (!config()) return res.status(503).json({ error: "Falta conectar Upstash en Vercel" });
  const n = Math.min(90, Math.max(7, parseInt(req.query?.dias ?? new URL(req.url, "https://x").searchParams.get("dias"), 10) || 30));
  const hoy = hoyMadrid();
  const dias = diasAtras(n, hoy);
  const cmds = [];
  for (const d of dias) cmds.push(["HGETALL", `uso:d:${d}`], ["PFCOUNT", `uso:u:${d}`], ["PFCOUNT", `uso:b:${d}`], ["HGETALL", `uso:o:${d}`], ["HGETALL", `uso:w:${d}`]);
  const u7 = dias.slice(-7).map(d => `uso:u:${d}`), b7 = dias.slice(-7).map(d => `uso:b:${d}`);
  cmds.push(["PFCOUNT", ...u7], ["PFCOUNT", ...dias.map(d => `uso:u:${d}`)], ["PFCOUNT", ...b7], ["PFCOUNT", ...dias.map(d => `uso:b:${d}`)], ["SCARD", "avisos:chats"]);
  let r;
  try { r = await pipeline(cmds); } catch { return res.status(502).json({ error: "No se ha podido leer el almacén" }); }
  const porDia = [], rutas = {}, origenes = {}, aparatos = {}, paises = {}, webs = {}, widget = {};
  let tgCanal = null, tgAvisos = null;
  dias.forEach((d, i) => {
    const h = aObjeto(r[i * 5]);
    const x = { fecha: d, vistas: h.vistas || 0, visitas: h.visitas || 0, personas: Number(r[i * 5 + 1]) || 0, instalada: h.instalada || 0,
      bot_mensajes: h["bot:mensajes"] || 0, bot_personas: Number(r[i * 5 + 2]) || 0,
      tg_canal: "tg:canal" in h ? h["tg:canal"] : null, tg_avisos: "tg:avisos" in h ? h["tg:avisos"] : null };
    porDia.push(x);
    if (x.tg_canal != null) tgCanal = x.tg_canal;
    if (x.tg_avisos != null) tgAvisos = x.tg_avisos;
    for (const [k, v] of Object.entries(h)) {
      const [tipo, nombre] = k.split(/:(.+)/);
      if (tipo === "ruta") rutas[nombre] = (rutas[nombre] || 0) + v;
      else if (tipo === "origen") origenes[nombre] = (origenes[nombre] || 0) + v;
      else if (tipo === "disp") aparatos[nombre] = (aparatos[nombre] || 0) + v;
      else if (tipo === "pais") paises[nombre] = (paises[nombre] || 0) + v;
    }
    sumar(webs, aObjeto(r[i * 5 + 3]));
    sumar(widget, aObjeto(r[i * 5 + 4]));
  });
  const k = dias.length * 5;
  const tot = c => porDia.reduce((s, x) => s + x[c], 0);
  return res.status(200).json({
    generado: new Date().toISOString(), hoy, dias: n, porDia,
    resumen: {
      personas_7: Number(r[k]) || 0, personas_periodo: Number(r[k + 1]) || 0, visitas_periodo: tot("visitas"), vistas_periodo: tot("vistas"),
      instalada_periodo: tot("instalada"), bot_personas_7: Number(r[k + 2]) || 0, bot_personas_periodo: Number(r[k + 3]) || 0,
      bot_mensajes_periodo: tot("bot_mensajes"), avisos_personas: Number(r[k + 4]) || 0, tg_canal: tgCanal, tg_avisos: tgAvisos,
    },
    rutas: top(rutas, 40), origenes: top(origenes, 20), aparatos: top(aparatos, 5), paises: top(paises, 15), webs: top(webs, 20), widget: top(widget, 20),
  });
}

module.exports = manejador;

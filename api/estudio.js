"use strict";
/* Fichas de reels del Estudio (/api/estudio). Solo con la contraseña del panel (cabecera «Authorization: Bearer
   <PANEL_CLAVE>»). Se guardan en Upstash (hash «estudio:reels»); el robot de redes las monta y publica el día elegido
   en la franja de las 18:37 (scraper/fichas.py). Nunca se guardan claves ni datos de personas.
   GET                          -> { fichas: [...] }
   POST {accion:"guardar", ficha}   crea o cambia una ficha (devuelve la ficha guardada)
   POST {accion:"borrar", id}
   POST {accion:"previa", id}       pide la vista previa por Telegram (la lanza «Órdenes de Telegram» en ≤ 15 min) */
const crypto = require("crypto");
const { config, pipeline, hoyMadrid } = require("./_almacen");

const CLAVE_HASH = "estudio:reels", MAX_FICHAS = 60, MAX_ESCENAS = 6;
const RE_ID = /^[a-z0-9]{8,24}$/, RE_FECHA = /^\d{4}-\d{2}-\d{2}$/;

function igual(a, b) {
  const x = Buffer.from(String(a)), y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}
const limpio = (s, n) => String(s ?? "").replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "").replace(/[ \t]+/g, " ").trim().slice(0, n);

/** Deja solo los campos conocidos, con su longitud máxima. Devuelve { ficha } o { error }. */
function sanear(f, ahora = new Date()) {
  if (!f || typeof f !== "object") return { error: "Ficha vacía" };
  const id = RE_ID.test(String(f.id || "")) ? f.id : crypto.randomBytes(6).toString("hex");
  const titulo = limpio(f.titulo, 60);
  if (!titulo) return { error: "Falta el título" };
  const escenas = (Array.isArray(f.escenas) ? f.escenas : []).slice(0, MAX_ESCENAS)
    .map(e => ({ titulo: limpio(e && e.titulo, 50), texto: limpio(e && e.texto, 160) })).filter(e => e.titulo || e.texto);
  if (!escenas.length) return { error: "Añade al menos una escena" };
  const fecha = RE_FECHA.test(String(f.fecha || "")) ? f.fecha : "";
  const estado = f.estado === "programado" && fecha ? "programado" : "borrador";
  const etiquetas = limpio(f.etiquetas, 300).split(/[\s,]+/).filter(Boolean).map(x => "#" + x.replace(/^#+/, "").replace(/[^\p{L}\p{N}_]/gu, ""))
    .filter(x => x.length > 1).slice(0, 10).join(" ");
  return { ficha: { id, titulo, subtitulo: limpio(f.subtitulo, 90), escenas, guion: limpio(f.guion, 900), copy: limpio(f.copy, 1500),
    etiquetas, fecha, estado, cambiado: ahora.toISOString().slice(0, 16) } };
}

function leerCuerpo(req) {
  let c = req.body;
  if (typeof c === "string") { try { c = JSON.parse(c); } catch { c = null; } }
  return c && typeof c === "object" ? c : null;
}

async function manejador(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (!["GET", "POST"].includes(req.method)) return res.status(405).json({ error: "solo GET o POST" });
  const clave = process.env.PANEL_CLAVE || "";
  const dada = String(req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (clave.length < 12) return res.status(503).json({ error: "Falta la variable PANEL_CLAVE en Vercel" });
  if (!igual(dada, clave)) {
    await new Promise(r => setTimeout(r, 600));
    return res.status(401).json({ error: "Contraseña incorrecta" });
  }
  if (!config()) return res.status(503).json({ error: "Falta conectar Upstash en Vercel" });
  try {
    if (req.method === "GET") {
      const [plano] = await pipeline([["HGETALL", CLAVE_HASH]]);
      const fichas = [];
      for (let i = 0; Array.isArray(plano) && i + 1 < plano.length; i += 2) { try { fichas.push(JSON.parse(plano[i + 1])); } catch { /* rota: se ignora */ } }
      fichas.sort((a, b) => (b.fecha || "9999").localeCompare(a.fecha || "9999") || String(b.cambiado).localeCompare(String(a.cambiado)));
      return res.status(200).json({ fichas, hoy: hoyMadrid() });
    }
    const c = leerCuerpo(req);
    if (!c) return res.status(400).json({ error: "Cuerpo no válido" });
    if (c.accion === "guardar") {
      const { ficha, error } = sanear(c.ficha);
      if (error) return res.status(400).json({ error });
      const [n, existe] = await pipeline([["HLEN", CLAVE_HASH], ["HEXISTS", CLAVE_HASH, ficha.id]]);
      if (!existe && n >= MAX_FICHAS) return res.status(400).json({ error: `Máximo ${MAX_FICHAS} fichas: borra alguna antigua` });
      await pipeline([["HSET", CLAVE_HASH, ficha.id, JSON.stringify(ficha)]]);
      return res.status(200).json({ ficha });
    }
    if (!RE_ID.test(String(c.id || ""))) return res.status(400).json({ error: "Ficha desconocida" });
    if (c.accion === "borrar") {
      await pipeline([["HDEL", CLAVE_HASH, c.id]]);
      return res.status(200).json({ ok: true });
    }
    if (c.accion === "previa") {
      const [existe] = await pipeline([["HEXISTS", CLAVE_HASH, c.id]]);
      if (!existe) return res.status(404).json({ error: "Guarda la ficha antes de pedir la vista previa" });
      await pipeline([["SET", "redes:previa_ficha", c.id, "EX", 86400]]);
      return res.status(200).json({ ok: true });
    }
    return res.status(400).json({ error: "Acción desconocida" });
  } catch {
    return res.status(502).json({ error: "El almacén no responde. Prueba en unos minutos." });
  }
}

module.exports = manejador;
module.exports.sanear = sanear;

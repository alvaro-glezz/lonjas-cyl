"use strict";
/* Contador anónimo de visitas (/api/uso). Lo llama contador.js desde la app, las páginas de precios y el widget.
   Privacidad: sin cookies ni identificadores en el teléfono. Para contar personas distintas se calcula un resumen
   (hash) de IP + navegador + una clave secreta que cambia cada día; la IP no se guarda y el resumen va a un
   HyperLogLog de Redis, que solo sirve para contar, no para listar. Al día siguiente no se puede relacionar con nada.
   Se guarda por día: vistas, visitas, personas, sección, origen (Google, Telegram…), tipo de aparato, país,
   app instalada y las webs que insertan el widget. Todo caduca a los 400 días. */
const crypto = require("crypto");
const { config, pipeline, hoyMadrid } = require("./_almacen");

const CADUCA = 400 * 86400;
const RUTAS = /^(hoy|lonjas|lonja-[a-z0-9-]{1,30}|comparar(-[a-z0-9-]{1,20})?|historico|favoritos|calculadora|oferta|explotacion|termometro|plazos|datos|metodo|fuentes|detalle|widget|tiempo|gasoleo|comentario|web:[a-z0-9-]{1,40})$/;
const ROBOTS = /bot|crawl|spider|slurp|preview|headless|lighthouse|monitor|curl|wget|python|axios|node-fetch|facebookexternalhit|whatsapp\//i;
const ORIGENES = [
  ["google", /(^|\.)google\.[a-z.]+$/], ["bing", /(^|\.)bing\.com$/], ["duckduckgo", /(^|\.)duckduckgo\.com$/],
  ["telegram", /(^|\.)(t\.me|telegram\.org|telegram\.me)$/], ["whatsapp", /(^|\.)(whatsapp\.com|wa\.me|l\.wl\.co)$/],
  ["instagram", /(^|\.)instagram\.com$/], ["facebook", /(^|\.)(facebook\.com|fb\.com|fb\.me)$/], ["x", /(^|\.)(t\.co|x\.com|twitter\.com)$/],
  ["web-antigua", /^alvaro-glezz\.github\.io$/],
];

function grupoOrigen(host, propio) {
  if (!host) return "directo";
  if (host === propio) return "interno";
  for (const [g, re] of ORIGENES) if (re.test(host)) return g;
  return "otras";
}
function aparato(ua) {
  if (/ipad|tablet|(android(?!.*mobile))/i.test(ua)) return "tableta";
  if (/mobi|iphone|android/i.test(ua)) return "movil";
  return "ordenador";
}
const hostOk = h => typeof h === "string" && /^[a-z0-9.-]{3,80}$/.test(h) && h.includes(".") ? h : "";

async function manejador(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "solo POST" });
  const ua = String(req.headers["user-agent"] || "").slice(0, 300);
  const propio = String(req.headers["x-forwarded-host"] || req.headers.host || "").toLowerCase();
  // Solo desde nuestras propias páginas (la app, las páginas de precios y el widget están en esta misma web)
  const origen = String(req.headers.origin || "");
  const sitio = String(req.headers["sec-fetch-site"] || "");
  if ((origen && origen !== `https://${propio}`) || (sitio && sitio !== "same-origin")) return res.status(403).json({ error: "origen" });
  if (!ua || ROBOTS.test(ua) || !config()) return res.status(204).end();
  let b = req.body;
  if (typeof b === "string") { try { b = JSON.parse(b.slice(0, 2000)); } catch { b = null; } }
  if (!b || typeof b !== "object") return res.status(400).json({ error: "cuerpo" });
  const ruta = typeof b.r === "string" ? b.r.toLowerCase() : "";
  if (!RUTAS.test(ruta)) return res.status(400).json({ error: "ruta" });
  const entrada = b.t === "e";
  const dia = hoyMadrid(), kd = `uso:d:${dia}`;
  const cmds = [["HINCRBY", kd, "vistas", 1], ["HINCRBY", kd, `ruta:${ruta}`, 1]];
  if (entrada) {
    const ip = String(req.headers["x-forwarded-for"] || req.headers["x-real-ip"] || "").split(",")[0].trim();
    const secreto = config().token;
    const huella = crypto.createHash("sha256").update(`${dia}|${ip}|${ua}|${secreto}`).digest("hex").slice(0, 20);
    const host = hostOk(String(b.o || "").toLowerCase().replace(/^www\./, ""));
    const grupo = ruta === "widget" ? "widget" : grupoOrigen(host, propio);
    const pais = /^[A-Z]{2}$/.test(String(req.headers["x-vercel-ip-country"] || "")) ? req.headers["x-vercel-ip-country"] : "XX";
    cmds.push(["PFADD", `uso:u:${dia}`, huella], ["HINCRBY", kd, "visitas", 1], ["HINCRBY", kd, `origen:${grupo}`, 1],
      ["HINCRBY", kd, `disp:${aparato(ua)}`, 1], ["HINCRBY", kd, `pais:${pais}`, 1]);
    if (b.i === true) cmds.push(["HINCRBY", kd, "instalada", 1]);
    if (ruta === "widget" && host && host !== propio) cmds.push(["HINCRBY", `uso:w:${dia}`, host, 1], ["EXPIRE", `uso:w:${dia}`, CADUCA]);
    else if (grupo === "otras") cmds.push(["HINCRBY", `uso:o:${dia}`, host, 1], ["EXPIRE", `uso:o:${dia}`, CADUCA]);
    cmds.push(["EXPIRE", kd, CADUCA], ["EXPIRE", `uso:u:${dia}`, CADUCA]);
  }
  try { await pipeline(cmds); } catch { /* el contador nunca debe molestar a quien visita */ }
  return res.status(204).end();
}

module.exports = manejador;
module.exports.grupoOrigen = grupoOrigen;
module.exports.aparato = aparato;

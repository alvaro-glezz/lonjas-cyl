"use strict";
/* Robot de Telegram de Lonjas CyL (función de Vercel: /api/telegram).
   Telegram le manda cada mensaje que recibe el robot; contesta en la misma respuesta (sin usar el token).
   - Solo acepta peticiones con la cabecera secreta X-Telegram-Bot-Api-Secret-Token = variable TELEGRAM_SECRETO.
   - Lee los precios publicados (data/precios.json de esta misma web) y responde a: un producto (trigo, cebada,
     lechazo…), una lonja (Salamanca, León…), /lonjas, /ayuda o cualquier palabra de un producto (cordero, alubia…).
   - En grupos solo responde a comandos («/trigo»); en privado, a cualquier mensaje. */

const PRODUCTOS = [
  ["trigo", "Trigo", ["trigo"]], ["cebada", "Cebada", ["cebada"]], ["maiz", "Maíz", ["maiz"]], ["avena", "Avena", ["avena"]],
  ["centeno", "Centeno", ["centeno"]], ["triticale", "Triticale", ["triticale"]], ["girasol", "Girasol", ["girasol", "pipa"]],
  ["alfalfa", "Alfalfa", ["alfalfa"]], ["paja", "Paja", ["paja"]], ["cerdo-normal", "Cerdo normal", ["cerdo", "cerdo normal", "porcino"]],
  ["cerdo-selecto", "Cerdo selecto", ["cerdo selecto", "selecto"]], ["lechones", "Lechones", ["lechon", "lechones"]],
  ["lechazo", "Lechazo", ["lechazo", "lechazos"]],
];
const LONJAS = { salamanca: "salamanca", leon: "leon", segovia: "segovia", lerma: "lerma", burgos: "lerma", zamora: "zamora" };
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const RE_ID = /^[a-z0-9][a-z0-9-]{0,99}$/;
const CACHE_MS = 5 * 60 * 1000;
let cache = { t: 0, datos: null };

const esc = s => String(s ?? "").replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const norm = s => String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9ñ ]+/g, " ").replace(/\s+/g, " ").trim();
const num = v => (typeof v === "number" && Number.isFinite(v) && Math.abs(v) < 1e7) ? v : null;
const fecha = iso => (typeof iso === "string" && /^\d{4}-\d{2}-\d{2}$/.test(iso)) ? `${+iso.slice(8)} ${MESES[+iso.slice(5, 7) - 1]}` : "—";
function precio(v, u) {
  const dec = /€\/t/.test(u) || Math.abs(v) >= 100 ? (Number.isInteger(v) ? 0 : 2) : Math.max(2, Math.min((String(v).split(".")[1] || "").length, 3));
  return v.toLocaleString("es-ES", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}
function flecha(f) {
  if (f.ant == null) return "";
  const d = Math.round((f.act - f.ant) * 1e5) / 1e5;
  return d === 0 ? " =" : ` ${d > 0 ? "▲ +" : "▼ −"}${Math.abs(d).toLocaleString("es-ES", { maximumFractionDigits: 3 })}`;
}
const corto = n => n.replace(/^Lonja de(l)? /, "");

/** Datos limpios: lonjas activas con sus precios cotizados (como en la app, nada se da por bueno). */
function sanear(crudo) {
  if (!crudo || !Array.isArray(crudo.lonjas)) throw new Error("datos");
  return crudo.lonjas.filter(l => l && RE_ID.test(l.id) && l.estado !== "suspendida").map(l => ({
    id: l.id, nombre: String(l.nombre || l.id).slice(0, 80), fecha: l.fecha, dia: String(l.dia || "").slice(0, 20),
    precios: (Array.isArray(l.precios) ? l.precios : []).map(p => ({
      producto: String((p && p.producto) || "").slice(0, 100), cat: String((p && p.cat) || "").slice(0, 60), unidad: String((p && p.unidad) || "").slice(0, 20),
      clave: p && typeof p.clave === "string" ? p.clave : null, act: num(p && p.act), ant: num(p && p.ant) }))
      .filter(p => p.producto && p.act !== null),
  }));
}

function ayuda(web) {
  return ["<b>Lonjas CyL</b> · precios de las lonjas de Castilla y León", "",
    "Escríbeme un producto o una lonja:",
    "• <b>trigo</b>, <b>cebada</b>, <b>maíz</b>, <b>girasol</b>, <b>cerdo</b>, <b>lechones</b>, <b>lechazo</b>…",
    "• <b>Salamanca</b>, <b>León</b>, <b>Segovia</b>, <b>Lerma</b>",
    "• /lonjas: la última sesión de cada una",
    "• Cualquier otra palabra: <b>cordero</b>, <b>alubia</b>, <b>vacas</b>…", "",
    `Toda la información, avisos y calculadora: ${web}`, "Precios orientativos de cada lonja."].join("\n");
}

function responder(textoCrudo, lonjas, web) {
  const t = norm(String(textoCrudo || "").replace(/^\/([a-z_]+)(@\w+)?/i, "$1").replace(/_/g, " ")).slice(0, 80);
  if (!t || ["start", "ayuda", "help", "hola", "menu"].includes(t)) return ayuda(web);
  if (t === "lonjas" || t === "lonja") {
    return ["<b>Última sesión de cada lonja</b>", ...lonjas.map(l => `• ${esc(l.nombre)}: ${fecha(l.fecha)} · ${l.precios.length} precios · cotiza los ${esc(l.dia.toLowerCase())}`),
      "", "Escribe el nombre de una para ver sus precios."].join("\n");
  }
  const lid = LONJAS[t] || LONJAS[t.replace(/^lonja (de )?/, "")];
  if (lid) {
    const l = lonjas.find(x => x.id === lid);
    if (!l) return `La ${t === "zamora" ? "Lonja de Zamora" : "lonja"} no tiene cotizaciones ahora mismo. Escribe /lonjas para ver las activas.`;
    const orden = PRODUCTOS.map(p => p[0]);
    const ps = l.precios.filter(p => orden.includes(p.clave)).sort((a, b) => orden.indexOf(a.clave) - orden.indexOf(b.clave)).slice(0, 12);
    return [`📊 <b>${esc(l.nombre)}</b> · sesión del ${fecha(l.fecha)}`, "",
      ...(ps.length ? ps : l.precios.slice(0, 12)).map(p => `${esc(p.producto)}: <b>${precio(p.act, p.unidad)}</b> ${esc(p.unidad)}${flecha(p)}`),
      "", `Todos sus precios (${l.precios.length}): ${web}lonja/${l.id}/`].join("\n");
  }
  const prod = PRODUCTOS.find(([, , alias]) => alias.includes(t)) || PRODUCTOS.find(([c]) => c === t.replace(/ /g, "-"));
  if (prod) {
    const filas = lonjas.flatMap(l => l.precios.filter(p => p.clave === prod[0]).map(p => ({ ...p, l })));
    if (!filas.length) return `Ahora mismo ninguna lonja cotiza ${esc(prod[1].toLowerCase())}.`;
    const u = filas[0].unidad;
    const mismas = filas.filter(f => f.unidad === u).sort((a, b) => b.act - a.act);
    return [`📊 <b>${esc(prod[1])}</b> · ${esc(u)}`, "",
      ...mismas.map(f => `${esc(corto(f.l.nombre))}: <b>${precio(f.act, f.unidad)}</b>${flecha(f)} · ${esc(f.producto)}, ${fecha(f.l.fecha)}`),
      "", `Comparar y crear avisos: ${web}precio/${prod[0]}/`].join("\n");
  }
  const palabras = t.split(" ").filter(w => w.length >= 3).map(w => w.length > 4 ? w.replace(/(es|s)$/, "") : w);
  if (palabras.length) {
    const hallados = lonjas.flatMap(l => l.precios.filter(p => palabras.every(w => norm(p.cat + " " + p.producto).includes(w))).map(p => ({ ...p, l })));
    // Si la palabra solo está en la mesa («Alubias» -> «Canela»), se muestra también la mesa
    const nombre = p => palabras.every(w => norm(p.producto).includes(w)) ? p.producto : `${p.cat} · ${p.producto}`;
    if (hallados.length) {
      const mas = hallados.length > 15 ? `\n…y ${hallados.length - 15} más en ${web}precios/` : "";
      return [`🔎 <b>${esc(String(textoCrudo).slice(0, 40))}</b>`, "",
        ...hallados.slice(0, 15).map(f => `${esc(corto(f.l.nombre))} · ${esc(nombre(f))}: <b>${precio(f.act, f.unidad)}</b> ${esc(f.unidad)}${flecha(f)}`)].join("\n") + mas;
    }
  }
  return `No he encontrado «${esc(String(textoCrudo).slice(0, 40))}». Prueba con <b>trigo</b>, <b>lechazo</b>, <b>Salamanca</b> o /lonjas.`;
}

async function cargar(origen) {
  if (cache.datos && Date.now() - cache.t < CACHE_MS) return cache.datos;
  const r = await fetch(new URL("data/precios.json", origen), { headers: { accept: "application/json" } });
  if (!r.ok) throw new Error("HTTP " + r.status);
  cache = { t: Date.now(), datos: sanear(await r.json()) };
  return cache.datos;
}

function origenDe(req) {
  if (process.env.LONJAS_WEB && /^https:\/\/[a-z0-9.-]+\/$/.test(process.env.LONJAS_WEB)) return process.env.LONJAS_WEB;
  const host = String(req.headers["x-forwarded-host"] || req.headers.host || "");
  if (!/^[a-z0-9.-]+(:\d+)?$/i.test(host)) throw new Error("host");
  return `https://${host}/`;
}

async function manejador(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "solo POST" });
  const secreto = process.env.TELEGRAM_SECRETO || "";
  if (secreto.length < 16 || req.headers["x-telegram-bot-api-secret-token"] !== secreto) return res.status(401).json({ error: "no autorizado" });
  let cuerpo = req.body;
  if (typeof cuerpo === "string") { try { cuerpo = JSON.parse(cuerpo); } catch { cuerpo = null; } }
  const msg = cuerpo && cuerpo.message;
  if (!msg || !msg.chat || typeof msg.text !== "string") return res.status(200).json({});
  const privado = msg.chat.type === "private";
  if (!privado && !msg.text.startsWith("/")) return res.status(200).json({});
  let texto;
  try {
    const web = origenDe(req);
    texto = responder(msg.text, await cargar(web), web);
  } catch {
    texto = "Ahora mismo no puedo leer los precios. Prueba en unos minutos.";
  }
  return res.status(200).json({ method: "sendMessage", chat_id: msg.chat.id, text: texto.slice(0, 4000), parse_mode: "HTML",
    disable_web_page_preview: true, ...(privado ? {} : { reply_to_message_id: msg.message_id }) });
}

module.exports = manejador;
module.exports.responder = responder;
module.exports.sanear = sanear;

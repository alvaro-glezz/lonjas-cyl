"use strict";
/* Robot de Telegram de Lonjas CyL (función de Vercel: /api/telegram).
   Telegram le manda cada mensaje que recibe el robot; contesta en la misma respuesta (sin usar el token).
   - Solo acepta peticiones con la cabecera secreta X-Telegram-Bot-Api-Secret-Token = variable TELEGRAM_SECRETO.
   - Lee los precios publicados (data/precios.json de esta misma web) y responde a: un producto (trigo, cebada,
     lechazo…), una lonja (Salamanca, León…), /lonjas, /ayuda o cualquier palabra de un producto (cordero, alubia…).
   - En grupos solo responde a comandos («/trigo»); en privado, a cualquier mensaje.
   - Avisos personales (solo en privado): «/aviso trigo salamanca 240», «/avisos», «/borrar 1». Se guardan en Upstash
     Redis (variables UPSTASH_REDIS_REST_URL y UPSTASH_REDIS_REST_TOKEN, o las KV_REST_API_* que crea Vercel) y los
     comprueba el robot de GitHub después de cada lectura (scraper/avisos_telegram.py). Solo se guarda el número de
     chat y los avisos; «/borrar todos» lo elimina todo. */

const PRODUCTOS = [
  ["trigo", "Trigo", ["trigo"]], ["cebada", "Cebada", ["cebada"]], ["maiz", "Maíz", ["maiz"]], ["avena", "Avena", ["avena"]],
  ["centeno", "Centeno", ["centeno"]], ["triticale", "Triticale", ["triticale"]], ["girasol", "Girasol", ["girasol", "pipa"]],
  ["alfalfa", "Alfalfa", ["alfalfa"]], ["paja", "Paja", ["paja"]], ["cerdo-normal", "Cerdo normal", ["cerdo", "cerdo normal", "porcino"]],
  ["cerdo-selecto", "Cerdo selecto", ["cerdo selecto", "selecto"]], ["cerdo-graso", "Cerdo graso", ["cerdo graso", "graso"]],
  ["cerda-extra", "Cerda extra", ["cerda extra", "cerda", "cerdas", "cerda desvieje"]], ["lechones", "Lechones", ["lechon", "lechones"]],
  ["cochinillo", "Cochinillo sin hierro", ["cochinillo", "cochinillos"]],
  ["lechazo", "Lechazo", ["lechazo", "lechazos"]],
];
const LONJAS = { salamanca: "salamanca", leon: "leon", segovia: "segovia", lerma: "lerma", burgos: "lerma", zamora: "zamora" };
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const RE_ID = /^[a-z0-9][a-z0-9-]{0,99}$/;
const CACHE_MS = 5 * 60 * 1000;
let cache = { t: 0, datos: null };
const uso = require("./_almacen");

/** Cuenta mensajes y personas del robot para el panel (sin guardar el número de chat: solo un resumen diario). */
async function contarBot(chat) {
  const c = uso.config();
  if (!c) return;
  const dia = uso.hoyMadrid();
  const huella = require("crypto").createHash("sha256").update(`${dia}|${chat}|${c.token}`).digest("hex").slice(0, 20);
  try {
    await uso.pipeline([["HINCRBY", `uso:d:${dia}`, "bot:mensajes", 1], ["PFADD", `uso:b:${dia}`, huella],
      ["EXPIRE", `uso:d:${dia}`, 400 * 86400], ["EXPIRE", `uso:b:${dia}`, 400 * 86400]]);
  } catch { /* el recuento nunca debe impedir la respuesta */ }
}

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
    "🔔 <b>Avisos</b>: /aviso trigo salamanca 240 te escribe cuando el trigo de Salamanca llegue a 240 €/t. /avisos para verlos.", "",
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

/* ---------- avisos personales ---------- */
const MAX_AVISOS_CHAT = 10;
const SUBE = new Set(["sube", "suba", "subir", "supera", "supere", "pase", "mas", "encima", "arriba", "mayor"]);
const BAJA = new Set(["baja", "baje", "bajar", "menos", "debajo", "abajo", "menor", "caiga", "cae"]);
const RELLENO = new Set(["de", "del", "el", "la", "los", "las", "si", "a", "en", "que", "cuando", "por", "euros", "eur", "e", "t", "kg", "lonja", "avisame", "aviso", "precio", "llegue", "llega"]);

function almacen() {
  const url = (process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL || "").replace(/\/$/, "");
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN || "";
  if (!/^https:\/\/[a-z0-9.-]+$/i.test(url) || !token) return null;
  const cmd = async (...args) => {
    const r = await fetch(url, { method: "POST", headers: { authorization: `Bearer ${token}`, "content-type": "application/json" }, body: JSON.stringify(args) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.error) throw new Error("almacén");
    return j.result;
  };
  return {
    async leer(chat) {
      try { const l = JSON.parse((await cmd("GET", `avisos:${chat}`)) || "[]"); return Array.isArray(l) ? l.slice(0, MAX_AVISOS_CHAT) : []; }
      catch (e) { if (e.message === "almacén") throw e; return []; }
    },
    async guardar(chat, lista) {
      if (lista.length) { await cmd("SET", `avisos:${chat}`, JSON.stringify(lista)); await cmd("SADD", "avisos:chats", String(chat)); }
      else { await cmd("DEL", `avisos:${chat}`); await cmd("SREM", "avisos:chats", String(chat)); }
    },
  };
}

/** «trigo salamanca más de 240» -> { clave, lonja, dir, umbral }. Admite coma decimal, «>» y «<». */
function leerAviso(texto) {
  const t = String(texto || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/(\d),(\d)/g, "$1.$2").replace(/>/g, " mas ").replace(/</g, " menos ");
  const tokens = t.split(/[^a-z0-9.]+/).map(x => x.replace(/^\.+|\.+$/g, "")).filter(Boolean);
  const nums = tokens.filter(x => /^\d+(\.\d+)?$/.test(x));
  if (!nums.length) return { error: "falta el precio" };
  const umbral = Number(nums.at(-1));
  const dir = tokens.some(x => SUBE.has(x)) ? "sube" : tokens.some(x => BAJA.has(x)) ? "baja" : null;
  const lonja = tokens.map(x => LONJAS[x]).find(Boolean) || null;
  const resto = " " + tokens.filter(x => !/^\d/.test(x) && !SUBE.has(x) && !BAJA.has(x) && !LONJAS[x] && !RELLENO.has(x)).join(" ") + " ";
  let mejor = null;
  for (const [clave, , alias] of PRODUCTOS) for (const a of alias) {
    if (resto.includes(` ${a} `) && (!mejor || a.length > mejor.len)) mejor = { clave, len: a.length };
  }
  if (!mejor) return { error: "falta el producto" };
  if (!(umbral > 0 && umbral < 1e6)) return { error: "precio no válido" };
  return { clave: mejor.clave, lonja, dir, umbral };
}
/** Precio con el que se juzga un aviso: la lonja elegida o, si no hay, la que más paga (sube) o la que menos (baja). */
function evaluarAviso(a, lonjas) {
  const filas = lonjas.filter(l => !a.lonja || l.id === a.lonja)
    .flatMap(l => l.precios.filter(p => p.clave === a.clave && (!a.unidad || p.unidad === a.unidad)).map(p => ({ ...p, l })));
  if (!filas.length) return null;
  const f = filas.reduce((x, y) => (a.dir === "sube" ? (y.act > x.act ? y : x) : (y.act < x.act ? y : x)));
  return { fila: f, cumple: a.dir === "sube" ? f.act >= a.umbral : f.act <= a.umbral };
}
const nombreProd = c => (PRODUCTOS.find(p => p[0] === c) || [c, c])[1];
const nombreLonja = (id, lonjas) => { const l = lonjas.find(x => x.id === id); return l ? corto(l.nombre) : id; };
function textoAviso(a, lonjas) {
  return `${esc(nombreProd(a.clave))}${a.lonja ? ` en ${esc(nombreLonja(a.lonja, lonjas))}` : " en cualquier lonja"} · ${a.dir === "sube" ? "suba a" : "baje a"} ${precio(a.umbral, a.unidad)} ${esc(a.unidad)} ${a.dir === "sube" ? "o más" : "o menos"}`;
}
const AYUDA_AVISOS = ["🔔 <b>Avisos de precio</b>", "", "Escríbeme el producto, la lonja (si quieres) y el precio:",
  "• /aviso trigo salamanca 240", "• /aviso cebada más de 230", "• /aviso cerdo baja de 1,10", "",
  "Te escribiré cuando una sesión cruce ese precio. Ver los tuyos: /avisos · borrar: /borrar 1 o /borrar todos.",
  "Solo guardo tu número de chat y tus avisos (/borrar todos lo elimina)."].join("\n");

async function procesarAvisos(t, crudo, msg, lonjas, alm) {
  const chat = msg.chat.id;
  if (msg.chat.type !== "private") return "Los avisos personales se crean en privado: escríbeme directamente.";
  if (!alm) return "Los avisos personales aún no están activados. Mientras tanto puedes crearlos en la app: toca un producto y «Avisarme».";
  const lista = await alm.leer(chat);
  if (/^(avisos|mis avisos)$/.test(t)) {
    if (!lista.length) return "No tienes avisos. Crea uno así: /aviso trigo salamanca 240";
    return ["🔔 <b>Tus avisos</b>", "", ...lista.map((a, i) => {
      const e = evaluarAviso(a, lonjas);
      return `${i + 1}. ${textoAviso(a, lonjas)}${e ? ` · ahora ${precio(e.fila.act, e.fila.unidad)}` : ""}`;
    }), "", "Borrar: /borrar 1 · /borrar todos"].join("\n");
  }
  const mB = t.match(/^(?:borrar|quitar)(?: (todos|todo|\d{1,2}))?$/);
  if (mB) {
    if (!mB[1]) return "Dime cuál: /borrar 1 o /borrar todos. Mira los números con /avisos.";
    if (mB[1].startsWith("tod")) { await alm.guardar(chat, []); return "Hecho: he borrado todos tus avisos y tus datos."; }
    const n = Number(mB[1]);
    if (!(n >= 1 && n <= lista.length)) return `No tienes el aviso ${n}. Mira tus avisos con /avisos.`;
    const [quitado] = lista.splice(n - 1, 1);
    await alm.guardar(chat, lista);
    return `Borrado: ${textoAviso(quitado, lonjas)}.`;
  }
  const resto = String(crudo).replace(/^\s*\/?\s*(aviso|av[ií]same)(@\w+)?\s*/i, "").trim();
  if (!resto) return AYUDA_AVISOS;
  const p = leerAviso(resto);
  if (p.error) return `No lo he entendido (${p.error}).\n\n${AYUDA_AVISOS}`;
  if (lista.length >= MAX_AVISOS_CHAT) return `Ya tienes ${MAX_AVISOS_CHAT} avisos, el máximo. Borra alguno con /borrar 1.`;
  if (p.lonja && !lonjas.some(l => l.id === p.lonja)) return `La lonja de ${esc(p.lonja)} no tiene cotizaciones ahora mismo.`;
  const filas = lonjas.filter(l => !p.lonja || l.id === p.lonja).flatMap(l => l.precios.filter(x => x.clave === p.clave));
  if (!filas.length) return `${p.lonja ? esc(nombreLonja(p.lonja, lonjas)) : "Ninguna lonja"} no cotiza ${esc(nombreProd(p.clave).toLowerCase())} ahora mismo.`;
  const cuenta = {}; filas.forEach(x => { cuenta[x.unidad] = (cuenta[x.unidad] || 0) + 1; });
  const unidad = Object.keys(cuenta).sort((a, b) => cuenta[b] - cuenta[a])[0];
  const vals = filas.filter(x => x.unidad === unidad).map(x => x.act), ref = vals.reduce((s, x) => s + x, 0) / vals.length;
  if (p.umbral < ref / 3 || p.umbral > ref * 3) {
    return `¿Seguro? ${esc(nombreProd(p.clave))} está ahora a unos ${precio(Math.round(ref * 1000) / 1000, unidad)} ${esc(unidad)}. Escribe el precio en ${esc(unidad)}.`;
  }
  const a = { clave: p.clave, lonja: p.lonja, dir: p.dir || (p.umbral >= ref ? "sube" : "baja"), umbral: p.umbral, unidad, armado: true,
    creado: new Date().toISOString().slice(0, 10) };
  const e = evaluarAviso(a, lonjas);
  if (e && e.cumple) a.armado = false;
  lista.push(a);
  await alm.guardar(chat, lista);
  return [`✅ Aviso ${lista.length} creado: ${textoAviso(a, lonjas)}.`,
    e ? `Ahora: ${precio(e.fila.act, e.fila.unidad)} ${esc(e.fila.unidad)} (${esc(corto(e.fila.l.nombre))}, ${fecha(e.fila.l.fecha)}).` : "",
    a.armado ? "Te escribiré en cuanto una sesión llegue a ese precio." : "Ya se cumple ahora: te escribiré cuando vuelva a cruzar ese precio.",
    "Ver tus avisos: /avisos"].filter(Boolean).join("\n");
}

async function procesar(textoCrudo, msg, lonjas, web, alm) {
  const t = norm(String(textoCrudo || "").replace(/^\/([a-z_]+)(@\w+)?/i, "$1")).slice(0, 120);
  if (t === "miid") {
    return `Tu número de chat es <code>${esc(String(msg.chat.id))}</code>.\nPara recibir aquí lo que publica el robot de redes, guárdalo en GitHub como secreto <b>TELEGRAM_ADMIN_CHAT</b>. No es una contraseña, pero no hace falta compartirlo.`;
  }
  if (/^(aviso|avisos|avisame|mis avisos|borrar|quitar)\b/.test(t)) {
    try { return await procesarAvisos(t, textoCrudo, msg, lonjas, alm); }
    catch { return "No he podido guardar o leer tus avisos ahora mismo. Prueba en unos minutos."; }
  }
  return responder(textoCrudo, lonjas, web);
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
  await contarBot(msg.chat.id);
  let texto;
  try {
    const web = origenDe(req);
    texto = await procesar(msg.text, msg, await cargar(web), web, almacen());
  } catch {
    texto = "Ahora mismo no puedo leer los precios. Prueba en unos minutos.";
  }
  return res.status(200).json({ method: "sendMessage", chat_id: msg.chat.id, text: texto.slice(0, 4000), parse_mode: "HTML",
    disable_web_page_preview: true, ...(privado ? {} : { reply_to_message_id: msg.message_id }) });
}

module.exports = manejador;
module.exports.responder = responder;
module.exports.sanear = sanear;
module.exports.leerAviso = leerAviso;
module.exports.evaluarAviso = evaluarAviso;

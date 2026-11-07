// Pruebas del robot de Telegram de Vercel (api/telegram.js). Uso: node scraper/pruebas/js/test_telegram_api.js
"use strict";
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const RAIZ = path.resolve(__dirname, "../../..");
const api = require(path.join(RAIZ, "api/telegram.js"));
const datos = JSON.parse(fs.readFileSync(path.join(RAIZ, "data/precios.json"), "utf8"));
let pedidas = 0;
const redis = new Map(), sets = new Map();
const REDIS_URL = "https://redis.example";
global.fetch = async (url, op = {}) => {
  if (String(url) === REDIS_URL) {                       // Upstash simulado (API REST: ["CMD", ...args])
    assert.strictEqual(op.headers.authorization, "Bearer tok");
    const [c, k, v] = JSON.parse(op.body);
    let result = null;
    if (c === "GET") result = redis.has(k) ? redis.get(k) : null;
    else if (c === "SET") { redis.set(k, v); result = "OK"; }
    else if (c === "DEL") { result = redis.delete(k) ? 1 : 0; }
    else if (c === "SADD") { (sets.get(k) || sets.set(k, new Set()).get(k)).add(v); result = 1; }
    else if (c === "SREM") { sets.get(k)?.delete(v); result = 1; }
    return { ok: true, json: async () => ({ result }) };
  }
  pedidas++; assert.strictEqual(String(url), "https://lonjas.example/data/precios.json"); return { ok: true, json: async () => datos };
};

function llamar(body, cab = {}, metodo = "POST") {
  return new Promise(resolve => {
    const res = { _s: 200, status(s) { this._s = s; return this; }, json(j) { resolve({ s: this._s, j }); return this; } };
    api({ method: metodo, headers: { host: "lonjas.example", ...cab }, body }, res);
  });
}
const ok = { "x-telegram-bot-api-secret-token": "s".repeat(32) };
const msg = (text, type = "private") => ({ update_id: 1, message: { message_id: 7, chat: { id: 42, type }, text } });

(async () => {
  process.env.TELEGRAM_SECRETO = "s".repeat(32);
  assert.strictEqual((await llamar(msg("trigo"), {}, "GET")).s, 405);
  assert.strictEqual((await llamar(msg("trigo"), {})).s, 401);                                  // sin clave
  assert.strictEqual((await llamar(msg("trigo"), { "x-telegram-bot-api-secret-token": "mala-clave-de-32-caracteres-xxxx" })).s, 401);

  let r = await llamar(msg("Trigo"), ok);
  assert.strictEqual(r.s, 200); assert.strictEqual(r.j.method, "sendMessage"); assert.strictEqual(r.j.chat_id, 42);
  assert.match(r.j.text, /<b>Trigo<\/b> · €\/t/); assert.match(r.j.text, /Salamanca: <b>236<\/b> ▼ −2/);
  assert.match(r.j.text, /precio\/trigo\//);
  r = await llamar(msg("/maiz@LonjasCyLBot"), ok); assert.match(r.j.text, /<b>Maíz<\/b>/);
  r = await llamar(msg("león"), ok); assert.match(r.j.text, /Lonja de León<\/b> · sesión del 4 nov/); assert.match(r.j.text, /lonja\/leon\//);
  r = await llamar(msg("/lonjas"), ok); assert.match(r.j.text, /Lonja de Segovia: 5 nov/);
  r = await llamar(msg("corderos"), ok); assert.match(r.j.text, /Cordero/);
  r = await llamar(msg("alubias"), ok); assert.match(r.j.text, /León · Alubias · Canela: <b>1,30<\/b>/);
  r = await llamar(msg("<script>alert(1)</script>"), ok); assert.ok(!r.j.text.includes("<script>")); assert.match(r.j.text, /No he encontrado/);
  r = await llamar(msg("/start"), ok); assert.match(r.j.text, /Escríbeme un producto/);
  r = await llamar(msg("hola a todos", "group"), ok); assert.deepStrictEqual(r.j, {});            // en grupos, solo comandos
  r = await llamar(msg("/trigo", "group"), ok); assert.strictEqual(r.j.reply_to_message_id, 7);
  r = await llamar({ update_id: 2, edited_message: {} }, ok); assert.deepStrictEqual(r.j, {});
  r = await llamar(JSON.stringify(msg("cebada")), ok); assert.match(r.j.text, /<b>Cebada<\/b>/);  // cuerpo como texto
  assert.strictEqual(pedidas, 1);                                                                // caché de 5 minutos

  // ---- avisos personales ----
  r = await llamar(msg("/aviso trigo salamanca 240"), ok); assert.match(r.j.text, /aún no están activados/);   // sin almacén
  process.env.UPSTASH_REDIS_REST_URL = REDIS_URL; process.env.UPSTASH_REDIS_REST_TOKEN = "tok";
  assert.deepStrictEqual(api.leerAviso("trigo salamanca más de 240"), { clave: "trigo", lonja: "salamanca", dir: "sube", umbral: 240 });
  assert.deepStrictEqual(api.leerAviso("cerdo selecto baja de 1,10"), { clave: "cerdo-selecto", lonja: null, dir: "baja", umbral: 1.1 });
  assert.deepStrictEqual(api.leerAviso("Cebada < 200 León"), { clave: "cebada", lonja: "leon", dir: "baja", umbral: 200 });
  assert.ok(api.leerAviso("salamanca 240").error);
  r = await llamar(msg("/aviso"), ok); assert.match(r.j.text, /Avisos de precio/);
  r = await llamar(msg("/aviso trigo salamanca 240"), ok);
  assert.match(r.j.text, /Aviso 1 creado: Trigo en Salamanca · suba a 240 €\/t o más/); assert.match(r.j.text, /Ahora: 236/);
  r = await llamar(msg("/aviso cerdo baja de 1,10"), ok); assert.match(r.j.text, /Aviso 2 creado: Cerdo normal en cualquier lonja · baje a 1,10 €\/kg vivo/);
  r = await llamar(msg("/aviso trigo 200"), ok); assert.match(r.j.text, /baje a 200/);              // sin dirección: por debajo del precio actual
  r = await llamar(msg("/aviso trigo 0,24"), ok); assert.match(r.j.text, /¿Seguro\?/);               // unidad equivocada
  r = await llamar(msg("/aviso trigo segovia sube a 220"), ok); assert.match(r.j.text, /Ya se cumple ahora/);
  const guardados = JSON.parse(redis.get("avisos:42"));
  assert.strictEqual(guardados.length, 4); assert.strictEqual(guardados[3].armado, false); assert.ok(sets.get("avisos:chats").has("42"));
  r = await llamar(msg("/avisos"), ok); assert.match(r.j.text, /1\. Trigo en Salamanca/); assert.match(r.j.text, /4\. Trigo en Segovia/);
  r = await llamar(msg("/borrar 2"), ok); assert.match(r.j.text, /Borrado: Cerdo normal/);
  assert.strictEqual(JSON.parse(redis.get("avisos:42")).length, 3);
  r = await llamar(msg("/borrar 9"), ok); assert.match(r.j.text, /No tienes el aviso 9/);
  r = await llamar(msg("/aviso trigo 240", "group"), ok); assert.match(r.j.text, /en privado/);
  r = await llamar(msg("/borrar todos"), ok); assert.match(r.j.text, /borrado todos/);
  assert.ok(!redis.has("avisos:42") && !sets.get("avisos:chats").has("42"));
  r = await llamar(msg("/avisos"), ok); assert.match(r.j.text, /No tienes avisos/);
  for (const t of ["trigo", "lechazo", "salamanca", "alubia", "vacas", "ovejas"]) {
    const x = (await llamar(msg(t), ok)).j.text; assert.ok(x.length < 4000, t); console.log(`— ${t}\n${x}\n`);
  }
  console.log("OK: todas las pruebas del robot de Telegram pasan");
})().catch(e => { console.error(e); process.exit(1); });

// Pruebas del robot de Telegram de Vercel (api/telegram.js). Uso: node scraper/pruebas/js/test_telegram_api.js
"use strict";
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const RAIZ = path.resolve(__dirname, "../../..");
const api = require(path.join(RAIZ, "api/telegram.js"));
const datos = JSON.parse(fs.readFileSync(path.join(RAIZ, "data/precios.json"), "utf8"));
let pedidas = 0;
global.fetch = async url => { pedidas++; assert.strictEqual(String(url), "https://lonjas.example/data/precios.json"); return { ok: true, json: async () => datos }; };

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
  for (const t of ["trigo", "lechazo", "salamanca", "alubia", "vacas", "ovejas"]) {
    const x = (await llamar(msg(t), ok)).j.text; assert.ok(x.length < 4000, t); console.log(`— ${t}\n${x}\n`);
  }
  console.log("OK: todas las pruebas del robot de Telegram pasan");
})().catch(e => { console.error(e); process.exit(1); });

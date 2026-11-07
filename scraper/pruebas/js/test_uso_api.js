// Pruebas del contador de visitas y del panel (api/uso.js y api/estadisticas.js). Uso: node scraper/pruebas/js/test_uso_api.js
"use strict";
const assert = require("assert");
const path = require("path");
const RAIZ = path.resolve(__dirname, "../../..");
process.env.UPSTASH_REDIS_REST_URL = "https://redis.example"; process.env.UPSTASH_REDIS_REST_TOKEN = "tok"; process.env.PANEL_CLAVE = "una-clave-larga-1";
const H = new Map(), HLL = new Map();
let comandos = [];
global.fetch = async (url, op) => {
  assert.strictEqual(String(url), "https://redis.example/pipeline");
  const cmds = JSON.parse(op.body); comandos.push(...cmds);
  return { ok: true, json: async () => cmds.map(([c, k, ...a]) => {
    if (c === "HINCRBY") { const h = H.get(k) || H.set(k, {}).get(k); h[a[0]] = (h[a[0]] || 0) + a[1]; return { result: h[a[0]] }; }
    if (c === "HGETALL") return { result: Object.entries(H.get(k) || {}).flat().map(String) };
    if (c === "PFADD") { (HLL.get(k) || HLL.set(k, new Set()).get(k)).add(a[0]); return { result: 1 }; }
    if (c === "PFCOUNT") { const u = new Set(); [k, ...a].forEach(x => (HLL.get(x) || []).forEach(v => u.add(v))); return { result: u.size }; }
    if (c === "SCARD") return { result: 3 };
    return { result: 1 };
  }) };
};
const uso = require(path.join(RAIZ, "api/uso.js"));
const est = require(path.join(RAIZ, "api/estadisticas.js"));
const MOVIL = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36";
function llamar(h, { metodo = "POST", body, cab = {}, url = "/api/uso" } = {}) {
  return new Promise(resolve => {
    const res = { _s: 200, h: {}, status(s) { this._s = s; return this; }, json(j) { resolve({ s: this._s, j }); return this; }, end() { resolve({ s: this._s }); return this; }, setHeader(k, v) { this.h[k] = v; } };
    h({ method: metodo, url, query: Object.fromEntries(new URL(url, "https://x").searchParams), body,
      headers: { host: "lonjas.example", origin: "https://lonjas.example", "sec-fetch-site": "same-origin", "user-agent": MOVIL, "x-forwarded-for": "198.51.100.4", "x-vercel-ip-country": "ES", ...cab } }, res);
  });
}
(async () => {
  // Contador
  assert.strictEqual((await llamar(uso, { metodo: "GET" })).s, 405);
  assert.strictEqual((await llamar(uso, { body: '{"t":"e","r":"hoy"}', cab: { origin: "https://malo.example" } })).s, 403);
  assert.strictEqual((await llamar(uso, { body: '{"t":"e","r":"hoy"}', cab: { "sec-fetch-site": "cross-site" } })).s, 403);
  assert.strictEqual((await llamar(uso, { body: '{"t":"e","r":"../../etc"}' })).s, 400);
  assert.strictEqual((await llamar(uso, { body: "{no es json" })).s, 400);
  comandos = [];
  assert.strictEqual((await llamar(uso, { body: '{"t":"e","r":"hoy"}', cab: { "user-agent": "Googlebot/2.1" } })).s, 204);
  assert.strictEqual(comandos.length, 0);                                                   // los robots no cuentan
  assert.strictEqual((await llamar(uso, { body: JSON.stringify({ t: "e", r: "web:precio-trigo", o: "google.es", i: false }) })).s, 204);
  assert.strictEqual((await llamar(uso, { body: '{"t":"v","r":"oferta"}' })).s, 204);
  assert.strictEqual((await llamar(uso, { body: JSON.stringify({ t: "e", r: "hoy", o: "t.me", i: true }), cab: { "x-forwarded-for": "198.51.100.9" } })).s, 204);
  assert.strictEqual((await llamar(uso, { body: JSON.stringify({ t: "e", r: "widget", o: "cooperativa.es" }) })).s, 204);
  assert.strictEqual((await llamar(uso, { body: JSON.stringify({ t: "e", r: "hoy", o: "blog-agricola.es" }), cab: { "x-forwarded-for": "198.51.100.20" } })).s, 204);
  const todo = JSON.stringify([...H.entries()]) + JSON.stringify([...HLL.entries()].map(([k, v]) => [k, [...v]]));
  assert.ok(!todo.includes("198.51.100"), "la IP nunca se guarda");
  assert.deepStrictEqual([uso.grupoOrigen("google.es", "x"), uso.grupoOrigen("l.instagram.com", "x"), uso.grupoOrigen("", "x"), uso.grupoOrigen("x", "x")],
    ["google", "instagram", "directo", "interno"]);
  assert.deepStrictEqual([uso.aparato(MOVIL), uso.aparato("Mozilla/5.0 (iPad; CPU OS 17)"), uso.aparato("Mozilla/5.0 (Windows NT 10.0)")], ["movil", "tableta", "ordenador"]);

  // Panel
  assert.strictEqual((await llamar(est, { metodo: "GET", url: "/api/estadisticas" })).s, 401);
  const mala = await llamar(est, { metodo: "GET", url: "/api/estadisticas", cab: { authorization: "Bearer otra-clave-larga" } });
  assert.strictEqual(mala.s, 401);
  const r = await llamar(est, { metodo: "GET", url: "/api/estadisticas?dias=7", cab: { authorization: "Bearer una-clave-larga-1" } });
  assert.strictEqual(r.s, 200);
  const j = r.j;
  assert.strictEqual(j.dias, 7); assert.strictEqual(j.porDia.length, 7);
  const hoy = j.porDia.at(-1);
  assert.strictEqual(hoy.personas, 3); assert.strictEqual(hoy.visitas, 4); assert.strictEqual(hoy.vistas, 5); assert.strictEqual(hoy.instalada, 1);
  assert.strictEqual(j.resumen.personas_7, 3); assert.strictEqual(j.resumen.avisos_personas, 3);
  const o = Object.fromEntries(j.origenes.map(x => [x.k, x.v]));
  assert.deepStrictEqual(o, { google: 1, telegram: 1, widget: 1, otras: 1 });
  assert.deepStrictEqual(j.widget, [{ k: "cooperativa.es", v: 1 }]); assert.deepStrictEqual(j.webs, [{ k: "blog-agricola.es", v: 1 }]);
  assert.ok(j.rutas.some(x => x.k === "web:precio-trigo") && j.rutas.some(x => x.k === "oferta"));
  assert.deepStrictEqual(j.paises, [{ k: "ES", v: 4 }]);
  console.log("OK: todas las pruebas del contador y del panel pasan");
})().catch(e => { console.error(e); process.exit(1); });

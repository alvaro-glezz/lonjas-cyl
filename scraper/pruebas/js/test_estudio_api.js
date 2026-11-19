// Pruebas de /api/estudio (fichas del Estudio). Uso: node scraper/pruebas/js/test_estudio_api.js
"use strict";
const assert = require("assert");
const path = require("path");
const api = require(path.resolve(__dirname, "../../../api/estudio.js"));
const hash = new Map(), kv = new Map();
global.fetch = async (url, op) => {
  assert.strictEqual(String(url), "https://redis.example/pipeline");
  const res = JSON.parse(op.body).map(([c, k, a, b]) => {
    if (c === "HGETALL") return [...hash].flat();
    if (c === "HLEN") return hash.size;
    if (c === "HEXISTS") return hash.has(a) ? 1 : 0;
    if (c === "HSET") { hash.set(a, b); return 1; }
    if (c === "HDEL") return hash.delete(a) ? 1 : 0;
    if (c === "SET") { kv.set(k, a); return "OK"; }
    throw new Error(c);
  });
  return { ok: true, json: async () => res.map(result => ({ result })) };
};
const llamar = (metodo, body, clave = "c".repeat(16)) => new Promise(resolve => {
  const res = { _s: 200, setHeader() {}, status(s) { this._s = s; return this; }, json(j) { resolve({ s: this._s, j }); return this; } };
  api({ method: metodo, headers: { authorization: "Bearer " + clave }, body }, res);
});
(async () => {
  process.env.PANEL_CLAVE = "c".repeat(16);
  process.env.UPSTASH_REDIS_REST_URL = "https://redis.example"; process.env.UPSTASH_REDIS_REST_TOKEN = "t";
  assert.strictEqual((await llamar("GET", null, "mala-clave-larga")).s, 401);
  assert.strictEqual((await llamar("DELETE")).s, 405);
  let r = await llamar("POST", { accion: "guardar", ficha: { titulo: "", escenas: [] } }); assert.strictEqual(r.s, 400);
  r = await llamar("POST", { accion: "guardar", ficha: { titulo: "Hola", escenas: [{ titulo: "Uno", texto: "x".repeat(500) }], fecha: "2026-11-20",
    estado: "programado", etiquetas: "campo, #lonja <script>", extra: "fuera" } });
  assert.strictEqual(r.s, 200);
  const f = r.j.ficha;
  assert.match(f.id, /^[a-z0-9]{12}$/); assert.strictEqual(f.escenas[0].texto.length, 160); assert.strictEqual(f.estado, "programado");
  assert.strictEqual(f.etiquetas, "#campo #lonja #script"); assert.ok(!("extra" in f));
  r = await llamar("POST", { accion: "guardar", ficha: { ...f, fecha: "", titulo: "Hola 2" } });
  assert.strictEqual(r.j.ficha.id, f.id); assert.strictEqual(r.j.ficha.estado, "borrador");       // sin fecha no se programa
  r = await llamar("GET"); assert.strictEqual(r.j.fichas.length, 1); assert.strictEqual(r.j.fichas[0].titulo, "Hola 2");
  r = await llamar("POST", { accion: "previa", id: f.id }); assert.strictEqual(r.s, 200); assert.strictEqual(kv.get("redes:previa_ficha"), f.id);
  r = await llamar("POST", { accion: "previa", id: "noexiste1" }); assert.strictEqual(r.s, 404);
  r = await llamar("POST", { accion: "borrar", id: "../x" }); assert.strictEqual(r.s, 400);
  r = await llamar("POST", { accion: "borrar", id: f.id }); assert.strictEqual(r.s, 200); assert.strictEqual(hash.size, 0);
  console.log("OK: /api/estudio");
})().catch(e => { console.error(e); process.exit(1); });

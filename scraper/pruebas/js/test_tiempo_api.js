// Pruebas de la previsión de AEMET (api/tiempo.js). Uso: node scraper/pruebas/js/test_tiempo_api.js
"use strict";
const assert = require("assert");
const path = require("path");
const RAIZ = path.resolve(__dirname, "../../..");

const horas = (desde, hasta, f) => Array.from({ length: hasta - desde + 1 }, (_, i) => f(desde + i));
const pad = h => String(h).padStart(2, "0");
const PREV = [{
  elaborado: "2026-11-11T09:11:24", nombre: "Peñafiel", provincia: "Valladolid", id: "47114",
  prediccion: { dia: [{
    fecha: "2026-11-11T00:00:00", orto: "08:17", ocaso: "18:07",
    estadoCielo: horas(10, 23, h => ({ value: h < 18 ? "12" : "11n", periodo: pad(h), descripcion: "x" })),
    precipitacion: horas(10, 23, h => ({ value: h === 15 ? "Ip" : h === 20 ? "1,5" : "0", periodo: pad(h) })),
    probPrecipitacion: [{ value: "", periodo: "0208" }, { value: "10", periodo: "0814" }, { value: "70", periodo: "1420" }, { value: "20", periodo: "2002" }],
    temperatura: horas(10, 23, h => ({ value: String(20 - Math.abs(h - 15)), periodo: pad(h) })),
    humedadRelativa: horas(10, 23, h => ({ value: "60", periodo: pad(h) })),
    vientoAndRachaMax: horas(10, 23, h => [{ direccion: ["NE"], velocidad: [String(h)], periodo: pad(h) }, { value: String(h + 10), periodo: pad(h) }]).flat(),
  }, {
    fecha: "2026-11-12T00:00:00", orto: "08:18", ocaso: "18:06",
    estadoCielo: horas(0, 23, h => ({ value: h === 12 ? "54" : "14", periodo: pad(h) })),
    precipitacion: horas(0, 23, h => ({ value: "0", periodo: pad(h) })),
    probPrecipitacion: [{ value: "0", periodo: "0208" }],
    temperatura: horas(0, 23, h => ({ value: "5", periodo: pad(h) })),
    humedadRelativa: horas(0, 23, h => ({ value: "90", periodo: pad(h) })),
    vientoAndRachaMax: horas(0, 23, h => [{ direccion: ["C"], velocidad: ["0"], periodo: pad(h) }, { value: "", periodo: pad(h) }]).flat(),
  }, {
    fecha: "2026-11-13T00:00:00", orto: "08:19", ocaso: "18:05",
    temperatura: horas(0, 6, h => ({ value: "4", periodo: pad(h) })),
  }] },
}];
const MAESTRO = [
  { id: "id47114", nombre: "Peñafiel", latitud_dec: "41.5997", longitud_dec: "-4.1172" },
  { id: "id05019", nombre: "Ávila", latitud_dec: "40.6564", longitud_dec: "-4.6997" },
  { id: "id28079", nombre: "Madrid", latitud_dec: "40.41", longitud_dec: "-3.70" },
  { id: "raro", nombre: "x" },
  ...Array.from({ length: 120 }, (_, i) => ({ id: "id09" + String(i + 1).padStart(3, "0"), nombre: "Pueblo " + i, latitud_dec: "42", longitud_dec: "-3.7" })),
];

let llamadas = [];
const latin1 = s => Uint8Array.from(Buffer.from(s, "latin1")).buffer;
const utf8 = s => Uint8Array.from(Buffer.from(s, "utf8")).buffer;
global.fetch = async (url, op = {}) => {
  url = String(url); llamadas.push({ url, op });
  if (url.startsWith("https://opendata.aemet.es/opendata/api/")) {
    assert.strictEqual(op.headers.api_key, "clave-de-prueba-123456789");
    if (url.endsWith("/horaria/47114")) return { ok: true, json: async () => ({ estado: 200, datos: "https://opendata.aemet.es/opendata/sh/prev" }) };
    if (url.endsWith("/horaria/47999")) return { ok: true, json: async () => ({ estado: 404, descripcion: "No hay datos" }) };
    if (url.endsWith("/horaria/47998")) return { ok: true, json: async () => ({ estado: 429 }) };
    if (url.endsWith("/maestro/municipios")) return { ok: true, json: async () => ({ estado: 200, datos: "https://opendata.aemet.es/opendata/sh/muni" }) };
  }
  if (url === "https://opendata.aemet.es/opendata/sh/prev") return { ok: true, arrayBuffer: async () => utf8(JSON.stringify(PREV)) };   // como llega de verdad
  if (url === "https://opendata.aemet.es/opendata/sh/muni") return { ok: true, arrayBuffer: async () => latin1(JSON.stringify(MAESTRO)) };
  throw new Error("URL inesperada " + url);
};
const tiempo = require(path.join(RAIZ, "api/tiempo.js"));

function llamar(url, metodo = "GET") {
  return new Promise(resolve => {
    const res = { _s: 200, h: {}, status(s) { this._s = s; return this; }, json(j) { resolve({ s: this._s, j, h: this.h }); return this; }, setHeader(k, v) { this.h[k] = v; } };
    tiempo({ method: metodo, url, query: Object.fromEntries(new URL(url, "https://x").searchParams), headers: {} }, res);
  });
}

(async () => {
  // sin clave: 503 y no se llama a AEMET
  delete process.env.AEMET_API_KEY;
  let r = await llamar("/api/tiempo?m=47114");
  assert.strictEqual(r.s, 503); assert.strictEqual(r.j.error, "sin-clave"); assert.strictEqual(llamadas.length, 0);

  process.env.AEMET_API_KEY = "clave-de-prueba-123456789";
  r = await llamar("/api/tiempo?m=47114");
  assert.strictEqual(r.s, 200, JSON.stringify(r.j));
  const d = r.j, H = d.hourly;
  assert.strictEqual(d.fuente, "aemet"); assert.strictEqual(d.municipio, "Peñafiel"); assert.strictEqual(d.codigo, "47114");
  assert.strictEqual(H.time.length, 14 + 24); assert.strictEqual(H.time[0], "2026-11-11T10:00");
  const i15 = H.time.indexOf("2026-11-11T15:00"), i20 = H.time.indexOf("2026-11-11T20:00"), i10 = 0;
  assert.strictEqual(H.temperature_2m[i15], 20);
  assert.strictEqual(H.precipitation[i15], 0.05);                 // «Ip»
  assert.strictEqual(H.precipitation[i20], 1.5);                  // coma decimal
  assert.strictEqual(H.precipitation_probability[i10], 10);       // tramo 08-14
  assert.strictEqual(H.precipitation_probability[i15], 70);       // tramo 14-20
  assert.strictEqual(H.precipitation_probability[i20], 20);       // tramo 20-02
  assert.strictEqual(H.wind_speed_10m[i15], 15); assert.strictEqual(H.wind_gusts_10m[i15], 25);
  assert.strictEqual(H.is_day[i15], 1); assert.strictEqual(H.is_day[i20], 0);
  assert.strictEqual(H.weather_code[i15], 1); assert.strictEqual(H.weather_code[i20], 0);
  const j12 = H.time.indexOf("2026-11-12T12:00");
  assert.strictEqual(H.wind_gusts_10m[j12], 0);                    // racha vacía
  assert.strictEqual(H.weather_code[j12], 95);                     // tormenta
  assert.deepStrictEqual(d.daily.time, ["2026-11-11", "2026-11-12"]);   // el 13 solo tenía madrugada: fuera
  assert.ok(!H.time.some(t => t.startsWith("2026-11-13")));
  assert.strictEqual(d.daily.temperature_2m_max[0], 20); assert.strictEqual(d.daily.temperature_2m_min[0], 12);
  assert.strictEqual(d.daily.precipitation_sum[0], 1.6); assert.strictEqual(d.daily.wind_speed_10m_max[0], 23);
  assert.strictEqual(d.daily.weather_code[1], 95);
  assert.match(r.h["Cache-Control"], /s-maxage=1800/);

  // municipios no válidos o de fuera de Castilla y León
  for (const m of ["28079", "4711", "47114x", ""]) assert.strictEqual((await llamar("/api/tiempo?m=" + m)).s, 400);
  assert.strictEqual((await llamar("/api/tiempo?m=47999")).s, 404);
  r = await llamar("/api/tiempo?m=47998");
  assert.strictEqual(r.s, 502); assert.strictEqual(r.j.error, "aemet-limite"); assert.strictEqual(r.h["Cache-Control"], "no-store");
  assert.strictEqual((await llamar("/api/tiempo?m=47114", "POST")).s, 405);

  // lista de municipios: solo Castilla y León, ordenada, con tildes bien leídas (ISO-8859-15)
  r = await llamar("/api/tiempo?lista=1");
  assert.strictEqual(r.s, 200);
  const l = r.j.municipios;
  assert.strictEqual(l.length, 122);
  assert.deepStrictEqual(l[0], { c: "05019", n: "Ávila", p: "Ávila", la: 40.656, lo: -4.7 });
  assert.ok(l.some(x => x.n === "Peñafiel" && x.p === "Valladolid"));
  assert.ok(!l.some(x => x.n === "Madrid"));
  assert.match(r.h["Cache-Control"], /s-maxage=604800/);

  // la clave nunca sale en la respuesta
  assert.ok(!JSON.stringify(r.j).includes("clave-de-prueba"));
  console.log("api/tiempo.js: todo bien");
})().catch(e => { console.error(e); process.exit(1); });

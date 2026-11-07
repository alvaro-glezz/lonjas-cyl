"use strict";
/* Acceso a Upstash Redis por su API REST (lo comparten /api/uso, /api/estadisticas y el robot de Telegram).
   El «_» del nombre hace que Vercel no lo publique como dirección propia.
   Variables: UPSTASH_REDIS_REST_URL y UPSTASH_REDIS_REST_TOKEN, o las KV_REST_API_* que crea Vercel. */

function config() {
  const url = (process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL || "").replace(/\/$/, "");
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN || "";
  return /^https:\/\/[a-z0-9.-]+$/i.test(url) && token ? { url, token } : null;
}

/** Varios comandos en una sola petición. Devuelve los resultados en el mismo orden. */
async function pipeline(cmds) {
  const c = config();
  if (!c) throw new Error("sin almacén");
  const r = await fetch(c.url + "/pipeline", {
    method: "POST", headers: { authorization: `Bearer ${c.token}`, "content-type": "application/json" }, body: JSON.stringify(cmds),
  });
  const j = await r.json().catch(() => null);
  if (!r.ok || !Array.isArray(j)) throw new Error("almacén");
  return j.map(x => (x && "result" in x ? x.result : null));
}

/** Fecha de hoy en España (AAAA-MM-DD): los días del panel van de medianoche a medianoche peninsular. */
function hoyMadrid(d = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
}

module.exports = { config, pipeline, hoyMadrid };

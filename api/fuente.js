"use strict";
/* Copia de la página de precios de la Lonja de Lerma para el robot (/api/fuente?l=lerma).
   Desde el 17 nov 2026 la web de Lerma rechaza (403) las peticiones que llegan desde los servidores de GitHub, donde
   corre el robot; desde Vercel sí responde. El robot pide aquí la página y la lee igual que siempre.
   Solo sirve esa página fija (no es un proxy abierto) y la CDN la guarda 15 minutos, así que a la web de Lerma le
   llegan muy pocas peticiones. */

const FUENTES = { lerma: "https://lerma.burgos.es/lonja" };

module.exports = async (req, res) => {
  const id = String(req.query?.l || "");
  const url = FUENTES[id];
  if (!url) { res.statusCode = 404; return res.end("Fuente desconocida"); }
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), 20000);
  try {
    const r = await fetch(url, { signal: c.signal, headers: { "User-Agent": "AppLonjasCyL/1.0 (lector semanal de cotizaciones publicas)", "Accept-Language": "es-ES,es;q=0.9" } });
    const cuerpo = Buffer.from(await r.arrayBuffer());
    res.statusCode = r.ok ? 200 : 502;
    res.setHeader("Content-Type", r.headers.get("content-type") || "text/html; charset=utf-8");
    res.setHeader("X-Origen-Estado", String(r.status));
    res.setHeader("Cache-Control", r.ok ? "public, s-maxage=900, stale-while-revalidate=3600" : "no-store");
    res.setHeader("X-Robots-Tag", "noindex");
    return res.end(r.ok ? cuerpo : `La web de origen respondió ${r.status}`);
  } catch (e) {
    res.statusCode = 504; res.setHeader("Cache-Control", "no-store");
    return res.end("No se pudo leer la web de origen");
  } finally { clearTimeout(t); }
};

// Funciona sin cobertura: guarda la app y los últimos precios descargados.
// Seguridad: solo se guardan respuestas correctas (200) del propio dominio; así un error 404/500 puntual
// no se queda "pegado" en la copia sin conexión.
const VERSION = "lonjas-v13";
const AJUSTES = "lonjas-ajustes";   // avisos y ajustes que guarda la app (no se borran al actualizar)
const APP = ["./", "index.html", "estilos.css", "app.js", "historico.js", "agricultor.js", "plazos.js", "abiertos.js", "herramientas.js", "contador.js", "manifest.webmanifest", "icons/icono.svg", "icons/icono-192.png",
  "fonts/barlow-condensed-latin-500-normal.woff2", "fonts/barlow-condensed-latin-600-normal.woff2", "fonts/barlow-condensed-latin-700-normal.woff2",
  "fonts/public-sans-latin-400-normal.woff2", "fonts/public-sans-latin-500-normal.woff2", "fonts/public-sans-latin-600-normal.woff2", "fonts/public-sans-latin-700-normal.woff2"];

const guardable = r => r && r.ok && r.type === "basic";

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(APP)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION && k !== AJUSTES).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  // Funciones del servidor y panel privado: nunca se guardan copias en el teléfono
  if (/\/(api|panel)\//.test(url.pathname)) return;
  // Precios: primero la red (siempre lo más nuevo); si no hay red, la copia guardada
  if (url.pathname.endsWith("/data/precios.json")) {
    e.respondWith(fetch(e.request).then(r => {
      if (guardable(r)) { const copia = r.clone(); caches.open(VERSION).then(c => c.put("data/precios.json", copia)); }
      return r;
    }).catch(() => caches.match("data/precios.json")));
    return;
  }
  // Resto de la app: primero la copia guardada, y se refresca por detrás
  e.respondWith(caches.match(e.request).then(guardado => {
    const red = fetch(e.request).then(r => {
      if (guardable(r)) { const c = r.clone(); caches.open(VERSION).then(x => x.put(e.request, c)); }
      return r;
    }).catch(() => guardado);
    return guardado || red;
  }));
});

/* ---------- avisos de precio con la app cerrada ----------
   En Android, con la app instalada, el teléfono despierta al service worker de vez en cuando («periodicsync»).
   Se descargan los precios, se comprueban los avisos guardados por la app y se notifica lo que se cumpla
   (una vez por sesión de la lonja). Los lunes, si se ha pedido, se avisa de que el resumen semanal está listo. */
self.addEventListener("periodicsync", e => {
  if (e.tag === "comprobar-avisos") e.waitUntil(comprobarEnSegundoPlano());
});
const fmt = v => typeof v === "number" ? v.toLocaleString("es-ES", { maximumFractionDigits: 3 }) : "S/C";
async function comprobarEnSegundoPlano() {
  const cache = await caches.open(AJUSTES);
  const r = await cache.match("ajustes/avisos.json");
  if (!r) return;
  const cfg = await r.json().catch(() => null);
  if (!cfg || !Array.isArray(cfg.avisos)) return;
  const resp = await fetch("data/precios.json", { cache: "no-cache" }).catch(() => null);
  if (!resp || !resp.ok) return;
  const datos = await resp.clone().json().catch(() => null);
  if (!datos || !Array.isArray(datos.lonjas)) return;
  if (guardable(resp)) (await caches.open(VERSION)).put("data/precios.json", resp);
  const filas = new Map();
  for (const l of datos.lonjas) for (const f of (Array.isArray(l.precios) ? l.precios : [])) {
    if (f && typeof f.id === "string") filas.set(f.id, { f, l });
  }
  let cambio = false;
  for (const a of cfg.avisos) {
    const x = a && filas.get(a.fila);
    if (!x || typeof x.f.act !== "number" || typeof a.umbral !== "number") continue;
    // Suena al cruzar el precio; se rearma cuando vuelve al otro lado (igual que en la app)
    const cumple = a.tipo === "sube" ? x.f.act >= a.umbral : x.f.act <= a.umbral;
    const sesion = String(x.l.fecha || "").slice(0, 10);
    if (a.sesion !== sesion) { a.sesion = sesion; cambio = true; }
    if (!cumple) { if (a.notificado) { a.notificado = false; cambio = true; } continue; }
    if (a.notificado) continue;
    a.notificado = true; cambio = true;
    const lonja = String(x.l.nombre || "").replace(/^Lonja de(l)? /, "").slice(0, 40), u = String(x.f.unidad || "").slice(0, 20);
    await self.registration.showNotification(`${String(x.f.producto).slice(0, 60)} · ${lonja}: ${fmt(x.f.act)} ${u}`, {
      body: `Se cumple tu aviso: que ${a.tipo === "sube" ? "suba a" : "baje a"} ${fmt(a.umbral)} ${u} ${a.tipo === "sube" ? "o más" : "o menos"}.`,
      tag: String(a.id).slice(0, 30), icon: "icons/icono-192.png", badge: "icons/icono-192.png", data: { url: "./#favoritos" },
    });
  }
  // Resumen de los lunes
  const hoy = new Date(), dia = hoy.toISOString().slice(0, 10);
  if (cfg.ajustes && cfg.ajustes.resumenLunes && hoy.getDay() === 1 && cfg.resumenAvisado !== dia) {
    cfg.resumenAvisado = dia; cambio = true;
    await self.registration.showNotification("Tu resumen de la semana está listo", {
      body: "Qué ha subido, qué ha bajado y qué lonja paga más esta semana.", tag: "resumen-semanal",
      icon: "icons/icono-192.png", badge: "icons/icono-192.png", data: { url: "./#hoy" },
    });
  }
  if (cambio) await cache.put("ajustes/avisos.json", new Response(JSON.stringify(cfg), { headers: { "Content-Type": "application/json" } }));
}
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const destino = new URL((e.notification.data && e.notification.data.url) || "./", self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(cs => {
    const c = cs.find(x => x.url.startsWith(self.registration.scope));
    if (c) return c.focus().then(v => v.navigate ? v.navigate(destino) : v);
    return self.clients.openWindow(destino);
  }));
});

// Funciona sin cobertura: guarda la app y los últimos precios descargados.
// Seguridad: solo se guardan respuestas correctas (200) del propio dominio; así un error 404/500 puntual
// no se queda "pegado" en la copia sin conexión.
const VERSION = "lonjas-v6";
const APP = ["./", "index.html", "estilos.css", "app.js", "historico.js", "manifest.webmanifest", "icons/icono.svg", "icons/icono-192.png",
  "fonts/barlow-condensed-latin-500-normal.woff2", "fonts/barlow-condensed-latin-600-normal.woff2", "fonts/barlow-condensed-latin-700-normal.woff2",
  "fonts/public-sans-latin-400-normal.woff2", "fonts/public-sans-latin-500-normal.woff2", "fonts/public-sans-latin-600-normal.woff2", "fonts/public-sans-latin-700-normal.woff2"];

const guardable = r => r && r.ok && r.type === "basic";

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(APP)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
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

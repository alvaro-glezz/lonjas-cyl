// Funciona sin cobertura: guarda la app y los últimos precios descargados.
const VERSION = "lonjas-v1";
const APP = ["./", "index.html", "manifest.webmanifest", "icons/icono.svg", "icons/icono-192.png"];

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
      const copia = r.clone(); caches.open(VERSION).then(c => c.put("data/precios.json", copia)); return r;
    }).catch(() => caches.match("data/precios.json")));
    return;
  }
  // Resto de la app: primero la copia guardada, y se refresca por detrás
  e.respondWith(caches.match(e.request).then(guardado => {
    const red = fetch(e.request).then(r => { const c = r.clone(); caches.open(VERSION).then(x => x.put(e.request, c)); return r; }).catch(() => guardado);
    return guardado || red;
  }));
});

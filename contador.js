"use strict";
/* Contador anónimo de Lonjas CyL (lo usan la app, las páginas de precios y el widget).
   No usa cookies ni guarda nada que identifique a nadie: solo avisa a /api/uso de qué sección se ha visto.
   «Entrada» = primera página de la visita (lleva de qué web viene); el resto, «vista».
   No cuenta si el navegador pide no ser rastreado, ni fuera de la web principal (GitHub Pages, pruebas locales). */
(function () {
  const ok = location.protocol === "https:" && !/github\.io$|^localhost$|^127\./.test(location.hostname)
    && !(navigator.globalPrivacyControl || navigator.doNotTrack === "1" || navigator.webdriver);
  const raiz = (document.currentScript && document.currentScript.src) ? new URL(".", document.currentScript.src).href : location.origin + "/";
  const destino = raiz + "api/uso";
  let marcaSesion = false;
  try { marcaSesion = sessionStorage.getItem("lc-visita") === "1"; } catch { /* modo privado: cuenta como entrada */ }

  function enviar(datos) {
    if (!ok) return;
    const cuerpo = JSON.stringify(datos);
    try {
      if (navigator.sendBeacon && navigator.sendBeacon(destino, new Blob([cuerpo], { type: "text/plain" }))) return;
    } catch { /* se intenta con fetch */ }
    fetch(destino, { method: "POST", body: cuerpo, keepalive: true, credentials: "omit", headers: { "content-type": "text/plain" } }).catch(() => {});
  }
  function hostDe(url) { try { return url ? new URL(url).hostname.replace(/^www\./, "") : ""; } catch { return ""; } }

  /** ruta: «hoy», «oferta», «lonja-salamanca», «web:precio-trigo», «widget»… */
  function contar(ruta) {
    if (!ruta) return;
    if (!marcaSesion || ruta === "widget") {
      marcaSesion = true;
      try { sessionStorage.setItem("lc-visita", "1"); } catch { /* sin almacenamiento: solo se pierde el detalle */ }
      const instalada = window.matchMedia && window.matchMedia("(display-mode: standalone)").matches;
      enviar({ t: "e", r: ruta, o: hostDe(document.referrer), i: !!instalada });
    } else {
      enviar({ t: "v", r: ruta });
    }
  }
  window.LonjasUso = { contar };

  // Páginas estáticas y widget: se cuentan solas al cargar (la app avisa desde su router)
  const auto = document.currentScript && document.currentScript.dataset.ruta;
  if (auto) contar(auto);
})();

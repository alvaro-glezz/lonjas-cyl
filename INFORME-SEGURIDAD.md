# Revisión de seguridad: Lonjas CyL

**Fecha:** 2026-11-04 · **Método:** checklist `revisarseguridad.md` (OWASP, enfoque «vibecoder»)
**Stack:** PWA estática (HTML/JS sin framework) + robot en Python (requests, BeautifulSoup, pdfplumber) en GitHub Actions + GitHub Pages
**Resumen:** 1 hallazgo alto, 5 medios y 6 bajos. **Todos corregidos en el código** y comprobados con pruebas. Quedan 4 tareas que solo puedes hacer tú (final del documento).

**No aplican** (no existen en este proyecto): autenticación y sesiones, base de datos/SQL, subida de archivos, IA/prompts, cookies, CORS. No hay claves ni contraseñas en el código ni en el historial de archivos (revisado); los resultados de `token` en el barrido son una variable del analizador de texto.

---

## ALTO

### A1. El robot descargaba cualquier dirección y sin límites
**Dónde:** `scraper/actualizar.py` (`bajar`, `enlaces_pdf`, `texto_pdf`)
**Problema:** las direcciones de los PDF salen del HTML de las webs de las lonjas y se descargaban sin comprobar el dominio (una web comprometida podía apuntar al robot a otro destino, p. ej. servicios internos del ejecutor). Tampoco había tope de tamaño, de páginas ni comprobación de que el archivo fuera un PDF.
**Arreglo:** solo https y dominios de `DOMINIOS_PERMITIDOS`; redirecciones revisadas una a una; tope de 15 MB; máximo 30 páginas; cabecera `%PDF-` obligatoria. *Probado:* se bloquean `http://`, dominios ajenos, `lasalina.es.evil.com`, `169.254.169.254` y `file://`.

## MEDIO

### M1. Datos de `precios.json` insertados en la página sin validar su tipo (XSS demostrado)
**Dónde:** `index.html` (`precio()`, `fechaLarga()`, `fuente`)
**Problema:** la app daba por hecho que `ant`/`act` eran números. Si llegaba un texto, `precio()` lo devolvía **sin escapar** dentro de `innerHTML`. Con un `precios.json` manipulado, abrir un producto ejecutaba código (**reproducido** en Chromium con la versión original). También se aceptaba como enlace de fuente `javascript:...`.
**Alcance real:** por el camino normal del robot los precios siempre son números, así que hace falta poder modificar `precios.json` (cuenta de GitHub comprometida o una fuente que cambie el flujo). Por eso es medio y no crítico, pero la app es lo que ven todos tus usuarios.
**Arreglo:** `sanear()` reconstruye todo el JSON con tipos y formatos comprobados (ids, fechas reales, números finitos, solo URL https); lo mismo para la copia guardada en el móvil. El escape ahora incluye `'` y `` ` ``, y todos los atributos con ids se escapan. *Probado en Chromium con datos hostiles:* no se ejecuta nada.

### M2. Sin política de seguridad de contenido (CSP)
**Problema:** sin CSP, cualquier fallo de inyección futuro se ejecuta sin freno.
**Arreglo:** CSP en `index.html` sin `unsafe-inline` (`script-src 'self'`). Para ello se movieron el script y los estilos a `app.js` y `estilos.css`, y se quitaron los `style="..."` en línea. *Probado:* un `<script>` en línea y uno de otro dominio inyectados por consola quedan bloqueados.

### M3. Una línea larga cuelga el lector (denegación de servicio)
**Dónde:** `scraper/comun.py`
**Problema:** una línea de 20.000 dígitos tardaba **9,5 s**; unas pocas líneas así agotan los 10 minutos del job y dejan los precios sin actualizar.
**Arreglo:** límite de 300 caracteres por línea y 600 filas por lonja. *Medido:* 9,5 s → 0,000 s; las líneas normales se leen igual.

### M4. Un CSV manual mal escrito tumbaba el robot para todas las lonjas
**Dónde:** `scraper/actualizar.py` (`leer_manual`, `main`)
**Problema:** una fecha imposible (`31/02/2026`) o una fila corta lanzaba una excepción **fuera** del `try`: fallaba el proceso entero. *Reproducido.*
**Arreglo:** lectura tolerante y gestionada por lonja; el error se anota solo en esa lonja.

### M5. Datos externos publicados sin validar; una fecha futura bloquea las actualizaciones
**Problema:** nombres, unidades, precios y fechas de webs ajenas se guardaban tal cual. Una fecha mal leída (p. ej. 2099) hacía que `aplicar()` rechazara para siempre las sesiones siguientes (solo acepta fechas más nuevas).
**Arreglo:** `limpiar_fila()` (sin `<>"'`, precios entre 0 y 100.000, unidad con formato válido) y `fecha_plausible()` (últimos 2 años, no futura).

## BAJO

| # | Problema | Arreglo |
|---|---|---|
| B1 | El service worker guardaba también respuestas 404/500 en la copia sin conexión | Solo guarda respuestas correctas del propio dominio; versión `lonjas-v2` |
| B2 | El JSON público incluía el texto interno de las excepciones (hasta 300 caracteres) | Mensaje genérico de ≤120 caracteres; el detalle queda solo en el registro de Actions |
| B3 | Cada vez que se volvía a la app se relanzaba la descarga | Máximo una cada 60 s |
| B4 | Favoritos y copia local se leían sin comprobar | Validados y con tope |
| B5 | `esc()` no escapaba `'`; faltaba `noreferrer`; meta `claude:viewport-fit-sides` residual; sin `Referrer-Policy` | Corregido |
| B6 | Sin `.gitignore` (riesgo de subir un `.env` en el futuro) | Añadido |

Además: dependencias sin versión mínima segura (`requests 2.32.3` tiene un aviso conocido, corregido en 2.32.4) → cotas mínimas actualizadas en `scraper/requirements.txt`.

---

## Actualización v3 (4 nov 2026, tarde)

- **Corregido un fallo introducido en la v2:** `leerFavs()` usaba `RE_ID` antes de que estuviera declarado; el error quedaba oculto y los favoritos aparecían vacíos (y se borraban al marcar uno nuevo). `RE_ID` se ha subido al principio de `app.js`. *Probado en Chromium:* el favorito se conserva tras recargar.
- **Fuentes alojadas en la app** (`fonts/`, licencia OFL incluida). La CSP queda en `style-src 'self'; font-src 'self'`: la app ya no hace ninguna petición a otros dominios. *Probado:* cero peticiones externas y cero errores de consola.
- **`pip-audit` ejecutado** sobre `scraper/requirements.txt`: *No known vulnerabilities found.*
- Recuperado `"use strict"` en `app.js`; caché del service worker `lonjas-v3`.

## Tareas que quedan para ti

La guía paso a paso está en el documento «Lonjas CyL: lo que tienes que hacer tú». Resumen:

1. **Activa la verificación en dos pasos en GitHub.** Es la protección más importante: quien entre en tu cuenta controla los precios que ven todos.
2. **Sube esta versión** al repositorio (si ya subiste una anterior, sube estos archivos encima).
3. **Primera ejecución del robot:** abre el registro de *Actions*. Si alguna lonja dice «Dirección no permitida», es que publica sus PDF en un dominio que no conocía: añádelo a `DOMINIOS_PERMITIDOS` **solo si es el oficial de la lonja**.
4. **De vez en cuando:** revisa que el robot sigue en verde y, antes de un uso comercial, pide permiso a las lonjas para reutilizar sus cotizaciones.

Ya no es tarea tuya: las fuentes de Google (resuelto) y `pip-audit` (ejecutado). Sigue vigente la limitación de GitHub Pages sobre el clickjacking (riesgo bajo; solo importa si algún día cambias de alojamiento: añade `frame-ancestors 'none'`).

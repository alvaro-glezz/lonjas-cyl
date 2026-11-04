# Lonjas CyL

App para el móvil con las cotizaciones semanales de las lonjas agropecuarias de Castilla y León. Se instala desde el navegador (Android e iPhone), funciona sin cobertura con los últimos precios guardados y se actualiza sola varias veces al día.

## Qué incluye esta primera versión

| Lonja | Día | De dónde lee los precios |
|---|---|---|
| Salamanca | lunes | PDF semanal de la Diputación (lasalina.es) |
| León | miércoles | Web de la Lonja (lonjadeleon.es) |
| Segovia | jueves | PDF semanal de la FES (fessegovia.es) |
| Lerma (Burgos) | viernes | Web del Ayuntamiento de Lerma |
| Zamora | — | Sin cotizar desde septiembre de 2026 |
| Valladolid y Palencia | — | Dejó de cotizar en julio de 2026 |

Pantallas: **Hoy** (resumen de trigo, cebada, maíz, cerdo, lechones y lechazo, y estado de cada lonja), **Lonjas** (la tablilla completa de cada una, por mesas y con buscador), **Comparar** (el mismo producto en todas las lonjas) **Histórico** (cotizaciones semanales oficiales de 2025 y 2026) y **Favoritos** (los precios que tú marques con la estrella). Al tocar un producto se ve su evolución semana a semana y, si la Junta lo publica, su histórico oficial 2025–2026.

## Cómo funciona

```
Lonjas (webs y PDF) ──► scraper/actualizar.py ──► data/precios.json ──► la app en el móvil
                          (GitHub lo ejecuta solo,
                           3 veces al día, lun–sáb)
```

La app no lee las webs de las lonjas: solo descarga `data/precios.json`. Así es rápida y no depende de que cada web esté disponible en ese momento. Si la lectura de una lonja falla, la app sigue mostrando su última sesión y marca esa lonja como «Revisar fuente».

## Ponerla en marcha (unos 15 minutos, todo desde el navegador)

1. **Crea una cuenta gratis en GitHub**: https://github.com/signup
2. **Crea un repositorio**: botón verde *New* → nombre `lonjas-cyl` → marca *Public* → *Create repository*.
3. **Sube los archivos**: en el repositorio, enlace *uploading an existing file*. Descomprime el zip en tu PC y arrastra **el contenido** de la carpeta `app-lonjas` (no la carpeta en sí) → *Commit changes*.
4. **Comprueba la tarea automática**: Windows a veces no arrastra la carpeta `.github` porque empieza por punto. Si en el repositorio no aparece `.github/workflows/actualizar-precios.yml`, créala a mano: *Add file → Create new file*, escribe como nombre `.github/workflows/actualizar-precios.yml`, pega el contenido de ese archivo (ábrelo con el Bloc de notas) y guarda.
5. **Da permiso para guardar precios**: *Settings → Actions → General → Workflow permissions* → marca *Read and write permissions* → *Save*. Además, activa la verificación en dos pasos en GitHub (*Settings → Password and authentication*): quien entre en tu cuenta puede cambiar los precios que ven todos.
6. **Publica la app**: *Settings → Pages* → en *Branch* elige `main` y `/ (root)` → *Save*. En un par de minutos GitHub te da la dirección, del tipo `https://tu-usuario.github.io/lonjas-cyl/`.
7. **Primera actualización**: pestaña *Actions* → *Actualizar precios* → *Run workflow*. Al terminar verás en verde ✔ o en rojo ✖; abre el registro para ver qué ha leído de cada lonja.

### Instalarla en el móvil

- **Android (Chrome)**: abre la dirección → menú ⋮ → *Añadir a pantalla de inicio* / *Instalar aplicación*.
- **iPhone (Safari)**: abre la dirección → botón *Compartir* → *Añadir a pantalla de inicio*.

## Seguridad

Resumen de lo que protege esta versión (detalle en `INFORME-SEGURIDAD.md`):

- **La app no se fía de los datos**: `precios.json` viene de webs y PDF de terceros, así que la app lo revisa campo a campo antes de mostrarlo y descarta lo que no encaja (HTML, enlaces `javascript:`, números raros). Además lleva una política de contenido (CSP) que impide ejecutar código que no sea el suyo.
- **El lector solo habla con webs conocidas**: descarga únicamente por https y de los dominios de `DOMINIOS_PERMITIDOS` (en `scraper/actualizar.py`). Si una lonja cambia de web o publica sus PDF en otro dominio, la app marcará «Revisar fuente» y el registro de *Actions* dirá «Dirección no permitida»: añade ese dominio a la lista **solo si es el oficial de la lonja**.
- **Nunca subas contraseñas ni claves** al repositorio (es público). Esta app no necesita ninguna; el `.gitignore` ya excluye los archivos típicos (`.env`, etc.).
- **Tipografías propias**: las fuentes *Barlow Condensed* y *Public Sans* van dentro de la carpeta `fonts/` (licencia libre OFL). La app no se conecta a Google ni a ningún otro sitio: mejor para la privacidad (RGPD).

## Histórico oficial 2025–2026 (Junta de Castilla y León)

La Junta publica cada semana un Excel con las cotizaciones de las lonjas y mercados de Castilla y León (y de las principales lonjas de España). La app los incorpora como histórico:

```
Web de la Junta (Excel semanales) ──► scraper/importar_jcyl.py ──► data/historico/indice.json
                                       (el robot lo ejecuta en         data/historico/2025.json
                                        cada actualización)            data/historico/2026.json
```

- **Originales**: `data/fuentes/jcyl/2025/` y `2026/`, sin modificar, con su `LEEME.md` y la lista de enlaces oficiales.
- **Datos para la app**: una serie por lonja, producto y unidad, tal como los publica la Junta. Cada punto lleva la fecha de celebración y la semana. Las unidades son las de la Junta (los cereales en €/100 kg), así que **no se mezclan** con las series de la app (€/t).
- **Pantalla Histórico**: filtros por ámbito (Castilla y León o toda España), categoría, producto, provincia, lonja y periodo (2025, 2026, todo o comparar 2025 con 2026). Muestra el último precio, la media, el mínimo y el máximo, la variación en el periodo, la variación interanual (misma semana del año anterior), la media del mismo periodo de los dos años, la tendencia de las últimas 4 sesiones, la comparativa entre lonjas y la tabla semana a semana.
- **Comprobación**: `python scraper/validar_historico.py` vuelve a leer todos los Excel y verifica que no falta ninguno, que los valores coinciden, que no hay duplicados y que cada serie tiene una sola unidad.
- Los valores que se apartan mucho del resto de su serie (casi siempre filas desplazadas en el Excel original) se marcan como «dudoso»: se ven en la tabla, pero no entran en gráficos ni medias.

Para importarlos a mano: `pip install -r scraper/requirements.txt` y `python scraper/importar_jcyl.py` (añade `--descargar` para bajar antes los Excel nuevos).

## Si una lonja deja de actualizarse

Las webs cambian de formato sin avisar. Hay dos salidas:

- **Carga manual (inmediata)**: en `data/manual/` crea `leon.csv`, `salamanca.csv`, `segovia.csv`, `lerma.csv`, `zamora.csv` o `valladolid-palencia.csv` copiando `ejemplo-plantilla.csv`. Se edita en la propia web de GitHub (*Add file → Create new file*). En la siguiente actualización se publica.
- **Arreglar el lector**: cada lonja tiene su función en `scraper/actualizar.py` (`leer_leon`, `leer_segovia`, …). El registro de *Actions* dice cuál falló y por qué.

## Estado de la versión

- Los datos de la carga inicial son las sesiones reales del 29 de octubre al 3 de noviembre de 2026, con algo de histórico de cereales y porcino.
- El lector de boletines se ha probado con el formato real de los boletines de Salamanca, León y Lerma, y con un PDF de prueba. Los lectores de cada web **no se han podido probar contra las webs reales** desde el entorno de desarrollo (sin acceso a esos dominios): la primera ejecución en GitHub es la prueba de verdad. Si alguno falla, la app sigue funcionando con los datos anteriores.
- Los precios son orientativos y propiedad de cada lonja. Antes de un uso comercial o de publicar en las tiendas, conviene pedir permiso a cada lonja para reutilizar sus cotizaciones citando la fuente.

## Siguientes pasos posibles

1. Ampliar a más lonjas de España (Binéfar, Mercolleida, Ebro, Albacete…) añadiendo un lector por lonja.
2. Avisos en el móvil cuando cambie un precio marcado como favorito.
3. Publicarla en Google Play y App Store empaquetando esta misma app con PWABuilder (https://www.pwabuilder.com): no hace falta reescribirla.

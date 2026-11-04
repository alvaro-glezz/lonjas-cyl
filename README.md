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

Pantallas: **Hoy** (resumen de trigo, cebada, maíz, cerdo, lechones y lechazo, y estado de cada lonja), **Lonjas** (la tablilla completa de cada una, por mesas y con buscador), **Comparar** (el mismo producto en todas las lonjas) y **Favoritos** (los precios que tú marques con la estrella). Al tocar un producto se ve su evolución semana a semana.

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
5. **Da permiso para guardar precios**: *Settings → Actions → General → Workflow permissions* → marca *Read and write permissions* → *Save*.
6. **Publica la app**: *Settings → Pages* → en *Branch* elige `main` y `/ (root)` → *Save*. En un par de minutos GitHub te da la dirección, del tipo `https://tu-usuario.github.io/lonjas-cyl/`.
7. **Primera actualización**: pestaña *Actions* → *Actualizar precios* → *Run workflow*. Al terminar verás en verde ✔ o en rojo ✖; abre el registro para ver qué ha leído de cada lonja.

### Instalarla en el móvil

- **Android (Chrome)**: abre la dirección → menú ⋮ → *Añadir a pantalla de inicio* / *Instalar aplicación*.
- **iPhone (Safari)**: abre la dirección → botón *Compartir* → *Añadir a pantalla de inicio*.

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

# Excel originales de la Junta de Castilla y León

Copia sin modificar de los Excel semanales «Precios de lonjas y mercados» que publica la Consejería de
Agricultura, Ganadería y Desarrollo Rural (Servicio de Estudios, Estadística y Planificación Agraria):

- 2026: https://agriculturaganaderia.jcyl.es/web/es/estadistica-informacion-agraria/lonjas-2026.html
- 2025: https://agriculturaganaderia.jcyl.es/web/es/estadistica-informacion-agraria/lonjas-2025.html

| Carpeta | Contenido |
|---|---|
| `2026/` | `semana-01.xlsx` … `semana-43.xlsx` (43 archivos, todos los publicados a 4 nov 2026) |
| `2025/` | 51 archivos: semanas 1–43 y 45–52 (la Junta no publicó la 44). Las semanas 1, 2, 3 y 5 están en el formato antiguo `.xls` |
| `enlaces.tsv` | Año, dirección oficial de cada Excel y título del enlace en la web |

La app **no lee estos archivos**: `scraper/importar_jcyl.py` los convierte en `data/historico/*.json`.
Se guardan para poder comprobar cualquier dato contra el original y para repetir la importación.

## Particularidades de la fuente (detectadas al importar)

- **2025, semana 41**: la página de 2025 enlaza dos veces «Semana 41»; uno de los enlaces es en realidad el Excel
  de la semana 41 de **2026**. Aquí se guarda el de 2025.
- **2025, semana 50**: no es el cuadro de lonjas sino otra publicación (precios medios por provincia). Se guarda,
  pero no se importa como cotización de lonja.
- **2025, «semana 45»** y **2026, semana 18**: el texto de cabecera indica otra semana, pero las fechas de
  celebración son las de la semana del enlace. Manda la fecha de celebración.
- **2026, semana 1**: varias lonjas tienen como fecha diciembre de 2026 (errata de año). Esos precios se
  importan sin fecha y se identifican por su semana.
- Algunas filas tienen valores desplazados o un mínimo mayor que el máximo. Las filas ambiguas no se importan, y
  los valores muy alejados del resto de su serie se marcan como «dudoso». El registro de la importación los
  enumera uno a uno.

## Actualización

El robot de GitHub (`.github/workflows/actualizar-precios.yml`) ejecuta una vez al día
`python scraper/importar_jcyl.py --descargar`, que baja los Excel nuevos que aparezcan en esas páginas y
rehace `data/historico/`. Solo descarga de dominios `jcyl.es` y por https.

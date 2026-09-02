# Informe de migración de la capa Adobe a LUCIDA

## Estado

La migración se ejecuta en la rama `ADOBE` del repositorio LUCIDA. La fuente `C:\IA\svg` se trató como sólo lectura. La identidad pública de la copia es LUCIDA; no se reemplazaron hashes, licencias ni campos de provenance de terceros.

## Código y documentación

Se trasladaron el núcleo `generic-interface-layer`, el companion/overlay, el puente Photoshop UXP, los contratos, los adaptadores Adobe, el runtime histórico necesario para el bridge, pruebas relacionadas y documentación operativa. Se ajustaron sólo nombres de paquete, IDs de manifiesto, rutas operativas al nuevo destino y el nombre del servicio local.

Se excluyeron proyectos ajenos, assets de librerías públicas, `node_modules`, caches, entornos virtuales, pesos/modelos, credenciales, bases privadas y archivos de trabajo.

## Assets CHEMSEX

El proceso reproducible está en `tools/migrate-chemsex-assets.mjs`. Usa SHA-256 de contenido, dimensiones y validación básica de formato PNG/SVG. Sólo copia archivos a la raíz de cada lámina; no crea subcarpetas.

Conteo de la ejecución actual:

| Lámina | Archivos únicos |
|---:|---:|
| 1 | 0 |
| 2 | 0 |
| 3 | 123 |
| 4 | 99 |
| 5 | 52 |
| 6 | 24 |
| 7 | 32 |
| 8 | 31 |
| **Total** | **361** |

Además se registraron 102 duplicados por hash, 238 descartes (técnicos, rechazados o variantes superadas) y seis grupos externos/ambiguos en `review-pending.json`. Las carpetas 1 y 2 están vacías porque no existe material propio con asignación comprobable; los iconos encontrados allí provienen de librerías externas.

## Revisión pendiente

`review-pending.json` conserva los grupos excluidos: iconos públicos seleccionados, previews de todas las láminas, histórico proveniente de `rd_database_complete`, assets públicos del proyecto, el corpus sin procedencia verificable y renders temporales sin asignación segura. No se copiaron al destino.

## Texto estructurado

El storyboard textual del proyecto se conserva por separado en `projects/chemsex/storyboard.json`. Contiene las ocho láminas en el orden original y sólo sus campos estructurales (`index`, `id`, `title`, `theme` y `text`); no incluye la ruta privada del documento fuente ni duplica recursos visuales.

El companion muestra el texto aunque una lámina no tenga grupos de recursos visuales. Cuando una fuente no contiene texto, la lámina sigue visible y el panel informa esa ausencia en lugar de ocultarla.

## Verificación

- La copia usa la identidad pública LUCIDA en código, paquetes y documentación.
- Las ocho carpetas numeradas existen y no contienen carpetas anidadas.
- El manifest conserva origen relativo, hash, formato, bytes, dimensiones, provenance, destino, duplicados y motivo de descarte.
- No se modificó la fuente; no se modificó `main`.
- No se hizo push.

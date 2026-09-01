# Arquitectura

## Propósito

`generic-interface-layer` es una capa local-first para una herramienta flotante que entiende el contexto disponible de una aplicación creativa y propone recursos o acciones sin convertirse en el editor. Puede funcionar sin Adobe abierto: en ese caso recibe contexto parcial, trabaja con catálogo local y deja explícito qué desconoce.

## Flujo de extremo a extremo

```text
host/plugin/archivo ──context.update──> normalizador
                                      │
                                      v
                                  análisis
                                      │
                                      v
                               ranking/propuesta
                                      │
                     confirmación explícita del usuario
                                      │
                                      v
                         acción autorizada y trazable
                                      │
                          resultado / cancelación
                                      │
                                      v
                            auditoría + replay
```

La secuencia no se salta etapas. Un resultado visual o textual puede sugerirse, pero no se importa ni modifica un documento sin una acción autorizada.

## Capas y responsabilidades

### `core`

No conoce Adobe, Blender, Electron, CUDA, MobileCLIP ni rutas del proyecto:

- `contracts`: schemas y envelopes estables.
- `context`: normalización de datos incompletos y hash determinista.
- `analysis`: términos, paleta, ocupación, áreas libres y completitud.
- `proposals`: ranking explicable, determinista y reemplazable.
- `actions`: ciclo de vida explícito, permiso, riesgo y rollback declarado.
- `audit`: eventos encadenados por hash.
- `replay`: reconstrucción de sesiones a partir de fixtures.
- `security`: allowlist, límites y bloqueo de shell.
- `jobs`: aislamiento de entradas/salidas y cancelación sin borrado.

### `providers`

Implementan capacidades sustituibles. El catálogo y la búsqueda textual son locales y livianos. La búsqueda visual/semántica puede estar ausente; cuando no está configurada devuelve estado `unavailable` con una razón, no instala ni descarga un modelo automáticamente.

### `adapters`

Traducen contratos genéricos a Adobe, Blender, GDKB, SVG o PDF. No filtran detalles del host al contrato central. Un adaptador puede declarar capacidades sin estar instalado ni tener la aplicación abierta.

### `transports`

Conectan procesos sin ejecutar instrucciones arbitrarias: HTTP local allowlisted, cola de archivos JSON y bridge de mensajes permitido.

### `clients`

Contienen estado de presentación. La ventana flotante es un cliente; no es el núcleo ni la fuente de verdad del contexto.

## Contratos clave

Un contexto tiene `schemaVersion`, identidad, host/documento/selección/capas, paleta, regiones ocupadas y seguras, `unknown` y `contextHash`. Los campos no entregados conservan `null` y una razón legible.

Una acción incluye `actionId`, idempotencia, tipo, estado, origen, destino, permisos, riesgo, payload y rollback. Las transiciones válidas exigen autorización explícita y un actor identificable.

Un evento de auditoría incluye secuencia, tipo, payload, timestamp, hash previo y hash propio. La cadena se puede verificar y reproducir offline.

## Adaptación a XIO/VJ

La integración recomendada es tratar XIO/VJ como otro host/adaptador:

1. XIO/VJ publica `context.update` con canvas, selección, capas o timeline disponibles.
2. El núcleo analiza sólo lo presente; no exige un documento tipo Adobe.
3. Los providers devuelven recursos/propuestas con IDs estables y procedencia.
4. XIO/VJ decide si muestra, acepta o rechaza una propuesta.
5. Una acción autorizada vuelve mediante `action.request`; el adaptador ejecuta sólo su operación permitida.
6. El resultado, error o cancelación vuelve como `action.result` y se registra.

Para tiempo real conviene enviar cambios por evento (selección, región, frame, capa) y aplicar debounce en el adaptador, no hacer polling agresivo desde el núcleo.

## Invariantes

- Sin host no hay fallo: hay contexto parcial y `unknown`.
- Sin provider pesado no hay fallo: hay búsqueda local o estado `unavailable`.
- Sin permiso no hay acción.
- Sin allowlist no hay lectura ni escritura.
- No existe ruta de shell, proceso o comando en el transporte genérico.
- No se editan documentos automáticamente.
- Los jobs cancelados conservan request, estado y auditoría.
- Los contratos no contienen assets ni datos de trabajos concretos.

## Estado de implementación

La implementación actual es un núcleo ejecutable y testeable offline en staging. La UI Electron, UXP, JSX, Blender, MobileCLIP y cualquier backend remoto requieren integración posterior, cada uno detrás de su adaptador/proveedor y sus propias pruebas.

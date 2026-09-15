# Mapa de extracción RESOLUME_ADAPTER → LUCIDA

LUCIDA consolida la coordinación común de RESOLUME_ADAPTER/VJ. No reemplaza RESOLUME_ADAPTER ni
absorbe clips, obras, presets, showfiles, XML de venues, rutas locales,
credenciales o configuraciones privadas.

## Capacidades genéricas reutilizables

| Capacidad | Extracción en LUCIDA | Evidencia |
| --- | --- | --- |
| Workflow por etapas | `VJState` y el orquestador | preflight → preparation → show → incident → recovery → closure |
| Eventos y timestamps | `VJEvent` | contrato ISO-8601 de `adapters.vj` |
| Estado común | `LucidaState` con `vj_state` anidado | una sola superficie de lectura |
| Propuestas | `VJProposal` | cada sugerencia es explícita, reversible y `proposal_only` |
| Resultados | `VJResult` | el operador o host registra el resultado observado |
| Replay | `lucida.replay` | dry-run determinista sin efectos externos |

## Tres capacidades internas

| Capacidad | Qué observa | Qué propone | Qué desconoce en offline |
| --- | --- | --- | --- |
| INSTAR | preflight de medios y mapping | revisar formatos, proporciones y preparación | estado real de Resolume, archivos y salida |
| NAYADE | soundcheck de señal y procesador | revisar señal, geometría y color | configuración real del procesador y módulo |
| IMAGO | show, incidentes y recuperación | registrar estado vivo y próximos pasos | señal en vivo, cues efectivos y resultado físico |

Las tres reportan simultáneamente en `LucidaState.capabilities`, aunque sólo
la capacidad correspondiente a la fase crea una propuesta para ese evento.

## Implementado y verificable en esta rama

- paquete Python `lucida` sin dependencias externas de runtime;
- orquestador único y método de lectura `read_overlay`;
- fachadas internas `InstarCapability`, `NayadeCapability` e `ImagoCapability`;
- reutilización de los contratos VJ existentes sin duplicar el core;
- fixture ficticio completo de preflight, preparación, show, incidente,
  recuperación y cierre;
- replay/dry-run y tests offline.
- consumidor offline XIO con resultado serializable, envelope de overlay
  atómico y validación runtime de identidad entre contratos.
- normalizador de `SignalProfile` para conservar hechos, origen, confianza y
  evidencia sin inferir ni controlar hardware.
- comparación segura de perfiles para detectar drift entre soundcheck y show
- contrato de entrada de show host-neutral para un futuro reducer de LUCIDA
  y conservar sus métricas al entrar en IMAGO.
  sin emitir correcciones.

## Implementado pero no verificado contra sistemas reales

- semántica de los datos que pueda entregar un futuro host de Resolume;
- correspondencia entre payloads VJ y protocolos o modelos de procesador;
- lectura de configuraciones reales, timing de transporte y sincronización;
- compatibilidad del transporte y de productores XIO reales.

## Fuera de LUCIDA; permanece exclusivo de RESOLUME_ADAPTER o requiere otro adaptador

- análisis de carpetas de INSTAR, sidecars, caché y backends GPU;
- conversión y validación DXV;
- análisis de ritmo, color, periodicidad y generación de cues;
- parser de composiciones Resolume, Advanced Output y generación de mapping;
- tarjetas de prueba y render de adaptaciones target-specific;
- catálogo, lectura o escritura de NovaStar, Colorlight, Brompton,
  Megapixel u otro hardware;
- Art-Net, DMX, sACN, FFGL, timecode, audio real y control de luces;
- base pública de venues, datos de colegas, UI embebida, MCP o GPU remota.

## Relación actual con XIO

XIO ya puede actuar como productor offline de eventos hacia LUCIDA. El bridge
conserva la trazabilidad en `ApplicationEvent`, convierte a `VJEvent` y
`SignalEnvelope`, registra el replay y devuelve un `XioConsumeResult` que
incluye el overlay atómico. `validate_xio_consume_result()` comprueba la
estructura y la identidad cruzada antes de que un host acepte el resultado.
La frontera sigue siendo `XIO → VJEvent → LUCIDA → propuesta → resultado`, sin
que LUCIDA tome control irreversible del show.

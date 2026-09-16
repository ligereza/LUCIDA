# Mapa de extracción MOSAIK -> VJ

Este documento registra qué ideas se extraen de `CAPACIDADES.md` y qué queda
fuera del adaptador reusable. VJ no copia obras, clips, presets personales,
showfiles, XML de venues, rutas locales ni configuraciones privadas.

Esta rama conserva la identidad VJ y no implementa un core nuevo.

## Núcleo reusable que entra en VJ

| Capacidad conceptual | Destino | Representación |
| --- | --- | --- |
| Workflow por etapas | `adapters/vj/adapter.py` | Transiciones `preflight`, `preparation`, `show`, `incident`, `recovery`, `closure` |
| Eventos | `adapters/vj/contracts/models.py` | `VJEvent` con timestamp, fase, tipo, payload y fuente |
| Estados | `adapters/vj/contracts/models.py` | `VJState` con secuencia, checkpoint, incidentes y resultados |
| Propuestas | `adapters/vj/contracts/models.py` y `adapter.py` | `VJProposal`, siempre explícita, reversible y solo propuesta |
| Checkpoints | `adapter.py` | Identificador determinista por evento relevante |
| Timestamps | `VJEvent`, `VJResult`, `VJState` | ISO-8601 y validación de orden temporal |
| Resultados | `VJResult` y `register_result` | Registro auditable de observado/aceptado/rechazado/ejecutado/omitido/fallido |
| Recuperación | `adapter.py` | Transiciones de incidente a recovery y verificación posterior |
| Análisis de errores | `incident.detected` | Categoría, síntomas y evidencia en payload; propuesta de captura sin intervención |
| Replay de sesión | `adapters/vj/replay/engine.py` | Replay determinista sin efectos externos |

## Adaptador VJ que entra en la capa de interfaz

Estos conceptos pertenecen al dominio VJ, pero el adaptador solo define el contrato y
el ciclo de vida; no incorpora los motores especializados de MOSAIK.

| Dominio | Cómo se representa ahora | Implementación especializada pendiente |
| --- | --- | --- |
| INSTAR | Evento de preflight/preparación y payload de checks | Analizador de media y catálogo |
| NAYADE | Evento de soundcheck/incidente/recuperación | Motor de patrones, señal y procesadores |
| Medios | Payload con asset_id, codec, FPS, resolución o resultado de preflight | FFprobe, PyAV, caché y sidecars |
| CUES | Payload con clip, posición y resultado | Parser y escritor de composición |
| DXV | Propuesta de conversión y resultado | Encoder/validador DXV |
| Art-Net/DMX/sACN | Eventos de patch, prueba o resultado | Transporte y universo DMX |
| LED processor | Snapshot, evidencia o incidente de señal | Adaptadores NovaStar/Colorlight/Brompton/etc. |
| Soundcheck | Eventos ordenados y checkpoints | Matriz de pruebas y tarjeta de prueba |
| Mapping/output | Payload de slice, canvas, orientación y validación | Parser de Advanced Output y generación de planes |

## Funciones futuras o no verificadas

Quedan explícitamente fuera de esta primera extracción:

- control activo de cualquier procesador LED;
- escritura en NovaStar, Colorlight, Brompton, Megapixel u otro hardware;
- identificación concluyente de módulo, pixel pitch, indoor/outdoor o nits a
  partir de HDMI solamente;
- modificación automática de Resolume, Advanced Output, cues o showfiles;
- ejecución de acciones Art-Net/DMX/sACN;
- sincronización con timecode o audio real;
- análisis de video en vivo o asistencia de IA durante el show;
- venue database pública, fotos de venues y datos de colegas;
- cachear un show dentro de Resolume o controlar su memoria interna;
- inferir una corrección de color como orden segura;
- UI embebida o panel superpuesto en Resolume;
- FFGL y plugins nativos;
- despliegue web, MCP, servidor remoto o GPU alquilada.

## Capacidades que permanecen exclusivas de MOSAIK

La rama VJ no copia ni extrae la implementación concreta de estas
capacidades:

- análisis de carpetas de visuales de INSTAR;
- sidecars `ClipProfile`, manifiestos y caché SQLite;
- backend NVDEC/CUDA y análisis de energía, color, periodicidad y cues;
- conversión y validación DXV;
- parser de composiciones Resolume `.avc`;
- extracción de CUES y transiciones de capas;
- parser de Advanced Output XML;
- ranking de visuales por proporción y estrategias crop/fit/fill/pattern/marquee;
- render de adaptaciones target-specific;
- generación de tarjetas de prueba geométricas;
- catálogo concreto de procesadores y manuales descargados;
- diagnóstico del caso real VC2 del 29 de agosto;
- perfiles reales de módulos, venues, artistas o shows;
- scripts PowerShell de preflight y snapshots del equipo.

Estas funciones pueden convertirse en futuros adaptadores que emitan eventos,
estados, propuestas y resultados, pero no forman parte de este adaptador VJ.

## Decisión sobre el core

No se encontró incompatibilidad que obligara a modificar el core. El nuevo
adaptador es independiente y se ubica únicamente en `adapters/vj`; las pruebas
se ubican en `tests/vj`. Por ello no se crea un ADR de modificación del core.

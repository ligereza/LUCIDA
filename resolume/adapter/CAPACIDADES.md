# LUCIDA/RESOLUME — Capacidades

Este documento describe el adaptador específico de Resolume dentro de la
superficie LUCIDA/RESOLUME. El identificador técnico resolume_adapter se
mantiene en comandos, módulos y rutas por compatibilidad.

Documento de referencia del estado real del repositorio. Última revisión:
2026-09-02.

El adaptador de Resolume es un conjunto de herramientas, contratos y conocimiento operativo
para trabajo VJ. Su objetivo es convertir problemas habituales de preparación,
soundcheck y show en procesos reproducibles, medibles y seguros.

## Estado general

| Área | Estado | Capacidad actual |
| --- | --- | --- |
| INSTAR | Implementado | Plugin FFGL para el VJ, guía de composición, generación de Advanced Output XML y parser offline de media/superficies |
| NAYADE | Implementado en primera versión | Tarjeta de prueba, matriz de soundcheck, catálogo de procesadores y diagnóstico de señal |
| IMAGO | Implementado en primera versión | Observación del show, cues, incidentes, checkpoints, recovery y cierre proposal-only |
| Procesadores LED | Base segura implementada | Descubrimiento pasivo USB/COM, snapshots y catálogo; el control activo depende del modelo confirmado |
| Integración Resolume | Lectura y generación de derivados | Lectura de composiciones, Advanced Output, cues y generación de planes; no modifica showfiles |
| Interfaz visual | No implementada | La prioridad actual es el núcleo, los contratos y los flujos verificables |
| CLI portable | Implementado | Launcher Windows, bootstrap opcional y diagnóstico `doctor`; no altera showfiles ni hardware |
| Incidentes VJ | Implementado en primera versión | Planes de evidencia, hipótesis y recuperación reversible compartidos por las tres etapas |

## Flujo LUCIDA/RESOLUME

```text
INSTAR  ->  NAYADE  ->  IMAGO
pre-show    soundcheck   show
```

- `INSTAR` prepara y describe el material y el destino.
- `NAYADE` verifica señal, geometría, superficie y condiciones del venue.
- `IMAGO` es la capa de asistencia para operar el show con lo que ya fue
  probado y aprobado. Su salida sigue siendo proposal-only.

IMAGO también puede registrar `guard_window_requested`: una ventana de
resguardo temporal para probar un efecto o absorber un missclick manteniendo
disponible la visual base. La duración debe ser positiva y no superar 60
segundos; se crea sólo una propuesta reversible y no se modifica Resolume.

## Capacidades transversales

### Diagnóstico portable

`doctor` comprueba la copia local antes de un show: estructura del repositorio,
versión de Python, módulos base, FFmpeg/FFprobe y módulos GPU opcionales. Su
salida distingue bloqueos (`FAIL`) de capacidades no instaladas (`WARN`) y
genera un JSON auditable. No abre Resolume, no modifica archivos de show y no
envía comandos a procesadores.

### Planes de incidentes

`incident-plan` convierte un síntoma en una secuencia segura de investigación.
Las categorías actuales son:

- `flicker`;
- `tearing`;
- `frames_dropped`;
- `lost_media`;
- `gray_black_levels`;
- `geometry_scaling`;
- `signal_loss`.

Cada plan contiene preguntas de evidencia, hipótesis sin confirmar,
propuestas `proposal_only` y una lista de recuperación. En particular, el caso
de negro gris orienta a comparar PLUGE, rampa de grises, fuente de referencia
y snapshot de procesador antes de tocar niveles o gamma.

## INSTAR — plugin de mapping VJ y preparación del material

La implementación nativa vive en `resolume/plugin/INSTAR/`. El plugin trabaja
en Resolume, conserva la textura de entrada, muestra una guía de composición y
genera `INSTAR_AdvancedOutput.xml` directamente desde `MapFile` (PNG/JPG) y el
canvas configurado. No pide un XML real a otra persona y no configura
procesadores LED.

El resto de esta sección describe el acompañante offline que prepara los
perfiles antes del show; no debe confundirse con el plugin FFGL.

### Preflight de media

INSTAR puede recorrer una carpeta de visuales sin decodificar todo el video y
obtener, mediante FFprobe y los analizadores disponibles:

- resolución, duración y FPS;
- codec, contenedor, pixel format y presencia de alpha;
- orientación y relación de aspecto;
- estado progresivo/interlaced cuando el medio lo declara;
- compatibilidad con un perfil de show;
- advertencias de codecs no recomendados para reproducción VJ;
- estado DXV y necesidad de crear un derivado.

Puede generar un informe JSON, sidecars por visual, un manifiesto portable,
reporte HTML y una caché SQLite para no repetir análisis que no cambiaron.

### Análisis visual y temporal

Con `--deep`, INSTAR puede producir descriptores que ayudan a preparar el
material para mezcla en vivo:

- energía y luminancia aproximada;
- color y distribución de tonos;
- cambios, eventos y estabilidad temporal;
- periodicidad y loopabilidad;
- sugerencias de CUE para cambio, impacto, strobo y loop;
- perfiles semánticos reutilizables por otros componentes.

Existe un backend opcional para NVIDIA/NVDEC/CUDA. Si se solicita el modo GPU,
no hace fallback silencioso a CPU. El análisis profundo sigue siendo un
análisis de apoyo y no reemplaza la revisión artística del VJ.

### DXV

El adaptador puede preparar una conversión a DXV usando el encoder disponible y
validar la salida. El flujo conserva resolución, FPS y alpha según la
configuración solicitada; no crea alpha falso para videos con fondo negro.

La conversión no sustituye la decisión del VJ sobre resolución, composición o
calidad. El objetivo es que el formato de reproducción sea adecuado para
Resolume y que el material quede documentado.

### Cues de Resolume

El adaptador puede leer una composición `.avc` y extraer:

- clips y capas;
- posiciones de CUE en milisegundos, segundos y normalizadas;
- slots vacíos;
- duración del transporte;
- BPM detectado/manual cuando está guardado;
- duración de transición de capa.

Actualmente extrae y analiza CUES existentes. No escribe nuevos CUES en el
showfile.

### Advanced Output y mapping

INSTAR puede leer un preset XML de Advanced Output y separar:

- composición de entrada;
- pantallas virtuales;
- `InputRect`;
- `OutputRect`;
- transformaciones, flip y key;
- warper y homografía;
- grupos que comparten la misma entrada;
- estadísticas de slices y salidas virtuales.

Con un catálogo de visuales puede construir un plan revisable que considera:

- relación de aspecto de entrada y salida;
- orientación horizontal/vertical;
- crop protegido;
- fit/fill sin estirar como primera opción;
- riesgo de deformación;
- candidatos alternativos;
- uso como patrón repetido;
- marquee para banners y superficies extremas.

No modifica Resolume. Si no existe una visual perfecta para un slice, el plan
puede proponer una adaptación, pero la aprobación sigue siendo humana.

### Adaptaciones target-specific

Desde un plan INSTAR puede generar previews derivados para comprobar:

- crop;
- fondo de apoyo;
- pattern repetido;
- marquee horizontal o vertical;
- copias espejadas alternas;
- exportación opcional a DXV separado.

Las fuentes originales permanecen intactas.

## NAYADE — soundcheck

### Tarjeta de prueba

NAYADE puede generar una tarjeta de prueba a partir de Advanced Output para
revisar en la pantalla real:

- color por grupo de entrada;
- etiquetas y bordes;
- cuadrícula;
- círculos y cuadrados para detectar deformación;
- inversión y flip;
- deslizamiento entre slices;
- solapamiento y límites;
- movimiento horizontal y vertical.

La tarjeta se genera como un único artefacto de prueba y no altera el
showfile.

### Sesiones reproducibles

NAYADE puede crear una sesión de soundcheck con una matriz de operaciones y
registrar el resultado de cada prueba:

- baseline;
- flip horizontal/vertical;
- pattern;
- marquee;
- alcance global, composición, input group, slice, clip;
- parámetros, notas, resultado y paso ejecutado.

Esto permite repetir una prueba en otro evento y conservar qué adaptación fue
aprobada para una superficie concreta.

### Procesadores LED

El catálogo inicial contiene perfiles de referencia para:

- NovaStar VX;
- Colorlight X6/X7;
- Brompton Tessera;
- Megapixel HELIOS;
- procesadores desconocidos.

El catálogo describe familias, transportes, capacidades documentadas,
parámetros de riesgo, fuentes y relación con receiving cards y módulos.

El descubrimiento actual es pasivo:

- enumera puertos USB/COM mediante PySerial;
- registra VID/PID y descriptores disponibles;
- ordena coincidencias tentativas del catálogo;
- no abre puertos;
- no envía bytes;
- no activa patrones;
- no modifica configuraciones.

El snapshot conserva la identidad tentativa, el perfil asociado, la conexión,
las limitaciones y el estado de seguridad. La lectura activa por protocolo
será una fase posterior y exigirá modelo, firmware y transporte confirmados.

### Perfiles de módulos y superficies

El contrato de módulo permite registrar, con origen y confianza:

- indoor, outdoor, semi-outdoor o dual-use;
- pixel pitch;
- resolución física;
- tamaño físico;
- brillo nominal en nits;
- refresh rate;
- receiving card;
- calibración;
- topología;
- condiciones de operación.

El adaptador no intenta inferir todo desde HDMI. El pitch puede calcularse cuando se
conocen dimensiones y píxeles, pero la marca, el brillo máximo, el entorno y
la calibración requieren una ficha, lectura, etiqueta, medición u otra fuente.

### Diagnóstico de color y señal

NAYADE puede ordenar hipótesis a partir de observaciones registradas, por
ejemplo:

- GPU en RGB Full y conversión Limited-to-Full en el procesador;
- gamma extrema con brillo muy bajo;
- brillo/contraste alterados también en Resolume;
- negro por encima de blackout;
- estado del rango del procesador no registrado.

La reconciliación de cadena cruza perfiles de señal, observaciones del
procesador, snapshots, módulos y Advanced Output. Calcula escalado, compara
resolución/FPS/rango, estima pixel pitch cuando hay medidas físicas y separa
conflictos de recomendaciones `proposal_only`.

`probe-output` captura el modo actual del adaptador Windows y la metadata EDID
disponible. El rango RGB de NVIDIA queda como `unknown` si WMI no lo expone;
la sonda no sustituye una prueba PLUGE ni confirma el routing del procesador.

`protocol` transforma la evidencia disponible en un checklist de soundcheck
ordenado. Incluye una línea base de blackout, PLUGE/near-black, grises,
primarios, geometría y movimiento, y eleva resolución/escalado cuando aparecen
conflictos de cadena o mapping. Cada paso explica qué observar y qué registrar;
el resultado es `plan_only`, sin patrones emitidos ni cambios de hardware.

Ese protocolo puede adjuntarse a `nayade-session init` mediante `--protocol`.
NAYADE valida el contrato y registra los checks de cadena antes de su matriz de
experimentos visuales, sin fusionar sus responsabilidades ni ejecutar acciones.

`nayade-session report` entrega un estado acotado de cierre (`READY`,
`INCOMPLETE`, `REVIEW` o `BLOCKED`), el próximo paso pendiente y los riesgos
derivados de resultados `review`, `running` o `rejected`. No expone notas ni
rutas privadas y no ejecuta acciones.

`nayade-session record --output` permite crear una nueva versión de la sesión
sin modificar el JSON de origen. El destino no se sobrescribe y el registro
normal escribe de forma atómica para evitar sesiones truncadas.

El diagnóstico separa hechos, hipótesis y acciones de verificación. No declara
que gamma sea la causa de un negro levantado sin medir la cadena completa.

## Motor de evidencia previsto

La siguiente evolución de NAYADE es reconciliar varias fuentes en vez de
confiar en un único panel del fabricante:

```text
configuración NovaLCT/Unico
       + receiving cards y topología
       + EDID y señal de entrada
       + XML Advanced Output
       + foto de etiqueta y gabinete
       + medidas físicas
       + patrones observados
       + historial del venue
       ↓
hechos normalizados -> cálculos -> conflictos -> recomendaciones
```

Cada hecho debe conservar:

- sujeto y propiedad;
- valor y unidad;
- origen;
- fecha;
- confianza;
- evidencia cruda;
- fuente relacionada;
- contradicciones.

El motor podrá calcular pitch, densidad, capacidad de canvas, deformación,
consistencia de gabinete y compatibilidad de señal. Una inferencia solo será
`confirmada` cuando exista evidencia suficiente; de lo contrario se marcará
como `calculada`, `probable`, `conflictiva` o `desconocida`.

## Seguridad y límites actuales

- Los comandos actuales son de lectura, generación de reportes o generación
  de derivados.
- El adaptador no cambia BIOS, drivers, perfil de energía ni configuración de
  Resolume.
- NAYADE no escribe en procesadores LED desconocidos.
- No se deben usar perfiles inferidos para enviar parámetros automáticamente.
- Los medios pesados y las referencias externas descargadas no se versionan
  por defecto.
- Las fuentes del proyecto se conservan; los derivados se generan en carpetas
  de salida.

## Comandos principales

```powershell
python tools/resolume_adapter_cli.py instar "D:\VJ\Media" --report artifacts\instar.json
python tools/resolume_adapter_cli.py instar "D:\VJ\Media" --deep --gpu
python tools/resolume_adapter_cli.py dxv "D:\VJ\Media\clip.mp4" --fps 60
python tools/resolume_adapter_cli.py resolume-cues "D:\VJ\Shows\show.avc" --report artifacts\cues.json
python tools/resolume_adapter_cli.py instar-cue-plan artifacts\clip-profile.json --report artifacts\cue-plan.json
python tools/resolume_adapter_cli.py instar-map "D:\VJ\Shows\advanced-output.xml" --report artifacts\mapping.json
python tools/resolume_adapter_cli.py instar-testcard "D:\VJ\Shows\advanced-output.xml" --output artifacts\testcard.mp4
python tools/resolume_adapter_cli.py nayade-session init artifacts\testcard.json --output artifacts\soundcheck.json
python tools/resolume_adapter_cli.py nayade-processor catalog
python tools/resolume_adapter_cli.py nayade-processor discover --report artifacts\processor-discovery.json
python tools/resolume_adapter_cli.py nayade-processor validate-case data\cases\soundcheck-2026-08-29-vc2.json
python tools/resolume_adapter_cli.py nayade-processor diagnose-case data\cases\soundcheck-2026-08-29-vc2.json
python tools/resolume_adapter_cli.py nayade-processor reconcile --processor-observation artifacts\processor-observation.json --mapping artifacts\mapping-plan.json --report artifacts\reconciliation.json
python tools/resolume_adapter_cli.py nayade-processor protocol --reconciliation artifacts\reconciliation.json --mapping artifacts\mapping-plan.json --report artifacts\soundcheck-protocol.json
python tools/resolume_adapter_cli.py nayade-processor probe-output --report artifacts\output-probe.json
python tools/resolume_adapter_cli.py nayade-session report artifacts\soundcheck.json --report artifacts\soundcheck-status.json
python tools/resolume_adapter_cli.py doctor --report artifacts\doctor.json
python tools/resolume_adapter_cli.py incident-plan gray_black_levels --stage soundcheck --report artifacts\incident-plan.json
python tools/resolume_adapter_cli.py vj-project instar artifacts\instar.json --event-id instar-001 --sequence 1 --mode projection
python tools/resolume_adapter_cli.py vj-project-replay artifacts\vj-project-manifest.json --report artifacts\vj-project-replay.json
```

## CLI portable

`tools\Invoke-RESOLUME_ADAPTER.ps1` permite ejecutar la CLI desde cualquier carpeta sin
conocer la ruta interna del repositorio. Si existe un entorno `.venv` local lo
usa; si no, utiliza `python` del sistema. `tools\Bootstrap-RESOLUME_ADAPTER.ps1` crea ese
entorno e instala las dependencias base; `-Gpu` agrega el backend NVIDIA
opcional. Ambos scripts sólo preparan el entorno o ejecutan el comando pedido;
no cambian BIOS, drivers, Resolume, procesadores ni showfiles.
El procedimiento completo está en `docs\runbooks\instalacion-portable.md`.

## Contratos y organización

- `schemas/`: contratos JSON de visuales, shows, mapping, cues, módulos,
  procesadores y snapshots.
- `data/processors/catalog.json`: catálogo inicial de familias y capacidades.
- `data/modules/`: perfiles físicos aportados por venues y colegas.
- `data/cases/`: casos reales y regresiones de soundcheck.
- `tools/resolume_adapter/`: núcleo Python.
- `tools/resolume_adapter_cli.py`: punto de entrada de consola.
- `docs/research/`: investigación técnica y herramientas adoptadas.
- `docs/runbooks/`: procedimientos operativos.
- `docs/references/`: manuales y referencias externas locales.

## Próximas capacidades

1. Importar exportaciones de NovaLCT/Unico y convertirlas en hechos
   normalizados.
2. Crear el motor de reconciliación entre procesador, receiving card, módulo,
   señal y Advanced Output.
3. Añadir adaptadores de lectura activa, empezando por un modelo NovaStar real
   y confirmado en terreno.
4. Incorporar captura de EDID y datos de señal de Windows/NVIDIA.
5. Generar automáticamente un protocolo de patrones según las hipótesis del
   diagnóstico.
6. Integrar venue, snapshots y resultados de soundcheck sin duplicar perfiles.
7. Extender IMAGO para consumir planes aprobados, manteniendo el modo seguro
   por defecto.

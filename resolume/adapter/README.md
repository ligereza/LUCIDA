# LUCIDA/RESOLUME — adaptador de Resolume

Este directorio contiene la integración operativa específica de Resolume.
El nombre técnico resolume_adapter se conserva en CLI, módulos y rutas por compatibilidad.

Repositorio personal de herramientas, procedimientos y conocimiento práctico para trabajo VJ.

El objetivo es convertir problemas reales —preparación de shows, reproducción en Resolume,
conversión a DXV, diagnóstico de rendimiento y organización de medios— en procedimientos
repetibles y verificables.

## Inicio rápido

Desde PowerShell, en la raíz del repositorio:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\tools\Test-VJPreflight.ps1 -MediaRoot "D:\VJ\Media" -ProjectRoot "D:\VJ\Shows\show-01"
.\tools\Get-VJSystemSnapshot.ps1 -OutputPath ".\artifacts\snapshot.json"

python .\tools\resolume_adapter_cli.py instar "D:\VJ\Media" --target-fps 60 --report ".\artifacts\instar.json" --sidecars-dir ".\artifacts\instar-sidecars"
python .\tools\resolume_adapter_cli.py instar "D:\VJ\Media" --deep --report ".\artifacts\instar-deep.json"
python .\tools\resolume_adapter_cli.py diagnose "D:\VJ\Media\clip.mp4" --report ".\artifacts\clip-report.json"
python .\tools\resolume_adapter_cli.py dxv "D:\VJ\Media\clip.mp4" --fps 60
python .\tools\resolume_adapter_cli.py instar-map "D:\VJ\Shows\venue-advanced-output.xml" --catalog ".\artifacts\instar-manifest.json" --report ".\artifacts\mapping-plan.json"
python .\tools\resolume_adapter_cli.py instar-testcard "D:\VJ\Shows\venue-advanced-output.xml" --output ".\artifacts\venue-geometry-testcard.mp4" --report ".\artifacts\venue-geometry-testcard.json"
python .\tools\resolume_adapter_cli.py nayade-session init ".\artifacts\venue-geometry-testcard.json" --output ".\artifacts\venue-soundcheck.json" --seed 4821
python .\tools\resolume_adapter_cli.py nayade-session init ".\artifacts\venue-geometry-testcard.json" --output ".\artifacts\venue-soundcheck-with-protocol.json" --protocol ".\artifacts\soundcheck-protocol.json"
python .\tools\resolume_adapter_cli.py nayade-session report ".\artifacts\venue-soundcheck-with-protocol.json" --report ".\artifacts\soundcheck-status.json"
python .\tools\resolume_adapter_cli.py resolume-cues "D:\VJ\Shows\show.avc" --report ".\artifacts\cues.json"
python .\tools\resolume_adapter_cli.py instar-cue-plan ".\artifacts\clip-profile.json" --report ".\artifacts\cue-plan.json"
python .\tools\resolume_adapter_cli.py nayade-processor catalog
python .\tools\resolume_adapter_cli.py nayade-processor discover --report ".\artifacts\processor-discovery.json"
python .\tools\resolume_adapter_cli.py nayade-processor validate-case ".\data\cases\soundcheck-2026-08-29-vc2.json"
python .\tools\resolume_adapter_cli.py nayade-processor reconcile --processor-observation ".\artifacts\processor-observation.json" --mapping ".\artifacts\mapping-plan.json" --report ".\artifacts\reconciliation.json"
python .\tools\resolume_adapter_cli.py nayade-processor protocol --reconciliation ".\artifacts\reconciliation.json" --mapping ".\artifacts\mapping-plan.json" --report ".\artifacts\soundcheck-protocol.json"
python .\tools\resolume_adapter_cli.py nayade-processor probe-output --report ".\artifacts\output-probe.json"
python .\tools\validate_schema_graph.py
python .\tools\resolume_adapter_cli.py vj-replay ".\adapters\vj\replay\fixtures\plugin-bridges-fictional.json" --report ".\artifacts\vj-replay.json"
python .\tools\resolume_adapter_cli.py vj-project instar ".\artifacts\instar.json" --event-id instar-001 --sequence 1 --mode projection --output ".\artifacts\instar-input.json"
python .\tools\resolume_adapter_cli.py vj-project-replay ".\artifacts\vj-project-manifest.json" --report ".\artifacts\vj-project-replay.json"
```

## Dependencias

Instala las dependencias Python con:

```powershell
python -m pip install -r requirements.txt
```

La suite local se ejecuta desde este repositorio con:

~~~
python -m pytest tests tools/tests
~~~

El archivo pytest.ini local evita heredar por accidente la configuración del
repositorio padre y deseleccionar todos los tests.

Para usar el adaptador de Resolume sin conocer la estructura del repositorio:

```powershell
.\tools\Bootstrap-RESOLUME_ADAPTER.ps1 -Dev
.\tools\Invoke-RESOLUME_ADAPTER.ps1 --help
```

El launcher usa `.venv` si existe y no cambia configuraciones del equipo.
`-Gpu` instala sólo las dependencias NVIDIA opcionales.

Para habilitar el análisis visual GPU en una máquina NVIDIA:

```powershell
python -m pip install -r requirements-gpu.txt
```

El runtime del adaptador usa la biblioteca estándar de Python. El preflight técnico
de INSTAR usa sólo FFprobe y no decodifica todo el video; `--deep` activa el
diagnóstico adicional de luminancia. `--gpu` usa NVDEC/CUDA y no hace fallback
silencioso a CPU. Para analizar media
se necesitan `ffmpeg` y `ffprobe` disponibles en `PATH`; para la integración
directa con Resolume se necesita Arena/Avenue 7.26 o posterior y su MCP local.

INSTAR también puede construir perfiles reutilizables, comparar la media con un
perfil de show y guardar una caché SQLite. Las dependencias Python de catálogo
(`PyAV`, `NumPy`, `Pillow`, `PySceneDetect`, OpenCV y `jsonschema`) están fijadas
en `requirements.txt`; el backend NVIDIA sigue separado en `requirements-gpu.txt`.

Los scripts solo leen el estado del equipo y muestran advertencias; no cambian el plan de
energía, BIOS, controladores, archivos ni configuraciones de Resolume.

Para un incidente durante soundcheck o show, se puede generar una guía sin
modificar el showfile:

```powershell
& ".\tools\Invoke-RESOLUME_ADAPTER.ps1" incident-plan gray_black_levels --stage soundcheck
```

El resultado separa evidencia, hipótesis y recuperación para flicker, tearing,
frames dropped, media ausente, niveles de negro, geometría y pérdida de señal.
No modifica el showfile, no ajusta el procesador y no ejecuta acciones.

`validate_schema_graph.py` comprueba el registry local de contratos y sus referencias sin
red. Para validar una instancia JSON concreta, agrega `--schema` y `--instance`.

## Estructura

```text
docs/
  architecture/     Arquitectura de componentes y etapas del adaptador.
  decisions/       Decisiones de diseño del repositorio.
  research/        Mapa de conceptos VJ y herramientas open source.
  runbooks/        Procedimientos operativos paso a paso.
  checklists/      Listas breves para usar antes o durante un show.
  templates/       Plantillas para registrar nuevos casos.
schemas/           Contratos compartidos para INSTAR, NAYADE e IMAGO.
tools/             Scripts locales y núcleo de herramientas del adaptador.
artifacts/         Salidas locales; ignoradas por Git.
```

## Catálogo INSTAR

### SVG → Advanced Output candidato

INSTAR puede convertir un SVG vectorial con rectángulos, polígonos, elipses o
paths Bézier en un XML candidato de Advanced Output. Un segundo SVG opcional
describe la geometría física de salida; ambas listas se emparejan por orden.
La salida no modifica Resolume y debe revisarse con NAYADE antes del evento.

```powershell
python .\tools\resolume_adapter_cli.py instar-map-svg `
  .\data\event\input-map.svg `
  --output-svg .\data\event\output-map.svg `
  --xml .\artifacts\event-advanced-output.xml `
  --report .\artifacts\event-mapping-candidate.json
```

Si no se entrega `--output-svg`, INSTAR escala la geometría del input para
formar un OutputRect candidato y lo marca como advertencia. Los arcos SVG
deben convertirse a Bézier antes de importar.

Cuando el SVG proviene de un informe generado, INSTAR detecta un canvas interno
si existe, usa solo shapes con nombre o relleno de superficie y trata los
fondos, grillas, bordes y textos como presentación. Los textos contenidos en
una superficie pueden aportar su nombre sin convertirse en slices adicionales;
la metadata textual del documento, como escala, módulos y área, se conserva en
el candidato JSON.

### Imagen raster → candidato de mapping

INSTAR también puede detectar superficies grandes diferenciadas por color en
un PNG/JPG de pixel mapping y generar un XML candidato. Esta ruta normaliza
las regiones al canvas declarado, pero queda en `REVIEW`: todavía no lee OCR,
números de panel ni routing de procesadores.

```powershell
python .\tools\resolume_adapter_cli.py instar-map-image `
  .\data\event\pixel-map.png `
  --canvas-size 4186x1283 `
  --xml .\artifacts\event-raster-candidate.xml `
  --svg .\artifacts\event-raster-candidate.svg `
  --report .\artifacts\event-raster-candidate.json
```

El XML sirve para inspección y posterior corrección; no se presenta como
mapping físico confirmado. La siguiente extensión es asociar OCR de nombres y
resoluciones a estas regiones antes de ajustar coordenadas.

Si existe un OCR externo compatible con el protocolo `OCR_LINE`, puede
conectarse sin convertirlo en dependencia del núcleo:

```powershell
python .\tools\resolume_adapter_cli.py instar-map-image `
  .\data\event\pixel-map.png `
  --canvas-size 4186x1283 `
  --ocr-exe C:\ruta\instar-ocr.exe `
  --xml .\artifacts\event-raster-candidate.xml `
  --report .\artifacts\event-raster-candidate.json
```

El OCR solo aporta etiquetas y anclas de resolución; la geometría sigue
siendo detectada por INSTAR y el resultado conserva estado `REVIEW`.

La misma orden acepta PDF. INSTAR rasteriza solo la página solicitada con
`pdftoppm` y continúa por la misma ruta de detección/OCR:

```powershell
python .\tools\resolume_adapter_cli.py instar-map-image `
  .\data\event\pixel-map.pdf `
  --pdf-page 13 `
  --xml .\artifacts\event-raster-candidate.xml
```

### Routing Pixel Peeker → INSTAR

La imagen o el PDF no contienen procesadores ni puertos. Cuando el diseño ya
existe en Pixel Peeker, su exportación `pixel-peeker.interchange/1` puede
normalizarse y cruzarse con el reporte de layout de INSTAR:

```powershell
python .\tools\resolume_adapter_cli.py instar-import-interchange `
  .\data\event\wall-interchange.json `
  --layout-report .\artifacts\event-raster-candidate.json `
  --report .\artifacts\event-processor-routing.json
```

INSTAR deriva el bounding box de cada puerto a partir de sus gabinetes y
reporta coincidencias geométricas con las superficies detectadas. `PASS` solo
significa coincidencia geométrica completa; `physical_status` queda
`UNVERIFIED` porque ningún JSON sustituye la comprobación del procesador, el
cableado o la carga en el venue.

### Aplicar solo la geometría de entrada sobre un template

Si ya existe un Advanced Output XML con routing de procesadores, INSTAR puede
actualizar únicamente `InputRect` por nombre y conservar `OutputRect`,
dispositivos y warpers:

```powershell
python .\tools\resolume_adapter_cli.py instar-apply-input-map `
  .\data\event\AdvancedOutput.xml `
  .\data\event\input-map.svg `
  --xml .\artifacts\event-advanced-output-candidate.xml `
  --report .\artifacts\event-input-template.json
```

Esta es la vía para unir un layout detectado con routing real sin inferir la
cadena física desde una imagen. La coincidencia ignora mayúsculas, acentos y
separadores; si los nombres de dos fuentes no coinciden, se puede entregar un
JSON explícito con `--aliases`, por ejemplo `{"CENTRAL":"MAIN CENTER"}`.
Si falta alguna superficie en cualquiera de las dos fuentes, el resultado
queda en `REVIEW` y no se aplica una coincidencia ambigua.

La misma operación puede recibir directamente una imagen o PDF:

```powershell
python .\tools\resolume_adapter_cli.py instar-apply-image-map `
  .\data\event\AdvancedOutput.xml `
  .\data\event\pixel-map.png `
  --ocr-exe C:\ruta\instar-ocr.exe `
  --xml .\artifacts\event-advanced-output-candidate.xml
```

La detección raster produce nombres y geometría candidatas; el template sigue
siendo la única fuente de `OutputRect` y routing físico.

La salida de una imagen se etiqueta como `stage_layout_candidate`. Si el
documento no aporta procesadores, puertos o cadena de datos, el campo
`processor_routing` queda en `UNKNOWN`; INSTAR no convierte una disposición
escénica en routing físico por inferencia.

Para preparar material contra un objetivo conocido:

```powershell
python .\tools\resolume_adapter_cli.py instar "D:\VJ\Media" `
  --show-profile ".\docs\templates\show-profile.json" `
  --cache-db ".\artifacts\instar.sqlite3" `
  --report ".\artifacts\instar.json" `
  --html-report ".\artifacts\instar.html" `
  --manifest ".\artifacts\instar-manifest.json"
```

El resultado incluye un `ClipProfile` por visual con metadata, compatibilidad,
energía visual, periodicidad, loopabilidad, eventos detectados y, cuando hay
muestras suficientes, sugerencias de CUE para cambio limpio, impacto, ventana
de strobo y loop. La caché evita repetir el trabajo pesado mientras el archivo
y los parámetros de análisis no cambien; los perfiles derivados se reconstruyen
para incorporar nuevos detectores.
El manifiesto permite consumir el catálogo desde otras herramientas sin volver a
leer el reporte completo. El detalle operativo está en `docs/runbooks/instar-catalogo.md`.

### Mapa de CUES de Resolume

Para inspeccionar los puntos CUE existentes en una composición sin modificarla:

```powershell
python .\tools\resolume_adapter_cli.py resolume-cues "D:\VJ\Shows\show.avc" `
  --report ".\artifacts\resolume-cues.json"
```

El mapa conserva la posición de cada CUE en milisegundos y segundos, su posición
normalizada respecto de la duración del clip, los slots vacíos, el BPM guardado
y la transición configurada en su capa. Todavía no asigna nombres semánticos ni
escribe nuevos CUES en la composición.

### Advanced Output y autoasignación

INSTAR puede leer un preset de Advanced Output y compararlo con el catálogo de
visuals. Conserva Input Selection y Output Transformation como espacios
separados, agrupa slices que comparten InputRect y genera sugerencias
revisables; no modifica showfiles, Resolume ni el procesador. El flujo está en
docs/runbooks/instar-advanced-output.md.

La tarjeta de prueba geométrica de NAYADE genera una sola composición desde el
Advanced Output, con colores por input group, etiquetas, bordes, cuadrícula,
movimiento, círculos y cuadrados. Sirve para detectar deformación, inversión,
deslizamiento y solapamiento durante el soundcheck sin modificar el showfile.
La sesión de NAYADE conserva la matriz de pruebas y permite registrar qué
rotación, flip, pattern o marquee fue aprobada en cada input group. El detalle
está en `docs/runbooks/nayade-soundcheck.md`.

La estrategia para adaptar visuales a banners, tótems y superficies extremas
está documentada en `docs/research/instar-adaptacion-superficies-extremas.md`.
INSTAR prioriza derivados target-specific con crop protegido, fondo, pattern o
marquee antes de permitir deformaciones.

Para generar previews de esas adaptaciones desde un plan de mapping:

```powershell
python .\tools\resolume_adapter_cli.py instar-adapt `
  ".\artifacts\mapping-plan.json" `
  --output-dir ".\artifacts\adapt-previews" `
  --dxv-output-dir ".\artifacts\adapt-dxv" `
  --encoder auto
```

El detalle operativo está en `docs/runbooks/instar-adaptacion.md`.
El flujo completo, desde catálogo hasta soundcheck, está en
`docs/runbooks/instar-preshow.md`.

`nayade-processor protocol` transforma los hallazgos de un caso, una
reconciliación y/o un mapping en un checklist de soundcheck ordenado. Incluye
blackout, PLUGE, grises, primarios, geometría y movimiento, y eleva las pruebas
de escalado cuando la evidencia lo justifica. Cada paso conserva su motivo,
observación esperada y campos de registro. El comando no genera patrones, no
envía comandos y no escribe en el procesador.
La decisión de herramientas adoptadas y pendientes está en
`docs/research/adopcion-herramientas.md`.

## Principios

- Priorizar procedimientos que puedan comprobarse en el equipo real.
- Separar hechos observados, hipótesis y acciones recomendadas.
- No versionar medios pesados ni datos que identifiquen innecesariamente al equipo.
- Evitar cambios irreversibles antes de un show.
- Registrar la fecha, el hardware, la versión de software y las condiciones de prueba.

## IMAGO: show

IMAGO observa el show en vivo, registra cues e incidentes, mantiene checkpoints
y publica propuestas reversibles para recovery y cierre. No ejecuta acciones en
Resolume, DMX ni procesadores. El contrato esta en
`schemas/imago-show-session.schema.json` y el flujo en
`docs/runbooks/imago-show.md`.

## Próximos incrementos

1. Validar `INSTAR Media Preflight` con clips sintéticos y casos reales.
2. Mejorar el asistente DXV con procesamiento por lotes y más perfiles.
3. Empaquetar las herramientas como aplicación portable para colegas.
4. Incorporar una plantilla de incidente para flicker, tearing, frames dropped y pérdida de rutas.
5. Registrar resultados de pruebas reales en `docs/cases/` sin copiar medios al repositorio.
6. Diseñar el perfil de señal de RESOLUME para diagnóstico seguro de GPU, HDMI y procesadores LED.
7. Crear en `INSTAR` el importador de `VENUE` y `BASE DE DATOS PUBLICA`, comenzando por Advanced Output XML.
8. Integrar el auditor de composición Resolume con el MCP local, manteniendo el modo de lectura como comportamiento por defecto.
9. Permitir que IMAGO consuma un plan de mapping aprobado, sin aplicar cambios
   automáticamente durante el primer ciclo.

La arquitectura de esta integración está documentada en
`docs/architecture/integracion-resolume_adapter-resolume-mcp.md`.

### Replay del flujo VJ

`vj-replay` verifica desde la CLI el recorrido sintético `INSTAR -> NAYADE ->
IMAGO`, incluyendo show, incidente, recuperación y cierre. Sólo procesa el
fixture indicado, no abre transportes y no ejecuta propuestas ni cambios en el
hardware.

El mismo dispatcher `tools/resolume_adapter_cli.py` acepta el envelope
`ResolumeAdapterSemanticLightFieldReplay` y lo entrega a
`VJAdapter.ingest_semantic_light_field()`. El resultado es un proposal
pendiente, reversible y `proposal_only`; aprobar, rechazar o deshacer requiere
una llamada explícita al adaptador y no ejecuta Resolume ni hardware.

`vj-project` convierte un reporte JSON real de `instar`, `nayade` o `imago` en
un evento canonico o en una proyeccion acotada. La secuencia la entrega el
operador/orquestador y `--previous` permite rechazar saltos de fase. El modo
`projection` no copia rutas privadas ni ejecuta acciones.

`vj-project-replay` encadena un manifest con rutas de reportes de las tres
etapas y devuelve un replay determinista. Las rutas se usan sólo como entrada
y no se incluyen en el reporte generado.

### Diagnóstico portable

La copia portable puede verificarse antes de un show sin abrir Resolume ni
modificar hardware:

```powershell
& ".\tools\Invoke-RESOLUME_ADAPTER.ps1" doctor --report ".\artifacts\doctor.json"
```

El comando revisa Python, módulos base, FFmpeg/FFprobe y los módulos GPU
opcionales. `FAIL` bloquea el entorno base; `WARN` sólo señala una capacidad
opcional o una herramienta externa ausente. El reporte declara sus límites y
no contiene rutas de medios analizados.

### NAYADE y procesadores LED

El catálogo inicial de procesadores está en `data/processors/catalog.json` y
los perfiles físicos de módulos siguen `schemas/module-profile.schema.json`.
NAYADE comienza con descubrimiento USB/COM y snapshots en solo lectura; no
envía comandos ni modifica procesadores. El flujo y sus límites están en
`docs/runbooks/nayade-processor.md`, y la investigación de familias, pitch,
indoor/outdoor y protocolos está en `docs/research/procesadores-led-y-modulos.md`.

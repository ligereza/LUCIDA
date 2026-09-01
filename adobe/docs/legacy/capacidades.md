# Capacidades del Agent Toolkit

Este documento es el mapa general del toolkit. Sirve para elegir la herramienta adecuada, conocer sus entradas y salidas y distinguir lo implementado de lo que todavía depende de un host externo.

## Estados

| Estado | Significado |
|---|---|
| `implemented` | Existe una herramienta ejecutable y hay verificación local. |
| `implemented-unverified` | Existe el contrato y el adaptador, pero falta una prueba completa en el host real. |
| `available-source` | La fuente o librería existe, pero falta crear un wrapper ejecutable. |
| `planned` | Capacidad definida para una fase posterior. |
| `blocked` | Hay un impedimento conocido que debe resolverse antes de continuar. |

## Mapa de capacidades

### 1. SVG, imágenes y gráficos 2D

| ID | Qué resuelve | Entrada | Salida | Estado |
|---|---|---|---|---|
| `svg.create` | Crear un SVG desde una especificación o template | JSON, texto o template | `.svg` | `implemented` |
| `svg.thi-ng-geom` | Crear primitivas geométricas con thi.ng | JSON de formas | `.svg` | `implemented` |
| `svg.embed-image` | Incrustar una imagen raster dentro de SVG | PNG, JPEG o WebP | `.svg` | `implemented` |
| `svg.rasterize` | Convertir SVG complejo a imagen manteniendo su apariencia | `.svg` | `.png` | `implemented` |
| `svg.vectorize` | Convertir raster a paths editables | PNG o JPEG | `.svg` | `implemented` |
| `svg.animate` | Animar atributos, estilos y transformaciones | SVG + timeline | SVG o HTML | `implemented` |
| `svg.particles` | Crear partículas, ruido y movimiento | parámetros de escena | SVG o HTML | `implemented` |
| `svg.validate` | Revisar XML, viewBox, paths y accesibilidad | `.svg` | reporte | `implemented` |
| `svg.preview` | Crear una vista previa local | `.svg` | HTML | `implemented` |
| `image.split` | Dividir una imagen o sprite sheet | imagen + filas/columnas | PNGs + manifiesto | `implemented` |
| `svg.layout` | Componer escenas 2D complejas | escena 2D | `.svg` | `available-source` |
| `svg.morph` | Interpolar entre conjuntos de paths | dos SVG compatibles | animación | `planned` |

### 2. Assets, iconografía y búsqueda

| ID | Qué resuelve | Entrada | Salida | Estado |
|---|---|---|---|---|
| `asset.search` | Resolver conceptos y proponer iconografía | consulta, términos o ancla | resultados semánticos y fuentes | `implemented` |
| `asset.fetch` | Obtener un SVG editable con procedencia | proveedor + identificador | SVG + metadata | `implemented` |
| `asset.select` | Materializar una selección de recursos | resultados + IDs | assets + manifiesto | `implemented` |
| `asset.index-local` | Indexar recursos locales por metadata | raíces de carpetas | catálogo JSON | `implemented` |
| `asset.catalog-groups` | Agrupar por tema, color, tamaño, proporción y formato | catálogo | grupos navegables | `implemented` |
| `semantic.index` | Generar embeddings y actualizar el índice | catálogo + modelo | vectores + índice | `implemented` |
| `semantic.search` | Buscar por texto o similitud visual | consulta + índice | resultados ordenados | `implemented` |

Las fuentes externas, como Iconify, Bioicons, PubChem, ChEBI y OLS, se usan
para investigación o procedencia cuando la tarea lo requiere. LUCIDA mantiene
separados los recursos generados por el proyecto y las librerías descargadas.

### 3. LUCIDA / Context Shelf

| ID | Qué resuelve | Entrada | Salida | Estado |
|---|---|---|---|---|
| `context.publish` | Publicar el contexto de una aplicación creativa | snapshot del host | contexto normalizado | `implemented` |
| `context.analyze` | Extraer términos, paleta, bounds y áreas libres | snapshot | análisis explicable | `implemented` |
| `context.recommend` | Ordenar recursos según contexto y similitud | contexto + catálogo | sugerencias | `implemented` |
| `project.inventory` | Organizar proyecto por lámina, grupo y variación | proyecto local | inventario navegable | `implemented` |
| `selection.save` | Guardar recursos marcados por proyecto y lámina | selección | JSON versionado | `implemented` |
| `companion.explore` | Navegar miniaturas en una ventana flotante | catálogo | vista Electron | `implemented` |
| `companion.drag` | Arrastrar un PNG o SVG a Adobe | tarjeta local | archivo en el destino | `implemented` |
| `adobe.enqueue` | Encolar una acción que requiere un host Adobe | command envelope | job local | `implemented` |

La documentación específica está en [`capacidades_lucida.md`](capacidades_lucida.md)
y [`LUCIDA.md`](LUCIDA.md).

### 4. Blender, 3D y Geometry Nodes

| ID | Qué resuelve | Entrada | Salida | Estado |
|---|---|---|---|---|
| `blender.create-scene` | Crear una escena desde una especificación | JSON de escena | `.blend` | `implemented` |
| `blender.render` | Renderizar una escena | escena | PNG | `implemented` |
| `blender.layout-scene` | Ubicar assets por lámina y construir un carrusel | storyboard + assets | `.blend` + previews | `implemented` |
| `blender.import-glb` | Importar GLB | `.glb` | `.blend` | `implemented` |
| `blender.export-glb` | Exportar una escena | escena | `.glb` | `implemented` |
| `scene3d.create` | Crear un preview 3D interactivo local | JSON | HTML | `implemented` |
| `scene3d.animate` | Animar una escena 3D | escena + timeline | HTML/JS | `available-source` |
| `scene3d.export` | Exportar escenas o frames | escena | GLTF, PNG o video | `planned` |

Geometry Nodes forma parte del flujo procedural en Blender, pero no se debe
afirmar que existe un node graph específico si no hay un `.blend`, manifest o
prueba que lo demuestre.

### 5. Adobe

| ID | Qué resuelve | Entrada | Salida | Estado |
|---|---|---|---|---|
| `adobe.enqueue` | Crear un comando para un host Adobe | envelope | JSON de job | `implemented` |
| `adobe.consume` | Consumir el comando dentro del host | job | documento o export | `implemented-unverified` |
| `photoshop.separate-objects` | Separar sujetos o regiones en capas | imagen + regiones | PSD, PNGs y manifiesto | `implemented-unverified` |
| `adobe.after-effects-render` | Renderizar un proyecto de After Effects | `.aep` + opciones | video o secuencia | `implemented-unverified` |
| `adobe.premiere` | Importar medios y crear secuencias | envelope | proyecto o media | `implemented-unverified` |

Estado de evidencia por host:

| Host | Evidencia |
|---|---|
| Illustrator 2026 | Importación SVG real mediante COM completada. |
| Photoshop 2026 | Importación/exportación por fallback JSX/COM; UXP directo preparado. |
| After Effects | Scripts y `aerender` preparados; prueba real pendiente. |
| Premiere Pro 2020 | Consumidor preparado; ejecutable local no localizado. |

### 6. Datos y automatización

| ID | Qué resuelve | Entrada | Salida | Estado |
|---|---|---|---|---|
| `data.chart` | Crear gráficos desde datos | CSV o JSON | SVG/HTML | `implemented` |
| `data.d3-chart` | Usar escalas y dominios D3 | CSV o JSON | SVG | `implemented` |
| `data.animate` | Animar un gráfico | SVG + timeline | SVG animado | `implemented` |
| `workflow.sequence` | Ejecutar pasos ordenados | lista de tareas | reporte + artefactos | `available-source` |
| `workflow.retry` | Reintentar una tarea con límites | operación + política | resultado o error | `available-source` |
| `workflow.rxjs-events` | Agregar eventos de un flujo | eventos | JSON auditable | `implemented` |
| `workflow.effect-retry` | Aplicar retry bounded | política | JSON | `implemented` |
| `math.stdlib-stats` | Calcular métricas simples | valores | JSON | `implemented` |

### 7. GDKB y trazabilidad

| ID | Qué resuelve | Entrada | Salida | Estado |
|---|---|---|---|---|
| `gdkb.health` | Inspeccionar el runtime | — | versión y operaciones | `implemented` |
| `gdkb.normalize` | Normalizar sin destruir el original | valor | valor normalizado | `implemented` |
| `gdkb.resolve` | Resolver entidades con evidencia | query + candidatos | decisión explicable | `implemented` |
| `gdkb.import` | Canonicalizar registros | JSON/JSONL | observaciones | `implemented` |
| `gdkb.replay` | Reconstruir estado desde eventos | eventos | estado + snapshot | `implemented` |
| `gdkb.merge-event` | Proponer un merge auditable | entidades + evidencia | evento | `implemented` |

## Cómo elegir una capacidad

| Necesidad | Comenzar con |
|---|---|
| Crear o validar SVG | `svg.create` / `svg.validate` |
| Convertir una imagen a vector | `svg.vectorize` |
| Animar un logo o gráfico | `svg.animate` |
| Buscar un icono por concepto | `asset.search` |
| Explorar visuales propios por significado | `semantic.search` |
| Organizar recursos por lámina | `project.inventory` |
| Sugerir un recurso para la capa actual | `context.recommend` |
| Arrastrar un asset a Adobe | `companion.drag` |
| Crear una escena o carrusel en Blender | `blender.layout-scene` |
| Consultar qué está conectado | `integration.sources` + `integration.validate` |
| Preparar un flujo sin ejecutarlo | `integration.plan` |
| Resolver identidad o procedencia | `gdkb.resolve` |

## Contrato de una herramienta

Cada wrapper debe declarar entrada, salida, estado y validación:

```yaml
id: svg.animate
description: Anima un SVG con una línea de tiempo declarativa.
entrypoint: src/tools/svg.mjs
status: implemented
input:
  svg: string | path
  timeline: object
output:
  files: [path]
  preview: path | null
  warnings: string[]
validation:
  - XML válido
  - viewBox presente
```

Las herramientas deben ser repetibles, escribir dentro del workspace, informar
errores claros y no sobrescribir un artefacto salvo que el usuario lo autorice.

## Jobs, seguridad y auditoría

Los trabajos usan esta estructura:

```text
jobs/<id>/request.json
jobs/<id>/status.json
jobs/<id>/summary.md
jobs/<id>/input/
jobs/<id>/work/
jobs/<id>/output/
```

El servidor local limita rutas, valida raíces, restringe cuerpos HTTP, usa
allowlists para operaciones y registra eventos en `logs/audit.ndjson`. No existe
un endpoint genérico para ejecutar shell remoto.

## Verificación

```powershell
cd C:\IA\LUCIDA\adobe
npm run companion:check
npm run verify
```

Una capacidad marcada como `planned` o `implemented-unverified` debe comunicarse
como tal; el agente no debe presentar una preparación como una prueba real.

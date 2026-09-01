# Capacidades de LUCIDA

LUCIDA es el companion visual flotante del toolkit. Extiende el flujo de trabajo
de Photoshop, Illustrator y otras aplicaciones creativas sin reemplazar el
editor ni obligar al usuario a buscar archivos manualmente.

## Qué resuelve

LUCIDA ataca cuatro problemas repetidos:

1. El recurso correcto está en una carpeta distinta a la que se abrió.
2. Buscar `.png` o `.svg` devuelve demasiados resultados y no ayuda a decidir.
3. Una biblioteca de filas y columnas no muestra bien variantes, transparencia o relación con la composición.
4. El usuario quiere revisar recursos para una lámina y conservar la selección antes de insertarlos.

La experiencia central es:

```text
ver → reconocer → comparar → seleccionar → arrastrar → recordar
```

## Capacidades principales

| Capacidad | Qué hace | Estado |
|---|---|---|
| Popup flotante | Mantiene el explorador visible, movible y discreto | `implemented` |
| Exploración visual | Prioriza miniaturas sobre títulos y permite paginar | `implemented` |
| Catálogo local | Lee SVG, PNG y otros recursos dentro de raíces autorizadas | `implemented` |
| Agrupación | Ordena por tema, color, formato, proporción, tamaño y tipo | `implemented` |
| Inventario de proyecto | Relaciona proyecto, lámina, grupo, capa y variaciones | `implemented` |
| Selección por lámina | Guarda checks y recursos elegidos en JSON | `implemented` |
| Búsqueda textual | Busca por términos del usuario | `implemented` |
| Búsqueda semántica | Relaciona conceptos aunque el nombre no coincida exactamente | `implemented` |
| Similitud visual | Permite usar un recurso como ancla de búsqueda | `implemented` |
| Sugerencias contextuales | Combina tema, paleta, proporción y espacio disponible | `implemented` |
| Drag-and-drop | Arrastra PNG/SVG directamente al canvas de Adobe | `implemented` |
| Inserción encolada | Usa el bridge cuando una operación necesita el host | `implemented` |
| Contexto Adobe | Recibe documento, capa y selección cuando UXP lo publica | `implemented-unverified` |
| Multiaplicación | Contrato común para Photoshop, Illustrator, After Effects y Premiere | `implemented-unverified` |

## Modos de uso

### Explorar sin Adobe

No hace falta iniciar Photoshop para:

- elegir un proyecto;
- abrir una lámina;
- revisar grupos y variaciones;
- filtrar por color, formato o proporción;
- buscar por texto o semántica;
- marcar una selección;
- inspeccionar la procedencia del archivo.

### Sugerir con Adobe

Con el adaptador UXP activo, el host puede publicar un snapshot cuando cambia
el documento, la capa, la selección o una operación relevante. LUCIDA usa ese
snapshot para priorizar recursos relacionados con la tarea actual.

La app no necesita grabar la pantalla. Trabaja con metadata y, cuando es
posible, hashes o IDs de recursos ya utilizados.

## Presentación visual

La ventana debe comportarse como una capa de apoyo, no como otra aplicación que
compite por la atención:

- fondo de la ventana con transparencia real;
- miniaturas grandes y legibles;
- damero sólo como indicador de un archivo que realmente contiene damero, no como fondo generado dentro del PNG;
- controles secundarios ocultables;
- navegación por páginas o grupos para no cargar miles de miniaturas a la vez;
- ventana siempre movible y opcionalmente siempre encima;
- título, ruta y metadata visibles sólo al pasar el cursor o abrir detalles.

La grilla puede existir como mecanismo de rendimiento, pero no es el modelo
mental principal. La organización importante ocurre mediante contexto, grupos,
variaciones y similitud.

## Navegación

La interfaz se divide en dos modos:

```text
Sugerido
  ├── para esta capa
  ├── para esta zona libre
  ├── similares al recurso ancla
  └── ya usados / descartados

Explorar
  ├── proyecto
  ├── lámina
  ├── grupo semántico
  ├── tema
  ├── color
  ├── formato
  ├── proporción
  └── tamaño
```

Controles mínimos:

- selector de proyecto;
- selector de lámina;
- `Sugerido` / `Explorar`;
- búsqueda textual opcional;
- filtros rápidos;
- check de selección;
- arrastre de la miniatura;
- botón `+` para la inserción encolada.

## Contexto y detector de composición

El contexto puede contener:

```json
{
  "sessionId": "photoshop-local",
  "host": "photoshop",
  "document": { "id": "doc-1", "name": "lamina-03", "width": 1080, "height": 1080 },
  "activeLayer": {
    "id": "layer-7",
    "name": "riesgo cardiovascular",
    "bounds": { "x": 80, "y": 120, "width": 420, "height": 260 }
  },
  "palette": ["#102a43", "#f26b38", "#e8dfc8"],
  "freeAreas": [
    { "x": 560, "y": 120, "width": 380, "height": 260, "score": 0.91 }
  ],
  "usedAssets": [],
  "source": "uxp"
}
```

El detector calcula áreas con baja ocupación, proporción, tamaño y proximidad a
la capa. Esa información es una señal para ordenar resultados; nunca es una
orden de inserción automática porque una zona vacía puede ser intencional.

## Catálogo y procedencia

El catálogo debe diferenciar:

- `generated`: recursos generados o creados para el proyecto;
- `downloaded-library`: material de librerías externas;
- `project-variant`: variaciones históricas de una lámina;
- `reference`: recursos de referencia que no deben confundirse con producción.

La vista propia de LUCIDA prioriza los recursos generados. Las fuentes externas
pueden permanecer en el disco para referencia, pero no deben aparecer como si
fueran recursos creados por el proyecto.

Cada registro debe conservar, cuando exista:

```json
{
  "assetId": "asset-014",
  "path": "projects/chemsex/context-shelf-library/01-generated/14-interaccion-ghb-alcohol-v3.png",
  "format": "png",
  "width": 1024,
  "height": 1024,
  "hasAlpha": true,
  "theme": ["interaccion", "ghb", "alcohol"],
  "dominantColor": "#102a43",
  "sourceKind": "generated",
  "sha256": "..."
}
```

## Búsqueda semántica

LUCIDA usa MobileCLIP-S2 local para generar embeddings de texto e imagen. El
runtime actual está preparado para CUDA mediante ONNX Runtime GPU y usa la CPU
sólo como respaldo o para trabajo auxiliar.

Estado verificado:

- checkpoint MobileCLIP-S2 de Apple;
- modelos ONNX separados para imagen y texto;
- tokenizer local;
- índice local de 407 recursos;
- 407 recursos codificados sin fallos;
- búsqueda semántica probada con `device: cuda`;
- no se requiere descargar modelos desde una fuente no verificada.

La búsqueda semántica ordena candidatos; no decide por sí sola qué debe entrar
en la composición. La decisión final queda en manos del usuario.

## Selecciones por proyecto y lámina

La selección se guarda por proyecto y lámina para poder volver a ella:

```json
{
  "schemaVersion": 1,
  "projectId": "chemsex",
  "slideId": "slide-03",
  "items": [
    {
      "assetId": "asset-014",
      "path": "projects/chemsex/context-shelf-library/01-generated/14-interaccion-ghb-alcohol-v3.png",
      "role": "selected",
      "checkedAt": "2026-08-31T00:00:00.000Z"
    }
  ],
  "updatedAt": "2026-08-31T00:00:00.000Z"
}
```

La selección puede incluir varias versiones del mismo concepto. No se deben
eliminar variantes sólo porque sean visualmente parecidas sin conservar su
procedencia y el motivo de la elección.

## Inserción en Adobe

El camino principal es el drag-and-drop:

1. abrir una tarjeta en LUCIDA;
2. arrastrarla al canvas visible de Photoshop o Illustrator;
3. dejar que Adobe importe el archivo normalmente.

Este flujo no necesita bridge. El bridge sólo interviene para publicar contexto,
solicitar recomendaciones, encolar una operación Adobe o recibir un resultado.

## API local permitida

El companion sólo usa rutas locales allowlisted:

| Ruta | Uso |
|---|---|
| `GET /context/current` | leer el último snapshot |
| `POST /recommendations` | calcular sugerencias |
| `GET /catalog/groups` | listar agrupaciones |
| `GET /catalog/assets` | paginar y filtrar recursos |
| `GET /catalog/projects` | listar proyectos, láminas y variaciones |
| `GET /semantic/status` | comprobar runtime e índice |
| `POST /semantic/index` | actualizar embeddings |
| `POST /insert` | encolar una inserción |

El bridge escucha en `127.0.0.1:47921` y no expone un ejecutor de shell ni
evalúa JavaScript recibido desde la red.

## Ejecutar

```powershell
cd C:\IA\LUCIDA\adobe
npm run companion:start
```

La app puede explorar sin Adobe. Para contexto de Photoshop se debe cargar el
manifiesto UXP en UXP Developer Tool y abrir el panel correspondiente.

## Verificación operativa

```powershell
cd C:\IA\LUCIDA\adobe
npm run companion:check
npm run verify
npm run tool -- semantic status --model mobileclip_s2
```

Si el estado muestra `torch: false`, no significa que la búsqueda esté rota:
el worker residente usa ONNX Runtime y no importa PyTorch deliberadamente para
reducir memoria y evitar cargar un segundo runtime.

## Límites actuales

- El contexto completo depende de lo que cada host Adobe exponga.
- Reconocer una capa visualmente no equivale a leer su nombre desde UXP.
- Las áreas libres son una señal geométrica, no una interpretación editorial.
- MobileCLIP recupera y ordena; no sustituye segmentación ni criterio de diseño.
- After Effects y Premiere tienen contratos preparados, pero requieren pruebas en sus hosts instalados.
- LUCIDA no modifica un documento sin una acción explícita del usuario.

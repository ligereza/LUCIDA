# Plan de Adobe Context Shelf / LUCIDA

## Objetivo

Construir una herramienta visual flotante que extienda el flujo de trabajo de Adobe sin convertirlo en otro editor. El usuario debe poder mirar, comparar, seleccionar y arrastrar recursos mientras trabaja en una lámina, una capa o una composición.

## Decisiones de producto

1. La superficie principal es un popup flotante, móvil y discreto.
2. La miniatura es el elemento dominante; el texto sólo apoya la búsqueda y la accesibilidad.
3. Explorar y sugerir son modos distintos: explorar no exige conocer el término exacto y sugerir usa el contexto disponible.
4. El proyecto se organiza por lámina, grupo, capa y variación, no sólo por carpetas.
5. El arrastre de archivos es el camino más simple para insertar un recurso.
6. El bridge no debe ser necesario para el drag-and-drop; sólo para contexto e inserciones que requieran comunicación con Adobe.
7. La app debe funcionar sin Adobe abierto para que el catálogo y la búsqueda sigan siendo útiles.

## Flujo principal

```text
Abrir LUCIDA
   │
   ├── sin Adobe: elegir proyecto → lámina → explorar / buscar / seleccionar
   │
   └── con Adobe: recibir snapshot → identificar documento/lámina/capa
                                      │
                                      ▼
                             sugerir recursos visuales
                                      │
                         revisar, marcar y arrastrar al canvas
```

## Contexto que puede aportar Adobe

El snapshot no necesita capturar la pantalla. El adaptador debe publicar, cuando el host lo permita:

- aplicación y versión;
- documento activo y dimensiones;
- capa o grupo activo y nombre;
- selección y límites de la capa;
- colores dominantes y color de fondo;
- rectángulos libres o zonas con baja ocupación;
- recursos ya insertados, cuando puedan identificarse;
- timestamp, sesión y fuente del dato.

Si un campo no está disponible, debe quedar como `null` o `unknown`; LUCIDA no debe inventarlo.

## Modelo de datos mínimo

```json
{
  "sessionId": "photoshop-local",
  "host": "photoshop",
  "document": {
    "id": "doc-1",
    "name": "chemsex-lamina-03",
    "width": 1080,
    "height": 1080
  },
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
  "source": "uxp",
  "capturedAt": "2026-08-31T00:00:00.000Z"
}
```

## Selecciones

La selección se guarda por proyecto y lámina, con una referencia estable al recurso y un registro de cuándo se marcó. Debe conservar el archivo elegido aunque existan múltiples variaciones.

```json
{
  "schemaVersion": 1,
  "projectId": "chemsex",
  "slideId": "slide-03",
  "items": [
    {
      "assetId": "asset-014",
      "path": "projects/chemsex/context-shelf-library/01-generated/14-interaccion-ghb-alcohol-v3.png",
      "role": "suggested",
      "checkedAt": "2026-08-31T00:00:00.000Z"
    }
  ],
  "updatedAt": "2026-08-31T00:00:00.000Z"
}
```

## API local

El companion usa sólo rutas allowlisted del bridge:

| Ruta | Función |
|---|---|
| `GET /context/current` | leer el último contexto publicado |
| `POST /recommendations` | calcular sugerencias para el contexto |
| `GET /catalog/groups` | obtener grupos de navegación |
| `GET /catalog/assets` | paginar recursos y aplicar filtros |
| `GET /catalog/projects` | inventariar proyectos, láminas y variaciones |
| `GET /semantic/status` | comprobar MobileCLIP e índice |
| `POST /semantic/index` | generar o actualizar embeddings |
| `POST /insert` | encolar una inserción que requiere Adobe |

## Fases

### Fase 1 — catálogo y popup

- miniaturas transparentes;
- navegación por proyecto y lámina;
- búsqueda por filtros;
- arrastre nativo de PNG/SVG;
- selección persistente.

### Fase 2 — búsqueda semántica

- MobileCLIP-S2 local;
- búsqueda por texto;
- búsqueda por imagen o recurso ancla;
- agrupación de duplicados y variantes;
- actualización incremental del índice.

### Fase 3 — contexto Adobe

- snapshot UXP de Photoshop;
- documento, capa, paleta y áreas libres;
- recomendaciones contextuales;
- detección de recursos ya usados sin grabar pantalla.

### Fase 4 — multiaplicación

- Illustrator;
- After Effects;
- Premiere;
- contrato común de contexto e inserción;
- adaptadores específicos sólo donde cada host lo exija.

## Criterios de éxito

- encontrar un recurso visual sin recordar su carpeta ni extensión;
- distinguir entre “quiero explorar” y “quiero sugerencias para esta capa”;
- insertar por drag-and-drop sin mantener dos procesos manualmente;
- mantener las selecciones por lámina;
- no modificar el documento sin una acción explícita;
- seguir siendo útil cuando Adobe está cerrado;
- no saturar la CPU durante la indexación: usar CUDA y limitar workers auxiliares.

## Riesgos y límites

- No todos los hosts Adobe exponen el mismo contexto.
- Reconocer una capa visualmente es distinto de leer su nombre desde UXP.
- Una zona libre geométrica no siempre es una zona semánticamente adecuada.
- MobileCLIP ayuda a ordenar y recuperar; no sustituye una segmentación perfecta ni entiende por sí solo la intención editorial.
- La app debe mostrar incertidumbre cuando el contexto sea incompleto.

# Mapa histórico de LUCIDA

## Alcance

LUCIDA es el nombre de la aplicación flotante Context Shelf: catálogo visual local, contexto de proyecto, selección de iconos, drag-and-drop, integración con Adobe y exploraciones de análisis semántico. Este documento sirve para migrar responsabilidades, no para trasladar datos de proyectos al núcleo.

## Correspondencias

| Componente histórico | Responsabilidad | Destino genérico | Qué cambia |
|---|---|---|---|
| Context Shelf/companion | Ventana flotante, preview y selección | `clients/companion` | Sólo queda el modelo de estado; la UI se integra aparte |
| Contexto Adobe | Documento, selección, capas, paleta | `core/context` + `adapters/adobe` | El core acepta cualquier host y campos desconocidos |
| Análisis de composición | Áreas ocupadas/libres, términos y capas | `core/analysis` | Se eliminan supuestos sobre láminas y proyectos específicos |
| Recomendaciones | Recursos ordenados por contexto | `core/proposals` + providers | Ranking determinista y explicable |
| Inserción/drag | Entrega de recurso al host | `core/actions` + adapter | Nunca es implícita; exige autorización y resultado |
| Bridge local | Comunicación companion/host | `transports/local-http`, `file-queue`, `plugin-bridge` | Allowlist estricta y sin shell |
| Auditoría | Estado/acciones/eventos | `core/audit` + replay | Cadena hash y fixtures reproducibles |
| Jobs | Indexado y tareas aisladas | `core/jobs` | Cancelación preserva evidencia y no ejecuta comandos |
| MobileCLIP/embeddings | Búsqueda visual/semántica | providers opcionales | No forma parte de la instalación base |
| Adobe UXP/JSX | Operaciones Photoshop/Illustrator | `adapters/adobe` | El código del host no entra al contrato central |
| Blender/Geometry Nodes | Contexto y acciones Blender | `adapters/blender` | No se copian escenas, geometría ni renders |
| GDKB | Fuente o destino externo | `adapters/gdkb` | No se copia la base ni su corpus |

## No correspondencias

Los assets generados o descargados, las láminas Chemsex, los catálogos personales, las bases de recursos, los renders, los proyectos concretos y los clones de terceros no tienen destino en `generic-interface-layer`. Pertenecen a aplicaciones, fixtures privados o repositorios de datos separados.

## Compatibilidad gradual

1. El companion existente puede seguir consumiendo su bridge histórico.
2. Un adaptador nuevo transforma el contexto histórico al contrato genérico.
3. Se comparan propuestas y resultados con fixtures, sin conectar assets reales.
4. Se habilita una acción host-specific detrás de permisos y auditoría.
5. Sólo después se evalúa sustituir rutas antiguas.

No se debe hacer un cambio masivo de endpoints ni borrar el bridge histórico durante esta extracción.

## Nombre y migración

El paquete usa `generic-interface-layer` como núcleo técnico de LUCIDA. Esto permite reutilizar la capa para Photoshop, Illustrator, Premiere, After Effects, Blender, XIO/VJ u otros hosts sin arrastrar el alcance editorial de la aplicación original.

# LUCIDA

LUCIDA es un acompañante visual local para explorar, ordenar y reutilizar recursos gráficos mientras se trabaja en Photoshop, Illustrator u otras aplicaciones creativas.

## Problema que resuelve

El flujo normal obliga a salir del documento, abrir el explorador de archivos y buscar dentro de carpetas poco claras. LUCIDA mantiene una ventana flotante y discreta que permite:

- explorar miniaturas sin depender de nombres de archivo;
- buscar por concepto, color, formato, proporción o similitud visual;
- ver el proyecto activo organizado por lámina, grupo y variación;
- guardar una selección de recursos por proyecto y lámina;
- arrastrar un PNG o SVG directamente al canvas de Adobe;
- recibir sugerencias según el contexto disponible de la composición.

## Principio de diseño

LUCIDA no reemplaza Photoshop ni Illustrator y no intenta convertirse en un editor de composiciones. Extiende la aplicación que ya está abierta con una capa de exploración visual. La ventana puede permanecer sobre otras aplicaciones, moverse y mostrar los recursos con transparencia real.

La integración con Adobe es opcional para explorar. Sin Adobe abierto se puede navegar el catálogo, revisar proyectos y usar la búsqueda semántica. Con un adaptador UXP activo, LUCIDA también puede recibir documento, capa, selección, paleta, dimensiones y zonas libres de la composición.

## Arquitectura actual

```text
Adobe UXP (opcional)
        │ snapshot de contexto
        ▼
bridge HTTP local 127.0.0.1:47921
        │
        ├── análisis de contexto y zonas libres
        ├── catálogo local de SVG/PNG/imagen
        ├── índice MobileCLIP-S2
        └── recomendaciones y selección persistente
                         │
                         ▼
                 LUCIDA Companion (Electron)
                         │
             arrastre de archivo o inserción encolada
```

Componentes principales:

- `companion/`: ventana flotante Electron, IPC allowlisted y navegación visual.
- `adobe-context-shelf/photoshop-uxp/`: adaptador UXP para publicar el contexto de Photoshop.
- `src/server.mjs`: bridge local y API HTTP.
- `src/tools/catalog-groups.mjs`: inventario, filtros y agrupaciones.
- `src/tools/project-inventory.mjs`: proyectos, láminas, capas y variaciones.
- `src/tools/context-analysis.mjs`: términos, paleta, proporción y espacio libre.
- `src/tools/mobileclip.mjs`: estado, indexación y búsqueda semántica.
- `scripts/mobileclip-worker.py`: inferencia ONNX con proveedores CUDA/CPU de respaldo.
- `companion/selection.schema.json`: contrato de selecciones guardadas.

## Funciones disponibles

### Explorar

La pestaña `Explorar` navega el catálogo por tema, color dominante, tamaño, dimensiones, proporción, formato, tipo y variante. La presentación prioriza la miniatura; el nombre y la metadata quedan como información secundaria.

### Proyecto

La pestaña `Proyecto` muestra el inventario por lámina. Cada lámina puede desplegar grupos semánticos, capas y todas las variaciones encontradas. El usuario puede marcar recursos y conservar la selección asociada a `projectId` y `slideId`.

### Sugerencias

Cuando existe un snapshot de Adobe, las sugerencias combinan el tema de la capa, términos visuales, paleta, formato, relación de aspecto y espacio libre. La sugerencia es una ayuda de navegación: no modifica el documento automáticamente.

### Inserción

El arrastre de una tarjeta entrega el archivo local directamente al canvas visible de Adobe. No depende del bridge. El botón `+` conserva la ruta de inserción encolada para las operaciones que sí requieren un adaptador de Adobe.

### Búsqueda semántica

MobileCLIP-S2 se ejecuta localmente mediante ONNX Runtime con CUDA cuando está disponible. El índice actual contiene 407 recursos generados o propios. La búsqueda por texto devuelve recursos relacionados aunque el nombre del archivo no coincida literalmente.

## Privacidad y límites

- No se graba la pantalla continuamente.
- No se envían imágenes a un servicio remoto para buscar.
- El bridge escucha sólo en `127.0.0.1`.
- La API no ejecuta JavaScript recibido desde la red ni shell arbitrario.
- El catálogo de LUCIDA debe priorizar recursos generados o seleccionados por el usuario; las librerías descargadas permanecen fuera de la vista propia.
- El contexto de Adobe sólo existe cuando un adaptador lo publica.

## Ejecutar

```powershell
cd C:\IA\LUCIDA\adobe
npm run companion:start
```

El companion inicia o reutiliza el bridge local. Para probar contexto de Photoshop hay que cargar el manifiesto UXP y abrir el panel correspondiente; para explorar y buscar recursos no es necesario abrir Adobe.

## Estado

Verificado localmente:

- ventana flotante y bridge local;
- catálogo de recursos propios y variantes;
- arrastre de archivos al destino;
- selección persistente por proyecto y lámina;
- MobileCLIP-S2 convertido a ONNX;
- 407 embeddings generados con CUDA;
- búsqueda semántica funcional;
- comprobaciones de sintaxis e integridad del toolkit.

Pendiente o dependiente del host:

- lectura directa y completa del contexto en cada aplicación Adobe;
- ejecución UXP directa de Photoshop desde el host;
- consumidores reales para After Effects y Premiere cuando sus instalaciones estén disponibles.

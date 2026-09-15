# Adaptive composition

La primera versión del compositor adaptativo de LUCIDA/ADOBE es local,
determinista y proposal-only. Recibe bloques de texto, capas y regiones
ocupadas; no modifica documentos de Adobe.

## Modelo

El compositor representa una lámina como:

```text
canvas + occupied regions + text blocks + visual blocks
    -> white-space candidates
    -> typography fit
    -> layout variants
    -> ranked proposals
```

El texto recibido se conserva literalmente. El motor solo puede dividirlo en
fragmentos que vuelven a concatenar exactamente la cadena original.

## Escala tipográfica

El tamaño se expresa en píxeles del lienzo de 1080 px. Su tamaño aproximado en
un teléfono se calcula como:

```text
displayPx = sourcePx * previewWidth / canvasWidth
```

La configuración inicial usa:

- cuerpo: mínimo 44 px, preferido 50 px, máximo 60 px;
- subtítulo: 56–80 px;
- título: 96–144 px;
- anchos de vista: 360, 390 y 430 px.

La propuesta se considera más legible cuando el cuerpo preferido alcanza al
menos 16 px en la vista de teléfono más pequeña. Si el contenido no cabe, el
motor intenta reducir hasta el mínimo de 44 px y luego propone división en
páginas.

## Espacio libre

La detección inicial transforma las regiones ocupadas en una retícula de 24 x
32 celdas. Una celda se considera ocupada cuando una región cubre al menos el
16% de su área. Las celdas libres se agrupan por conectividad y se buscan
rectángulos máximos. Las regiones declaradas por el host tienen prioridad.

Esta es una aproximación geométrica: todavía no interpreta píxeles de una
imagen plana. El adaptador puede mejorarla enviando bounds de capas o regiones
seguras explícitas.

## Propuestas

Se prueban cuatro variantes:

- columna única;
- texto e ilustración lateral;
- texto arriba e ilustración abajo;
- ilustración arriba y texto abajo.

Cada propuesta incluye bounds, tamaño tipográfico, líneas estimadas, densidad,
espacio restante, páginas sugeridas, advertencias y razones de puntuación.

La puntuación combina ajuste, legibilidad, densidad, calidad del espacio libre y
adecuación de la variante. El resultado es una recomendación auditable, no una
orden de edición.

## Integración

Al publicar un contexto mediante `POST /context`, el resultado de
`GET /analysis/current` incluye `analysis.composition`. El host puede
renderizar las propuestas, pedir una confirmación y ejecutar una operación
separada mediante la cola existente.

# Mapa de scripting Adobe

Adobe funciona como una estacion especializada dentro del flujo, no como la
fuente de verdad de la composicion. El toolkit entrega archivos y manifiestos a
un job; el host Adobe consume una orden y escribe resultados en el mismo job.

## Photoshop

Hay dos consumidores para la misma orden:

- `photoshop/agent.psjs`: runtime UXP moderno y `batchPlay`.
- `photoshop/agent.jsx`: fallback ExtendScript/COM para automatizacion local.

Operaciones:

- `import-svg`: abre/importa SVG y exporta el resultado.
- `separate-objects`: recibe `mode: subject|regions`, genera PNG transparentes,
  PSD y `manifest.json`.

En `regions`, cada objeto tiene bounds en pixeles. El resultado registra
`selectionMethod` y `selectionError`. Si Select Subject no aisla realmente el
objeto, se conserva el metodo `rectangle-fallback`; el sistema no lo presenta
como segmentacion semantica exitosa.

Ejemplo de orden:

```json
{
  "app": "photoshop",
  "operation": "separate-objects",
  "input": "jobs/<job>/input/photoshop-source-image.png",
  "options": {
    "mode": "regions",
    "objects": [
      { "name": "subject", "bounds": { "left": 120, "top": 180, "right": 620, "bottom": 1280 } }
    ],
    "output": "jobs/<job>/output/separated/manifest.json",
    "psdOutput": "jobs/<job>/output/separated/objects.psd"
  }
}
```

Las acciones `batchPlay` deben permanecer en el adapter y no llegar como
Javascript arbitrario desde el bridge. Para descubrir una accion nueva se puede
grabarla en Photoshop, copiar su ActionJSON/JavaScript y encapsularla en una
operacion allowlisted.

## Illustrator

`illustrator/agent.jsx` importa los SVG generados por el workflow y conserva
sus identificadores de zona (`text-zone`, `illustration-zone`, `generated-icon`).
Es el lugar adecuado para limpieza vectorial, ajustes finales y exportacion de
SVG/PDF, mientras que Blender conserva la composicion espacial, los materiales
y la animacion.

## After Effects y Premiere

Los consumidores JSX/ExtendScript estan presentes como colas, pero siguen
marcados como pendientes de validacion de host. After Effects puede recibir
un SVG o un proyecto para render; Premiere puede crear una secuencia y exportar.
No se consideran parte del camino critico hasta que el host produzca un resultado
verificable.

## Contrato entre Adobe y Blender

Adobe devuelve assets con `id`, `source`, `bounds`, `selectionMethod` y
`selectionError`. Blender recibe el manifest, aplica placement y conecta cada
asset al grupo `GN_Asset_2D_Transform`. La imagen rasterizada es un fallback de
apariencia; el PSD, SVG o PNG separado se conserva como evidencia de entrada.

## Fuentes oficiales

- [Photoshop Document API](https://developer.adobe.com/photoshop/uxp/ps_reference/classes/document/)
- [Photoshop Layer API](https://developer.adobe.com/photoshop/uxp/ps_reference/classes/layer/)
- [Photoshop batchPlay](https://developer.adobe.com/photoshop/uxp/ps_reference/media/batchplay/)
- [Photoshop Selection API](https://developer.adobe.com/photoshop/uxp/ps_reference/classes/selection/)
- [Adobe ActionJSON](https://developer.adobe.com/firefly-services/docs/photoshop/guides/actionjson-endpoint/)

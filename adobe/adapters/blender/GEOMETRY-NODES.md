# Blender, Cycles y Geometry Nodes

Este adaptador usa Blender como compositor editable y como salida final del
flujo. El archivo de entrada es un manifiesto JSON: el texto, las zonas, los
assets y sus transformaciones permanecen separados para poder regenerar una
lamina sin perder editabilidad.

## Regla de render

La función `configure_cycles()` fuerza `scene.render.engine = "CYCLES"` y
configura muestras y denoise. No se debe cambiar a Eevee para una salida de
produccion. El modo de previsualizacion puede ser un render de baja cantidad de
muestras, pero sigue siendo Cycles.

## Grupos generados

`agent_blender.py` crea dos familias de grupos:

- `GN_Asset_2D_Transform`: se añade a cada asset importado. Sus controles son
  `Scale X`, `Scale Y`, `Offset X`, `Offset Y`, `Rotation` y `Pulse`.
- `GN_Slide_XX_<theme>`: se crea por slide para representar las cajas de texto
  y de ilustracion calculadas en el storyboard. Sus controles son `Text Width`,
  `Text Height`, `Text X`, `Text Y`, `Art Width`, `Art Height`, `Art X`, `Art Y`
  y `Depth`.

Las dimensiones de las zonas se expresan como fraccion del canvas en el
manifiesto (`0..1`). El adaptador las convierte a unidades de Blender. El eje
Y del documento crece hacia abajo; el eje Y de la escena crece hacia arriba,
por eso la conversion se realiza en el propio grupo de layout.

## Especificacion minima

```json
{
  "canvas": { "width": 1080, "height": 1440, "resolution": 1, "unit": "px" },
  "design": { "cyclesSamples": 64 },
  "parts": [
    {
      "index": 0,
      "theme": "context",
      "textBox": { "x": 0.08, "y": 0.08, "width": 0.42, "height": 0.36 },
      "artBox": { "x": 0.56, "y": 0.18, "width": 0.34, "height": 0.52 }
    }
  ],
  "assets": [
    {
      "id": "network",
      "kind": "svg",
      "source": "assets/network.svg",
      "part": 0,
      "placement": { "x": 0.56, "y": 0.18, "width": 0.34, "height": 0.52 },
      "singleSlide": true
    }
  ]
}
```

Para un asset que debe pertenecer unicamente al slide seleccionado, usar
`singleSlide: true`. Para un asset compartido, usar `part`, `slide` o una
referencia de manifest. El renderer no vuelve a interpretar la ilustracion ni
la convierte en una imagen plana si el SVG puede importarse como curvas.

## SVG y color

El parser local resuelve estilos CSS, `fill`, `stroke`, opacidad y transforms.
Cuando se importa SVG se intenta mantener curvas y materiales separados. Para
rasters se usa un material de emision con textura sRGB y alpha, evitando que
Cycles oscurezca una ilustracion plana por una interpretacion fisica de sus
colores. Si el SVG tiene filtros o texto que el parser no puede representar,
`image.rasterize-svg` con CairoSVG es el fallback visual, conservando el SVG
original como fuente editable.

## Animacion

Los controles del modifier son propiedades animables de Blender. Ejemplo desde
la consola de Blender:

```python
obj = bpy.data.objects["asset_network"]
modifier = obj.modifiers[0]
modifier["Input_5"] = 0.0  # Rotation, el identificador real se lee del modifier
modifier.keyframe_insert(data_path='["Input_5"]', frame=1)
modifier["Input_5"] = 0.08
modifier.keyframe_insert(data_path='["Input_5"]', frame=24)
```

El script debe consultar los identificadores de sockets escritos en
`geometry_nodes_controls`; no debe asumir que Blender mantiene el mismo
`Input_N` entre versiones.

## Operaciones disponibles

```powershell
npm run tool -- blender run --operation layout-scene --spec projects/chemsex/storyboard.json --output jobs/manual/output/chemsex.blend --render-output jobs/manual/output/chemsex.png
npm run tool -- blender run --operation render --spec projects/chemsex/storyboard.json --output jobs/manual/output/chemsex.blend --render-output jobs/manual/output/chemsex.png
```

Para control live se usa el puente de consola de Blender y el script versionado
`adapters/blender/agent_blender.py`. Para ejecuciones repetibles, el manifiesto
es la fuente de verdad y el `.blend` es un artefacto editable generado.

## Limites actuales

Los repositorios `umbrella`, `d3`, `three.js`, `effect`, `rxjs` y `stdlib` estan
inventariados como fuentes disponibles, pero no se importan automaticamente en
Blender. Esa separacion evita convertir el bridge en un cargador arbitrario.
Su integracion debe entrar por adaptadores pequenos y declarados: geometria y
SVG desde thi.ng, layout desde D3, preview web desde three.js, orquestacion
durable desde Effect/RxJS y calculo desde stdlib.

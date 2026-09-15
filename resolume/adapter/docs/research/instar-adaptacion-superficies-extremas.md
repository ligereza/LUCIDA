# INSTAR: adaptación de visuales a superficies extremas

## Problema

Una visual 16:9 no puede llenar una superficie 10:1 o 1:10 conservando a la
vez todo su contenido, su proporción y una composición estable. Siempre hay
que elegir entre recortar, dejar espacio, repetir, desplazar o deformar.

INSTAR no debe buscar una única respuesta universal. Debe seleccionar una
estrategia según la proporción del slice, el tipo de contenido y la evidencia
visual disponible.

## Herramientas investigadas

| Herramienta | Aporta | Encaje en RESOLUME_ADAPTER | Decisión |
| --- | --- | --- | --- |
| FFmpeg | crop, cropdetect, scale proporcional, pad, overlay, loop, filtros temporales y expresiones por frame | Render reproducible por lote para video | Base de INSTAR |
| FFmpeg + libplacebo | Escalado y procesamiento con GPU/Vulkan, además de gestión de color y debanding | Reduce trabajo de CPU cuando la cadena conserva frames en GPU | Backend GPU opcional |
| OpenCV | Crop dinámico, affine/perspective warp, remap, tracking y detección de regiones relevantes | Decide dónde mirar; no es el encoder final | Analizador de contenido |
| GStreamer | Compositor, crop, flip y escalado; tiene elementos GL y backends de aceleración | Preview o procesamiento en vivo | Fase posterior |
| libvips | Smart crop y resize eficiente para imágenes | Logos, PNG y stills del catálogo | Adaptador de imágenes |
| ImageMagick | Crop, extent, composición, seam carving y operaciones raster | Generar fondos, stills y pruebas | Complementario |
| smartcrop.js | Selecciona crops usando bordes, saturación, piel y regiones impulsadas por rostros | Buen prototipo de atención para imágenes | Referencia, no motor de video |
| VapourSynth | Scripts reproducibles de crop, resize, flip, stack y composición por frames | Pipelines técnicos y batch avanzados | Alternativa, no primera dependencia |
| Natron | Compositor nodal, Python y render por línea de comandos | Plantillas complejas creadas por artistas | Herramienta de autoría, no núcleo |
| SAM 2 | Segmentación y seguimiento de objetos en video | Separar sujeto y crear fondo extendido | Opcional y pesado |

## Qué puede hacer realmente INSTAR

### 1. Crop protegido

Calcula un crop que llena el slice conservando la proporción. OpenCV permite
calcular crops y transformaciones geométricas; FFmpeg puede ejecutar el crop
por frame y cambiar su posición con expresiones temporales.

Para una superficie 10:1 esta estrategia solo es aceptable si la visual es
abstracta o si el sujeto importante permanece dentro de la franja elegida.

### 2. Fit con fondo complementario

La visual se conserva completa y el espacio restante se rellena con un fondo
derivado: color dominante, gradiente, blur ampliado o una copia reflejada.
Sirve para logos, rostros y material con composición central, pero no entrega
una superficie completamente llena con el contenido original.

### 3. Pattern

La visual se escala manteniendo su proporción y se repite en el eje necesario.
El patrón puede ser:

- repetición directa;
- espejo alternado para reducir cortes visibles;
- mosaico con desplazamiento de fase;
- varias copias con pequeñas diferencias de escala o rotación.

Esta es la estrategia más segura para texturas, ruido, partículas y loops
abstractos. No debe aplicarse automáticamente a texto, rostros o logos.

### 4. Marquee

La visual se escala a la altura —o al ancho, si la superficie es vertical— y
se desplaza lentamente por el slice con wrap. No intenta fingir que una visual
16:9 es 10:1: convierte la superficie en una ventana móvil sobre el material.

Es adecuada para movimiento continuo, texturas y elementos gráficos anchos.
Debe evitarse si el clip depende de una composición fija o si el contenido
queda ilegible durante el desplazamiento.

### 5. Crop dinámico con atención

OpenCV puede recalcular el área visible por frame a partir de tracking, bordes,
rostros u objetos. El resultado debe suavizarse temporalmente para evitar
temblores. Es útil para un sujeto principal, pero no es confiable como regla
general para visuales abstractas.

### 6. Seam carving o expansión generativa

ImageMagick ofrece seam carving para imágenes. SAM 2 puede entregar máscaras de
objetos en video y permitir una composición con fondo extendido. Ambos caminos
son interesantes para material estático o clips especiales, pero no deben ser
la primera solución para un show: pueden cambiar la forma de personas, letras
y geometrías, y el procesamiento puede ser pesado.

## Arquitectura recomendada

```text
XML Advanced Output + catálogo INSTAR
                |
                v
       clasificación de superficie
                |
     +----------+----------+----------------+
     |                     |                |
  crop protegido       fit/fondo         pattern/marquee
     |                     |                |
     +----------+----------+----------------+
                |
                v
      render target-specific con FFmpeg
                |
                v
          DXV para Resolume
```

La decisión debe quedar guardada como una receta de render por slice o
`input_group`, no como una orden de modificación del XML. El archivo original
se conserva y el resultado es un derivado nuevo, por ejemplo:

```json
{
  "strategy": "pattern",
  "axis": "horizontal",
  "target": {"width": 1520, "height": 180},
  "source": "gorra.mp4",
  "mirror_alternate": true,
  "requires_preview": true
}
```

## Selección para INSTAR

### Primera versión

1. Usar FFmpeg para renderizar video y conservar una cadena reproducible.
2. Usar el perfil GPU/espacial existente para estimar si los bordes permiten
   repetición.
3. Usar tokens y análisis básico para proteger texto, logos, rostros y círculos.
4. Generar tres candidatos por superficie: `crop`, `pattern` y `marquee`.
5. Renderizar previews pequeños antes del DXV final.
6. Convertir solo la opción aprobada a DXV.

### No incluir todavía

- Natron como dependencia obligatoria: añade una aplicación completa cuando
  necesitamos un motor batch pequeño y determinista.
- SAM 2 por defecto: su coste de instalación, memoria y revisión humana no se
  justifica para la mayoría de loops VJ abstractos.
- Seam carving para video: puede producir deformaciones semánticas difíciles
  de detectar en un análisis numérico.
- Autoaplicación de crop a rostros, texto, logos o geometría circular.

## Herramientas y evidencia

- FFmpeg documenta `crop`, `cropdetect`, `scale`, `loop`, `scroll`, expresiones
  por frame y `libplacebo` para procesamiento GPU: <https://ffmpeg.org/ffmpeg-filters.html>.
- OpenCV documenta `resize`, `remap`, `warpAffine` y `warpPerspective` para
  transformaciones geométricas: <https://docs.opencv.org/4.x/da/d54/group__imgproc__transform.html>.
- GStreamer documenta `aspectratiocrop`, `videocrop`, `videoflip` y su
  compositor; también documenta backends de aceleración: <https://gstreamer.freedesktop.org/documentation/compositor/>.
- libvips documenta thumbnails con crop inteligente sin romper la proporción
  salvo que se solicite explícitamente: <https://www.libvips.org/API/current/ctor.Image.thumbnail.html>.
- ImageMagick documenta `-crop`, `-extent` y `-liquid-rescale`:
  <https://imagemagick.org/command-line-options/>.
- smartcrop.js explica su ranking de bordes, saturación, piel y rostros:
  <https://github.com/jwagner/smartcrop.js/>.
- Natron ofrece composición nodal, Python y render por línea de comandos:
  <https://natron.readthedocs.io/en/rb-2.6/index.html>.
- VapourSynth expone crop, resize, flip, loop y stacking mediante scripts:
  <https://www.vapoursynth.com/doc/>.
- SAM 2 ofrece segmentación guiada y seguimiento en imágenes y video:
  <https://github.com/facebookresearch/sam2>.

## Conclusión

El núcleo de INSTAR debe ser un **adaptador de contenido a superficie**, no un
editor general. Para el caso PLOX, el orden recomendado es `pattern` para
texturas con bordes compatibles, `marquee` para material con movimiento legible
y `crop` solo cuando el análisis de atención indica que no se perderá el
contenido importante. El resultado final debe ser un derivado target-specific
listo para revisar y luego convertir a DXV.

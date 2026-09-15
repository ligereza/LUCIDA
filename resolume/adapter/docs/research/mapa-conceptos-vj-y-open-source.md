# Mapa de conceptos VJ y ecosistema open source

Estado: investigación base para RESOLUME_ADAPTER  
Fecha: 2026-08-28

Este documento no pretende ser un manual académico exhaustivo. Es un inventario operativo de los problemas que un VJ puede encontrar entre el archivo original y la luz que finalmente llega a una pantalla LED o un proyector, junto con herramientas abiertas que pueden servir para diagnosticarlos, prepararlos o corregirlos.

## 1. La cadena completa

```text
Contenido / cámara / generador
          ↓
Codec + contenedor + color + alpha + FPS
          ↓
Resolume / otro media server
          ↓
CPU + GPU + VRAM + compositor + sincronía
          ↓
Salida Windows/NVIDIA: resolución + Hz + espacio de color + rango
          ↓
HDMI / DisplayPort / SDI / red / captura / conversores
          ↓
Procesador LED o proyector
          ↓
Escalado + mapping + gamma + brillo + calibración + timing
          ↓
Sender / receiving cards / panel LED o proyector
          ↓
Percepción del público
```

La misma imagen puede verse distinta en cada etapa. Por eso RESOLUME_ADAPTER debe diferenciar entre:

- lo que el archivo declara;
- lo que Windows y la GPU están enviando;
- lo que el procesador declara recibir;
- lo que se puede inferir observando el resultado;
- lo que sólo puede verificarse con una cámara, colorímetro o fotómetro.

## 2. Conceptos que un VJ debe enfrentar

### 2.1 Señal, conexiones y hardware

- **Fuente**: equipo o dispositivo que produce la señal de video.
- **GPU**: procesa texturas, efectos, composición y salida.
- **VRAM**: memoria de la GPU; condiciona resolución, cantidad de capas y texturas.
- **Scanout**: lectura final del framebuffer por la GPU hacia la salida física.
- **HDMI / DisplayPort**: interfaces digitales de video; no garantizan por sí mismas que toda la cadena comparta la misma configuración.
- **SDI**: transporte profesional de video, normalmente usado con hardware dedicado.
- **EDID**: información que el dispositivo de destino comunica a la GPU sobre modos soportados.
- **DisplayID**: descriptor más moderno y ampliable de capacidades de pantalla.
- **Handshake**: negociación de capacidades entre fuente, cable, conversor y destino.
- **HDCP**: protección de contenido; puede provocar pantalla negra o incompatibilidad con ciertas fuentes/capturadoras.
- **Ancho de banda**: límite combinado de resolución, Hz, profundidad de color y submuestreo.
- **RGB**: señal de imagen por canales rojo, verde y azul.
- **YCbCr**: representación con luminancia y crominancia, habitual en video.
- **Chroma subsampling**: reducción de resolución de color, por ejemplo 4:4:4, 4:2:2 o 4:2:0.
- **Rango Full**: niveles nominales de 0 a 255 en 8 bits.
- **Rango Limited/Studio**: niveles nominales de 16 a 235 para una señal de video de 8 bits.
- **Profundidad de color**: bits por canal; 8, 10, 12 o 16 bits ofrecen distinta cantidad de niveles.
- **Conversor**: dispositivo que transforma formato, resolución, frecuencia o protocolo.
- **Splitter/distribuidor**: replica una señal a varios destinos.
- **Extensor**: transporta la señal a distancia por fibra, cobre, red u otro medio.
- **Capturadora**: convierte una entrada de video en una fuente para el software.
- **Procesador de video**: recibe, transforma y distribuye la señal a proyectores o paneles LED.
- **Sender card**: hardware que prepara la información para enviarla hacia la pantalla.
- **Receiving card**: tarjeta en el sistema LED que recibe y distribuye datos a los módulos.
- **Integridad de señal**: calidad eléctrica y temporal de la conexión; una señal débil puede generar cortes o errores.
- **Latencia de transporte**: tiempo agregado por conversores, capturadoras, procesadores y redes.

### 2.2 Tiempo, frecuencia y sincronización

- **FPS**: cantidad de frames producidos por segundo por el contenido o la aplicación.
- **Hz**: cantidad de ciclos de actualización de la salida o pantalla por segundo.
- **Frame time**: duración real de cada frame; a 60 FPS el objetivo aproximado es 16,67 ms.
- **Frame pacing**: regularidad con que se entregan los frames.
- **VSync**: sincronización entre render y refresco de pantalla.
- **Tearing**: una actualización muestra partes de dos frames distintos, generalmente como cortes horizontales.
- **Stutter**: irregularidad visible en el movimiento por tiempos de frame inestables.
- **Judder**: movimiento entrecortado por conversión de cadencias o repetición irregular de frames.
- **Dropped frame**: frame que no llegó a tiempo.
- **Repeated frame**: frame mostrado más de una vez porque el siguiente no estuvo listo.
- **Frame duplication**: repetición intencional o derivada de una conversión de FPS.
- **Frame interpolation**: creación de frames intermedios; puede generar artefactos en loops y visuales.
- **Refresh mismatch**: FPS y Hz incompatibles o no relacionados de forma estable.
- **Variable Refresh Rate**: frecuencia que cambia dinámicamente; puede no ser conveniente para una salida de show.
- **Genlock**: bloqueo de varios dispositivos a una referencia común.
- **Framelock**: sincronización de render o presentación entre varias salidas.
- **Timecode**: referencia temporal compartida, como LTC, MTC o timecode de red.
- **Clock drift**: diferencia acumulada entre relojes de audio, video, software y hardware.
- **Audio/video sync**: alineación temporal entre música, disparadores y visuales.
- **BPM sync**: relación de parámetros y disparos con el tempo musical.
- **Latency budget**: suma de todas las latencias que el operador y el público perciben.

### 2.3 Color y señal de imagen

- **Luminancia**: componente relacionada con la intensidad percibida.
- **Crominancia**: información de color separada de la luminancia.
- **Gamma**: curva que relaciona valores codificados con luminancia; no es lo mismo que brillo.
- **OETF/EOTF**: curvas de codificación y decodificación entre señal y luz.
- **Transfer function**: forma completa de describir cómo se transforma una señal en luminancia.
- **sRGB**: espacio de color común en informática y contenido SDR.
- **Rec.709**: referencia habitual para video HD SDR.
- **Rec.2020**: espacio de color amplio asociado a UHD y HDR.
- **BT.1886**: referencia de transferencia para pantallas SDR de producción.
- **PQ/ST 2084**: transferencia HDR basada en luminancia absoluta.
- **HLG**: transferencia HDR pensada para compatibilidad con ciertos flujos de emisión.
- **SDR**: rango dinámico estándar.
- **HDR**: rango dinámico alto; exige coherencia entre metadata, transferencia, gamut y display.
- **Gamut**: conjunto de colores que un dispositivo puede representar.
- **Color space**: definición conjunta de primarios, blanco y transferencia.
- **White point**: blanco de referencia, normalmente D65 en muchos flujos digitales.
- **Primaries**: coordenadas de rojo, verde y azul del espacio de color.
- **ICC profile**: descripción de comportamiento cromático de un dispositivo o flujo.
- **LUT 1D**: transformación independiente por canal, útil para curvas.
- **LUT 3D**: transformación conjunta de color, útil para correcciones complejas.
- **Color management**: conjunto de reglas para traducir color entre espacios y dispositivos.
- **Tone mapping**: conversión entre rangos dinámicos, especialmente HDR a SDR.
- **Gamut mapping**: tratamiento de colores fuera de la capacidad del destino.
- **Black level**: nivel mínimo de luminancia que entrega una cadena o pantalla.
- **Lifted blacks**: negros elevados que se perciben como gris.
- **Black crush**: pérdida de detalle en sombras por comprimir o cortar niveles bajos.
- **White clipping**: pérdida de detalle en altas luces por saturación.
- **Contrast**: relación entre niveles oscuros y claros; puede aplicarse en varias etapas.
- **Banding/posterization**: escalones visibles en degradados suaves por cuantización, compresión o transformaciones.
- **Dithering**: ruido controlado para disimular cuantización y banding.
- **Temporal dithering/FRC**: alternancia entre niveles en el tiempo para simular mayor profundidad.
- **Color clipping**: recorte de canales o colores fuera de rango.
- **Color cast**: dominante de color causada por balance, calibración o transformación.
- **Color temperature**: apariencia cálida o fría asociada al blanco.
- **Delta E**: diferencia perceptual entre un color de referencia y uno medido.
- **Nits/cd/m²**: unidad de luminancia útil para describir displays.
- **Calibración**: ajuste del dispositivo hacia un objetivo.
- **Caracterización**: medición y descripción del comportamiento sin necesariamente modificarlo.

### 2.4 Imagen, video y media

- **Resolución**: cantidad de píxeles del frame.
- **Aspect ratio**: relación entre ancho y alto de la imagen.
- **Pixel aspect ratio**: forma del píxel; en la mayoría de los contenidos modernos es 1:1.
- **Canvas/composición**: superficie virtual donde el VJ compone sus capas.
- **Scaling**: cambio de tamaño; puede introducir blur, aliasing o ringing.
- **Crop**: recorte de una región de la imagen.
- **Letterbox/pillarbox**: bandas agregadas para conservar proporción.
- **Progressive**: cada frame contiene la imagen completa.
- **Interlaced**: cada frame se divide en campos; puede generar combing si se interpreta mal.
- **Deinterlacing**: reconstrucción de imagen progresiva desde campos entrelazados.
- **Container**: envoltorio como MOV, MP4, MKV o WebM.
- **Codec**: método de codificación como H.264, H.265, ProRes, CineForm, DXV o Hap.
- **Intra-frame codec**: cada frame es relativamente independiente; suele facilitar reproducción y seek.
- **Inter-frame codec**: usa referencias entre frames; puede ahorrar espacio y exigir más decodificación.
- **Bitrate**: cantidad de datos por segundo.
- **Keyframe/GOP**: puntos de referencia y estructura temporal de un codec inter-frame.
- **Pixel format**: organización y precisión de los datos, como RGBA, YUV420p o 10-bit.
- **Alpha channel**: transparencia por píxel.
- **Straight alpha**: color almacenado separado del alpha.
- **Premultiplied alpha**: RGB ya multiplicado por alpha; una interpretación incorrecta produce halos.
- **Frame sampling**: selección de frames sin generar nuevos.
- **Motion blur**: desenfoque asociado al movimiento, ya creado o aplicado en tiempo real.
- **Aliasing**: patrones o bordes falsos por muestreo insuficiente.
- **Moiré**: interferencia visual entre patrones o rejillas.
- **Ringing**: halos cerca de bordes por filtros o compresión.
- **Blocking**: bloques visibles por compresión.
- **Noise/grain**: variación aleatoria de imagen, estética o indeseada.
- **Deflicker**: estabilización temporal de variaciones de luminancia.
- **Debanding**: reducción de bandas visibles en degradados.
- **Deblocking**: reducción de artefactos de bloques.
- **Sharpening**: aumento de contraste local de bordes; puede exagerar ruido y ringing.
- **Scene cut**: cambio brusco de escena que un filtro temporal debe reconocer para no crear estelas.

### 2.5 Resolume y composición en tiempo real

- **Clip**: recurso reproducible dentro de Resolume.
- **Layer**: capa de composición.
- **Column/deck**: organización y disparo de clips.
- **Composition**: conjunto de capas, clips, efectos y configuración de salida.
- **Opacity**: mezcla de una capa con las inferiores.
- **Blend mode**: regla matemática de mezcla, como Add, Screen, Multiply o Difference.
- **Transform**: posición, escala, rotación y anclaje.
- **Mask**: recorte o limitación de una capa.
- **Effect**: procesamiento aplicado a clip, layer, group o composition.
- **Source/generator**: imagen generada en tiempo real en vez de un archivo.
- **Feedback**: reutilización de la salida anterior como entrada.
- **Texture**: imagen residente en GPU usada por el render.
- **Render target**: superficie de GPU donde se dibuja un resultado intermedio.
- **FFGL**: interfaz de plugins nativos para efectos y fuentes en Resolume.
- **ISF**: formato de shaders GLSL con metadata de parámetros.
- **Wire**: entorno de Resolume para construir recursos y patches visuales.
- **Spout**: intercambio de frames por texturas compartidas en Windows.
- **Syphon**: intercambio de frames por texturas compartidas en macOS.
- **OSC**: control y telemetría por mensajes de red.
- **MIDI**: control por notas, CC y otros mensajes.
- **DMX**: protocolo de control habitual en iluminación.
- **Art-Net/sACN**: transporte de DMX sobre red.
- **Advanced Output**: configuración de pantallas, fixtures, slices, warping y edge blend.
- **Fixture**: representación virtual de una superficie o salida física.
- **Slice**: región de salida asignada a un destino.
- **Projection mapping**: adaptación de contenido a una superficie física.
- **Warp/mesh warp**: deformación geométrica de la imagen.
- **Keystone**: corrección trapezoidal, normalmente menos flexible que un warp de malla.
- **Edge blending**: mezcla de bordes entre proyectores superpuestos.

### 2.6 Handoff de festival, video control y routing

En un festival grande, la “consola de pantallas” puede ser un **video switcher/vision mixer**, un **presentation system**, un **video router**, un **media server central** o una combinación de ellos. Ejemplos de familias profesionales son Barco Event Master, Analog Way LivePremier/Aquilon, Ross Carbonite/Ultrix y sistemas basados en servidores de medios. El nombre exacto importa menos que dibujar el camino real de la señal.

```text
VJ A ─┐
VJ B ─┼→ captura o entrada del sistema de house
VJ C ─┘                 ↓
                 video control / switcher
                 ↓       ↓        ↓
              Main LED  Side LED  IMAG/stream
                 ↓       ↓        ↓
             procesadores y pantallas físicas
```

Conceptos específicos:

- **House video**: infraestructura de video común del festival.
- **Video control**: área, sistema y equipo que recibe, monitorea y distribuye fuentes.
- **FIJO**: operador o media server que mantiene el contenido del evento entre presentaciones.
- **CONSOLA**: operador que conmuta, enruta o compone señales hacia los destinos.
- **VJ handoff**: entrega temporal de una fuente externa al sistema de house.
- **Capture input**: entrada de una capturadora que convierte la salida HDMI/SDI del VJ en una fuente interna.
- **Direct input**: señal del VJ que entra directamente al switcher o processor sin pasar por una captura intermedia.
- **Source/input**: nombre lógico asignado a una señal entrante.
- **Program/PVW**: salida al aire y salida de previsualización en un switcher.
- **M/E**: banco de mezcla que puede generar una salida diferente de la principal.
- **Aux bus**: salida auxiliar que puede recibir una fuente o composición distinta.
- **Destination/Screen**: destino lógico que representa una pantalla, un grupo o una composición física.
- **Output group**: conjunto de salidas que se alimentan con la misma fuente o layout.
- **Multiview**: salida de monitoreo donde el operador observa fuentes, programa, preview y estados.
- **Preset/scene**: memoria de routing, capas, escala y composición lista para activar.
- **Source lock**: condición de señal estable que permite al sistema aceptar una entrada.
- **EDID emulation**: el sistema presenta a la GPU del VJ una resolución y frecuencia elegidas por el festival.
- **Input format**: resolución, Hz, color y profundidad que el sistema acepta de la señal del VJ.
- **Output format**: resolución, Hz y formato que entrega hacia cada destino.
- **Key/fill**: pareja de señales para imagen y máscara/transparencia, si el sistema lo soporta.
- **Clean feed**: salida sin determinados overlays o elementos de composición.
- **Frame sync**: adaptación temporal para que una fuente sea utilizable dentro del sistema.
- **Scaler**: procesador que cambia resolución o encuadre; puede existir en la captura, switcher, processor y pantalla.
- **Double scaling**: escalado repetido que produce blur, ringing, aliasing o encuadre inesperado.
- **Destination mapping**: asignación de regiones del canvas a las salidas físicas.
- **Screen take**: acción de llevar una fuente a un destino visible.
- **Tally/status**: indicación de qué fuente está al aire o activa.
- **Fallback source**: fuente que queda visible si el VJ se desconecta o la entrada pierde lock.

El caso “no me pasan todas las pantallas” puede significar varias cosas distintas:

1. El VJ sólo fue asignado a una entrada o a un destino, no a todo el grupo de pantallas.
2. El sistema recibió una señal 16:9, pero el evento trabaja con un canvas panorámico o varias superficies independientes.
3. La señal sí llega a todas las salidas, pero cada destino aplica un crop, escala o preset diferente.
4. El sistema de house captura a una resolución y entrega otra, generando doble escalado.
5. La entrada está en `Preview` o `Aux`, mientras el `Program` sigue mostrando las visuales del FIJO.
6. Una pantalla o procesador tiene otra frecuencia, resolución, ruta o condición de lock.

Por eso no se debe diagnosticar automáticamente como “problema de escala”. Primero hay que separar **captura**, **routing**, **canvas**, **formato de entrada**, **formato de salida** y **procesamiento final**.

### 2.7 LED, proyectores y procesadores

- **Native output**: resolución y frecuencia propias del destino.
- **Processor canvas**: área lógica que el procesador espera recibir.
- **Input mode**: formato que el procesador interpreta en su entrada.
- **Output mapping**: distribución de la imagen hacia salidas y puertos.
- **Scaling interno**: redimensionamiento realizado por el procesador.
- **Input crop**: recorte realizado antes de enviar al panel.
- **Cabinet mapping**: relación entre la imagen lógica y los gabinetes físicos.
- **Receiving-card configuration**: parámetros internos de las tarjetas receptoras.
- **Scan mode**: forma en que el módulo LED actualiza sus filas o subpíxeles.
- **Pixel order/RGB order**: orden físico de canales o módulos.
- **Cabinet resolution**: resolución de cada gabinete o bloque.
- **Refresh rate del LED**: frecuencia interna de actualización del panel, distinta de los Hz HDMI.
- **PWM**: modulación de ancho de pulso usada para controlar brillo; puede generar parpadeo visible o registrado por cámara.
- **Brightness**: nivel global de emisión, no equivalente a gamma.
- **Gamma del procesador**: transformación de niveles aplicada antes del panel.
- **Calibration data**: correcciones de uniformidad, color o brillo.
- **Dead pixel/failed module**: módulo o píxel defectuoso.
- **Scan lines**: patrones o líneas asociadas a lectura, cableado o sincronización del LED.
- **Genlock del procesador**: referencia temporal compartida entre entradas/salidas compatibles.
- **Redundancy**: ruta o equipo de respaldo ante fallos.
- **Telemetry**: temperatura, estado de señal, ventiladores, puertos y errores.
- **EDID passthrough/emulation**: forma en que el procesador presenta capacidades a la GPU.
- **Black floor**: mínimo físico o electrónico de luz que la pantalla puede producir.

### 2.8 Red, control, audio y automatización

- **OSC routing**: envío y recepción de mensajes entre aplicaciones.
- **MIDI mapping**: asociación de controles físicos o virtuales a parámetros.
- **MIDI clock/MTC**: sincronización temporal por MIDI.
- **Art-Net universe**: bloque de hasta 512 canales DMX transportado por red.
- **sACN/E1.31**: protocolo de streaming de DMX sobre IP.
- **RDM**: gestión y consulta bidireccional de ciertos dispositivos de iluminación.
- **NDI**: transporte de video por red; el protocolo y sus componentes no deben asumirse totalmente abiertos.
- **SRT/RTMP/WebRTC**: transporte de video en red, útil en casos de streaming o instalaciones.
- **JACK/PipeWire**: enrutamiento de audio entre aplicaciones y dispositivos.
- **Audio input**: señal que alimenta análisis o reactividad.
- **Onset detection**: detección de ataques o golpes.
- **Beat tracking**: estimación del tempo y pulsos.
- **FFT/spectrum**: análisis de energía por frecuencia.
- **Envelope/RMS/peak**: medidas de amplitud para modular parámetros.
- **Trigger quantization**: alineación de disparos con la rejilla musical.

### 2.9 Rendimiento, estabilidad y recuperación

- **CPU load**: trabajo de decodificación, lógica y preparación de frames.
- **GPU load**: trabajo de composición, efectos, escalado y salida.
- **VRAM pressure**: saturación de memoria gráfica.
- **Decode load**: coste de descomprimir el codec.
- **Upload/download GPU**: transferencias entre RAM y VRAM.
- **Disk throughput**: velocidad de lectura de media.
- **Asset caching**: precarga o almacenamiento temporal de recursos.
- **Thermal throttling**: reducción de frecuencia por temperatura.
- **Power limit**: límite energético que afecta frecuencia y rendimiento.
- **Driver version**: versión del controlador que puede cambiar compatibilidad y rendimiento.
- **Background process**: proceso que consume recursos durante el show.
- **Watchdog**: mecanismo que detecta bloqueos y recupera o avisa.
- **Crash recovery**: reapertura o restauración después de un fallo.
- **Fallback media**: contenido de emergencia.
- **Redundant output**: salida o equipo alternativo.
- **Frame-time capture**: registro de tiempos por frame para distinguir carga promedio de irregularidad.
- **Stress test**: prueba controlada antes del show.

### 2.10 Operación, documentación y seguridad

- **Preflight**: revisión previa de contenido, equipo, señal y rutas.
- **Show file**: archivo de composición y configuración.
- **Media relink**: reconstrucción de rutas después de mover archivos.
- **Asset manifest**: inventario reproducible de archivos, hashes y versiones.
- **Version pinning**: fijación de versiones de software, plugins y drivers.
- **Runbook**: instrucciones operativas para montar, probar y recuperar.
- **Changeover**: transición entre operadores, equipos o shows.
- **Signal handoff**: entrega de una señal ya configurada por otra persona.
- **Test pattern**: patrón diseñado para verificar niveles, geometría, color y timing.
- **Color bars**: barras de referencia cromática.
- **PLUGE**: patrón para ajustar negros y niveles bajos.
- **Gradient ramp**: degradado para evaluar banding y uniformidad.
- **Flash/strobe safety**: control de flashes y cambios rápidos que pueden afectar a personas fotosensibles.
- **Blackout**: salida negra controlada para emergencia o cambio.
- **Credential/license check**: verificación de licencias y accesos antes del show.
- **Logbook**: registro de configuración, anomalías y soluciones.
- **Evidence capture**: fotos, capturas, logs y perfiles que permiten reproducir un caso.

## 3. Síntoma, diagnóstico y respuesta segura

| Síntoma | Conceptos sospechosos | Primera respuesta RESOLUME_ADAPTER | Lo que no puede prometer |
|---|---|---|---|
| Negro convertido en gris | Rango, gamma, black level, calibración | Comparar GPU, EDID, procesador y patrón PLUGE; recomendar transformación | No puede recuperar negro físico perdido |
| Degradados con franjas | Profundidad, cuantización, codec, LUT | Medir gradiente; recomendar 10 bits cuando exista y dithering controlado | El dithering sólo enmascara; no recupera información descartada |
| Parpadeo de toda la imagen | Flicker de contenido, PWM, refresh, señal | Separar análisis temporal del archivo y prueba de salida | Un FFGL no corrige PWM ni un LED defectuoso |
| Líneas horizontales | Tearing, scan, cableado, salida | Registrar frame time, VSync y topología de señal | No debe llamarse automáticamente flickering |
| Movimiento entrecortado | FPS, Hz, pacing, judder, dropped frames | Comparar frame time, FPS efectivo y Hz | Subir los Hz no repara una fuente con pacing inestable |
| Colores lavados | Limited/Full, YCbCr, gamma, HDR/SDR | Construir perfil de niveles y espacio de color | NVIDIA Full no garantiza que el procesador interprete Full |
| Colores sobresaturados o extraños | Gamut, primaries, LUT, RGB order | Detectar espacio declarado y ofrecer gamut mapping | Sin medición del destino la corrección es aproximada |
| Halo en transparencia | Alpha premultiplicado/straight, blend mode | Diagnosticar alpha y ofrecer conversión | Un plugin no puede reconstruir alpha inexistente |
| Bordes borrosos o dentados | Scaling, filtros, resolución, aliasing | Recomendar resolución nativa y filtro apropiado | El procesador puede volver a escalar después |
| Imagen negra o sin señal | EDID, HDCP, handshake, cable, input mode | Capturar estado de salida y probar patrón seguro | El software no sustituye comprobar cableado y hardware |
| Sólo aparece en algunas pantallas | Routing, destination, Aux/M/E, output group | Confirmar entrada, programa, destino y preset activo antes de tocar escala | El FFGL no puede activar salidas que el house no le haya asignado |
| Se ve en todas, pero encuadrado distinto | Canvas, crop, scaler, double scaling | Comparar resolución de captura, canvas del VJ y formato de cada destino | La corrección depende del mapa físico configurado por producción |
| Cambio al entrar/salir un VJ | Handoff, source lock, frame sync, fallback | Registrar qué fuente queda en Program y qué preset se activa | No debe asumirse que el VJ controla la conmutación final |
| Un panel no coincide con otro | Calibración, gamma, módulos, receiving cards | Registrar diferencias por zona y perfil | Requiere medición o acceso técnico al panel |
| Resolume se ralentiza | Decode, VRAM, GPU, disco, efectos, thermal | Medir tiempos y clasificar cuello de botella | El diagnóstico no aumenta recursos físicos |

## 4. Ecosistema de herramientas abiertas

### 4.1 Media, conversión y diagnóstico de archivos

- **[FFmpeg](https://ffmpeg.org/)**: base para inspección, conversión, extracción de frames, filtros, codecs y automatización. Sus filtros incluyen `signalstats`, `deflicker`, `deband`, `gradfun`, `idet`, `fps`, `blackdetect`, `showinfo` y mediciones de histograma. Es la base inmediata para el núcleo Python de RESOLUME_ADAPTER.
- **[MediaInfo](https://github.com/MediaArea/MediaInfo)**: CLI y GUI para mostrar metadata técnica y tags de video/audio. Útil como segunda fuente de verificación para `ffprobe`.
- **[GStreamer](https://gstreamer.freedesktop.org/)**: framework de pipelines multimedia para construir reproducción, captura, conversión y procesamiento en tiempo real.
- **[VapourSynth](https://www.vapoursynth.com/doc/)**: frameserver programable para análisis y procesamiento por frame. Es apropiado para pruebas offline reproducibles y filtros especializados.
- **[OpenCV](https://github.com/opencv/opencv)**: visión artificial y análisis de imagen para construir detectores de flicker, banding, uniformidad, cortes y patrones.

### 4.2 Color, HDR, gamut y calidad

- **[OpenColorIO](https://github.com/AcademySoftwareFoundation/OpenColorIO)**: gestión de color orientada a producción audiovisual, VFX y animación; sirve para normalizar espacios, transferencias y LUTs.
- **[libplacebo](https://libplacebo.org/options/)**: biblioteca de procesamiento GPU con escalado, debanding, dithering, tone mapping HDR y gamut mapping. Es una referencia técnica muy fuerte para futuros filtros de RESOLUME_ADAPTER.
- **[ArgyllCMS](https://www.argyllcms.com/doc/ArgyllDoc.html)**: gestión de color ICC, creación de perfiles y calibración con instrumentos. Permite pasar de una compensación estimada a una transformación basada en medición.
- **[DisplayCAL](https://displaycal.org/)**: interfaz abierta para flujos de calibración que utilizan ArgyllCMS. Requiere colorímetro o espectrofotómetro para medir de verdad.
- **[VMAF/libvmaf](https://github.com/Netflix/vmaf)**: evaluación de calidad perceptual entre referencia y resultado; incluye métricas como PSNR, SSIM y CAMBI para evaluar banding en ciertos escenarios. No sustituye el juicio visual del VJ.
- **[FFmpeg color filters](https://ffmpeg.org/ffmpeg-filters.html)**: `colorspace`, `colorlevels`, `curves`, `eq`, `lut`, `lut3d`, `zscale`, `tonemap` y filtros relacionados permiten prototipar transformaciones antes de escribir un shader.

### 4.3 Rendimiento y sincronización

- **[PresentMon](https://github.com/GameTechDev/PresentMon)**: captura métricas de CPU, GPU, display frame time y latencias en Windows. Puede ayudar a separar un problema de imagen de un problema de presentación.
- **[TestUFO](https://testufo.com/)**: conjunto de pruebas web para refresco, motion, stutter, persistence y ghosting. No es open source, pero es útil como prueba manual rápida.
- **[HWiNFO](https://www.hwinfo.com/)**: no es open source, pero resulta práctico para temperatura, potencia y throttling durante pruebas del equipo.

### 4.4 Composición en vivo, mapping y generación

- **[OBS Studio](https://github.com/obsproject/obs-studio)**: compositor, captura, mezcla y salida en tiempo real; tiene API, plugins y estadísticas. Es más orientado a broadcast, pero sirve como plataforma de prueba y captura.
- **[MapMap](https://github.com/mapmapteam/mapmap)**: software GPL para video mapping. Útil para estudiar warping, superficies y proyección; conviene validar mantenimiento y estabilidad antes de usarlo en un show crítico.
- **[Ghost Arcade](https://github.com/riskcapital/ghost-arcade)**: proyecto AGPL de VJ/mapping con GPU, shaders, MIDI, múltiples capas y Spout. Es interesante como referencia de arquitectura moderna, todavía debe evaluarse por versión y estabilidad.
- **[Veejay](https://github.com/game-stop/veejay)**: instrumento visual y sampler de tiempo real, especialmente orientado a Linux.
- **[Blender](https://www.blender.org/)**: generación, animación, composición, render y preparación offline.
- **[Natron](https://github.com/NatronGitHub/Natron)**: composición nodal open source para preparación y procesamiento de imagen.
- **[Kdenlive](https://github.com/KDE/kdenlive)**: edición y conformado de media para generar entregables consistentes.

### 4.5 Intercambio de frames y control

- **[Spout2](https://github.com/leadedge/Spout2)**: intercambio de texturas/frame sharing en Windows con soporte para OpenGL y DirectX. Es relevante para conectar herramientas RESOLUME_ADAPTER con Resolume sin re-encodear video.
- **[Syphon](https://syphon.info/)**: intercambio de frames acelerado por GPU en macOS.
- **[ISF](https://isf.video/)**: formato abierto para shaders GLSL con parámetros, filtros, generadores, transiciones y buffers persistentes. Puede servir para prototipos de corrección antes de compilar FFGL.
- **[FFGL oficial](https://github.com/resolume/ffgl)**: SDK y ejemplos para plugins nativos de Resolume. Es la integración específica que RESOLUME_ADAPTER debe usar para el efecto en tiempo real.
- **[frei0r](https://github.com/dyne/frei0r)**: ecosistema de plugins de video libre y portable; no es FFGL, pero ofrece ideas, filtros reutilizables y una referencia para efectos simples.
- **[liblo](https://github.com/radarsat1/liblo)**: implementación LGPL de OSC para integrar herramientas externas con Resolume y otros programas.
- **[RtMidi](https://github.com/thestk/rtmidi)**: biblioteca multiplataforma para MIDI; adecuada para utilidades de control y pruebas.
- **[aubio](https://github.com/aubio/aubio)**: análisis de audio, ataques, tempo, pitch y beats para futuras funciones audio-reactivas.

### 4.6 Iluminación y protocolos de escenario

- **[Open Lighting Architecture](https://github.com/OpenLightingProject/ola)**: framework para DMX/RDM, Art-Net, sACN y otros protocolos; útil para integración con iluminación, aunque su soporte de plataformas debe verificarse para cada caso.
- **[QLC+](https://www.qlcplus.org/)**: software libre de control de iluminación con DMX y Art-Net; no corrige una cadena HDMI, pero permite probar la relación entre visuales, iluminación y píxeles.
- **[Wireshark](https://www.wireshark.org/)**: captura y análisis de protocolos. Puede ser una herramienta de laboratorio para estudiar comunicaciones de un procesador, siempre en modo pasivo o con autorización.

### 4.7 Procesadores LED y hardware específico

- **[novastar.js](https://github.com/sarakusha/novastar)**: API TypeScript basada en ingeniería inversa para dispositivos NovaStar, con bindings de red/serial y dissector de Wireshark. Es una referencia prometedora para un adaptador de lectura, pero no debe llevarse a producción sin probar el modelo exacto.
- **[Colorlight 5A Programs](https://github.com/haraldkubota/colorlight)**: ejemplos de detección y comunicación con hardware Colorlight 5A. Es útil como investigación de protocolo, no como garantía para todos los procesadores Colorlight.
- **[NovaStar downloads y manuales](https://novastar.store/downloads/)**: software y documentación oficial. Son cerrados, pero necesarios para comparar qué parámetros existen realmente en cada familia.

Conclusión de esta sección: hay mucha infraestructura abierta alrededor de media, color, timing y control, pero la lectura universal y segura de procesadores LED sigue siendo dependiente del fabricante, modelo, firmware y protocolo.

## 5. Qué debería construir RESOLUME_ADAPTER

### 5.1 Capa de conocimiento

Un esquema común de perfil, independiente del fabricante:

```json
{
  "source": {
    "resolution": "1920x1080",
    "fps": 60,
    "color_model": "RGB",
    "range": "full",
    "transfer": "sRGB",
    "primaries": "BT.709",
    "bit_depth": 8
  },
  "output": {
    "resolution": "1920x1080",
    "refresh_hz": 60,
    "edid_available": true,
    "color_space": "RGB_FULL_G22_NONE_P709"
  },
  "processor": {
    "vendor": "unknown",
    "model": "unknown",
    "connection": "HDMI",
    "declared_range": null,
    "declared_gamma": null,
    "read_only": true
  },
  "inference": {
    "possible_lifted_blacks": true,
    "possible_banding_risk": true,
    "possible_timing_mismatch": false,
    "confidence": 0.62
  }
}
```

El perfil debe conservar tres fuentes distintas:

1. **Declarado**: lo que reporta el dispositivo.
2. **Observado**: lo que reportan Windows, DXGI, EDID, GPU y mediciones de archivo.
3. **Inferido**: hipótesis de RESOLUME_ADAPTER con evidencia y confianza.

### 5.2 Componentes del producto

- **RESOLUME_ADAPTER Probe**: utilidad externa, primero local y de sólo lectura.
- **RESOLUME_ADAPTER Report**: explicación en lenguaje de VJ, no sólo valores técnicos.
- **RESOLUME_ADAPTER Test Patterns**: PLUGE, rampas, barras, checkerboard, movimiento y patrones de sincronía.
- **RESOLUME_ADAPTER Black Level Guard**: transformación de niveles/gamma/LUT con bypass.
- **RESOLUME_ADAPTER Temporal Deflicker**: filtro temporal con protección ante cortes de escena.
- **RESOLUME_ADAPTER Banding Guard**: dithering y debanding controlados según profundidad y señal.
- **RESOLUME_ADAPTER Output Check**: resolución, Hz, FPS efectivo, frame pacing y estado de la salida.
- **Hardware adapters**: módulos independientes por familia de procesadores; nunca un protocolo universal supuesto.

### 5.3 Orden de implementación recomendado

1. Perfil de salida Windows/GPU y diagnóstico de archivos.
2. Patrones de prueba y reporte de rango/gamma/banding.
3. FFGL `Black Level Guard` con transformaciones manuales y bypass.
4. FFGL `Temporal Deflicker` y comparación con fixtures sintéticos.
5. FFGL `Banding Guard` basado en dithering/debanding.
6. Primer adaptador de hardware en modo lectura, usando un procesador real en laboratorio.
7. Perfiles adaptativos y recomendaciones específicas por fabricante.
8. Integración OSC/Spout para telemetría y pruebas, sin crear una interfaz propia todavía.

## 6. Límites y reglas de seguridad

- El plugin de render no debe abrir USB, red ni procesos externos dentro del hilo que dibuja frames.
- La consulta de hardware debe vivir fuera de Resolume y entregar un perfil congelado al plugin.
- El MVP no debe incluir comandos de escritura al procesador.
- No se debe enviar firmware, modificar receiving cards ni cambiar mapping automáticamente.
- Toda corrección debe tener bypass, valores conservadores y registro del perfil usado.
- Si el dispositivo no es reconocido, RESOLUME_ADAPTER debe decir “sin evidencia suficiente”, no inventar una configuración.
- Una corrección visual puede ocultar un síntoma sin resolver su causa física.
- Para conocer el negro, gamma o uniformidad reales del panel hace falta medición óptica o una verificación visual controlada.
- El modo de show debe degradar de forma segura: si RESOLUME_ADAPTER falla, Resolume debe seguir pudiendo emitir la señal original.

## 7. Fuentes principales

- [Resolume: Playing Content](https://www.resolume.com/support/en/playing-content)
- [Resolume: Advanced Output](https://www.resolume.com/support/en/advanced-output)
- [Resolume: Video y DXV](https://www.resolume.com/support/en/video)
- [Resolume: FFGL](https://github.com/resolume/ffgl)
- [Microsoft: Display, EDID, HDR y Advanced Color](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/display)
- [Microsoft: DXGI color spaces](https://learn.microsoft.com/en-us/windows/win32/api/dxgicommon/ne-dxgicommon-dxgi_color_space_type)
- [FFmpeg Filters](https://ffmpeg.org/ffmpeg-filters.html)
- [OpenColorIO](https://opencolorio.readthedocs.io/en/main/)
- [libplacebo options](https://libplacebo.org/options/)
- [ArgyllCMS](https://www.argyllcms.com/doc/ArgyllDoc.html)
- [PresentMon](https://github.com/GameTechDev/PresentMon)
- [Open Lighting Architecture](https://docs.openlighting.org/ola/doc/latest/index.html)

# Adopción de herramientas y repositorios para RESOLUME_ADAPTER

Decisión de arquitectura revisada el 29 de agosto de 2026. RESOLUME_ADAPTER adopta
herramientas externas como dependencias o ejecutables detectables; no copia
repositorios completos dentro del proyecto. Cada integración debe conservar
una salida reproducible, una versión identificable y una alternativa cuando
sea razonable.

## Adoptadas ahora

| Herramienta | Uso en RESOLUME_ADAPTER | Estado |
| --- | --- | --- |
| [FFmpeg](https://github.com/FFmpeg/FFmpeg) / FFprobe | Lectura técnica, filtros, previews, NVENC y exportación DXV | Operativo en el equipo |
| [PyNvVideoCodec](https://github.com/NVIDIA/VideoProcessingFramework) | Decodificación/análisis GPU con NVIDIA | Instalado; es la línea recomendada frente al VPF antiguo |
| CuPy | Cálculos de luminancia, movimiento, periodicidad y bordes en GPU | Instalado |
| [PyAV](https://github.com/PyAV-Org/PyAV) | Acceso Python a contenedores, streams y frames cuando FFprobe no alcanza | Instalado: 16.1.0 |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | Cortes, fades, escenas y posibles puntos de cambio | Instalado: 0.6.7.1 |
| [OpenCV](https://github.com/opencv/opencv) | Transformaciones geométricas, remap, perspectiva y análisis espacial | Instalado: 5.0.0.93 |

PyAV, PySceneDetect y OpenCV ya están declarados en `requirements.txt`; no se
agregan como repositorios copiados. La extracción de escenas se incorporará a
los perfiles de INSTAR cuando el contrato de escenas esté definido, para no
confundir un corte detectado con un cue aprobado.

## Próxima adopción, sin instalar todavía

| Herramienta | Aporte | Motivo para esperar |
| --- | --- | --- |
| [libvips](https://github.com/libvips/libvips) | Contact sheets, thumbnails y procesamiento rápido de imágenes con bajo uso de memoria | No resuelve el pipeline de video; se añadirá cuando INSTAR genere el catálogo visual de previews |
| [OpenColorIO](https://github.com/AcademySoftwareFoundation/OpenColorIO) | Espacios de color, gamma, LUTs y comparación coherente entre displays | Debe entrar como diagnóstico explícito; no queremos aplicar transforms de color a ciegas |
| [Chataigne](https://github.com/benkuper/Chataigne) | Puente opcional para OSC/MIDI/DMX y registro operativo | NAYADE debe estabilizar primero sus contratos; no será una dependencia del núcleo |

## Fase posterior

- [GStreamer](https://github.com/GStreamer/gstreamer): útil para captura,
  reproducción o test en vivo de baja latencia. Su instalación y sus plugins
  tienen una matriz de licencias más amplia; el núcleo y la distribución deben
  aislarse antes de adoptarlo.
- [OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO):
  útil para intercambiar cortes, markers y tiempos entre aplicaciones, pero no
  reemplaza el parser de Advanced Output de Resolume ni contiene los medios.
- [Essentia](https://github.com/MTG/essentia): muy potente para BPM, beats,
  onsets y descriptores musicales, pero está bajo AGPL-3.0. Se evaluará como
  módulo opcional aislado antes de incorporarlo a una distribución gratuita.

## No adoptar ahora

- SAM2 u otros modelos de segmentación: son demasiado pesados para el primer
  flujo y no solucionan por sí mismos el escalado, la deformación o los cues.
- Natron, Blender u otra aplicación de autoría: contradicen el objetivo actual
  de un núcleo sin UI típica.
- Decord/TorchCodec: duplican el acceso GPU que ya cubren PyNvVideoCodec y
  FFmpeg; se reconsideran sólo si aparece un cuello de botella medido.
- Un fork privado de Resolume o del procesador LED: RESOLUME_ADAPTER lee evidencia y
  propone; no debe escribir configuración en hardware ajeno automáticamente.

## Regla de incorporación

Antes de sumar una herramienta, debe responder a una función concreta de
INSTAR, NAYADE o IMAGO, pasar una prueba con material real y declarar licencia,
versión, consumo esperado y ruta de fallback. Las dependencias de Python se
fijan en `requirements.txt`; los binarios externos se comprueban al inicio del
comando y se reportan con claridad.


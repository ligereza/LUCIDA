# Runbook: preparar medios DXV para Resolume

## Cuándo usarlo

Úsalo cuando se preparen clips para reproducción en Resolume y se quiera reducir el trabajo
de decodificación durante el show.

## Procedimiento recomendado

1. Conserva una copia del archivo original.
2. En Adobe Media Encoder selecciona el formato **DXV3**.
3. Mantén la resolución que realmente necesita la composición o la salida. No conviertas a
   4K si el show no lo requiere.
4. Usa **Square Pixels (1.0)** salvo que el proyecto tenga una razón documentada para otro
   pixel aspect ratio.
5. Usa un frame rate fijo y coherente entre material, composición y salida.
6. Selecciona **Progressive**.
7. En **Time Interpolation**, usa **Frame Sampling** para loops VJ salvo que exista una
   necesidad concreta de crear cuadros intermedios.
8. Usa **Normal Quality** como punto de partida.
9. Selecciona **With Alpha** solo si el clip tiene transparencia real. Para un video normal,
   usa **No Alpha**.
10. Exporta primero un clip representativo y pruébalo en la composición real.
11. Si la prueba es correcta, procesa el resto y guarda los DXV en el SSD con más espacio
    libre, usando carpetas estables.

## Validación en Resolume

- Comprueba que el clip llena la composición con la escala esperada.
- Reproduce el loop durante varios minutos.
- Verifica que no haya flicker, tearing, saltos ni pérdida de sincronía.
- Observa el rendimiento durante reproducción, no solo durante la conversión.
- Guarda una copia del proyecto y de los medios en la estructura definitiva antes de moverlos.

Si Resolume pierde rutas después de mover archivos, usa **Media Manager > Relocate** y apunta
a la carpeta raíz correcta.

## Diagnóstico rápido

| Síntoma | Primeras comprobaciones |
|---|---|
| Flicker dentro del archivo | Reproducir el original; revisar FPS, progresivo e interpolación |
| Flicker solo en pantalla/proyector | Frecuencia de refresco, PWM/LED y cadena de salida |
| Cortes horizontales | Considerar tearing; revisar sincronización y salida |
| CPU alta durante la conversión | Esperable en Media Encoder; revisar ventilación y alimentación |
| CPU alta durante reproducción | Revisar códec, resolución, composición, procesos y salida |
| Clips offline | Relocate en Media Manager; revisar que la estructura no haya cambiado |

## Reglas para el SSD

La instalación de Resolume puede permanecer en el SSD original si funciona correctamente. La
ubicación de los medios y proyectos se puede elegir por espacio libre, velocidad medida y
organización. Mover solo la instalación no garantiza una reducción apreciable de temperatura
o uso de CPU.


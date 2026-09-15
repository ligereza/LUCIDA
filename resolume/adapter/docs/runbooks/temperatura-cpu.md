# Runbook: interpretar temperatura y consumo de CPU antes de un show

## Objetivo

Distinguir un pico breve de Turbo Boost de una temperatura anormal sostenida, sin hacer cambios
arriesgados justo antes de una presentación.

## Prueba de bajo riesgo

1. Conecta el portátil a corriente.
2. Cierra renders y aplicaciones que no sean necesarias.
3. Deja Firefox reproduciendo un video y mantén la carga de trabajo habitual durante 5–10
   minutos.
4. En HWiNFO observa los valores **Current**, **Average** y **Maximum** por separado.
5. Registra temperatura del paquete, temperatura máxima de núcleo, consumo total de CPU,
   uso total y si aparece thermal throttling.

## Interpretación orientativa

- Un pico corto al abrir Illustrator, Media Encoder u otra aplicación puede venir de Turbo
  Boost y no implica por sí solo un problema.
- Si el equipo baja aproximadamente a 45–60 °C con carga ligera, el comportamiento parece
  compatible con una respuesta térmica normal.
- Si permanece alrededor de 70–80 °C con menos de 10% de uso y consumo bajo, investigar
  perfil de energía, procesos en segundo plano, control de ventiladores y refrigeración.
- **Thermal throttling: No** y **Critical temperature: No** son más informativos para el
  estado actual que un máximo histórico aislado.

Los límites exactos dependen del modelo, firmware y perfil térmico del portátil. No uses el
apagado de emergencia como prueba y no actualices BIOS ni hagas cambios grandes antes del
show salvo que exista un fallo reproducible que lo justifique.

## Registro conocido del equipo

En una prueba previa del GIGABYTE AORUS 17 BS se observó aproximadamente:

- Reposo inicial: 49 °C y 17,5 W.
- Pico al abrir Illustrator: cerca de 96 °C y 59 W.
- Después de estabilizar: cerca de 52 °C y 9,7 W.
- Uso ligero posterior: alrededor de 6% de CPU y 17,8 W.
- Máximo histórico de una captura posterior: 84 °C.
- No había desaceleración térmica ni temperatura crítica activa.

Estos valores sirven como línea base del equipo, no como garantía para cualquier carga,
temperatura ambiente o superficie.


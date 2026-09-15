# INSTAR Media Preflight

INSTAR comienza con una inspección técnica rápida de las visuales. El modo
normal usa FFprobe y no decodifica todo el video; el archivo original no se
modifica.

## Uso

Desde la raíz del repositorio:

```powershell
python .\tools\resolume_adapter_cli.py instar "D:\VJ\Media" `
  --report ".\artifacts\instar-preflight.json" `
  --sidecars-dir ".\artifacts\instar-sidecars"
```

Para comparar contra una composición o salida conocida:

```powershell
python .\tools\resolume_adapter_cli.py instar "D:\VJ\Media" `
  --target-fps 60 `
  --target-resolution 1920x1080 `
  --target-codec dxv
```

## Qué informa

- Contenedor, codec y pixel format.
- Resolución, FPS, duración y cantidad de frames cuando están disponibles.
- Bit depth, bitrate, relación de aspecto y metadata de color.
- Presencia de audio embebido.
- Alpha declarado por el pixel format.
- Diferencia respecto de FPS, resolución o codec objetivo.

La extensión `.mp4` o `.mov` no basta para decidir si un archivo tiene alpha:
INSTAR inspecciona el contenedor, el codec y el pixel format. En DXV el alpha
puede quedar indeterminado únicamente con FFprobe, por lo que se marca como
`unknown` y se recomienda una prueba visual sobre fondo contrastante.

## Modo profundo

```powershell
python .\tools\resolume_adapter_cli.py instar "D:\VJ\Media" `
  --deep `
  --report ".\artifacts\instar-deep.json"
```

`--deep` conserva el análisis adicional de luminancia existente. Sus alertas no
confirman un problema de proyector, LED, PWM, cableado o procesador; sólo
indican que el archivo merece una prueba más específica.

## Análisis GPU

En una máquina NVIDIA con el backend instalado:

```powershell
python .\tools\resolume_adapter_cli.py instar "D:\VJ\Media" `
  --gpu `
  --gpu-max-frames 900 `
  --gpu-batch-size 16 `
  --report ".\artifacts\instar-gpu.json"
```

Esta ruta utiliza NVDEC para decodificar y CuPy para calcular luminancia,
movimiento, color, saturación y periodicidad candidata en GPU. Los frames no
se copian a la CPU para calcular las métricas; sólo regresan números pequeños
para el JSON. Si el codec no es compatible, el archivo queda como
`GPU_UNAVAILABLE` y no se procesa silenciosamente con CPU.

La periodicidad no se presenta como BPM musical: es una candidata de repetición
basada en autocorrelación de luminancia y debe confirmarse antes de usarla como
cue de IMAGO.

## Sidecars

Cada visual puede producir un archivo `<nombre>.<extensión>.resolume_adapter.json`. El
sidecar contiene el perfil técnico, estado, comprobaciones y recomendaciones
para que NAYADE e IMAGO puedan reutilizarlos sin volver a inspeccionar el
medio durante el show.

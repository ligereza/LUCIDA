# RESOLUME_ADAPTER Diagnose y DXV Assistant

## Requisitos actuales

- Windows PowerShell.
- Python 3.11 o superior.
- FFmpeg y FFprobe accesibles desde `PATH`.
- Para DXV: una build de FFmpeg que exponga el encoder `dxv`.

Comprobar el encoder:

```powershell
ffmpeg -hide_banner -h encoder=dxv
```

## Diagnosticar un clip

Desde la raíz de RESOLUME_ADAPTER:

```powershell
python .\tools\resolume_adapter_cli.py diagnose "D:\VJ\Media\clip.mp4" --target-fps 60 --target-resolution 1920x1080 --report ".\artifacts\clip-report.json"
```

El análisis revisa metadata, estabilidad temporal, orden de campos, codec y una señal global de luminancia. El resultado es orientativo: no puede confirmar problemas del proyector, PWM, frecuencia de refresco, tearing o cableado.

## Convertir a DXV

Conversión básica a DXV Normal Quality / No Alpha:

```powershell
python .\tools\resolume_adapter_cli.py dxv "D:\VJ\Media\clip.mp4" --fps 60 --resolution 1920x1080
```

Simular la operación sin crear el archivo:

```powershell
python .\tools\resolume_adapter_cli.py dxv "D:\VJ\Media\clip.mp4" --fps 60 --dry-run
```

La herramienta valida que el resultado tenga codec `dxv`. Si la salida ya existe, se debe indicar `--overwrite` conscientemente.

## Alcance actual

- La primera versión procesa un archivo por ejecución.
- Se conserva el audio y se lo convierte a PCM cuando existe.
- El formato soportado inicialmente es DXV `dxt1`, equivalente a Normal Quality / No Alpha en el encoder probado.
- Alpha, batch processing y una capa portable sin consola quedan para el siguiente incremento.

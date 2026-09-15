# INSTAR: catálogo, perfiles y caché

INSTAR prepara material para un show sin modificar los videos originales. Puede
leer metadata técnica, reutilizar análisis anteriores y comparar cada visual con
un perfil de destino.

## Análisis técnico con caché

```powershell
python .\tools\resolume_adapter_cli.py instar "D:\VJ\Media" `
  --cache-db ".\artifacts\instar.sqlite3" `
  --report ".\artifacts\instar.json" `
  --html-report ".\artifacts\instar.html" `
  --manifest ".\artifacts\instar-manifest.json" `
  --sidecars-dir ".\artifacts\sidecars"
```

La caché identifica cada archivo con una huella rápida de tamaño, fecha de
modificación y extremos del archivo. Si el archivo y los parámetros no cambian,
INSTAR reutiliza el reporte sin volver a llamar a FFprobe ni al análisis visual.

## Comparar contra un perfil de show

```powershell
python .\tools\resolume_adapter_cli.py instar "D:\VJ\Media" `
  --show-profile ".\docs\templates\show-profile.json" `
  --cache-db ".\artifacts\instar.sqlite3" `
  --report ".\artifacts\instar-show.json" `
  --html-report ".\artifacts\instar-show.html"
```

El perfil puede declarar resolución, FPS, codec permitido, alpha, rango de
color y refresco. Las reglas solo agregan advertencias al informe; no escalan,
convierten ni corrigen archivos.

## Modos GPU

Para un análisis visual con NVIDIA se puede añadir `--gpu`. La salida incluye un
`ClipProfile` con movimiento, luminancia, energía, periodicidad, candidatos de
flash, picos visuales y una estimación de continuidad del loop. El análisis GPU
también calcula similitud de bordes horizontal y vertical para priorizar
visuales que puedan repetirse como `pattern` o desplazarse como `marquee`.

Cuando existe una serie temporal suficiente, el perfil también incluye
`events.cue_suggestions`. Son candidatos semánticos para operar el clip en
vivo:

- `change` + `clean`: momento de baja actividad para cambiar de visual con
  menos riesgo de corte brusco.
- `change` + `impact`: cambio de alta actividad o contraste, útil para entrar en
  un drop o acento visual.
- `strobe_window`: rango donde se concentran candidatos de flash; siempre
  requiere revisión humana y nunca dispara un estrobo automáticamente.
- `loop`: rango `in_position_s` / `out_position_s` con similitud temporal; es
  una sugerencia de prueba, no una garantía de loop perfecto.

Las posiciones se expresan en segundos y milisegundos para facilitar una
futura asociación con los seis slots de CUE de Resolume. INSTAR no escribe
estos puntos en el `.avc`, no cambia el transporte y no activa efectos.

Para convertir los candidatos de uno o más `ClipProfile` en una disposición
revisable de los seis slots:

```powershell
python .\tools\resolume_adapter_cli.py instar-cue-plan `
  ".\artifacts\clip-profile.json" `
  --report ".\artifacts\cue-plan.json"
```

La política reserva `Position1` para el mejor cambio limpio, `Position2` para
impacto, `Position3` para el inicio de una ventana de strobe, `Position4` y
`Position5` para los extremos del mejor loop, y `Position6` para el candidato
restante con mayor confianza. Un slot sin evidencia queda vacío y los CUES
sobrantes se conservan como `unassigned_candidates`. El resultado es un plan
`review_required`; el `.avc` permanece intacto.

El perfil `visual.behavior` es el contrato que consume NAYADE. Separa señales
espaciales medidas en GPU de inferencias débiles basadas en nombre, movimiento
y continuidad. Incluye `pattern.horizontal`, `pattern.vertical`,
`marquee.horizontal`, `marquee.vertical` y la seguridad sugerida para flip o
rotación. Un score `inferred` ordena el soundcheck, pero siempre exige preview;
no es una autorización automática.

```powershell
python .\tools\resolume_adapter_cli.py instar "D:\VJ\Media" `
  --gpu --gpu-max-frames 900 --gpu-batch-size 16 `
  --cache-db ".\artifacts\instar-gpu.sqlite3" `
  --report ".\artifacts\instar-gpu.json"
```

Si el codec no es compatible con la ruta NVDEC disponible, INSTAR lo marca como
`GPU_UNAVAILABLE`; no hace fallback silencioso a CPU.

## Salidas

- `*.json`: informe completo del lote.
- `*.resolume_adapter.json`: sidecar por visual para NAYADE e IMAGO.
- `*.html`: tabla navegable para revisar el material.
- `*-manifest.json`: catálogo portable con rutas relativas, estados y perfiles.
- `*.sqlite3`: caché local, no debe versionarse en Git.
- `clip_profile.schema.json`: contrato de cada visual.

## Seguridad operativa

- El perfil de show es de solo lectura.
- No se modifican videos, composiciones, Resolume ni procesadores.
- La huella rápida no reemplaza una verificación forense; solo decide si es
  razonable reutilizar el análisis local.
- Las alertas de flash, loop y color son señales de revisión, no certificaciones
  de la cadena física de salida.

# INSTAR: adaptación target-specific

Este comando genera previews derivados para superficies que no tienen un
material con la proporción correcta. Lee un plan creado por `instar-map` y no
modifica el XML, el showfile, los medios fuente ni el procesador LED.

## Uso

```powershell
python .\tools\resolume_adapter_cli.py instar-adapt `
  "Z:\RESOLUME_ADAPTER\runs\plox-mapping-plan-gpu-full.json" `
  --output-dir "Z:\RESOLUME_ADAPTER\runs\plox-adapt-previews" `
  --duration 6 `
  --encoder auto `
  --dxv-output-dir "Z:\RESOLUME_ADAPTER\runs\plox-adapt-dxv" `
  --report "Z:\RESOLUME_ADAPTER\runs\plox-adaptation.json"
```

`auto` usa `h264_nvenc` cuando la build de FFmpeg lo expone y vuelve a
`libx264` cuando no está disponible. El encoder GPU acelera la compresión del
preview; algunos filtros de composición todavía pueden ejecutarse en CPU.

Si se indica `--dxv-output-dir`, INSTAR crea además un DXV Normal Quality / No
Alpha por tarea. Es un derivado candidato que debe revisarse en el LED real;
no reemplaza automáticamente un archivo existente.

## Estrategias

- `crop`: llena el target conservando la proporción y recorta los excedentes.
- `fit_background`: conserva la visual completa sobre un fondo derivado y
  desenfocado.
- `pattern`: repite la visual y espeja copias alternas para reducir costuras.
- `marquee`: desplaza la repetición por el eje de la superficie.

`auto` renderiza los candidatos derivados desde `fallback_strategies`. Cada
salida tiene dimensiones exactas del slice, exige preview físico y queda lista
para convertirse a DXV después de la aprobación. Con `--dxv-output-dir`, el
DXV se genera en una carpeta separada para facilitar esa revisión.

En un `input_group` compartido se genera una sola tarea, aunque el grupo tenga
varias slices de salida. Esto evita renderizar tres veces la misma adaptación.

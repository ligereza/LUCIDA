# INSTAR: flujo preshow completo

INSTAR trabaja como una cadena de evidencia, no como un botón mágico. El
material original y el preset XML se leen; los derivados se escriben en una
carpeta separada; ninguna etapa modifica Resolume, el showfile o el procesador
LED.

## Flujo recomendado

### 1. Analizar el catálogo

```powershell
python .\tools\resolume_adapter_cli.py instar `
  "Z:\RESOLUME_ADAPTER\test-corpus\plox visuales" `
  --deep `
  --gpu auto `
  --report "Z:\RESOLUME_ADAPTER\runs\instar-catalog.json" `
  --manifest "Z:\RESOLUME_ADAPTER\runs\instar-manifest.json"
```

El catálogo conserva dimensiones, FPS, codec, duración, luminancia, señales
de movimiento, periodicidad, colores y descriptores espaciales GPU cuando
están disponibles. Los resultados son pistas para decidir; no reemplazan la
revisión artística ni la prueba física.

### 2. Leer Advanced Output

```powershell
python .\tools\resolume_adapter_cli.py instar-map `
  "C:\Users\issvk\Documents\Resolume Arena\Presets\Advanced Output\PLOX.xml" `
  --catalog "Z:\RESOLUME_ADAPTER\runs\instar-catalog.json" `
  --report "Z:\RESOLUME_ADAPTER\runs\mapping-plan.json"
```

El plan separa `InputRect` de `OutputRect`, conserva los grupos que comparten
una entrada y alerta cuando una transformación no uniforme puede deformar una
geometría circular. No se debe confundir una resolución de composición con la
resolución física del procesador LED.

### 3. Generar previews y candidatos DXV

```powershell
python .\tools\resolume_adapter_cli.py instar-adapt `
  "Z:\RESOLUME_ADAPTER\runs\mapping-plan.json" `
  --output-dir "Z:\RESOLUME_ADAPTER\runs\adapt-previews" `
  --dxv-output-dir "Z:\RESOLUME_ADAPTER\runs\adapt-dxv" `
  --encoder auto `
  --report "Z:\RESOLUME_ADAPTER\runs\adaptation-plan.json"
```

`auto` usa NVENC si está disponible y cae a `libx264` si no. El DXV se genera
en una carpeta distinta y en Normal Quality / No Alpha. Se considera candidato
hasta verlo en el LED real.

Estrategias:

- `crop`: llena sin estirar y recorta los bordes.
- `fit_background`: conserva la imagen completa sobre un fondo derivado.
- `pattern`: repite la unidad y espeja copias alternas para ocultar costuras.
- `marquee`: usa una repetición y la desplaza por el eje del banner o tótem.

### 4. Preparar soundcheck

```powershell
python .\tools\resolume_adapter_cli.py nayade-session init `
  "Z:\RESOLUME_ADAPTER\runs\mapping-plan.json" `
  --output "Z:\RESOLUME_ADAPTER\runs\nayade-soundcheck.json" `
  --catalog "Z:\RESOLUME_ADAPTER\runs\instar-catalog.json" `
  --adaptation-plan "Z:\RESOLUME_ADAPTER\runs\adaptation-plan.json"
```

NAYADE agrega los derivados como pasos explícitos por `input_group_id`. En el
venue, el VJ registra si cada variante fue aprobada, rechazada o quedó en
revisión. La sesión es evidencia; no envía órdenes al procesador ni al
showfile.

## Criterio de aprobación

Una variante sólo se considera lista cuando pasa estas comprobaciones:

- la geometría de la visual no aparece estirada;
- los bordes del slice no invaden el slice vecino;
- el movimiento no revela costuras o saltos molestos;
- el negro y el rango de señal se ven coherentes con la cadena real;
- el FPS y la lectura del DXV son estables en Resolume;
- el operador confirma que el input group correcto recibe la señal.

Si no hay una visual apropiada, INSTAR debe dejar visible esa incertidumbre y
proponer `pattern` o `marquee`; no debe inventar que existe un match perfecto.

# NAYADE: sesión reproducible de soundcheck

NAYADE convierte las pruebas que normalmente quedan en la memoria del VJ en
un registro portable. La sesión puede iniciarse directamente desde un
Advanced Output XML real de INSTAR, desde un informe de mapping o desde la
tarjeta geométrica, y conserva el `input_group_id` como unidad de prueba.
Esto evita tratar como independientes varias slices que comparten el mismo
InputRect.

## Iniciar la sesión

~~~powershell
python .\tools\resolume_adapter_cli.py nayade-session init `
  "C:\Users\issvk\Documents\Resolume Arena\Presets\Advanced Output\VENUE.xml" `
  --output "Z:\RESOLUME_ADAPTER\runs\plox-nayade-soundcheck.json" `
  --name "PLOX — Soundcheck Mapping" `
  --seed 4821 `
  --adaptation-plan "Z:\RESOLUME_ADAPTER\runs\plox-instar-adaptation-dxv-v1.json" `
  --protocol "Z:\RESOLUME_ADAPTER\runs\plox-soundcheck-protocol.json"
~~~

La sesión crea una matriz corta y determinista:

- baseline;
- flip horizontal;
- flip vertical;
- rotación de 180 grados;
- pattern por input group;
- marquee en el eje de la superficie.
- variantes target-specific generadas por INSTAR, cuando se entrega
  `--adaptation-plan`.
- checks de cadena del procesador, cuando se entrega `--protocol`.

La semilla permite repetir variaciones futuras. Los pasos comienzan como
`planned`; INSTAR y NAYADE no inventan si una transformación funcionó en la
pantalla real.

El protocolo se adapta como pasos `processor_check` al comienzo de la sesión.
Esto conserva la diferencia entre comprobar la cadena —blackout, PLUGE,
grises, geometría y estabilidad— y experimentar con las visuales —flip,
pattern, marquee o adaptaciones target-specific—. Ambos resultados pueden
registrarse en el mismo archivo, pero ninguna de las dos capas envía comandos
automáticos al procesador.

El contrato del protocolo se valida antes de incorporarlo a la sesión. Si está
incompleto, NAYADE detiene la creación para no registrar una matriz ambigua.

## Registrar un resultado

Después de probar una variación en Resolume:

~~~powershell
python .\tools\resolume_adapter_cli.py nayade-session record `
  "Z:\RESOLUME_ADAPTER\runs\plox-nayade-soundcheck.json" `
  --operation marquee `
  --scope input_group `
  --target input-group-003 `
  --result approved `
  --parameters '{"axis":"horizontal","speed":0.18,"wrap":true}' `
  --notes "La franja se lee limpia y no invade el slice vecino."
~~~

Los resultados válidos son `approved`, `rejected`, `review`, `running` y
`planned`. Se pueden registrar varios objetivos repitiendo `--target`.

NAYADE vincula automáticamente el registro con el primer paso pendiente que
coincide. Para evitar cualquier ambigüedad se puede indicar el ID exacto:

```powershell
python .\tools\resolume_adapter_cli.py nayade-session record `
  "Z:\RESOLUME_ADAPTER\runs\plox-nayade-soundcheck.json" `
  --step-id step-009 `
  --operation instar_adaptation `
  --result approved `
  --notes "El marquee se lee sin costura."
```

Para conservar la sesión anterior y crear una nueva versión del registro:

```powershell
python .\tools\resolume_adapter_cli.py nayade-session record `
  "Z:\RESOLUME_ADAPTER\runs\plox-nayade-soundcheck.json" `
  --step-id processor-check-002 `
  --operation processor_check `
  --scope signal_and_processor `
  --result approved `
  --notes "PLUGE correcto; near-black visible sin gris levantado." `
  --output "Z:\RESOLUME_ADAPTER\runs\plox-nayade-soundcheck-after-pluge.json"
```

`--output` exige que el destino no exista y deja intacto el origen. Sin esa
opción, el registro conserva el comportamiento habitual pero escribe de forma
atómica para no dejar un JSON parcial si la operación se interrumpe.

Para continuar sin buscar manualmente en el JSON:

```powershell
python .\tools\resolume_adapter_cli.py nayade-session next `
  "Z:\RESOLUME_ADAPTER\runs\plox-nayade-soundcheck.json"
```

Para revisar si la sesión está lista antes de abandonar el venue:

```powershell
python .\tools\resolume_adapter_cli.py nayade-session report `
  "Z:\RESOLUME_ADAPTER\runs\plox-nayade-soundcheck.json" `
  --report "Z:\RESOLUME_ADAPTER\runs\plox-nayade-soundcheck-status.json"
```

El reporte clasifica la sesión como `READY`, `INCOMPLETE`, `REVIEW` o
`BLOCKED`, indica el siguiente paso y resume sólo riesgos derivados del estado
registrado. No copia notas del operador ni rutas privadas.

La sesión todavía registra decisiones, pero no envía órdenes a Resolume. Esto
deja abierta una integración posterior con OSC, MIDI o Chataigne sin mezclar
la capa de control con la evidencia del soundcheck.

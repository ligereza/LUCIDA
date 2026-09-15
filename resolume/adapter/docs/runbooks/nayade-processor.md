# NAYADE — procesador primero

## Objetivo

Llegar al soundcheck, registrar qué equipo existe en la cadena y separar lo que se sabe del procesador de lo que se sabe de la pantalla. La herramienta orienta la prueba; no cambia el procesador automáticamente.

## Comandos actuales

Desde la raíz del checkout LUCIDA/RESOLUME:

```powershell
python tools/resolume_adapter_cli.py nayade-processor catalog
python tools/resolume_adapter_cli.py nayade-processor discover --report Z:\RESOLUME_ADAPTER\runs\nayade\processor-discovery.json
python tools/resolume_adapter_cli.py nayade-processor snapshot --device COM3 -o Z:\RESOLUME_ADAPTER\runs\nayade\processor-snapshot.json
python tools/resolume_adapter_cli.py nayade-processor validate-case data\cases\soundcheck-2026-08-29-vc2.json
python tools/resolume_adapter_cli.py nayade-processor diagnose-case data\cases\soundcheck-2026-08-29-vc2.json
python tools/resolume_adapter_cli.py nayade-processor reconcile `
  --processor-observation Z:\RESOLUME_ADAPTER\runs\nayade\processor-observation.json `
  --mapping Z:\RESOLUME_ADAPTER\runs\nayade\mapping-plan.json `
  --report Z:\RESOLUME_ADAPTER\runs\nayade\reconciliation.json
python tools/resolume_adapter_cli.py nayade-processor probe-output `
  --report Z:\RESOLUME_ADAPTER\runs\nayade\output-probe.json
python tools/resolume_adapter_cli.py nayade-processor protocol `
  --reconciliation Z:\RESOLUME_ADAPTER\runs\nayade\reconciliation.json `
  --mapping Z:\RESOLUME_ADAPTER\runs\nayade\mapping-plan.json `
  --report Z:\RESOLUME_ADAPTER\runs\nayade\soundcheck-protocol.json
```

`discover` consulta el inventario USB/COM del sistema, pero no abre los puertos. Si no aparece nada, todavía puede existir un procesador controlable por Ethernet o por el software del fabricante.

`snapshot` puede usar `--model` cuando el técnico o una etiqueta confirma el modelo. Si no se entrega, el resultado conserva una coincidencia tentativa o `unknown-led-processor`. Siempre deja pendiente el `ModuleProfile`.

`validate-case` comprueba que el registro conserva observaciones, hipótesis y
secuencia temporal con el contrato `NayadeProcessorCase`. `diagnose-case` hace
esta validación automáticamente antes de aplicar reglas de rango, gamma y
negros.

`reconcile` cruza sólo los documentos que se entreguen. Si encuentra entrada y
salida con resoluciones distintas, lo marca como escalado observado/inferido;
si encuentra rangos distintos, eleva una revisión de alto riesgo. No modifica
el procesador y todas sus recomendaciones requieren aprobación explícita.

`probe-output` se ejecuta en el portátil VJ antes de tocar la cadena. Registra
resolución, Hz, adaptador y EDID de forma acotada; no puede confirmar por sí
solo RGB Full/Limited ni lo que finalmente recibe cada salida del procesador.

`protocol` convierte la evidencia disponible en un checklist determinista. La
línea base cubre blackout, PLUGE/near-black, grises, primarios, geometría y
movimiento; los conflictos de rango, escalado, resolución, deformación o
estabilidad elevan las pruebas relacionadas. La salida es `plan_only`: no emite
patrones ni cambia el hardware.

## Flujo de llegada al venue

1. Capturar foto del procesador, modelo, firmware, entradas, salidas y cable conectado.
2. Ejecutar `discover`; guardar el JSON y anotar si el enlace es USB, Ethernet o solo HDMI.
3. Identificar el modelo exacto sin cambiar parámetros.
4. Asociar un perfil de módulo: indoor/outdoor, pitch, resolución física, tamaño, receiving card y condición visible.
5. Capturar el estado del software del fabricante o una foto legible antes de tocar color.
6. Probar patrón negro, near-black/PLUGE, blanco, primarios, grises y geometría.
7. Registrar cada cambio como experimento reversible; no “corregir al ojo” sin snapshot y resultado.

## Qué debe informar NAYADE

- rango de la GPU y del procesador, si están confirmados;
- resolución y frecuencia de entrada/salida;
- si hay escalado, crop, mapping o deformación;
- gamma, brillo, contraste, saturación y conversiones de rango cuando el modelo las expone;
- relación entre el procesador y la superficie física;
- hipótesis priorizadas, no una falsa certeza;
- qué dato falta para continuar.

## Política de equipos desconocidos

Un dispositivo no identificado puede ser observado y documentado. No recibe comandos, patrones ni escrituras. Un VID/PID coincidente tampoco habilita el protocolo: el modelo, firmware y transporte deben confirmarse primero.

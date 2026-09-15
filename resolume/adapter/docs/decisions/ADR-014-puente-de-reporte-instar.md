# ADR-014: Puente seguro de reporte INSTAR al contrato VJ

## Estado

Aceptado.

## Contexto

INSTAR ya produce reportes de preflight y perfiles de clip. El adaptador VJ
recibe eventos canonicos, pero no tenia una frontera explicita para consumir
un reporte de INSTAR. Pasar el reporte completo propagaria rutas locales,
mensajes de error y campos privados que no necesita el flujo de estado.

## Decision

`adapters/vj/instar_input.py` construye un evento `preflight` de fuente
`INSTAR` usando una lista blanca de datos tecnicos y de estado. El llamador
debe proporcionar `event_id` y `sequence`; el timestamp se toma de
`generated_at` y debe incluir zona horaria.

El puente conserva como resumen por asset el identificador estable, estado,
codec, FPS, dimensiones, alpha, estado de loop y cantidad de cues. Conserva
tambien contadores del reporte. No copia `path`, `media_root`, `error` ni
campos desconocidos. `project_instar_show_input()` reutiliza la proyeccion
acotada existente para consumidores futuros.

## Consecuencias

- INSTAR puede entregar observaciones al adaptador VJ sin importar su
  implementacion ni ejecutar sus herramientas.
- El resumen es suficiente para estado y replay, pero no reemplaza el reporte
  completo de INSTAR.
- La secuencia sigue siendo responsabilidad del orquestador o del productor
  de eventos; los datos fuera de orden son rechazados por la proyeccion.
- El puente no abre procesos, sockets, archivos de media ni modifica
  Resolume.

## Alternativas descartadas

- Copiar el reporte completo: expone datos privados y rompe el limite de
  contrato.
- Importar `tools.resolume_adapter.instar`: acopla el adaptador a una implementacion y
  dificulta su reutilizacion por replay o por otro productor.
- Inferir la secuencia localmente: puede ocultar perdida o reordenamiento de
  eventos.

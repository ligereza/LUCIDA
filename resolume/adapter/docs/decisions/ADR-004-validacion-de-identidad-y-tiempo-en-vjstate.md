# ADR-004: Validacion de identidad y tiempo al restaurar VJState

**Estado:** Accepted
**Fecha:** 2026-09-01
**Alcance:** contrato compartido `adapters.vj`

## Contexto

La auditoria de restauracion encontro que `VJState.from_dict()` copiaba sin
validar `last_event_id`, `last_timestamp` y `checkpoint_id`. Eso permitia
restaurar ids que no eran texto y timestamps que no eran ISO-8601, aunque el
schema de `VJState` los declara texto o nulo.

Un timestamp invalido podia fallar mas tarde dentro de la validacion de orden
del adaptador, fuera de la frontera de restauracion. El estado parcialmente
aceptado dejaba de ser una base confiable para replay o recuperacion.

## Decision

Validar los tres campos opcionales al construir `VJState` desde un mapping:

- `last_event_id` y `checkpoint_id` deben ser texto no vacio o `null`;
- `last_timestamp` debe ser ISO-8601 con zona horaria o `null`;
- no se realizan coerciones de tipos.

## Consecuencias

- Los snapshots invalidos fallan en la frontera comun con `ContractError`.
- Los estados validos y los fixtures existentes conservan su representacion.
- La recuperacion no desplaza errores de identidad o reloj hacia el procesamiento
  de eventos.

## Verificacion

La cobertura esta en `tests/vj/test_adapter.py`; la suite completa y el grafo
local de schemas deben ejecutarse antes de publicar cambios posteriores.

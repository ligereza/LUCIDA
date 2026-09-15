# ADR-008: Estado de capacidad JSON-safe

**Estado:** Accepted
**Fecha:** 2026-09-01
**Alcance:** contrato de integracion `lucida`

## Contexto

`CapabilityReport.state` es una superficie interna que puede conservar datos
privados, pero forma parte de `LucidaState.to_dict()` y alimenta replay y
diagnostico. Antes de esta decision aceptaba objetos Python como `set` o
`NaN`; el fallo aparecia solo al serializar el reporte, lejos de la frontera de
entrada. La metadata de `LucidaState` tenia el mismo riesgo.

## Decision

Validar `CapabilityReport.state` y `LucidaState.metadata` como mappings con
valores serializables en JSON y sin valores no finitos. La validacion no aplica
redaccion ni elimina datos privados: solo garantiza que el contrato puede
transportarse y reproducirse de forma determinista.

## Consecuencias

- Los errores de serializacion se detectan al restaurar el estado.
- La proyeccion publica sigue siendo la responsable de filtrar claves privadas.
- Los estados JSON-validos conservan su representacion y sus roundtrips.

## Verificacion

Las regresiones estan en `tests/lucida/test_lucida.py`; la suite global y el
grafo local de schemas deben seguir pasando antes de publicar.

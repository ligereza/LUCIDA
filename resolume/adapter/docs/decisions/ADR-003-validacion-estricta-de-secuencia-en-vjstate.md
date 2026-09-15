# ADR-003: Validacion estricta de secuencia al restaurar VJState

**Estado:** Accepted
**Fecha:** 2026-09-01  
**Alcance:** contrato compartido `adapters.vj`  

## Contexto

Durante la auditoria de fronteras de `LUCIDA` se comprobo que
`OscBridgeState.from_dict()` aceptaba valores ambiguos para `received_count`.
Ese caso fue corregido en la frontera OSC. La misma revision encontro que
`VJState.from_dict()` convierte `sequence` mediante `int(value.get("sequence", 0))`.

Esa conversion acepta representaciones que no pertenecen al contrato estricto,
por ejemplo `true` o un texto numerico. Tambien deja que errores de tipo aparezcan
como errores de conversion en vez de un `ContractError` explicito. Un snapshot
alterado podria entrar al adaptador con una secuencia distinta de la declarada.

## Decision

Validar `sequence` como entero no negativo y excluir booleanos antes de construir
`VJState`. No se debe usar `int(...)` para normalizar snapshots recibidos.

La correccion debe incluir regresiones para booleanos, negativos, texto numerico
y un roundtrip valido. Cualquier cambio debe conservar la compatibilidad del
fixture de replay y ejecutarse antes de que una rama de integracion consuma el
estado restaurado.

## Consecuencias

- Los snapshots invalidos fallaran de forma determinista en el contrato comun.
- `LUCIDA` podra confiar en que la secuencia restaurada tiene el tipo esperado.
- El cambio queda cubierto por regresiones y mantiene la compatibilidad de los
  snapshots validos y de los fixtures existentes.

## Estado actual

La validacion fue implementada en `adapters/vj/contracts/models.py` y queda
cubierta por `tests/vj/test_adapter.py`. La frontera OSC tambien rechaza de
forma estricta `received_count` y su historial de secuencias.

# ADR-005: Integridad de proyecciones pendientes en LucidaState

**Estado:** Accepted
**Fecha:** 2026-09-01
**Alcance:** contrato de integracion `lucida`

## Contexto

`LucidaState.to_dict()` publica dos representaciones relacionadas de las
propuestas pendientes: `vj_state.pending_proposal_ids` y el campo superior
`pending_proposal_ids`. Antes de esta decision, `LucidaState.from_dict()` leia
solo la representacion anidada y podia ignorar una alteracion en la superior.
Tambien podia restaurar ids pendientes sin una propuesta correspondiente en
`proposals`.

## Decision

Al restaurar un mapping que contiene la proyeccion superior:

- `pending_proposal_ids` debe ser una lista de textos y coincidir exactamente
  con `vj_state.pending_proposal_ids`;
- cada id pendiente debe existir en `proposals`;
- `proposal_id` no puede repetirse en la lista global.

La igualdad se valida antes de exponer el estado restaurado al overlay, replay o
adaptadores de señales.

## Consecuencias

- Un snapshot alterado falla en la frontera de contrato.
- El overlay no puede perder ni inventar propuestas pendientes por divergencia
  entre campos duplicados.
- Los estados validos generados por el orquestador conservan el mismo roundtrip.

## Verificacion

Las regresiones estan en `tests/lucida/test_lucida.py`. La validacion completa
debe incluir la suite y el grafo local de schemas.

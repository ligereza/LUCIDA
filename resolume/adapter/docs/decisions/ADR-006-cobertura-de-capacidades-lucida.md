# ADR-006: Cobertura completa de capacidades en LucidaState

**Estado:** Accepted
**Fecha:** 2026-09-01
**Alcance:** contrato de integracion `lucida`

## Contexto

La superficie de LUCIDA se define con tres capacidades ordenadas:
`INSTAR`, `NAYADE` e `IMAGO`. El orquestador ya exigia esa configuracion, pero
`LucidaState.from_dict()` podia restaurar una lista con nombres duplicados o con
una capacidad ausente. Eso producia un overlay ambiguo y no representaba la
superficie que el contrato promete.

## Decision

Cuando un mapping contiene `capabilities`, debe contener exactamente una entrada
para cada capacidad de LUCIDA: `INSTAR`, `NAYADE` e `IMAGO`. El runtime rechaza
duplicados o ausencias; el schema limita la lista a tres entradas.

## Consecuencias

- El estado restaurado mantiene cobertura completa y determinista.
- Un overlay no puede confundir una capacidad duplicada con otra ausente.
- Los estados generados por el orquestador mantienen el mismo roundtrip.

## Verificacion

Las regresiones estan en `tests/lucida/test_lucida.py`; el grafo local y la
validacion de instancia XIO cubren tambien el schema actualizado.

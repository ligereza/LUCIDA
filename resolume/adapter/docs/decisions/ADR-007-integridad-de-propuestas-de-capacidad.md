# ADR-007: Integridad de propuestas de capacidad

**Estado:** Accepted
**Fecha:** 2026-09-01
**Alcance:** contrato de integracion `lucida`

## Contexto

Cada `CapabilityReport` puede contener propuestas especificas de `INSTAR`,
`NAYADE` o `IMAGO`. El estado tambien conserva una lista global de propuestas,
que es la fuente usada por el overlay para mostrar pendientes. Antes de esta
decision, una propuesta podia existir solo dentro de un reporte de capacidad o
repetirse entre reportes sin que la restauracion lo rechazara.

## Decision

Al restaurar `LucidaState`, los ids de propuestas incluidos por los reportes de
capacidad deben ser unicos y cada uno debe existir en la lista global
`proposals`. Las propuestas de ciclo de vida pueden seguir existiendo solo en la
lista global; la regla evita perder propuestas de capacidad, sin exigir que
todas las propuestas globales pertenezcan a un reporte.

## Consecuencias

- El overlay conserva todas las propuestas de capacidad restauradas.
- Un snapshot con duplicados o referencias huérfanas falla en la frontera.
- El contrato sigue siendo proposal-only y no ejecuta ninguna acción.

## Verificacion

Las regresiones estan en `tests/lucida/test_lucida.py`; la suite y el grafo de
schemas validan el roundtrip generado por los adaptadores.

# ADR-012: Paridad del contrato de propuesta VJ

**Estado:** Accepted  
**Fecha:** 2026-09-01  
**Alcance:** `adapters.vj.contracts.VJProposal`

## Contexto

El schema de `VJProposal` exigía identidad, riesgo, aprobación explícita,
recuperabilidad y modo `proposal_only`, además de rechazar propiedades extra.
El parser runtime validaba varios valores, pero aplicaba defaults a campos
obligatorios y descartaba silenciosamente campos desconocidos.

## Decision

`VJProposal.from_dict()` comprueba la presencia de todos los campos obligatorios
y rechaza cualquier propiedad fuera del contrato publicado. `evidence` sigue
siendo opcional porque así lo define el schema. Las reglas de seguridad
`requires_explicit_approval`, `reversible` y `execution_mode` permanecen
estrictas.

## Consecuencias

- Una propuesta truncada o enriquecida accidentalmente no entra al estado.
- LUCIDA puede confiar en que sus propuestas anidadas tienen forma estable.
- No se agrega ejecución automática ni se modifica el comportamiento de show.

## Verificacion

Las regresiones están en `tests/vj/test_adapter.py`; la suite global y el
grafo de schemas deben continuar pasando.

# ADR-011: Paridad entre runtime y schema de LUCIDA

**Estado:** Accepted  
**Fecha:** 2026-09-01  
**Alcance:** deserialización de `LucidaState` y `CapabilityReport`

## Contexto

Los schemas publicados declaraban campos obligatorios y prohibían propiedades
extra, pero la restauración Python usaba valores por defecto y no comprobaba
el tipo ni la versión de `LucidaState`. Un snapshot incompleto podía llegar al
orquestador como si fuera válido.

## Decision

`LucidaState.from_dict()` y `CapabilityReport.from_dict()` exigen exactamente
los campos publicados por sus schemas. La restauración de estado verifica
`contract_type == "LucidaState"`, `schema_version == "0.1"` y mantiene las
validaciones existentes de cobertura, propuestas y estado pendiente.

## Consecuencias

- Un snapshot truncado o enriquecido accidentalmente falla en la frontera.
- Runtime y JSON Schema describen la misma forma serializada.
- No se cambia el flujo de propuestas ni se ejecutan acciones externas.
- Los productores deben serializar siempre el contrato completo mediante
  `to_dict()`.

## Verificacion

Las regresiones están en `tests/lucida/test_lucida.py`; la suite completa y el
grafo de schemas deben continuar pasando.

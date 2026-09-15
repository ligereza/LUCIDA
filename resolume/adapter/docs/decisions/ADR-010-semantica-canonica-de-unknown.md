# ADR-010: Semantica canonica de `unknown` en SignalFact

**Estado:** Accepted  
**Fecha:** 2026-09-01  
**Alcance:** contrato compartido de perfil de señal

## Contexto

El perfil distingue entre datos declarados, observados, inferidos y no
disponibles. El contrato permitía representar un dato con origen `unknown`
pero conservar al mismo tiempo un valor concreto o una confianza positiva.
Eso hacía posible que una proyección interpretara como ausencia de información
un dato que en realidad afirmaba un valor.

## Decision

Un `SignalFact` con origen `unknown` debe usar exactamente `value: "unknown"`
y `confidence: 0`. La regla se aplica tanto en la normalización Python como
en el schema JSON. Los orígenes `declared`, `observed` e `inferred` mantienen
el intervalo general de confianza `0..1`; `inferred` no requiere `source`
porque puede ser una hipótesis calculada localmente, aunque una fuente
disponible debe conservarse.

## Consecuencias

- La ausencia de información no puede confundirse con una medición débil.
- Los cambios hacia o desde `unknown` producen drift interpretable.
- Los adaptadores deben convertir cualquier lectura no disponible al sentinel
  canónico antes de emitir el perfil.
- No se impone una fuente artificial a las hipótesis internas.

## Verificacion

La regresión está cubierta en `tests/lucida/test_signal_profile.py` y el
contrato queda reflejado en `schemas/signal-profile.schema.json`.

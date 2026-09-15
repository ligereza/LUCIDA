# ADR-009: Drift de procedencia y capacidades del procesador

**Estado:** Accepted
**Fecha:** 2026-09-01
**Alcance:** perfil de señal compartido

## Contexto

La comparación de perfiles detectaba cambios en el valor, origen y confianza
de cada hecho. No detectaba que el mismo valor pasara a estar respaldado por
otra fuente, ni que cambiara una capacidad declarada del procesador LED. En un
soundcheck eso podía ocultar un cambio de medición o de capacidad técnica.

## Decision

`compare_signal_profiles()` reporta rutas acotadas para cambios de
`SignalFact.source` y para diferencias en `processor.capabilities`. Esas rutas
se incorporan al estado de drift de NAYADE/IMAGO, pero nunca se incluyen los
valores observados en la comparación pública.

## Consecuencias

- Un cambio de procedencia deja de presentarse como estado estable.
- Las propuestas pueden pedir revisión cuando cambia la capacidad declarada del
  procesador.
- El overlay conserva sólo conteos y banderas bounded.

## Verificacion

Las regresiones estan en `tests/lucida/test_signal_profile.py`; la suite global
y el grafo local deben continuar pasando.

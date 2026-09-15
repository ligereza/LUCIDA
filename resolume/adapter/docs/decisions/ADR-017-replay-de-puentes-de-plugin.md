# ADR-017: Replay conjunto de puentes de plugin

## Estado

Aceptado.

## Contexto

Los puentes INSTAR, NAYADE e IMAGO pueden producir eventos VJ por separado,
pero una prueba individual no demuestra que sus fases convivan en una sesion.
La integracion real con hardware o software de show no es adecuada para una
prueba determinista.

## Decision

`adapters/vj/replay/plugin_bridges.py` carga registros sinteticos, construye
los eventos mediante los tres puentes y los pasa por `VJAdapter`. Exige
identificadores unicos y secuencias estrictamente crecientes. El reporte
expone el orden de plugin, el orden de fases, el estado final y las garantias
de seguridad.

El replay no abre transportes, ejecuta propuestas, lee media, invoca INSTAR,
NAYADE o IMAGO, ni usa datos de un show real.

## Consecuencias

- La transicion `preflight -> preparation -> show -> incident -> recovery -> closure`
  queda verificada como una sola ruta.
- Los eventos de snapshot pueden actualizar el status comun segun su fase sin
  fabricar propuestas.
- La prueba no demuestra el estado fisico de una pantalla ni la integracion
  con un host; esos limites permanecen explicitos.

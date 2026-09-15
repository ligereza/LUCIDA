# LUCIDA session replay

Este módulo define un contrato append-only para conservar una sesión VJ como
pares `VJEvent` + `SignalEnvelope`. El replay reutiliza el orquestador y las
tres capacidades actuales; no crea un motor alternativo ni abre Resolume o
sockets. El envelope puede conservar señales `osc` o eventos `xio` ya
inyectados por un consumidor.

## Flujo

```text
SignalEnvelope + VJEvent
          |
          +--> validate pair, sequence, ids, timestamps
          |
          +--> LUCIDA orchestrator
          |
          +--> INSTAR / NAYADE / IMAGO proposals
          |
          +--> explicit results, if present
          |
          +--> immutable record + audit log
```

La secuencia debe ser contigua desde `first_sequence` —por defecto `1`—. Se
rechazan gaps, duplicados y retrocesos. El timestamp del evento y el envelope
deben coincidir; la procedencia del evento normalizado y la del transporte se
conservan por separado.

## Uso offline

```python
from lucida.replay.session import replay_fixture

report = replay_fixture(fixture_data)
assert report["status"] == "PASS"
assert report["safety"]["proposal_only"] is True
```

El reporte contiene registros, propuestas, resultados, estado final y un audit
log determinista. Un resultado ausente deja la propuesta pendiente; el replay
no inventa una ejecución.

`SessionReplay.public_report()` genera una vista para compartir: conserva
fases, timestamps, conteos, estados redacted, propuestas resumidas y estados
de resultados, pero omite payloads, argumentos de señal, metadata, notas y
evidencia libre. `report()` sigue siendo la representación interna completa
necesaria para reproducir la sesión.
En los receipts públicos, `mode` sólo se conserva como `proposal_only`; otros
textos de host se descartan.
Los estados enumerados de `HostResult` (`accepted`, `rejected` o `unknown`) y
`execution_asserted=false` sí se conservan para mantener la trazabilidad de la
decisión sin publicar su razón o provenance.
Para el flujo basado en fixtures también se puede usar
`lucida.replay.public_replay_fixture(...)`; reutiliza exactamente el mismo
motor y sólo cambia la proyección de salida.
Los consumidores pueden pasar la vista recibida por
`validate_public_report(...)` antes de procesarla; rechaza campos no
allowlisted, payloads, timestamps o garantías de seguridad alteradas.

## Limites

- `SignalEnvelope` es un contrato de entrada, no un receptor de red.
- `OscEnvelope` se reutiliza sólo para validar los campos OSC; no se abre ningún
  socket.
- Los resultados son observaciones registradas por un host u operador; no
  representan ejecución automática.
- La conexión real con Resolume, cues, clips, GPU, DMX o hardware sigue fuera
  de este módulo.

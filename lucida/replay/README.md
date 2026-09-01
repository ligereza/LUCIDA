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

## Limites

- `SignalEnvelope` es un contrato de entrada, no un receptor de red.
- `OscEnvelope` se reutiliza sólo para validar los campos OSC; no se abre ningún
  socket.
- Los resultados son observaciones registradas por un host u operador; no
  representan ejecución automática.
- La conexión real con Resolume, cues, clips, GPU, DMX o hardware sigue fuera
  de este módulo.

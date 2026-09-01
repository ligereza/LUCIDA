# VJ Adapter

Adaptador de dominio para conectar una sesión VJ con el núcleo reusable de
VJ. En esta primera extracción el adaptador es una máquina de estados pura:
recibe eventos y estado, genera propuestas auditables y registra resultados.

No ejecuta comandos, no abre puertos, no llama a Resolume, no controla
procesadores LED y no modifica un show.

## Uso mínimo

```python
from adapters.vj import VJAdapter

adapter = VJAdapter()
state = adapter.initial_state("session-001")
state, proposals = adapter.process(
    {
        "event_id": "evt-001",
        "timestamp": "2026-01-10T20:00:00Z",
        "phase": "preflight",
        "event_type": "phase.completed",
        "payload": {"status": "pass"},
    },
    state,
)
state = adapter.register_result(
    state,
    {
        "result_id": "res-001",
        "proposal_id": proposals[0].proposal_id,
        "recorded_at": "2026-01-10T20:01:00Z",
        "status": "observed",
        "notes": "Checkpoint revisado por el operador.",
    },
)
```

## Replay

```python
from adapters.vj.replay import replay_path

report = replay_path("adapters/vj/replay/fixtures/session-fictional.json")
assert report["status"] == "PASS"
```

El replay no usa la hora actual ni dependencias externas: con el mismo fixture
produce el mismo resultado. Las propuestas siempre contienen
`requires_explicit_approval=true`, `reversible=true` y
`execution_mode=proposal_only`.

## Extensión

Los adaptadores concretos de medios, cues, DXV, Art-Net/DMX/sACN, LED
processors y mapping deben traducir sus observaciones a `VJEvent` y sus
resultados a `VJResult`. No deben saltarse la máquina de estados ni ejecutar
acciones dentro de `VJAdapter`.

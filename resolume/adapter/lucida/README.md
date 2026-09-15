# LUCIDA

LUCIDA es la capa integradora de RESOLUME_ADAPTER/VJ: una única superficie estructurada
que coordina tres capacidades internas —`INSTAR`, `NAYADE` e `IMAGO`— sin
convertirlas en tres interfaces separadas.

La primera entrega es deliberadamente offline y proposal-only. Consume los
contratos comunes de `adapters.vj` (`VJEvent`, `VJState`, `VJProposal` y
`VJResult`), produce reportes de observación y permite registrar resultados,
pero no abre Resolume, no accede a hardware y no ejecuta acciones.

## Flujo

```text
VJEvent + VJState
       |
       v
LUCIDA Orchestrator
       |
       +--> INSTAR  - preflight de medios y mapping
       +--> NAYADE  - soundcheck de señal y procesador
       +--> IMAGO   - show, incidente y recuperación
       |
       v
Single read-only overlay
       |
       +--> observaciones
       +--> estado por capacidad
       +--> propuestas explícitas
       +--> resultados esperados
       +--> desconocidos
```

## Uso mínimo

```python
from lucida import LucidaOrchestrator

orchestrator = LucidaOrchestrator()
state = orchestrator.initial_state("fictional-session")
state = orchestrator.propose(
    {
        "event_id": "evt-001",
        "timestamp": "2026-01-10T20:00:00Z",
        "phase": "preflight",
        "event_type": "phase.completed",
        "payload": {"status": "pass"},
    },
    state,
)
overlay = orchestrator.read_overlay(state)
```

`read_overlay` es una superficie de datos, no una ventana. Una futura UI puede
renderizarla dentro del host que corresponda, pero LUCIDA no asume un toolkit
gráfico ni una integración no autorizada.

`read_overlay_view` ofrece una proyección compacta y acotada para esa futura
superficie. Incluye estado, capacidades, propuestas pendientes y desconocidos,
pero omite payloads de eventos, metadata arbitraria, rutas y credenciales. Su
modo es siempre `read_only` y `proposal_only`.

The bounded view uses deterministic ordering, explicit list limits, and always
returns one `next_attention` item. When no proposal or unknown is available,
the item points to the current phase without requesting an action.

`diff_overlay_view(previous_view, current_view)` accepts only complete
`LucidaOverlayView` dictionaries. It compares seven safe fields in fixed order
and returns at most seven JSON-safe change records. It ignores identity and
phase-only changes, and rejects payloads, metadata, filesystem paths,
credentials, and action fields.

`LucidaOrchestrator.diff_overlay_view(previous_state, current_state)` accepts
`LucidaState` objects or state mappings, projects both through
`read_overlay_view`, and delegates the comparison to the bounded diff
implementation. Invalid state mappings are rejected by the existing state
contracts. Internal payloads and metadata are never emitted in the result.

The machine-readable contracts are
[`overlay-view.schema.json`](overlay/contracts/overlay-view.schema.json) and
[`overlay-diff.schema.json`](overlay/contracts/overlay-diff.schema.json). They
allow a future host or transparent overlay to validate the safe shape without
importing LUCIDA internals.

The serialized integration state has its own registered contracts:
[`lucida-state.schema.json`](../schemas/lucida-state.schema.json) and
[`lucida-capability-report.schema.json`](../schemas/lucida-capability-report.schema.json).
Replay records reference the complete `LucidaState` contract instead of relying
on a partial inline description.

La restauración runtime exige esos mismos campos, versión y tipo de contrato:
un snapshot parcial o con campos extra se rechaza antes de entrar al
orquestador.

`LucidaOrchestrator.read_overlay_cursor(state)` exposes only the session
sequence, last event timestamp, last event id, and checkpoint id needed by an
incremental consumer to identify the state revision. It excludes metadata and
keeps the same proposal-only safety flags. Its machine-readable contract is
[`overlay-cursor.schema.json`](overlay/contracts/overlay-cursor.schema.json).

`OverlayConsumer` is the host-neutral state machine for an incremental reader.
It accepts one initial snapshot, applies only deltas whose `before` values
match the current bounded view, rejects stale cursors and sequence gaps, and
requires `recovery=True` for a replacement snapshot. `checkpoint()` and
`restore_checkpoint()` provide explicit recoverability without executing
actions. Its checkpoint contract is
[`overlay-consumer-checkpoint.schema.json`](overlay/contracts/overlay-consumer-checkpoint.schema.json).
Ready checkpoints include a SHA-256 digest of the projected view and reject
altered or mixed view data before restoration.

`build_overlay_update(previous_state, current_state)` packages the complete
projected view, its SHA-256 view digest, bounded changes, and the matching
revision cursor in one atomic `LucidaOverlayUpdate` envelope. The builder
rejects truncated diffs and the digest prevents mixing a view from another
revision.
`OverlayConsumer.apply_update(update)` reconstructs the candidate view before
mutating local state, so a mismatched view, diff, cursor, or safety envelope
fails without a partial update. Its contract is
[`overlay-update.schema.json`](overlay/contracts/overlay-update.schema.json).

`replay_overlay_json(source)` and `replay_overlay_path(path)` consume the
strict `LucidaOverlayReplay` envelope, apply snapshots, deltas, and atomic
updates through
`OverlayConsumer`, and return a deterministic `LucidaOverlayReplayReport`.
`validate_overlay_replay(envelope)` performs the same structural and contract
checks without applying records, so a host can preflight an envelope first.
The replay is local and read-only; malformed records, unsafe deltas, stale
cursors, and sequence gaps fail explicitly. The fictional fixture is
[`overlay-session-fictional.json`](overlay/fixtures/overlay-session-fictional.json)
and its input contract is
[`overlay-replay.schema.json`](overlay/contracts/overlay-replay.schema.json).
The deterministic output contract is
[`overlay-replay-report.schema.json`](overlay/contracts/overlay-replay-report.schema.json).
The atomic update path is exercised by
[`overlay-atomic-update-fictional.json`](overlay/fixtures/overlay-atomic-update-fictional.json).
`OverlayReplayRecorder` creates the same strict envelope from successive
`LucidaState` values: it starts with a snapshot, records atomic updates, and
requires an explicit `recovery=True` for replacement snapshots. Its output can
be passed directly to `replay_overlay_json` for an offline roundtrip check.

## Replay y dry-run

```python
from lucida.replay import replay_path

report = replay_path("lucida/replay/fixtures/session-fictional.json")
assert report["status"] == "PASS"
```

El replay usa sólo el fixture ficticio, reloj incluido en los eventos y la
lógica pura del adaptador. Repetirlo con el mismo fixture produce el mismo
reporte.

## Límites y dependencias

- Dependencia de runtime: biblioteca estándar de Python y `adapters.vj`.
- `pytest` se usa únicamente para la suite de tests.
- No hay subprocess, red, GPU, Resolume, FFGL, DXV, DMX, Art-Net, sACN ni
  control de procesadores LED.
- Las propuestas requieren que un operador o un host autorizado decida qué
  hacer y registre el resultado; no existe un método de ejecución automática.
- Los detalles de medios, cues, mapping, GPU, protocolos y hardware siguen
  siendo implementaciones exclusivas o pendientes de RESOLUME_ADAPTER.

La convención de ASCII técnico y la verificación offline están documentadas en
[`CONTRIBUTING.md`](CONTRIBUTING.md).

La frontera opcional de señales OSC/Resolume está documentada en
[`signals/README.md`](signals/README.md); recibe envelopes inyectados y no abre
sockets por sí misma.

## Estado actual de XIO

LUCIDA ya dispone de un consumidor offline para el `ApplicationEvent` de XIO.
El bridge convierte cada evento a `VJEvent` y `SignalEnvelope`, lo registra en
`SessionReplay` y devuelve un resultado serializable con el overlay atómico.
`validate_xio_consume_result()` permite prevalidar ese resultado antes de que
un host lo acepte. El transporte real, la conexión con XIO y cualquier efecto
externo siguen fuera de esta rama y requieren un adaptador autorizado.

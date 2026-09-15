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

La restauración de propuestas también respeta el schema publicado: exige los
campos obligatorios y rechaza propiedades extra antes de registrar una
propuesta.

## Show input projection

`ShowInputProjector` consumes a canonical `VJEvent` and returns only the
metadata a future LUCIDA reducer needs: `show_state`, `show_phase`, an optional
`preview_candidate`, source timestamp, sequence, and bounded provenance.
Existing `OscResolumeBoundary.normalize()` can provide the event; `artnet`,
`sacn`, and `timecode` are accepted as transport labels without opening a
socket or implementing a protocol parser here.
`project_osc_show_input()` is the convenience path that calls the existing OSC
normalizer and then applies the same bounded projection.

The projector rejects stale sequence or timestamp input and never mutates a
`VJState`, creates a host action, or executes a `VJProposal`. Its replay helper
uses the existing fixture loader and remains deterministic and side-effect free.
The machine-readable contract is
[`show-input.schema.json`](contracts/show-input.schema.json).
`validate_show_input()` provides the matching public validator for a future
reducer or replay consumer.
The kill test patches socket and subprocess entry points and confirms that
projection does not open transport or spawn a process.

## Semantic light field input

`VJAdapter.ingest_semantic_light_field()` is the concrete RESOLUME_ADAPTER/VJ boundary
for an XIO semantic light field. It accepts the existing `VJProposal` contract
plus a tape resolver keyed by the proposal `tape_sha256` evidence. The proposal
contains metadata only; the replay tape remains a separate resolved input.
The bridge validates the tape schema, digest, frame count, calibration status,
and `proposal_only` markers before returning a reversible
`ResolumeAdapterVJSemanticLightFieldPending` state envelope.

The application-facing intake is the existing `VJAdapter` instance. Call
`ingest_semantic_light_field()` to stage the proposal, then call exactly one
explicit decision operation: `approve_proposal()`, `reject_proposal()`, or
`undo_proposal()`. These operations reuse `register_result()` and record
`accepted`, `rejected`, or `skipped` respectively; they never execute the
proposal. A semantic light-field result with status `executed` is rejected.

The bridge is offline and proposal-only. It does not open a transport, call
Resolume, access a GPU or camera, or execute hardware actions. The end-to-end
fixture test reads the existing XIO replay fixture and proves the path
`replay JSON -> semantic proposal -> VJProposal -> VJAdapter -> pending state`.
The dispatcher does not connect to Resolume or a live VJ surface; it calls the
adapter at its proposal intake boundary without changing the VJ state machine
or copying frames into `VJProposal`.

The current application dispatcher is `tools/resolume_adapter_cli.py` and its existing
`vj-replay` command. It selects this bridge when the replay envelope has
`replay_type=ResolumeAdapterSemanticLightFieldReplay`; no second command or application
entrypoint is introduced. The dispatcher reports the pending state and leaves
all decisions to the explicit adapter operations above.

## INSTAR report bridge

`build_instar_event()` converts one INSTAR report into a canonical preflight
event that can be consumed by `VJAdapter`. It keeps only bounded technical
summaries: asset identifiers, status, codec, dimensions, FPS, alpha, loop
status, and cue count. Local roots, filenames, error text, and arbitrary report
fields are not copied into the event.
`project_instar_show_input()` sends the same event through the existing bounded
show-input projection. The caller supplies the event sequence; a report cannot
silently invent ordering. This bridge is read-only and does not invoke INSTAR,
FFmpeg, Resolume, or any transport.

## NAYADE soundcheck bridge

`build_nayade_event()` converts a NAYADE session into a `preparation` event.
It keeps counts and bounded summaries for slices, input groups, planned steps,
operator results, readiness, signal facts, and the passive processor observation. A
processor observation must explicitly declare `read_only=true` and
`commands_sent=false`; USB, serial, Ethernet, HDMI, and manual are recorded as
facts only. Private source fields, notes, evidence text, and arbitrary payloads
are not copied.
`project_nayade_show_input()` reuses the same projection and requires the
caller-provided sequence. It never opens a port or changes a soundcheck,
processor, mapping, or show.

## IMAGO show bridge

`build_imago_event()` converts an IMAGO session snapshot into an event whose
phase follows the observed session status: preparation, show, incident,
recovery, or closure. It preserves only bounded counts and summaries for
checkpoints, incidents, proposals, results, profile identifiers, and event
types, including `guard_window_requested`. Event payloads, notes, reasons, and unknown text are intentionally not
copied.
Every proposal must still declare explicit approval, reversibility, and
`proposal_only`; otherwise the bridge rejects the snapshot. The bridge records
state for replay and downstream review, but never executes a cue, Resolume
operation, recovery action, DMX message, or processor command.

## Plugin bridge replay

`replay_plugin_bridge_path()` replays a fictional cross-plugin sequence through
the shared state machine: INSTAR preflight, NAYADE soundcheck, and IMAGO show,
incident, recovery, and closure. It requires strictly increasing producer
sequences, rejects duplicate event identifiers, and reports no external side
effects. The fixture is synthetic and contains no media or machine paths.

For real JSON reports, `vj-project` in `tools/resolume_adapter_cli.py` exposes the same
bridges without requiring Python imports. Use `--mode event` to emit the
canonical event or `--mode projection` to emit the bounded show-input view;
`--previous` enables phase-order validation.

For a complete session assembled from real report files, use
`vj-project-replay` with a manifest containing `stage`, `event_id`, `sequence`,
`input`, and the optional `processor_observation` path for NAYADE. Relative
paths are resolved from the manifest directory and never appear in the output.

## Extensión

Los adaptadores concretos de medios, cues, DXV, Art-Net/DMX/sACN, LED
processors y mapping deben traducir sus observaciones a `VJEvent` y sus
resultados a `VJResult`. No deben saltarse la máquina de estados ni ejecutar
acciones dentro de `VJAdapter`.

# LUCIDA Resolume surface

This branch contains the portable VJ integration extracted from MOSAIK. The
source package remains in `lucida/`; the integration is proposal-only and does
not open Resolume, sockets or external processes during replay.

Included capabilities:

- injected OSC boundary with source, route, sequence and replay metadata;
- normalization of INSTAR, NAYADE and IMAGO proposals;
- session replay with duplicate, out-of-order and sequence-gap detection;
- deterministic fictional fixtures and offline tests.

Source provenance:

- source repository: MOSAIK (`C:\IA\VJ`);
- source branch: `LUCIDA`;
- source commits: `e43422d`, `7daa9fb`, `206b844`, `f4e9f21`, `9b3c2b3`, `6ff293d`, `1ee6d1b`;
- copied files exclude media, presets, models, caches and private runtime data.

Run from this repository root:

```text
python -m pytest -q
```

Run the deterministic semantic light-field smoke evidence:

```text
python -m lucida.signals.smoke
```

The default command uses the recorded `signal-envelope-v1` path. The legacy
raw OSC path remains available for comparison:

```text
python -m lucida.signals.smoke --raw
```

Expected output:

```text
LUCIDA_RESOLUME_OFFLINE_SMOKE
input_contract=SignalEnvelopeV1
session_replay_status=REVIEW
session_signal_count=2
runtime_dispatcher=lucida.signals.replay.replay_fixture
overlay_surface=LUCIDA
preview_surface=RESOLUME
replay_status=REVIEW
proposal_id=proposal-cli-light-field-001
overlay_status=pending_approval
execution_mode=proposal_only
reversible=true
requires_explicit_approval=true
tape_schema=farmaxia:semantic-light-field-tape:0.1
tape_sha256=f69e170a3447924a7e30126572c659bf61a353d6628ae9e4cd1359aa035bbaec
frame_count=1
frames_copied=false
automatic_actions=false
resolume_opened=false
external_side_effects=false
```

The smoke entry point validates the existing recorded signal-envelope-v1
fixture, feeds its normalized signals into the existing replay dispatcher with
the MOSAIK semantic report fixture, and reads the existing RESOLUME overlay
contract. The `REVIEW` status is expected because the proposal remains pending
approval. Repeating the command with the same fixtures produces the same
evidence.

The default envelope-backed path first validates the fictional
`signal-envelope-v1` fixture through `SessionReplay`, then feeds the normalized
signals into the existing RESOLUME runtime dispatcher. Its proposal and
overlay invariants must match the preserved raw path.

This is suitable evidence for live-show postulation: it demonstrates the
replay-to-overlay contract, deterministic proposal metadata, explicit approval
requirement, reversibility, tape identity, and no-effect safety boundary. It is
not hardware validation and does not claim Resolume execution, network
transport, GPU behavior, camera input, timing, or fixture calibration.

Inspect the pending overlay directly as compact JSON:

```text
python -m lucida.signals.smoke --preview
```

The output contains the LUCIDA and RESOLUME surface names, pending proposal
reason and evidence, tape schema and hash, reversibility, explicit approval,
and no-side-effect status. This is an offline preview only; live Resolume was
not tested.

The committed machine-readable artifact is
[`resolume/evidence-manifest.json`](evidence-manifest.json). Reproduce the
artifact in one command from the repository root:

```text
python -m lucida.signals.smoke --manifest
```

The command prints stable JSON containing the fixture hashes, tape hash,
`runtime_integration_base_commit`, reproducible test commands, proposal-only
guarantees, and the exact live-system limitation. This field identifies the
commit that introduced the offline RESOLUME smoke integration; it is not the
source commit of later evidence artifacts. The manifest regression compares this
generated JSON with the committed artifact and compares its evidence section
with the current smoke result.

## Recorded signal-envelope-v1 boundary

The reusable offline boundary is
`lucida.replay.session.adapt_signal_envelope_v1()`. It normalizes recorded
`osc` and `timecode` envelopes into the existing `SignalEnvelope` contract;
`replay_signal_envelope_v1_fixture()` then reuses `SessionReplay` and the
existing proposal-only runtime. Unknown optional fields are ignored, while
schema, identity, timestamp, sequence, address, argument, and transport
errors fail closed. The recorded schema is
`lucida/replay/contracts/signal-envelope-v1.schema.json`.

This is a recorded integration boundary only. It is not live XIO support,
does not import or activate an XIO transport, and does not open Resolume or
any external device.

The test suite validates the adapter, the XIO application-event consumer and
the explicit host-result boundary, including receipt deserialization, offline.
A live Resolume host connection remains an explicit integration step for a
future host adapter.

## Semantic light-field consumer

The concrete RESOLUME surface entrypoint is
`lucida.signals.boundary.OscResolumeBoundary`. Its
`ingest_semantic_light_field_report()` method consumes the existing MOSAIK
`MosaikSemanticLightFieldReplayReport`, validates the existing `VJProposal`
contract and the tape SHA-256/schema evidence, and projects a bounded
`resolume_preview` with `pending_approval` status.

The projection keeps `proposal_only=true`, `reversible=true`, and
`resolume_opened=false`. It carries tape schema, hash, frame count, and
calibration status only; tape frames stay in the upstream replay report and
are never copied into `VJProposal` or the LUCIDA surface state. Approval still
uses the existing explicit result boundary. No XIO/MOSAIK rendering engine,
ledger, replay engine, socket, GPU, camera, or hardware implementation is
duplicated here.

The existing runtime entrypoint is
`lucida.signals.replay.replay_path()` (or its in-memory
`replay_fixture()` variant). A replay JSON may provide `semantic_reports`; the
dispatcher sends each report to the existing
`OscResolumeBoundary.ingest_semantic_light_field_report()` surface method.
The resulting `resolume_preview` remains pending approval in the replay state.
This wiring does not create a second runtime, router, ledger, or replay engine.
The same bounded preview is reconstructed by `OscResolumeBoundary.read_overlay()`
from the persisted pending state, so a consumer can refresh the existing
overlay without retaining tape frames. After an explicit approval, rejection,
or undo, the pending preview is removed from that overlay.

## Shared surface-projection-v1 contract

The portable projection is `lucida.surface_projection.SurfaceProjectionV1`,
defined by `lucida/contracts/surface-projection-v1.schema.json`. It carries only
the common fields needed by a proposal-only surface: `host_id`, `surface_id`,
pending status, proposal identity, reason, evidence, explicit approval,
reversibility, execution mode, and no-side-effect guarantees. The current
RESOLUME adapter emits this object as `resolume_preview.projection` and keeps
RESOLUME-specific tape metadata beside it; tape frames are not part of the
shared projection.

ADOBE, PUPILA, and VIZZ can consume the serialized `projection` object by
validating the shared schema or calling `SurfaceProjectionV1.from_dict()`.
Their adapters should map `surface_id` to their own surface and preserve the
proposal-only and explicit-approval guarantees. They do not need to import
`lucida.signals.semantic_light_field`, RESOLUME code, or any replay engine.
Unknown optional fields are ignored, while malformed required fields fail
closed. This is a reusable offline contract, not live support for any of those
hosts.

Run the two-consumer conformance check from the repository root:

```text
python -m lucida.surface_conformance
```

The command validates the RESOLUME projection emitted by this candidate and a
fictional consumer projection using only `SurfaceProjectionV1` fields. It
reports host/surface identity, proposal status, approval, reversibility, and
side-effect guarantees. RESOLUME tape metadata remains outside the projection
object. The conformance check is offline schema compatibility evidence only;
it does not connect ADOBE, PUPILA, VIZZ, RESOLUME, hardware, or any live host.

## Offline postulation evidence bundle

Build the deterministic JSON evidence bundle from the repository root:

```text
python -m lucida.evidence_bundle --json
```

For a concise human-readable view of the same bundle:

```text
python -m lucida.evidence_bundle --report
```

The bundle records `artifact_source_commit` as the exact local HEAD used to
generate it. Its embedded manifest carries
`runtime_integration_base_commit`, the historical commit that introduced the
offline RESOLUME smoke integration. These are deliberately different roles;
the bundle rejects the old ambiguous `integration_commit` label. It also
records the projection schema hash, fixture and tape hashes,
smoke/preview/conformance output, and test counts collected from the actual
pytest runtime. It separates implemented code,
recorded replay evidence, proposed live light/audio behavior, and untested
hardware or venue assumptions. The live behavior section is postulation only;
the artifact does not claim live Resolume, audio, venue, timing, calibration,
or hardware validation.

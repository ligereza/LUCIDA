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

# LUCIDA Resolume surface

This branch contains the portable VJ integration for LUCIDA/RESOLUME. The
source package remains in `lucida/`; the integration is proposal-only and does
not open Resolume, sockets or external processes during replay.

Included capabilities:

- injected OSC boundary with source, route, sequence and replay metadata;
- normalization of INSTAR, NAYADE and IMAGO proposals;
- session replay with duplicate, out-of-order and sequence-gap detection;
- deterministic fictional fixtures and offline tests.

Source provenance:

- canonical repository: `ligereza/X-ANA-X`, branch `LUCIDA`;
- canonical adapter path: `LUCIDA/resolume/adapter/`;
- integrated source snapshot: `44b456d`;
- standalone mirror path: `resolume/adapter/`;
- private media, presets, caches and runtime data are not part of this mirror.

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
the semantic report fixture, and reads the existing RESOLUME overlay
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
`ingest_semantic_light_field_report()` method consumes the existing semantic
`ResolumeAdapterSemanticLightFieldReplayReport`, validates the existing `VJProposal`
contract and the tape SHA-256/schema evidence, and projects a bounded
`resolume_preview` with `pending_approval` status.

The projection keeps `proposal_only=true`, `reversible=true`, and
`resolume_opened=false`. It carries tape schema, hash, frame count, and
calibration status only; tape frames stay in the upstream replay report and
are never copied into `VJProposal` or the LUCIDA surface state. Approval still
uses the existing explicit result boundary. No rendering engine,
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

ADOBE, PUPILA, and VISUAL can consume the serialized `projection` object by
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
it does not connect ADOBE, PUPILA, VISUAL, RESOLUME, hardware, or any live host.

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
or hardware validation. Evidence file hashes canonicalize CRLF to LF so the
same Git blob produces the same manifest in Windows worktrees.

## Native INSTAR Capture source

The native Resolume unit is `resolume/plugin/INSTAR/INSTAR.cpp`. `INSTAR.dll`
is an `FF_SOURCE` inspired by FLUJO's venue viewer. Its primary
`XML_PLANES` mode reads the `InputRect` planes of an Advanced Output XML and
uses them as the authoritative front-view arrangement. It creates exactly one
preview plane per XML `Slice`; it does not infer a main screen, banners,
totems, stage dimensions or other venue objects from slice count or size.
`Depth` applies one Z value to every slice, while the optional `SliceDepths`
text field accepts comma-separated values in XML slice order, for example
`0,0.2,-0.1`. Missing entries use `Depth` and extra entries are ignored.
This keeps the control tied to the actual XML instead of exposing a fixed
number of fictional slices. `MapFile` can texture those planes with an image
from the same composition, while `TemplateXML` remains the real routing
template and `OutputRect` is never used to invent the front-view composition.

The XML preview contains only mapping geometry. A venue shell or a tarima
model must come from an explicit `VenueFile`/model source; FLUJO's tarima
sliders are not silently copied into an unrelated Advanced Output XML.
`CameraDistance` complements the existing `AEREO`, `PISTA` and `LIBRE` camera
controls.

The same source retains `VENUE_3D` for confidence-coloured venue JSON and
`RASTER_PIXEL_MAP` for a flat PNG/JPG inspection with detected surface
outlines. The camera and scene core are local and do not need a network, model
service or LED processor. `EdgeBudget` keeps the highest-confidence polylines
first and reports omitted edges rather than trimming a line silently;
`ConfidenceCeiling` can exclude unverified tiers explicitly. `ExportMapXML`
remains a separate explicit action from the preview.

INSTAR also exposes an explicit `ExportMapXML` event. The VJ supplies a raster
pixel map through `MapFile` (PNG/JPG) and a real Resolume Advanced Output file
through `TemplateXML`. INSTAR preserves that template's composition size,
screen, output device, device identity and slice parameter structure, replacing
only the existing slices' `InputRect` values with the detected raster
surfaces. The detected surface count must match the template slice count;
otherwise the export is rejected instead of inventing physical routing. This path is
separate from the 3D model viewer: an OBJ is never converted to XML by default.
After a successful export, `OutputXML` becomes the active XML preview source
automatically; the original `TemplateXML` remains the export source and can be
restored by selecting it again. INSTAR rejects an output path that would
overwrite the template.
PDF and SVG inputs remain with the offline adapter, which can rasterize or
vector-map them before an explicit export.

Build from this repository with the official FFGL checkout available at
`C:/IA/vendor/resolume-ffgl`:

```text
cmake -S resolume/plugin -B work/resolume-plugin-build -DFFGL_ROOT=C:/IA/vendor/resolume-ffgl
cmake --build work/resolume-plugin-build --config Release
```

The resulting DLLs are copied to
`work/resolume-plugin-build/Extra Effects/`. Add that folder in
Resolume Preferences → Video → FFGL Directories and restart Resolume. The
native build and contracts are verified locally; live host loading still
requires the final installation step on a machine with Resolume.

## Native INSTAR 3D source

`resolume/plugin/INSTAR/INSTAR_3D.cpp` builds `INSTAR_3D.dll` as an independent
`FF_SOURCE`. It loads Wavefront OBJ geometry into the composition and renders
a filled mesh plus wireframe over a transparent background. `TextureFile` can
load a PNG/JPG texture; OBJ UV coordinates are respected and planar UVs are
generated when the model does not provide them. It is for arbitrary 3D models;
it does not create Advanced Output XML.

OBJ `mtllib`/`usemtl` records are read for diffuse material colours; when no
material is available, deterministic fallback colours keep the scene legible.

Both sources share the scene renderer and camera selector. INSTAR's venue
geometry and the model viewer remain distinct data paths: venue polylines are
for Capture-like spatial context, while OBJ geometry is for importing a model
as visual content. Unnamed OBJ geometry remains visible but has no mapping
meaning.

Both DLLs are produced by the same build:

```text
work/resolume-plugin-build/Extra Effects/INSTAR.dll
work/resolume-plugin-build/Extra Effects/INSTAR_3D.dll
```

# ADR-013: Host-neutral VJ show input projection

**Status:** Accepted
**Date:** 2026-09-02
**Scope:** `adapters.vj.show_input`

## Context

The future LUCIDA reducer needs a small input surface during a show. Existing
RESOLUME_ADAPTER contracts already normalize VJ phases, OSC events, proposals, overlay
views, and replay fixtures, but exposing a complete event payload would leak
transport details and Resolume-specific data into the reducer.

## Decision

Add `ShowInputProjector` as a pure RESOLUME_ADAPTER adapter boundary. It consumes a
canonical `VJEvent` and emits `ResolumeAdapterShowInput` with only `show_state`,
`show_phase`, `preview_candidate`, `source_timestamp`, `sequence`, and bounded
provenance. It accepts the existing transport labels `osc`, `artnet`, `sacn`,
`timecode`, `xio`, and `unknown`; protocol parsing remains outside this task.

The projector rejects non-monotonic sequence or source timestamp input,
reuses the shared VJ phase transition contract, canonicalizes provenance, and
performs no state mutation, network I/O, host
action, proposal execution, overlay rendering, or generic reducer work.
`adapters.vj.replay.show_input` reuses the existing fixture loader for a
deterministic synthetic replay. `validate_show_input()` validates a received
projection without constructing or running the generic reducer.
`project_osc_show_input()` composes the existing OSC normalizer with the same
projection and wraps invalid OSC boundary input without opening transport.

## Options considered

### Option A: expose the complete VJ event

This preserves all source data but couples the reducer to transport and
Resolume payloads and makes accidental leakage likely.

### Option B: add a new transport-specific parser

This could decode Art-Net or timecode immediately, but duplicates boundary
logic and expands the task into network and hardware integration.

### Option C: bounded projection from canonical VJEvent

This reuses existing contracts, keeps source semantics in RESOLUME_ADAPTER, and leaves
transport adapters replaceable. It is the selected option.

## Consequences

- LUCIDA receives deterministic metadata with explicit provenance and order.
- Preview candidates are stable identifiers, not file paths or raw payloads.
- Art-Net, sACN, and timecode are represented but not parsed or transported.
- A future reducer can consume the projection without importing Resolume logic.

## Verification

`tests/vj/test_show_input.py` covers OSC normalization, phase/order replay,
stale sequence and timestamp input, provenance conflicts, invalid input, and
schema validation. Its kill test patches socket and subprocess entry points to
guard the no-side-effect boundary. The fixture is
`adapters/vj/replay/fixtures/show-input-fictional.json`.

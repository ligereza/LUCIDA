# LUCIDA Python engine

This package is the host-neutral reducer for the LUCIDA surface. It accepts
bounded events and emits a read-only `RenderPlan`.

It does not open a camera, network connection, window, Resolume instance or
Adobe process. It does not execute proposals. Domain repositories provide
events through adapters; the engine owns only reduction, priority, expiry and
render output.

Adapters are registered explicitly by an ASCII `adapter_id`. The engine never
auto-detects a source from payload shape: an unknown or mismatched adapter is a
hard error. This keeps XIO, MOSAIK, VIZZ and PUPILA replaceable and prevents a
payload from silently entering the wrong domain boundary.

The first slice is intentionally small:

```text
XIO event or MOSAIK state
        -> EngineEvent
        -> LucidaEngine
        -> RenderPlan
        -> LucidaOverlayFrame
        -> future LUCIDA surface
```

The executable integration path is explicit:

```text
adapter_id + contract_id
        -> bounded EngineEvent
        -> LucidaPipeline
        -> LucidaEngine
        -> RenderPlan
```

Contract validation happens before reduction. The transition records both
selected ids, so replay and audit can prove how a domain event entered the
engine. No adapter or contract is inferred from payload shape.

All technical identifiers, fixture keys and parseable values use English
ASCII. The summary is scalar and bounded so raw payloads cannot pass through
this boundary accidentally.

`OverlayFrameConsumer` is the host-neutral delivery boundary after reduction.
It validates snapshots, checks revision continuity, accepts exact duplicates
idempotently and rejects stale, skipped or conflicting frames. It does not open
a transparent window or execute a host action.

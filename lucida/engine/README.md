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
        -> future LUCIDA surface
```

All technical identifiers, fixture keys and parseable values use English
ASCII. The summary is scalar and bounded so raw payloads cannot pass through
this boundary accidentally.

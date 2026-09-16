# LUCIDA integration boundary

The integration order is explicit:

```text
domain payload -> domain adapter -> InputContract -> EngineEvent -> reducer
```

An adapter performs translation. An `InputContract` declares the source,
version, event vocabulary and capabilities. The registry requires the caller
to select both ids explicitly. LUCIDA never guesses a domain from payload
shape.

The current engine includes strict metadata-only adapters for RESOLUME, VISUAL
and PUPILA.
They translate already-redacted domain states into `EngineEvent` values; they do
not capture sensors, infer attention, open a window or execute host actions.
XIO and RESOLUME remain contract slots owned by their repositories:

| Domain | Source role | Candidate event families | Current owner |
| --- | --- | --- | --- |
| XIO | transport and signal observation | `signal.observed`, `peer.updated`, `timecode.observed` | XIO adapter |
| RESOLUME | show-state projection | `show.state`, `show.phase`, `preview.candidate` | `resolume.state` |
| VISUAL | bounded perception state | `focus.state`, `geometry.state`, `perception.quality` | `visual.metadata` |
| PUPILA | coordination proposals | `coordination.state`, `coordination.proposal` | `pupila.coordination` |

The RESOLUME, VISUAL and PUPILA route ids are explicit: `resolume.state` with
`resolume.show.v1`, `visual.metadata` with
`visual.perception.v1`, and `pupila.coordination` with
`pupila.coordination.v1`. Unknown keys, raw fields, executable proposal fields
and undeclared event types are rejected before reduction. No raw video,
documents, credentials or host actions cross this boundary. A future domain
adapter must pass its own tests and the LUCIDA engine suite before integration.

The engine output is a `RenderPlan`. `build_overlay_frame` projects it into a
`LucidaOverlayFrame` with `transparent=true`, `click_through=true`,
`blocking=false` and no automatic or external side effects. This is distinct
from the richer `LucidaOverlayView` state protocol owned by the VJ branch; the
engine does not flatten that state protocol or silently discard its cursor and
diff semantics. `OverlayFrameConsumer` then provides an atomic, revisioned
delivery boundary for the generic frame without opening a host surface.

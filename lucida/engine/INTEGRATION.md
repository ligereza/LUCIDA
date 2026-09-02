# LUCIDA integration boundary

The integration order is explicit:

```text
domain payload -> domain adapter -> InputContract -> EngineEvent -> reducer
```

An adapter performs translation. An `InputContract` declares the source,
version, event vocabulary and capabilities. The registry requires the caller
to select both ids explicitly. LUCIDA never guesses a domain from payload
shape.

The current engine includes strict metadata-only adapters for VIZZ and PUPILA.
They translate already-redacted domain states into `EngineEvent` values; they do
not capture sensors, infer attention, open a window or execute host actions.
XIO and MOSAIK remain contract slots owned by their repositories:

| Domain | Source role | Candidate event families | Current owner |
| --- | --- | --- | --- |
| XIO | transport and signal observation | `signal.observed`, `peer.updated`, `timecode.observed` | XIO adapter |
| MOSAIK | show-state projection | `show.state`, `show.phase`, `preview.candidate` | MOSAIK adapter |
| VIZZ | bounded perception state | `focus.state`, `geometry.state`, `perception.quality` | `vizz.metadata` |
| PUPILA | coordination proposals | `coordination.state`, `coordination.proposal` | `pupila.coordination` |

The VIZZ and PUPILA route ids are explicit: `vizz.metadata` with
`vizz.perception.v1`, and `pupila.coordination` with
`pupila.coordination.v1`. Unknown keys, raw fields, executable proposal fields
and undeclared event types are rejected before reduction. No raw video,
documents, credentials or host actions cross this boundary. A future domain
adapter must pass its own tests and the LUCIDA engine suite before integration.

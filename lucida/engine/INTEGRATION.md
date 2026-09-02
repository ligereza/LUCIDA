# LUCIDA integration boundary

The integration order is explicit:

```text
domain payload -> domain adapter -> InputContract -> EngineEvent -> reducer
```

An adapter performs translation. An `InputContract` declares the source,
version, event vocabulary and capabilities. The registry requires the caller
to select both ids explicitly. LUCIDA never guesses a domain from payload
shape.

The current engine implements the generic boundary only. The following are
future contract slots, not implemented domain behavior:

| Domain | Source role | Candidate event families | Current owner |
| --- | --- | --- | --- |
| XIO | transport and signal observation | `signal.observed`, `peer.updated`, `timecode.observed` | XIO adapter |
| MOSAIK | show-state projection | `show.state`, `show.phase`, `preview.candidate` | MOSAIK adapter |
| VIZZ | bounded perception state | `focus.state`, `geometry.state`, `perception.quality` | VIZZ adapter |
| PUPILA | learning and analogy proposals | `learning.context`, `analogy.proposal`, `workflow.pause` | PUPILA adapter |

These names remain provisional until the owning repository publishes a
versioned contract and replay fixture. No raw video, documents, credentials or
host actions cross this boundary. A future domain adapter must pass its own
tests and the LUCIDA engine suite before integration.

# Predictive lighting outputs

`adapters.vj.console_proposals` consumes an XIO
`xio:predictive-semantic-lighting-frame:0.1` and produces one proposal for each
host surface:

```text
XIO semantic frame
    ├── Resolume Arena: OSC parameter intents
    └── Avolites Titan: WebAPI playback/cue intents
```

Both outputs are declarative and `proposal_only`. The adapter never opens a
socket, starts a host, emits OSC, or calls the Titan API. A later operational
adapter may execute an approved proposal after resolving the real host address,
composition mapping, playback handle and fixture patch.

Resolume receives parameter-shaped OSC intents for opacity, rotation, transport
position and a pulse-conditioned clip connection. Titan receives a playback
level intent and a pulse-conditioned playback fire intent, plus per-fixture
semantic states for a patch-aware adapter.

The model deliberately keeps the mathematical scene upstream. Resolume and
Titan are output surfaces, not competing audio-analysis engines.

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
- source commits: `e43422d`, `7daa9fb`, `206b844`, `f4e9f21`, `9b3c2b3`, `6ff293d`;
- copied files exclude media, presets, models, caches and private runtime data.

Run from this repository root:

```text
python -m pytest -q
```

The test suite validates the adapter, the XIO application-event consumer and
the explicit host-result boundary offline. A live Resolume host connection
remains an explicit integration step for a future host adapter.

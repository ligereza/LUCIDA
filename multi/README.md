# LUCIDA multi-device surface

This branch contains the router-agnostic transport and peer-session layer
extracted from XIO. It is designed to carry application events between
authorized devices over an injected local transport; the core does not open
sockets or discover peers by itself.

Included capabilities:

- explicit endpoint policy for local, LAN and WAN scope;
- handshake and peer authorization with revocation checks;
- directed fan-out with deduplication and sequence validation;
- canonical application events for OSC and Art-Net payloads;
- deterministic JSONL replay preserving raw payload hashes and provenance.

Source provenance:

- source repository: XIO (`C:\IA\XIO`);
- source branch: `codex/xio-transport`;
- source commits: `bbc7534`, `151670d`, `b8f8ba0`, `7a9dad3`, `4280b47`, `61b3bd2`;
- copied files exclude machine caches, credentials, runtime outputs and
  unrelated worktree changes.

Run from this repository root:

```text
python -m unittest discover -s XIO_LAYER/tests -v
```

The network writer is an explicit host dependency. The XIO-to-LUCIDA bridge
accepts only canonical application events and remains offline by default. The
connectivity probe reports only host-supplied measurements; it does not scan or
invent link state. This branch is therefore safe to replay offline and does not
claim a live router integration yet.

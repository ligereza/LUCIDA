# LUCIDA

Portable adaptation surfaces for visual, creative and multi-device workflows.

## Branches

- `ADOBE`: contextual shelf, companion overlay and Adobe adapters.
- `RESOLUME`: single-surface VJ boundary and deterministic session replay.
- `MULTI`: router-agnostic transport, peer sessions and application signals.

Each branch keeps its host-specific code isolated. Shared contracts must be
explicit, replayable and independent of a particular application.

Technical identifiers, file names, event keys, fixtures and parseable logs use
English ASCII. User-facing text may be localized separately.

LUCIDA proposes and records. It does not silently control a host application,
discover peers, open network sockets or execute an action without an explicit
host policy and authorization.

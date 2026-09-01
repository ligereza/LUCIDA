# LUCIDA

LUCIDA is a portable surface for adapting information and interaction across
applications. The repository is divided by integration target so each branch
can evolve without copying private projects, media libraries, credentials or
machine-specific state.

## Branches

- `ADOBE`: contextual shelf, companion overlay and Adobe adapters.
- `RESOLUME`: Resolume integration consolidated from the MOSAIK workstream.
- `MULTI`: multi-device transport and session capabilities from XIO.

The branches share contracts only when the contract is explicit, replayable and
independent of a particular host application. Integration code must preserve
source timestamps, sequence, provenance and user confirmation boundaries.

Technical identifiers, file names, event keys, fixtures and parseable logs use
English ASCII. User-facing text may be localized separately.

## Safety boundary

LUCIDA proposes and records. It does not silently control an application,
discover peers, open network sockets, collect camera data or execute an action
without an explicit host policy and authorization.

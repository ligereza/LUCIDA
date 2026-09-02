# Self-critique 14

## Decision

Remove the active runtime's dependency on a private module inside the extracted generic package, while preserving the generic package as a standalone unit.

## Why

The active signal bridge imported only stable hash and clone primitives from `generic-interface-layer`. That made an otherwise optional extraction a runtime dependency and meant removing the extraction would break the active Adobe bridge. The two contexts and analyses are not semantically identical, so replacing the active implementation wholesale would be unsafe.

## Trade-off

The active runtime now owns the same small stable-contract implementation under `contracts/stable.mjs`; the generic package keeps its local copy for standalone use. A parity test prevents silent drift. This is deliberate duplication at a package boundary, not accidental duplication of the Adobe context logic.

## Next decision gate

Do not merge the two context or analysis implementations until their privacy, host constraints and output semantics have a contract-level comparison and host/runtime regression coverage.

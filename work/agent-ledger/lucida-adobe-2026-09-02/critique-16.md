# Self-critique 16

## Decision

Keep the generic and Adobe context normalizers separate and make the difference executable.

## Why

The generic layer preserves provenance-oriented fields and explicit unknowns, while the Adobe runtime applies stricter host and privacy rules. A wholesale replacement would silently change path handling, completeness semantics and output shape.

## Trade-off

There is still deliberate duplication, but it is now an explicit package boundary with stable primitives parity-checked and a fixture proving the semantic difference. This is safer than pretending the two contexts are interchangeable.

## Next decision gate

Only consolidate the normalizers after defining a versioned shared context contract and validating it against the active Adobe bridge and the standalone package.

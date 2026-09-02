objective: Make the shared LUCIDA surface understandable to different clients without expanding Adobe, XIO or host responsibilities.
current_state: The bridge returns per-source state and active proposals, while the transparent companion reconstructs the aggregate status locally and only renders the first proposal summary.
verified_evidence: signal-bridge tests cover redaction, sequence ordering, bounded history, expiry and proposal-only safety; the surface schema has no aggregate status field.
strongest_failure_mode: Different consumers interpret the same surface differently, hiding stale signals or discarding useful proposal context.
alternatives:
  - action: add_aggregate_surface_status
    benefit: one deterministic status contract can be consumed by Adobe now and by future RESOLUME/MULTI clients later.
    risk: additive schema change requires tests and must not imply host action.
  - action: keep_client_side_derivation
    benefit: no contract change.
    risk: duplicates semantics and creates cross-project drift.
  - action: add_external_state_storage
    benefit: history survives a bridge restart.
    risk: expands privacy and persistence scope before the surface semantics are stable.
selected_action: add_aggregate_surface_status
decision_delta: Add a read-only aggregate status and render bounded proposal details; keep the surface proposal-only and in-memory.
confidence: high

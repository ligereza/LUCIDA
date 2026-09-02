objective: Keep LUCIDA ADOBE portable and prevent Adobe, Resolume and XIO responsibilities from drifting across branches.
current_state: Host capability data drives the agent-card and Adobe queue, but semantic contract validation was not centralized.
verified_evidence: The validator checks branch/focus identity, exact host membership, operation fields, connector input modes, proposal-only modes and required exclusions. It accepts harmless key ordering and rejects a RESOLUME-shaped contract. The full bridge suite passes 33/33.
strongest_failure_mode: A malformed or cross-branch capability file remains parseable JSON and silently changes the meaning of the Adobe bridge.
highest_consequence_error: A future agent interprets a valid-looking contract as authority to execute unsupported host or transport behavior.
options:
  - action: continue
    setup_cost: low
    execution_cost: low
    verification_cost: low
    rework_risk: low
    context_cost: low
    expected_benefit: high
    reversibility: high
    evidence_needed: Semantic validator, server, adapter and tests stay aligned.
  - action: ask_user
    setup_cost: low
    execution_cost: high
    verification_cost: high
    rework_risk: medium
    context_cost: high
    expected_benefit: low
    evidence_needed: A live Adobe host is not available in this cycle.
selected_action: continue
decision_delta: Validate the capability contract semantically before exposing or using it, without claiming live host support.
confidence: high
next_checkpoint: After commit and push; next live boundary is Photoshop UXP loading.

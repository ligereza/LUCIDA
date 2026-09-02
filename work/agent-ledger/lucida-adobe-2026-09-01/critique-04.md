objective: Keep LUCIDA ADOBE portable and prevent Adobe, Resolume and XIO responsibilities from drifting across branches.
current_state: The agent-card and host capability contract described the Adobe boundary, but the command queue kept a separate hardcoded host and operation allowlist.
verified_evidence: src/adapters/adobe.mjs now loads the branch-local capability contract and derives both host and operation allowlists; importing the adapter succeeds and all 31 legacy tests pass.
strongest_failure_mode: A future contributor edits the contract but forgets the queue, or edits the queue and forgets the contract, creating an apparent capability that differs from the executed behavior.
highest_consequence_error: An unsupported or cross-branch command reaches a job queue and is presented as a valid Adobe operation.
options:
  - action: continue
    setup_cost: low
    execution_cost: low
    verification_cost: low
    rework_risk: low
    context_cost: low
    expected_benefit: high
    reversibility: high
    evidence_needed: Queue import and full suite remain green.
  - action: ask_user
    setup_cost: low
    execution_cost: high
    verification_cost: high
    rework_risk: medium
    context_cost: high
    expected_benefit: low
    evidence_needed: A live Adobe host is not available in this cycle.
selected_action: continue
decision_delta: Derive the Adobe queue allowlist from the machine-readable ADOBE contract and keep host runtime status separate from declared operations.
confidence: high
next_checkpoint: After commit and push; next live boundary is Photoshop UXP loading.

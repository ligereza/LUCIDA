objective: Keep LUCIDA ADOBE portable and prevent Adobe, Resolume and XIO responsibilities from drifting across branches.
current_state: The ADOBE branch has a scope guard in the agent-card, but host operations and context-provider status were still duplicated in server code.
verified_evidence: The new contract is loaded by the server, exposed in the agent-card, required by offline verification and covered by a dedicated test. All 31 legacy tests pass.
strongest_failure_mode: A later change updates the visible scope but leaves operations or provider status inconsistent, causing agents to assume an unsupported Adobe integration exists.
highest_consequence_error: The companion or an external connector requests a host capability that the branch has not actually verified, increasing integration risk and user confusion.
options:
  - action: continue
    setup_cost: low
    execution_cost: low
    verification_cost: low
    rework_risk: low
    context_cost: low
    expected_benefit: high
    reversibility: high
    evidence_needed: Contract, server response and tests remain aligned.
  - action: ask_user
    setup_cost: low
    execution_cost: high
    verification_cost: high
    rework_risk: medium
    context_cost: high
    expected_benefit: low
    evidence_needed: A live Adobe host is not available in this cycle.
selected_action: continue
decision_delta: Centralize host, connector and exclusion declarations in contracts/host-capabilities.json without expanding runtime behavior.
confidence: high
next_checkpoint: After commit and push; next live boundary is Photoshop UXP loading.

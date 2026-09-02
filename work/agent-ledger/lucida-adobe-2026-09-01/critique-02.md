objective: Keep LUCIDA ADOBE focused while extending the portable Adobe companion and its explicit connectors.
current_state: The ADOBE branch is clean and pushed; host preflight is positive but no Adobe process is active, so live UXP validation is not available in this cycle.
verified_evidence: Adobe adapters resolve local roots; the UXP panel uses Manifest v5 lifecycle hooks; all offline suites pass; the agent card still uses a generic inherited name and does not explicitly declare the ADOBE boundary.
strongest_failure_mode: A future agent or connector interprets the inherited registry/agent-card wording as permission to mix Adobe, Resolume or XIO responsibilities.
highest_consequence_error: Scope drift causes host-specific actions or duplicated transport logic to enter the wrong branch and increases later integration cost.
options:
  - action: continue
    setup_cost: low
    execution_cost: low
    verification_cost: low
    rework_risk: low
    context_cost: low
    expected_benefit: high
    reversibility: high
    evidence_needed: Agent-card and server tests expose an explicit ADOBE scope.
  - action: ask_user
    setup_cost: low
    execution_cost: high
    verification_cost: high
    rework_risk: medium
    context_cost: high
    expected_benefit: low
    reversibility: medium
    evidence_needed: Live Photoshop process, which is absent now.
selected_action: continue
decision_delta: Add a machine-readable branch scope to the Adobe bridge before the next live-host attempt.
confidence: high
next_checkpoint: After scope contract tests and push.

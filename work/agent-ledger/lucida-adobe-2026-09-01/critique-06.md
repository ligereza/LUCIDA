objective: Keep LUCIDA ADOBE portable and prevent Adobe, Resolume and XIO responsibilities from drifting across branches.
current_state: The migrated companion source passed syntax checks but its local Electron runtime had not been restored or launched in this checkout.
verified_evidence: npm ci restored the locked Adobe and companion dependencies; Electron opened from the checkout-local binary; the bridge health endpoint reported branch ADOBE and focus adobe; the surface endpoint responded with proposalOnly=true and no host actions.
strongest_failure_mode: Treating a source-only migration as executable without verifying the local runtime and bridge process.
highest_consequence_error: Reporting the companion as migrated while the user cannot actually open it from the destination checkout.
options:
  - action: continue
    setup_cost: low
    execution_cost: low
    verification_cost: low
    rework_risk: low
    context_cost: low
    expected_benefit: high
    reversibility: high
    evidence_needed: Runtime remains open and health/surface endpoints remain responsive.
  - action: ask_user
    setup_cost: low
    execution_cost: high
    verification_cost: high
    rework_risk: medium
    context_cost: high
    expected_benefit: low
    evidence_needed: Photoshop is not open, so UXP runtime validation cannot be completed in this cycle.
selected_action: continue
decision_delta: Restore only the locked local dependencies required by the migrated companion and verify its real process/bridge boundary; leave Photoshop UXP validation for an actual host session.
confidence: high
next_checkpoint: After runtime evidence is committed; next live boundary is Photoshop UXP loading.

objective: Make the ADOBE branch portable, usable and safely connected to XIO, VIZZ and PUPILA without changing the host-specific focus of MOSAIK or the transport focus of XIO.
acceptance_criteria:
  - Adobe adapters resolve the checked-out package root instead of a stale machine path.
  - The Photoshop UXP bridge contract remains local, bounded and proposal-only where applicable.
  - No host runtime is claimed as verified without an actual Adobe result envelope.
current_state:
  verified_evidence: ADOBE branch is clean and pushed; local signal bridge and Python publisher pass; 361 migrated CHEMSEX assets are present and indexed by branch-local paths; Adobe executables are installed but no Adobe process is running.
assumptions:
  - The ExtendScript adapters run from their own script files.
  - The Photoshop UXP adapter is loaded as a plugin from its manifest folder when used.
strongest_failure_mode: The bridge appears healthy while a host adapter silently reads or writes the old C:/IA/LUCIDA/adobe location.
highest_consequence_error: A command could be reported as queued or empty against the wrong checkout, causing false confidence and lost time.
options:
  - action: continue
    setup_cost: low
    execution_cost: low
    verification_cost: medium
    rework_risk: low
    context_cost: low
    expected_benefit: high
    reversibility: high
    evidence_needed: Syntax checks plus a read-only host preflight from the current checkout.
  - action: ask_user
    setup_cost: low
    execution_cost: high
    verification_cost: high
    rework_risk: medium
    context_cost: high
    expected_benefit: medium
    reversibility: medium
    evidence_needed: User-operated Photoshop session before the portable path defect is fixed.
search_gap:
  uncertainty: Exact UXP filesystem and panel lifecycle behavior.
  consequence: Medium; wrong assumptions could make the plugin fail or poll while hidden.
  expected_error_reduction: medium
  search_cost: low
  marginal_value: positive
  stop_reason: Official Adobe documentation confirms getPluginFolder/getNativePath and panel show/hide hooks; known Photoshop versions may still differ at runtime.
selected_action: continue
confidence: high
next_checkpoint: After the adapter-root patch and its offline checks.

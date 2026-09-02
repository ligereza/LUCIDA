run_id: lucida-adobe-2026-09-01
objective: Continue autonomous development of LUCIDA ADOBE as a portable transparent Adobe companion connected through explicit local contracts to XIO, VIZZ and PUPILA.
scope: ADOBE branch only; preserve MOSAIK/RESOLUME, XIO/MULTI and original SVG sources.
core_acceptance_criteria:
  - Preserve branch separation and ASCII technical identifiers.
  - Keep local signals bounded and proposal-only.
  - Make host integration portable and testable without inventing live Adobe validation.
authorized_extensions:
  - Improve offline preflight and host contract checks when reversible and directly tied to portability.
status: active
completed:
  - item: Migrated branch-local CHEMSEX catalog and provenance.
    evidence: 361 assets in ICONOS/CHEMSEX with manifest and pending review record.
  - item: Added local signal surface and Python publisher.
    evidence: Node, Python and live cross-process checks passed; raw content is rejected.
  - item: Added Photoshop UXP context shelf and transparent companion integration.
    evidence: Existing syntax, server and generic-core suites pass.
  - item: Removed stale checkout-root coupling from Adobe adapters and migration defaults.
    evidence: ExtendScript adapters resolve from their script location; PSJS resolves from the UXP plugin folder; source contract test passes.
  - item: Bound Photoshop UXP polling to the panel lifecycle and upgraded its manifest.
    evidence: Manifest v5 with Photoshop 23.3.0 minimum; lifecycle contract test passes.
  - item: Added read-only Adobe host auto-discovery.
    evidence: Preflight found Photoshop 2026, Illustrator 2026 and After Effects 2026; adapter syntax is ok for all three.
  - item: Added an explicit machine-readable ADOBE scope to the bridge.
    evidence: Health and agent-card responses identify LUCIDA/ADOBE, list Adobe hosts, classify XIO/VIZZ/PUPILA as signal inputs, and exclude Resolume and transport responsibilities; server tests pass.
  - item: Added a single host capability contract for the ADOBE branch.
    evidence: contracts/host-capabilities.json drives the agent-card scope and operations; Photoshop is the only host with a prepared UXP context provider, while other context providers remain explicit as not implemented.
  - item: Made Adobe command validation consume the capability contract.
    evidence: src/adapters/adobe.mjs derives allowed hosts and operations from contracts/host-capabilities.json; unsupported commands are rejected before job creation.
  - item: Added semantic validation for the host capability contract.
    evidence: src/tools/host-capabilities.mjs checks branch identity, host membership, connector modes, exclusions and required fields; order-only JSON changes are accepted and cross-branch contracts are rejected.
current_state:
  files_or_resources: C:/IA/LUCIDA_ADOBE/adobe; branch ADOBE tracking origin/ADOBE; Photoshop 2025/2026 and Illustrator 2026 are installed; no Adobe process is active.
  tests_and_checks: legacy Node suite 33/33, server scope and signal tests pass, generic core 11/11, companion syntax pass, smoke and verify pass, Python publisher 3/3, live signal publisher pass, Adobe host preflight pass for installed executables; command adapter and capability validator pass.
  assumptions: UXP plugin folder is the checked-out plugin folder; actual host runtime remains unverified until user loads it in Photoshop.
  open_questions: Whether the installed Photoshop build accepts the current UXP manifest and context API without a live Developer Tool run; whether its panel lifecycle callbacks fire as documented.
  blockers: None for offline work; live UXP validation requires a user-opened Adobe host.
  research_refs: Official Adobe UXP docs for getPluginFolder/getNativePath and panel lifecycle hooks.
  delegation_refs: None.
  last_critique: After making the queue contract-driven, the remaining offline drift risk was accepting a syntactically valid but semantically cross-branch contract; selected a central validator without expanding Adobe host behavior.
  estimated_remaining_effort: Complete for this contract-validation milestone; live host validation remains a user-operated boundary.
next_action: On the next cycle, inspect the live Photoshop UXP load if the user opens it; otherwise audit command envelopes and host adapter parity without adding Resolume/XIO behavior.
next_checkpoint_trigger: After semantic contract validation and push.

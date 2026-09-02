run_id: lucida-adobe-2026-09-02
objective: Continue autonomous development of LUCIDA ADOBE as a portable transparent Adobe companion connected through explicit local contracts to XIO, VIZZ and PUPILA.
scope: ADOBE branch only; preserve MOSAIK/RESOLUME, XIO/MULTI and original SVG sources.
core_acceptance_criteria:
  - Preserve branch separation and ASCII technical identifiers.
  - Keep local signals bounded and proposal-only.
  - Make host integration portable, contract-driven and testable without inventing live Adobe validation.
status: active
completed:
  - item: Published the pre-improvement baseline checkpoint.
    evidence: b171401fe91826e7ced9951fa06644ef2df2ed24 was recorded and bb64db5 was pushed before implementation.
  - item: Audited the migrated companion, bridge and Adobe adapters.
    evidence: The bridge and companion run locally; the host contract declared operations but verification did not compare them with agent.jsx/agent.psjs dispatches.
in_progress:
  - item: Add contract-to-adapter parity verification and reduce companion polling overlap.
    acceptance: verify fails on an operation mismatch, current adapters pass, and renderer requests cannot stack.
open_questions:
  - Whether the installed Photoshop build accepts and executes the UXP panel in a user-operated host session.
  - Whether a real Adobe context publisher will remain stable across host versions.
next_action: Implement the parity guard and polling guard, run all offline suites, then publish a checkpoint.
next_checkpoint_trigger: A coherent code change with passing suites and a pushed commit.

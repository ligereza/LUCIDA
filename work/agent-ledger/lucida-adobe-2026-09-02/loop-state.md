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
  - item: Added contract-to-adapter parity verification and reduced companion polling overlap.
    evidence: verify now checks every declared operation against each JSX/PSJS dispatch; current Adobe adapters pass, and renderer syntax checks pass with a single poll in flight.
  - item: Bounded cross-project signal state and proposal lifetime.
    evidence: VIZZ/PUPILA proposals are clamped to 45 seconds and filtered from the derived surface after expiry; signal history and deduplication memory stay at 96 events per session.
  - item: Added a deterministic bridge-facing status boundary.
    evidence: The companion accepts only an ADOBE bridge identity, avoids overlapping refresh requests, and the shared signal surface now exposes only active proposals with bounded state.
in_progress:
  - item: Improve the bridge-facing companion presentation and evidence path.
    acceptance: the user can distinguish bridge offline, Adobe context absent, stale external signals and active proposal state without host actions being implied.
open_questions:
  - Whether the installed Photoshop build accepts and executes the UXP panel in a user-operated host session.
  - Whether a real Adobe context publisher will remain stable across host versions.
next_action: Inspect the companion state presentation and add only a deterministic status model that keeps connector ownership explicit.
next_checkpoint_trigger: A coherent code change with passing suites and a pushed commit.

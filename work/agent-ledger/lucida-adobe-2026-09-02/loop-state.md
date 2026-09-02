run_id: lucida-adobe-2026-09-02
objective: Continue autonomous development of LUCIDA ADOBE as a portable transparent Adobe companion connected through explicit local contracts to XIO, VIZZ and PUPILA.
scope: ADOBE branch only; preserve MOSAIK/RESOLUME, XIO/MULTI and original SVG sources.
core_acceptance_criteria:
  - Preserve branch separation and ASCII technical identifiers.
  - Keep local signals bounded and proposal-only.
  - Make host integration portable, contract-driven and testable without inventing live Adobe validation.
status: active
completed:
  - item: Made project collections visible and exposed per-file inventory errors.
    evidence: renderer consumes projectInventory.collections; inventory schema exposes indexErrors; 42 legacy tests pass.
  - item: Bounded context sessions, recommendation cache and insert result retention; unknown session lookups no longer fall back to another session.
    evidence: context regression test passes with 40 sessions and diagnostics remain bounded.
  - item: Bounded external signal session state without changing proposal-only semantics.
    evidence: signal regression test passes with 40 sessions; signal history remains capped at 96 events per session.
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
  - item: Added an aggregate status to the shared signal surface.
    evidence: Surface schema and runtime now expose empty/active/stale state, active and stale source counts, and current proposal count; the companion renders proposal origin and reason while keeping confirmation required.
  - item: Made external signal changes invalidate recommendation cache entries.
    evidence: recommendationCacheKey includes context hash, result limit and derived surface hash; a signal or lifecycle change cannot leave the companion on an older recommendation set.
in_progress:
  - item: Audit the insertion path against external signal proposals.
    acceptance: XIO, VIZZ and PUPILA signals can enrich context but cannot create or bypass an Adobe host command without the existing explicit authorization path.
files_or_resources:
  - adobe/companion/renderer.js
  - adobe/src/tools/project-inventory.mjs
  - adobe/src/tools/context.mjs
tests_and_checks:
  - npm run legacy:test: 42 passed
  - npm run test: 11 passed
  - npm run smoke: passed
  - npm run companion:check: passed
assumptions:
  - ADOBE remains a local-first companion; host runtime validation is still external.
blockers: []
research_refs: []
delegation_refs: []
last_critique: critique-10.md
estimated_remaining_effort: one focused implementation and verification pass
open_questions:
  - Whether the installed Photoshop build accepts and executes the UXP panel in a user-operated host session.
  - Whether a real Adobe context publisher will remain stable across host versions.
next_action: Confirm the insertion path and host adapter authorization boundaries, then record whether a code change is justified.
next_checkpoint_trigger: A coherent code change with passing suites and a pushed commit.

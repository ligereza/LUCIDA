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
  - item: Audited insertion boundary against external proposals.
    evidence: The new regression confirms a VIZZ proposal produces no queued insertion; host actions remain false and proposal-only remains true.
  - item: Published the structural audit and insertion-boundary fixes.
    evidence: Commits 2985f1f, 76c459d and 22808d2 are pushed to origin/ADOBE; branch is clean and synchronized.
  - item: Audited the repository package boundary.
    evidence: npm pack dry-run contains 703 files and about 687595 KB, with zero forbidden cache, dependency-tree, secret, root-job or root-log entries; required companion and runtime entrypoints are present. High size is explained by the intentional high-resolution ICONOS/CHEMSEX library.
  - item: Added explicit npm packaging exclusions and documented private-repository installation.
    evidence: .npmignore excludes development state without excluding generic-interface-layer/core/jobs runtime code; README and audit record that npm omits the root lockfile from tarballs by design.
  - item: Closed the Adobe document-path privacy gap at both bridge and UXP boundaries.
    evidence: Adobe context normalization forces document.path to null, UXP emits a null path, and dedicated regressions cover both behavior and source contract; 47 legacy tests pass.
  - item: Closed the remaining Photoshop output-name encoding gap.
    evidence: UXP and JSX output names reject non-ASCII characters; a source-contract regression covers both adapters.
  - item: Completed the insert-result memory and path boundary.
    evidence: Result data is bounded by depth, keys and string length and removes file/path/content-like keys; the UXP consumer reports only assetId; regression coverage confirms a large path-bearing payload stays bounded.
  - item: Moved UXP manifest validation into the executable verifier.
    evidence: A dedicated validator checks manifest version, Photoshop host, permissions, bridge domain and panel entrypoint; valid and missing-permission fixtures are covered by tests.
  - item: Hardened the Photoshop UXP queue consumer around host mutation rules.
    evidence: Open, save, close and import operations are now inside core.executeAsModal scopes, with an offline source-contract regression; actual Photoshop execution remains external.
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
  - item: Bounded Photoshop UXP context production and bridge retry pressure.
    evidence: UXP layer traversal stops at 200 layers and depth 64, layer text is capped at 1000 characters, active/imported reads are limited, and failed bridge polls wait five seconds before retrying with duplicate errors suppressed; source-contract regression passes.
  - item: Closed the UXP generated-layer naming encoding gap.
    evidence: Photoshop UXP now sanitizes generated asset names to ASCII and uses ASCII analysis-layer labels; the Adobe source-contract regression covers the UXP path.
  - item: Closed the remote preview and renderer CSP mismatch.
    evidence: Electron now fetches only allowlisted HTTPS SVG hosts, enforces status/content-type/size/timeout checks, returns a data URL to the local renderer, and the renderer no longer assigns remote URLs directly; source-contract regression passes.
  - item: Bounded Electron bridge response accumulation.
    evidence: bridgeRequest rejects response bodies above four megabytes while streaming and has a source-contract regression for the bound.
  - item: Made the root test command cover both execution paths.
    evidence: `npm test` now runs `test:core` and `test:runtime`; `legacy:test` remains an explicit runtime alias so existing operator commands continue to work.
  - item: Removed active-runtime coupling to extracted-core internals.
    evidence: signal-bridge now imports stable primitives from `contracts/stable.mjs`; structure regression prevents reintroducing the dependency while generic-interface-layer keeps its standalone copy.
  - item: Made the shared stable-contract boundary explicit and parity-checked.
    evidence: The active runtime owns `contracts/stable.mjs`, the generic package remains standalone, both implementations are checked for exact parity ignoring line endings, and `npm test` passes 11 core plus 56 runtime tests.
in_progress:
  - item: Prepare the next operator validation pass.
    acceptance: Repository checks remain green and the remaining uncertainty is isolated to user-operated Adobe host execution, not local bridge structure.
files_or_resources:
  - adobe/companion/renderer.js
  - adobe/src/tools/project-inventory.mjs
  - adobe/src/tools/context.mjs
  - adobe/adobe-context-shelf/photoshop-uxp/index.js
  - adobe/contracts/stable.mjs
tests_and_checks:
  - npm run test: 11 core tests and 56 runtime tests passed
  - npm run test:runtime: 56 passed
  - npm run smoke: passed
  - npm run companion:check: passed
  - npm run verify: passed
assumptions:
  - ADOBE remains a local-first companion; host runtime validation is still external.
blockers: []
research_refs: []
delegation_refs: []
last_critique: critique-14.md
estimated_remaining_effort: one focused implementation and verification pass
open_questions:
  - Whether the installed Photoshop build accepts and executes the UXP panel in a user-operated host session.
  - Whether a real Adobe context publisher will remain stable across host versions.
  - Whether remote preview URLs should use a constrained main-process proxy or a small explicit origin allowlist.
  - Whether UXP supports the cancellation primitive needed to bound a hung fetch without creating overlapping requests.
next_action: Keep the package boundary stable and prepare a focused Photoshop UXP validation checklist; do not claim host execution until the user runs the companion inside Photoshop. Resolve remote preview policy and UXP cancellation only after the host validation gate.
next_checkpoint_trigger: A coherent code change with passing suites and a pushed commit.

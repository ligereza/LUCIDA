objective: Improve LUCIDA ADOBE without taking ownership of Resolume, XIO transport or source-project migration.
current_state: The transparent companion and local bridge have been executed successfully, but host capability declarations and Adobe adapter dispatches were only tested independently.
verified_evidence: contracts/host-capabilities.json lists four hosts and their operations; five Adobe adapter files exist; the current test suite checks syntax and contract shape but not operation parity.
strongest_failure_mode: The contract can advertise an operation that an actual JSX/PSJS consumer does not dispatch, causing a job to queue successfully and fail later inside Adobe.
alternatives:
  - action: add_parity_audit
    benefit: catches contract drift before runtime and keeps host ownership explicit.
    risk: static extraction cannot prove Adobe host behavior; it must remain a preflight guard, not a live-runtime claim.
  - action: add_more_host_features
    benefit: broader functionality.
    risk: expands scope before the existing contract boundary is trustworthy.
  - action: run_new_live_test
    benefit: could verify one host build.
    risk: requires user-operated Adobe runtime and cannot replace deterministic offline checks.
selected_action: add_parity_audit
decision_delta: Add a narrow static contract-to-adapter parity check, strengthen the companion scheduler against overlapping polls, and keep live UXP validation explicitly pending.
confidence: high

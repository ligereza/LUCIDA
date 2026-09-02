# Research ledger

run_id: lucida-adobe-uxp-timeout-2026-09-02
question: Does the installed-era UXP fetch surface provide a compatible cancellation primitive for bounded bridge requests?
decision: Use AbortController and AbortSignal in the Photoshop UXP bridge, with route-specific timeout budgets.
scope: Official Adobe UXP network documentation and the current Photoshop plugin source.
acceptance_criteria: The primitive is documented by Adobe, the request timeout does not leak timeoutMs into fetch, settled failures are reported explicitly, and the existing source-contract suite remains green.
effort_budget: One focused documentation round and one implementation pass.
status: decided

concepts:
  - id: C-001
    term: UXP fetch
    meaning: Promise-based network request available to the plugin.
    related_to: [C-002, C-003]
    origin: source
    next_query: null
  - id: C-002
    term: AbortController
    meaning: Controller used to abort an in-flight fetch through its signal.
    related_to: [C-001]
    origin: source
    next_query: null
  - id: C-003
    term: route-specific timeout
    meaning: Short timeout for context and queue polling, longer bounded timeout for an asset fetch.
    related_to: [C-001, C-002]
    origin: inference
    next_query: Validate behavior in the installed Photoshop host.

queries:
  - id: QRY-001
    text: site:developer.adobe.com photoshop UXP fetch AbortController abort timeout
    channel: web
    reason: Verify the cancellation API before changing host plugin code.
    expected_gain: Determine whether a real abort signal is supported by UXP fetch.
    result: Adobe's UXP fetch reference documents network errors/timeouts; Adobe's UXP network recipe provides safeFetch using AbortController, setTimeout and controller.signal.
    next_action: Implement the documented pattern with bounded route-specific budgets.

sources:
  - id: S-001
    title: window.fetch
    author_or_org: Adobe
    date: null
    accessed: 2026-09-02
    type: official
    url_or_path: https://developer.adobe.com/photoshop/uxp/2022/uxp/reference-js/Global%20Members/Data%20Transfers/fetch/
    supports: [CL-001]
    contradicts: []
    quality: Primary official API reference.
    limitations: Does not establish behavior for every historical Photoshop build.
  - id: S-002
    title: Network Operations
    author_or_org: Adobe
    date: null
    accessed: 2026-09-02
    type: official
    url_or_path: https://developer.adobe.com/premiere-pro/uxp/resources/recipes/network/
    supports: [CL-001, CL-002]
    contradicts: []
    quality: Primary official UXP recipe with explicit timeout example.
    limitations: The page is written for Premiere UXP; compatibility with Photoshop still requires host validation.

claims:
  - id: CL-001
    statement: UXP fetch accepts an AbortSignal and Adobe documents aborting a request with AbortController.
    status: supported
    evidence: [S-001, S-002]
    inference_notes: The API is documented across UXP references; host execution remains a separate validation step.
    confidence: high
  - id: CL-002
    statement: A route-specific timeout is preferable here because remote asset retrieval can outlive local context polling but must remain bounded.
    status: partially_supported
    evidence: [S-002]
    inference_notes: The timeout budgets are an engineering choice for this bridge, not a physiological or host performance guarantee.
    confidence: medium

models:
  - id: M-001
    kind: hypothesis
    statement: Aborting a hung UXP request releases the in-flight guard and lets the existing retry backoff recover without overlapping intentional polls.
    assumptions: The installed Photoshop UXP host implements AbortController for fetch as documented.
    predictions: A timeout produces an explicit error and the next scheduled attempt can proceed after the retry interval.
    evidence_for: [CL-001]
    evidence_against: []
    status: pending-host-validation

open_questions:
  - id: OQ-001
    question: Does the installed Photoshop build execute AbortController cancellation exactly as documented?
    why_it_matters: An unsupported primitive would leave the UXP panel dependent on the old unbounded behavior.
    next_test: Run the panel in Photoshop with the bridge stopped and observe timeout, offline status and recovery.
    stop_condition: Keep host validation pending until a user-operated run confirms timeout and recovery.

decision:
  recommendation: Implement AbortController now and retain host validation as an explicit gate.
  rationale: The API is documented by Adobe and the current UXP source had no bounded cancellation path.
  risks: Historical host differences could reject AbortController or produce a generic TypeError.
  reversibility: High; the change is isolated to the UXP request helper.
  confidence: medium-high
  unresolved_but_accepted: Actual Photoshop host behavior is not proven by source tests.
  next_review_trigger: First user-operated Photoshop UXP run.

run_id: lucida-adobe-2026-09-02
question: Can the Photoshop UXP host supply a bounded composite sample for useful visual-space analysis without adding dependencies or repeatedly processing the full canvas?
decision: Prototype a small, cached composite-detail grid through the existing UXP adapter; report it as visual quietness, not empty space. Keep geometry-only blank areas separate.
scope: Official Adobe Photoshop UXP Imaging API and current ADOBE host adapter only; no model download, external library, or modification to the active PSB.
acceptance_criteria:
  - Request a small target size and dispose the returned image buffer.
  - Key cache by document/history state and throttle expensive samples.
  - If the imaging API is unavailable or fails, preserve the bounds-only fallback and label it accurately.
  - Never convert low texture alone into a claim of blank/transparent pixels.

queries:
  - id: QRY-001
    text: site:developer.adobe.com/photoshop/uxp imaging.getPixels targetSize Photoshop UXP
    channel: web
    reason: Verify whether Photoshop can return a small composite sample without exporting a full-size image.
    expected_gain: Decide whether real visual-space inspection can be added without a third-party library.
    result: Official Imaging API documents composite getPixels, targetSize downscaling, async retrieval, imageData.dispose, and recommends the smallest target size because access can incur I/O.
    next_action: Add a bounded adapter experiment with explicit fallback and hostless tests.
  - id: QRY-002
    text: site:developer.adobe.com/photoshop/uxp activeHistoryState HistoryState id
    channel: web
    reason: Find a cache key that updates when the user edits pixels without sampling on every 1.2-second poll.
    expected_gain: Avoid repeated image-composite work and stale samples.
    result: Document exposes activeHistoryState; HistoryState exposes an id unique for the document lifetime.
    next_action: Key successful samples to document id + active history-state id; throttle changes.

sources:
  - id: S-001
    title: Imaging API
    author_or_org: Adobe
    date: Current UXP Photoshop 2022 reference; opened 2026-09-14
    accessed: 2026-09-14
    type: official
    url_or_path: https://developer.adobe.com/photoshop/uxp/2022/ps-reference/media/imaging
    supports: [CL-001, CL-002, CL-003]
    contradicts: []
    quality: high
    limitations: Does not prove the installed Photoshop 2026 host executes this repository's UXP panel or the speed of this specific document.
  - id: S-002
    title: Document API reference
    author_or_org: Adobe
    date: Current UXP Photoshop 2022 reference; opened 2026-09-14
    accessed: 2026-09-14
    type: official
    url_or_path: https://developer.adobe.com/photoshop/uxp/2022/ps-reference/classes/document
    supports: [CL-004]
    contradicts: []
    quality: high
    limitations: API documentation, not a runtime test on this workstation.
  - id: S-003
    title: HistoryState API reference
    author_or_org: Adobe
    date: Current UXP Photoshop reference; opened 2026-09-14
    accessed: 2026-09-14
    type: official
    url_or_path: https://developer.adobe.com/photoshop/uxp/2022/ps_reference/classes/historystate/
    supports: [CL-004]
    contradicts: []
    quality: high
    limitations: Confirms identity of history states, not sampling cadence performance.

claims:
  - id: CL-001
    statement: Photoshop UXP can request pixels from the full document composite and scale them to a smaller target size.
    status: supported
    evidence: [S-001]
    inference_notes: A target width of 192 for the active document's 1.83 aspect ratio would yield roughly 192x105 pixels if Photoshop preserves that ratio; exact output dimensions are host-returned and must be read, not assumed.
    confidence: high
  - id: CL-002
    statement: The sample path can reduce memory use by requesting the smallest useful size and disposing PhotoshopImageData after analysis.
    status: supported
    evidence: [S-001]
    inference_notes: Memory savings for this exact document are estimated from the requested thumbnail dimensions and remain subject to host behavior.
    confidence: high
  - id: CL-003
    statement: Pixel detail is evidence of visual quietness, not proof of semantic blankness or suitable text contrast.
    status: supported
    evidence: [S-001]
    inference_notes: This is a product-safety boundary inferred from the API's raw pixel output; texture/edge metrics do not understand design intent.
    confidence: high
  - id: CL-004
    statement: Document.activeHistoryState.id can identify the state used to cache a pixel sample per open document.
    status: supported
    evidence: [S-002, S-003]
    inference_notes: Throttling and sample freshness still need local tests.
    confidence: high

decision:
  recommendation: Continue with a reversible hostless prototype that adds an optional visual-detail grid to UXP context; do not replace or relabel geometric blank detection.
  rationale: This addresses the actual full-canvas-layer failure mode using an existing Adobe API, avoids another library/model, and makes no claim that low texture equals whitespace.
  risks: Imaging retrieval may be slow or unsupported for some document modes; history changes can be frequent; quiet regions can include flat foreground shapes.
  reversibility: High; the visual grid is optional and geometry-only fallback remains authoritative when absent.
  confidence: High that the API exists; medium that the proposed sampling cadence will be acceptable; low on actual PSB quiet-region quality until UXP host testing.
  unresolved_but_accepted: UXP panel is not loaded and local bridge 127.0.0.1:47921 is not listening; active PSB must remain untouched.
  next_review_trigger: Hostless UXP tests pass and, only when the user-operated panel is available, one safe read-only sample is observed.

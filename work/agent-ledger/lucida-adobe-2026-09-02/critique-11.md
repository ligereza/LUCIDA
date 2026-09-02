# Critique 11

objective: make the ADOBE branch portable and executable through explicit local contracts.
evidence: ADOBE is clean and synchronized; 50 bridge tests, 11 core tests, smoke, companion syntax and verifier pass. Adobe host execution is still external.
strongest_failure_mode: a malformed or incomplete UXP manifest can pass local JavaScript checks and fail before Photoshop loads the panel.
alternatives:
  - ask_user: provides host evidence but cannot improve offline detection while Photoshop is closed.
  - continue_code: validate the manifest and required UXP entrypoints in the existing verifier; low risk and reusable.
  - add_new_runtime: would increase scope before the host contract is verified.
selected_action: continue_code
decision_delta: move the next gate from source-only UXP checks into the repository verifier.
confidence: high
verification_signal: npm run verify must fail on an invalid UXP manifest and pass on the current manifest; legacy tests must remain green.
reversal_condition: if Photoshop's installed UXP manifest accepts a different documented shape, revise the validator from host evidence rather than weakening it silently.

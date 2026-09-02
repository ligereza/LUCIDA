previous_action: Add collection rendering, index diagnostics and bounded context state.
selected_action: continue
decision_delta: Extend the bounded-state fix to cache writes and asset path validation; defer dependency replacement.
objective: Keep LUCIDA ADOBE portable, transparent and contract-driven without hiding indexing failures or leaking one session into another.
evidence:
  - Project inventory reports 96 mini-icons and the renderer now consumes projectInventory.collections.
  - 42 legacy tests, 11 core tests, smoke and companion syntax checks pass after the correction.
  - A missing sessionId previously fell back to the newest context; the regression test exposed and fixed it.
strongest_failure_mode: A long-running companion can retain stale state or accept a path that is lexically inside the checkout but resolves outside it.
alternatives:
  - Stop after functional fixes: lower immediate risk, but leaves predictable memory and path issues.
  - Replace the Adobe SDK dependency now: higher compatibility and review risk without an available audit fix.
  - Continue with bounded cache writes and realpath checks: small, reversible changes with direct tests.
cost_assessment: The bounded cache/path work is lower total cost than debugging stale UI, corrupted cache or path escapes later.
verification_signal: Full legacy/core suites, a cache concurrency regression, and asset-root path tests remain green.
next_checkpoint: Commit only after all tests, syntax checks, audit diff and branch status are clean.

import test from "node:test"
import assert from "node:assert/strict"
import { currentSurface, publishSignal } from "../src/tools/signal-bridge.mjs"
import { derivePupilaAssistance } from "../src/tools/pupila-assistance.mjs"

function signal(overrides = {}) {
  return {
    signalId: "pupila-test-001",
    source: "pupila",
    sessionId: "pupila-assistance-session",
    sequence: 0,
    eventType: "learning.progress",
    receivedAt: "2026-09-14T12:00:00.000Z",
    metadata: { focusScore: 0.12, attentionScore: 0.2 },
    ...overrides,
  }
}

test("a low score alone remains observation, not an assistance claim", () => {
  const result = derivePupilaAssistance(signal(), Date.parse("2026-09-14T12:00:10.000Z"))
  assert.equal(result.state, "observing")
  assert.equal(result.proposal, undefined)
})

test("explicit blocked evidence creates a confirmation-only assistance proposal", () => {
  const result = derivePupilaAssistance(signal({
    eventType: "interaction.blocked",
    metadata: { state: "blocked", intent: "illustrator-text", target: "adobe" },
  }), Date.parse("2026-09-14T12:00:10.000Z"))
  assert.equal(result.state, "assist")
  assert.equal(result.proposal.kind, "assistance.contextual")
  assert.equal(result.proposal.proposalOnly, true)
  assert.equal(result.proposal.requiresConfirmation, true)
})

test("an expired PUPILA proposal cannot keep the companion in assist state", () => {
  const result = derivePupilaAssistance(signal({
    eventType: "learning.progress",
    proposal: { title: "Expired help", reason: "stale", expiresAt: "2026-09-14T11:59:00.000Z" },
  }), Date.parse("2026-09-14T12:00:10.000Z"))
  assert.equal(result.state, "observing")
  assert.equal(result.proposal, undefined)
})

test("surface exposes stable PUPILA assistance without turning age into hash churn", () => {
  const first = publishSignal({
    source: "pupila",
    sessionId: "pupila-surface-stable",
    eventType: "workflow.repeated",
    metadata: { intent: "photoshop-layer", state: "uncertain" },
  })
  const second = currentSurface({ sessionId: "pupila-surface-stable", now: new Date(Date.now() + 1000) })
  assert.equal(first.surface.assistance.state, "assist")
  assert.equal(first.surface.assistance.proposal.proposalOnly, true)
  assert.equal(first.surface.surfaceHash, second.surfaceHash)
})

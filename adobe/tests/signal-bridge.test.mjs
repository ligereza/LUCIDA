import test from "node:test"
import assert from "node:assert/strict"
import { currentSignals, currentSurface, normalizeSignal, publishSignal, signalDiagnostics } from "../src/tools/signal-bridge.mjs"

function sessionId(label) {
  return `signal-${label}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

test("signal bridge redacts raw content and deduplicates source events", () => {
  const id = sessionId("redaction")
  const input = {
    signalId: "xio-001",
    source: "xio",
    sessionId: id,
    eventType: "workspace.focus",
    metadata: { app: "photoshop", intent: "insert", action: "select" },
    payload: { text: "private text", path: "C:\\private.psd", count: 2 },
  }
  const first = publishSignal(input)
  assert.equal(first.accepted, true)
  assert.equal(first.duplicate, false)
  assert.equal(first.signal.metadata.app, "photoshop")
  assert.equal(first.signal.metadata.count, 2)
  assert.equal(first.signal.metadata.text, undefined)
  assert.equal(first.signal.metadata.path, undefined)
  assert.equal(first.signal.redaction.rawContentForwarded, false)
  assert.ok(first.signal.redaction.droppedKeys.includes("text"))
  assert.ok(first.signal.redaction.droppedKeys.includes("path"))
  assert.equal(first.surface.sources.xio.state, "active")
  assert.deepEqual(first.surface.status, { state: "active", sourceCount: 3, activeSourceCount: 1, staleSourceCount: 0, proposalCount: 0 })

  const duplicate = publishSignal(input)
  assert.equal(duplicate.duplicate, true)
  assert.equal(currentSignals({ sessionId: id }).count, 1)

  const xioEnvelope = publishSignal({
    signalId: "xio-002",
    source: "xio",
    sessionId: id,
    event: "radio.sample",
    timestamp_utc: "2026-09-01T12:00:00Z",
    metadata: {
      channel: "wifi",
      status: "ready",
      wifi_signal_percent: 84,
      gateway_loss_percent: 1.5,
      wifi_receive_mbps: 12.25,
      cell_rat: "nr",
      cell_channel: 78,
    },
  })
  assert.equal(xioEnvelope.signal.eventType, "radio.sample")
  assert.equal(xioEnvelope.signal.timestamp, "2026-09-01T12:00:00.000Z")
  assert.equal(xioEnvelope.signal.metadata.signalPercent, 84)
  assert.equal(xioEnvelope.signal.metadata.lossPercent, 1.5)
  assert.equal(xioEnvelope.signal.metadata.receiveMbps, 12.25)
  assert.equal(xioEnvelope.signal.metadata.radioType, "nr")
  assert.equal(xioEnvelope.signal.metadata.cellChannel, 78)
  assert.equal(currentSignals({ sessionId: id }).count, 2)
})

test("vizz and pupila proposals remain explicit and confirmation-only", () => {
  const id = sessionId("proposal")
  const result = publishSignal({
    signalId: "vizz-001",
    source: "vizz",
    sessionId: id,
    eventType: "attention.shift",
    metadata: { focusScore: 0.72, region: "canvas" },
    proposal: {
      kind: "visual.reorder",
      title: "Prioritize canvas",
      reason: "Focus moved to the canvas",
      command: "execute-host-action",
      reversible: false,
    },
  })
  assert.equal(result.signal.proposal.proposalOnly, true)
  assert.equal(result.signal.proposal.requiresConfirmation, true)
  assert.equal(result.signal.proposal.reversible, false)
  assert.equal(result.signal.proposal.command, undefined)
  assert.equal(result.surface.safety.hostActions, false)
  assert.equal(result.surface.proposals[0].source, "vizz")
  assert.equal(result.surface.status.proposalCount, 1)

  assert.throws(() => publishSignal({
    signalId: "vizz-002",
    source: "vizz",
    sessionId: id,
    sequence: 0,
    eventType: "attention.shift",
  }), /sequence must increase/)

  const pupila = publishSignal({
    source: "pupila",
    sessionId: id,
    eventType: "workflow.handoff",
    metadata: { workflow: "adobe", participantCount: 2 },
  })
  assert.equal(pupila.signal.metadata.participantCount, 2)
  assert.equal(currentSurface({ sessionId: id }).sources.pupila.state, "active")
})

test("proposal expiry is bounded and expired proposals leave the derived surface", () => {
  const now = new Date("2026-09-02T12:00:00.000Z")
  const normalized = normalizeSignal({
    source: "vizz",
    sessionId: "signal-expiry-fixed",
    eventType: "attention.shift",
    proposal: { title: "Short lived", reason: "test", expiresAt: "2030-01-01T00:00:00Z" },
  }, { now })
  assert.equal(normalized.proposal.expiresAt, "2026-09-02T12:00:45.000Z")

  const id = sessionId("expired")
  const result = publishSignal({
    source: "vizz",
    sessionId: id,
    eventType: "attention.shift",
    proposal: { title: "Expired", reason: "test", expiresAt: "2000-01-01T00:00:00Z" },
  })
  assert.equal(result.signal.proposal !== null, true)
  assert.deepEqual(currentSurface({ sessionId: id }).proposals, [])
})

test("signal history and deduplication memory stay bounded", () => {
  const id = sessionId("bounded")
  for (let sequence = 0; sequence < 100; sequence += 1) {
    publishSignal({ signalId: `bounded-${sequence}`, source: "xio", sessionId: id, sequence, eventType: "workspace.focus" })
  }
  assert.equal(currentSignals({ sessionId: id }).count, 96)
  const reintroduced = publishSignal({ signalId: "bounded-0", source: "xio", sessionId: id, sequence: 100, eventType: "workspace.focus" })
  assert.equal(reintroduced.duplicate, false)
})

test("signal session state stays bounded", () => {
  const prefix = `signal-session-bound-${Date.now()}`
  for (let index = 0; index < 40; index += 1) {
    publishSignal({ source: "xio", sessionId: `${prefix}-${index}`, sequence: 0, eventType: "workspace.focus" })
  }
  assert.ok(signalDiagnostics().sessions <= 32)
  assert.equal(currentSignals({ sessionId: `${prefix}-0` }).count, 0)
  assert.equal(currentSignals({ sessionId: `${prefix}-39` }).count, 1)
})

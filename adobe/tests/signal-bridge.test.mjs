import test from "node:test"
import assert from "node:assert/strict"
import { currentSignals, currentSurface, publishSignal } from "../src/tools/signal-bridge.mjs"

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

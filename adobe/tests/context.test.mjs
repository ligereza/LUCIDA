import test from "node:test"
import assert from "node:assert/strict"
import path from "node:path"
import { TOOLKIT_ROOT } from "../src/utils.mjs"
import { claimInsert, currentContext, publishContext, queueInsert, recordInsertResult } from "../src/tools/context.mjs"

function context(sessionId, text = "") {
  return {
    schemaVersion: 1,
    sessionId,
    host: "photoshop",
    hostVersion: "2026",
    project: { name: "CHEMSEX" },
    document: { id: "doc-1", name: "lamina-03.psd", width: 1080, height: 1440, unit: "px" },
    location: { kind: "slide", index: 3, label: "Contexto" },
    selection: { kind: "text-layer", id: "layer-1", name: "Texto principal", text, bounds: { left: 80, top: 100, right: 900, bottom: 480 } },
    layers: [{ id: "layer-1", name: "Texto principal", kind: "text", visible: true, text }],
    palette: ["#fff", "#123456"],
    occupiedRegions: [{ left: 80, top: 100, right: 900, bottom: 480 }],
    safeRegions: [{ left: 80, top: 700, right: 1000, bottom: 1320 }],
  }
}

test("context store normalizes snapshots and computes a stable hash", () => {
  const sessionId = `test-context-${Date.now()}`
  const stored = publishContext(context(sessionId, "Cuidado y contexto"))
  assert.equal(stored.schemaVersion, 1)
  assert.equal(stored.host, "photoshop")
  assert.match(stored.contextHash, /^sha256:[0-9a-f]{64}$/)
  assert.deepEqual(stored.palette, ["#fff", "#123456"])
  assert.equal(currentContext({ sessionId }).contextHash, stored.contextHash)
})

test("insert queue is session-bound and returns a completed result", () => {
  const sessionId = `test-insert-${Date.now()}`
  publishContext(context(sessionId))
  const queued = queueInsert({
    sessionId,
    asset: { assetId: "local:test", file: path.join(TOOLKIT_ROOT, "tests", "fixtures", "multi-app-asset.svg") },
    mode: "unitary",
    placement: "safe-region",
  })
  const claimed = claimInsert(sessionId)
  assert.equal(claimed.requestId, queued.requestId)
  assert.equal(claimed.state, "claimed")
  const result = recordInsertResult({ requestId: claimed.requestId, sessionId, state: "completed", data: { inserted: true } })
  assert.equal(result.state, "completed")
  assert.equal(result.data.inserted, true)
})

test("insert queue rejects an unknown context session", () => {
  assert.throws(() => queueInsert({ sessionId: `missing-${Date.now()}`, assetId: "local:test" }), /live context session/)
})

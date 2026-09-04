import test from "node:test"
import assert from "node:assert/strict"
import {
  detectWhiteSpace,
  estimateDisplayPx,
  measureTextBlock,
  proposeAdaptiveComposition,
} from "./adaptive-composition.mjs"

test("display scale converts canvas pixels to phone viewport pixels", () => {
  assert.equal(estimateDisplayPx(48, 1080, 360), 16)
  assert.equal(estimateDisplayPx(52, 1080, 390), 18.78)
})

test("text measurement wraps deterministically without changing the source text", () => {
  const text = "Cuidado y salud sexual\nUsa información clara."
  const result = measureTextBlock(text, { width: 420, role: "body", size: 48 })
  assert.equal(result.text, text)
  assert.ok(result.lineCount >= 2)
  assert.ok(result.height > 0)
  assert.equal(result.method, "deterministic-font-metrics-v1")
})

test("white-space detection returns a free region around an occupied header", () => {
  const candidates = detectWhiteSpace({
    canvas: { width: 1080, height: 1440 },
    occupiedRegions: [{ left: 0, top: 0, right: 1080, bottom: 300 }],
  })
  assert.ok(candidates.length > 0)
  assert.ok(candidates[0].bounds.top >= 300 - 45)
  assert.equal(candidates[0].source, "detected")
})

test("composition proposes readable layouts and preserves every text block", () => {
  const blocks = [
    { id: "title", role: "title", text: "CHEMSEX" },
    { id: "subtitle", role: "subtitle", text: "Información y cuidado" },
    { id: "body", role: "body", text: "Cuidarse también es una decisión. Revisa la información y busca apoyo cuando lo necesites." },
  ]
  const result = proposeAdaptiveComposition({
    document: { width: 1080, height: 1440 },
    textBlocks: blocks,
    occupiedRegions: [{ left: 0, top: 0, right: 1080, bottom: 240 }],
  })
  assert.equal(result.status, "proposed")
  assert.ok(result.proposals.length > 0)
  assert.equal(result.constraints.textPreserved, true)
  assert.equal(result.typography.bodyRange.min, 44)
  const proposal = result.proposals[0]
  assert.ok(proposal.metrics.bodySourcePx >= 44)
  assert.equal(proposal.pages[0].textPreserved, blocks.map((block) => block.text).join(""))
})

test("dense content generates a split proposal instead of shrinking below the floor", () => {
  const text = Array.from({ length: 160 }, (_, index) => `palabra${index}`).join(" ")
  const result = proposeAdaptiveComposition({
    document: { width: 1080, height: 1440 },
    textBlocks: [{ id: "body", role: "body", text }],
  })
  assert.ok(result.proposals.some((proposal) => proposal.pages.length > 1))
  assert.ok(result.proposals.every((proposal) => proposal.metrics.bodySourcePx >= 44))
})

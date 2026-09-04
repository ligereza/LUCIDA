import test from "node:test"
import assert from "node:assert/strict"
import { analyzeContext } from "../src/tools/context-analysis.mjs"

test("context analysis exposes adaptive composition proposals", () => {
  const result = analyzeContext({
    document: { width: 1080, height: 1440 },
    selection: { name: "Texto principal", text: "Información y cuidado" },
    layers: [
      { id: "title", name: "Titulo", kind: "text", visible: true, text: "Información" },
      { id: "body", name: "Texto principal", kind: "text", visible: true, text: "Cuidarse también es una decisión." },
      { id: "illustration", name: "Illustration", kind: "image", visible: true, bounds: { left: 680, top: 500, right: 1000, bottom: 1050 } },
    ],
    occupiedRegions: [{ left: 0, top: 0, right: 1080, bottom: 220 }],
    safeRegions: [],
  })
  assert.equal(result.composition.status, "proposed")
  assert.equal(result.composition.constraints.textPreserved, true)
  assert.ok(result.composition.proposals.length > 0)
  assert.ok(result.composition.proposals.every((proposal) => proposal.metrics.bodySourcePx >= 44))
  assert.equal(result.composition.typography.displayFormula, "sourcePx * previewWidth / canvasWidth")
})

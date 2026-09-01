import test from "node:test"
import assert from "node:assert/strict"
import { analyzeContext } from "../src/tools/context-analysis.mjs"

test("context analysis detects content and ranks a free region", () => {
  const result = analyzeContext({
    document: { width: 1000, height: 1000 },
    selection: { text: "Cuidado y salud sexual" },
    occupiedRegions: [{ left: 0, top: 0, right: 1000, bottom: 300 }],
    palette: ["#112233", "#fefefe"],
  })
  assert.equal(result.content.primaryTopic.id, "care")
  assert.ok(result.content.visualTerms.includes("health"))
  assert.ok(result.layout.blankAreas[0].areaRatio > 0.5)
  assert.equal(result.layout.placementCandidates[0].source, "detected")
  assert.equal(result.palette.available, true)
  assert.equal(result.suggestions.some((item) => item.type === "placement"), true)
})

test("explicit host safe regions take priority over detected blank regions", () => {
  const result = analyzeContext({
    document: { width: 1000, height: 1000 },
    layers: [{ visible: true, bounds: { left: 0, top: 0, right: 1000, bottom: 900 } }],
    safeRegions: [{ left: 50, top: 50, right: 200, bottom: 200 }],
  })
  assert.equal(result.layout.placementCandidates[0].source, "host")
  assert.deepEqual(result.layout.placementCandidates[0].bounds, { left: 50, top: 50, right: 200, bottom: 200 })
})

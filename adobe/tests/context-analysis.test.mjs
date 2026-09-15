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
  assert.equal(result.layout.basis, "explicit-regions")
  assert.match(result.layout.note, /no analiza transparencia/)
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
  assert.equal(result.layout.basis, "host-safe-regions")
  assert.deepEqual(result.layout.placementCandidates[0].bounds, { left: 50, top: 50, right: 200, bottom: 200 })
})

test("a full-canvas foreground layer is occupied, not an invented blank area", () => {
  const result = analyzeContext({
    document: { width: 1000, height: 1000 },
    layers: [{ id: "hero", name: "Hero image", kind: "image", visible: true, bounds: { left: 0, top: 0, right: 1000, bottom: 1000 } }],
  })
  assert.equal(result.layout.occupiedRatio, 1)
  assert.equal(result.layout.blankRatio, 0)
  assert.deepEqual(result.layout.blankAreas, [])
  assert.deepEqual(result.layout.placementCandidates, [])
})

test("missing spatial evidence is unknown, not a whole-canvas blank region", () => {
  const result = analyzeContext({ document: { width: 1000, height: 1000 }, selection: { text: "flyer" } })
  assert.equal(result.layout.basis, "unavailable")
  assert.equal(result.layout.blankRatio, null)
  assert.equal(result.layout.occupiedRatio, null)
  assert.deepEqual(result.layout.blankAreas, [])
  assert.deepEqual(result.layout.placementCandidates, [])
  assert.match(result.layout.note, /bounds espaciales suficientes/)
})

test("low-detail pixel samples suggest quietness without claiming blank space", () => {
  const detail = Array(24 * 24).fill(0.9)
  for (let y = 0; y < 24; y += 1) {
    for (let x = 0; x < 12; x += 1) detail[y * 24 + x] = 0.01
  }
  const result = analyzeContext({
    document: { width: 1080, height: 1440 },
    selection: { text: "Cuidado y salud sexual" },
    visualGrid: {
      columns: 24,
      rows: 24,
      detail,
      alphaCoverage: Array(24 * 24).fill(1),
      sampleWidth: 144,
      sampleHeight: 192,
      historyStateId: 7,
      method: "edge-alpha-grid-v1",
    },
  })

  assert.equal(result.layout.basis, "visual-sample")
  assert.equal(result.layout.visualSampleAvailable, true)
  assert.equal(result.layout.blankRatio, null)
  assert.deepEqual(result.layout.blankAreas, [])
  assert.equal(result.layout.placementCandidates[0].source, "visual-quietness")
  assert.match(result.suggestions.find((item) => item.type === "placement").reason, /no implica área vacía/)
})

test("an explicitly named full-canvas background remains available for overlay placement", () => {
  const result = analyzeContext({
    document: { width: 1000, height: 1000 },
    layers: [{ id: "background", name: "Background", kind: "image", visible: true, bounds: { left: 0, top: 0, right: 1000, bottom: 1000 } }],
  })
  assert.equal(result.layout.occupiedRatio, 0)
  assert.equal(result.layout.placementCandidates[0].source, "detected")
})

test("overlapping occupied regions use their union area for ratios", () => {
  const result = analyzeContext({
    document: { width: 1000, height: 1000 },
    occupiedRegions: [
      { left: 0, top: 0, right: 600, bottom: 600 },
      { left: 400, top: 400, right: 1000, bottom: 1000 },
    ],
  })
  assert.equal(result.layout.occupiedArea, 680000)
  assert.equal(result.layout.occupiedRatio, 0.68)
  assert.equal(result.layout.blankRatio, 0.32)
  assert.ok(result.layout.blankAreas.length > 0)
})

import test from "node:test"
import assert from "node:assert/strict"
import { integrationPlan, integrationScriptingMap, integrationSources, validateIntegration } from "../src/tools/integration.mjs"

test("integration inventory resolves local sources without scanning repositories", async () => {
  const result = await integrationSources()
  assert.equal(result.sources.length, 9)
  assert.ok(result.sources.filter((source) => source.required !== false).every((source) => source.exists))
  assert.ok(result.sources.filter((source) => source.required === false).some((source) => !source.exists))
  assert.equal(result.sources.find((source) => source.id === "thi-ng-umbrella")?.required, false)
  assert.ok(result.sources.find((source) => source.id === "blender-adapter")?.entrypointStatus.some((entry) => entry.path === "agent_blender.py" && entry.exists))
})

test("integration contracts and scripting surfaces validate", async () => {
  const result = await validateIntegration()
  assert.equal(result.ok, true)
  assert.equal(result.issues.length, 0)
  const map = await integrationScriptingMap()
  assert.ok(map.contracts.asset.required.includes("id"))
  assert.ok(map.surfaces.find((surface) => surface.id === "geometry-nodes").operations.includes("blender.render-cycles"))
})

test("integration plan keeps Adobe, Geometry Nodes and Cycles explicit", async () => {
  const result = await integrationPlan({ source: "chemsex", storyboard: "projects/chemsex/storyboard.json" })
  assert.equal(result.status, "planned")
  assert.deepEqual(result.constraints, { useAdobe: true, useGeometryNodes: true, useCycles: true })
  assert.match(result.stages.find((stage) => stage.id === "support-runtimes").operation, /workflow.effect-retry/)
  assert.equal(result.stages.find((stage) => stage.id === "render").operation, "blender.render-cycles")
})

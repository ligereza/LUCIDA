import test from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { TOOLKIT_ROOT } from "../src/utils.mjs"
import { WEB_RUN_TOOLS } from "../src/dispatcher.mjs"

test("LUCIDA Adobe layout and manifests are present", async () => {
  for (const entry of ["generic-interface-layer", "companion", "adobe-context-shelf", "contracts", "adapters", "src", "tools", "tests", "docs", "ICONOS", "jobs", "logs", "scripts", "README.md", "registry.json"]) {
    await fs.access(path.join(TOOLKIT_ROOT, entry))
  }
  await fs.access(path.join(TOOLKIT_ROOT, "contracts", "stable.mjs"))
  const registry = JSON.parse(await fs.readFile(path.join(TOOLKIT_ROOT, "registry.json"), "utf8"))
  const adobeSchema = JSON.parse(await fs.readFile(path.join(TOOLKIT_ROOT, "adapters", "adobe", "command-schema.json"), "utf8"))
  assert.ok(Array.isArray(registry.tools))
  assert.ok(adobeSchema.properties.app.enum.includes("premiere"))
  const ids = new Set(registry.tools.map((tool) => tool.id))
  for (const webTool of WEB_RUN_TOOLS) assert.ok(ids.has(webTool), `Web dispatcher tool missing from registry: ${webTool}`)
  assert.equal(WEB_RUN_TOOLS.has("adobe.after-effects-render"), false)
  for (const required of [
    "svg.create", "svg.embed-image", "svg.rasterize", "svg.vectorize", "svg.animate", "svg.particles",
    "svg.validate", "svg.preview", "svg.thi-ng-geom", "data.chart", "data.d3-chart", "data.animate", "scene3d.create", "math.stdlib-stats", "workflow.rxjs-events", "workflow.effect-retry", "image.split", "blender.create-scene",
    "blender.render", "blender.import-svg", "blender.import-glb",
    "blender.export-glb", "adobe.enqueue", "photoshop.separate-objects", "adobe.consume", "workflow.image-to-svg-preview",
    "workflow.image-to-svg-blender-illustrator",
    "workflow.document-to-animated-post", "workflow.multi-app-composition", "integration.sources", "integration.scripting-map", "integration.validate", "integration.plan",
  ]) assert.ok(ids.has(required), `Missing registry capability: ${required}`)
  await fs.access(path.join(TOOLKIT_ROOT, "ICONOS", "CHEMSEX", "manifest.json"))
  for (const slide of ["1", "2", "3", "4", "5", "6", "7", "8"]) {
    await fs.access(path.join(TOOLKIT_ROOT, "ICONOS", "CHEMSEX", slide))
  }
  await fs.access(path.join(TOOLKIT_ROOT, "ICONOS", "CHEMSEX", "mini-icons"))
})

test("Active runtime does not depend on extracted core internals", async () => {
  const signalBridge = await fs.readFile(path.join(TOOLKIT_ROOT, "src", "tools", "signal-bridge.mjs"), "utf8")
  const sharedContracts = await fs.readFile(path.join(TOOLKIT_ROOT, "contracts", "stable.mjs"), "utf8")
  const genericContracts = await fs.readFile(path.join(TOOLKIT_ROOT, "generic-interface-layer", "core", "contracts", "stable.mjs"), "utf8")
  assert.doesNotMatch(signalBridge, /generic-interface-layer/)
  assert.match(signalBridge, /\.\.\/\.\.\/contracts\/stable\.mjs/)
  assert.match(sharedContracts, /export function stable\(value\)/)
  assert.match(sharedContracts, /export function deterministicId\(prefix, value\)/)
  assert.equal(sharedContracts.replace(/\r\n/g, "\n"), genericContracts.replace(/\r\n/g, "\n"))
})

import test from "node:test"
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { spawn } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = fileURLToPath(new URL("..", import.meta.url))

function checkSyntax(source) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ["--check", "-"], { cwd: root })
    let stderr = ""
    child.stderr.on("data", (chunk) => { stderr += chunk })
    child.on("error", reject)
    child.on("close", (code) => code === 0 ? resolve() : reject(new Error(stderr)))
    readFile(source, "utf8").then((text) => child.stdin.end(text.replace(/^#include .*$/gm, "")), reject)
  })
}

test("Adobe host consumers have valid JavaScript syntax", async () => {
  for (const relative of [
    "adapters/adobe/json-compat.jsxinc",
    "adapters/adobe/illustrator/agent.jsx",
    "adapters/adobe/photoshop/agent.jsx",
    "adapters/adobe/after-effects/agent.jsx",
    "adapters/adobe/photoshop/agent.psjs",
    "adapters/adobe/premiere/agent.jsx",
  ]) {
    await checkSyntax(path.join(root, relative))
  }
  assert.ok(true)
})

test("Adobe adapters do not depend on the retired checkout path", async () => {
  for (const relative of [
    "adapters/adobe/illustrator/agent.jsx",
    "adapters/adobe/photoshop/agent.jsx",
    "adapters/adobe/photoshop/agent.psjs",
    "adapters/adobe/after-effects/agent.jsx",
    "adapters/adobe/premiere/agent.jsx",
  ]) {
    const source = await readFile(path.join(root, relative), "utf8")
    assert.equal(source.includes("C:/IA/LUCIDA/adobe") || source.includes("C:\\IA\\LUCIDA\\adobe"), false)
  }
})

test("Photoshop UXP contract keeps the bridge local and polling visible", async () => {
  const manifest = JSON.parse(await readFile(path.join(root, "adobe-context-shelf/photoshop-uxp/manifest.json"), "utf8"))
  const source = await readFile(path.join(root, "adobe-context-shelf/photoshop-uxp/index.js"), "utf8")
  const adapter = await readFile(path.join(root, "adapters/adobe/photoshop/agent.psjs"), "utf8")
  assert.equal(manifest.manifestVersion, 5)
  assert.equal(manifest.host.app, "PS")
  assert.equal(manifest.host.minVersion, "23.3.0")
  assert.deepEqual(manifest.requiredPermissions.network.domains, ["http://127.0.0.1:47921"])
  assert.match(adapter, /getPluginFolder\(\)/)
  assert.match(source, /show\(\)\s*\{\s*startPolling\(\)/)
  assert.match(source, /hide\(\)\s*\{\s*stopPolling\(\)/)
  assert.match(source, /destroy\(\)\s*\{\s*stopPolling\(\)/)
})

test("Photoshop UXP does not forward local document paths", async () => {
  const source = await readFile(path.join(root, "adobe-context-shelf/photoshop-uxp/index.js"), "utf8")
  assert.match(source, /path: null/)
  assert.doesNotMatch(source, /path:\s*documentValue\.path/)
})

test("Photoshop generated output names stay ASCII", async () => {
  const psjs = await readFile(path.join(root, "adapters/adobe/photoshop/agent.psjs"), "utf8")
  const jsx = await readFile(path.join(root, "adapters/adobe/photoshop/agent.jsx"), "utf8")
  assert.match(psjs, /replace\(\/\[\^a-z0-9 _-\]\//)
  assert.match(jsx, /replace\(\/\[\^a-z0-9 _-\]\//)
})

test("Companion applies a local-only content policy and realpath asset guard", async () => {
  const html = await readFile(path.join(root, "companion/index.html"), "utf8")
  const main = await readFile(path.join(root, "companion/main.cjs"), "utf8")
  assert.match(html, /Content-Security-Policy/)
  assert.match(html, /connect-src http:\/\/127\.0\.0\.1:47921/)
  assert.match(main, /realpathSync/)
  assert.match(main, /Asset path is outside the package/)
})

test("Project companion keeps slide text visible without visual groups", async () => {
  const source = await readFile(path.join(root, "companion/renderer.js"), "utf8")
  assert.match(source, /function projectTextMarkup\(text\)/)
  assert.match(source, /Texto de la lámina no disponible/)
  assert.match(source, /\$\{groupMarkup \|\| emptyMarkup\}/)
  assert.equal(source.includes("return groupMarkup ?"), false)
})

test("Project companion renders indexed collections", async () => {
  const source = await readFile(path.join(root, "companion/renderer.js"), "utf8")
  assert.match(source, /projectInventory\.collections/)
  assert.match(source, /project-collection/)
  assert.match(source, /collection\.variants/)
  assert.match(source, /projectInventory\.indexErrors/)
  assert.match(source, /project-index-errors/)
})

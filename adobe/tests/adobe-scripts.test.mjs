import test from "node:test"
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { spawn } from "node:child_process"
import vm from "node:vm"
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

test("Photoshop UXP bounds layer snapshots and bridge retries", async () => {
  const source = await readFile(path.join(root, "adobe-context-shelf/photoshop-uxp/index.js"), "utf8")
  assert.match(source, /const MAX_LAYERS = 200/)
  assert.match(source, /const MAX_LAYER_DEPTH = 64/)
  assert.match(source, /const MAX_LAYER_TEXT = 1000/)
  assert.match(source, /const BRIDGE_TIMEOUT_MS = 3000/)
  assert.match(source, /const BRIDGE_LONG_TIMEOUT_MS = 30000/)
  assert.match(source, /function layersOf\(collection, limit = MAX_LAYERS\)/)
  assert.match(source, /nextContextAttemptAt = Date\.now\(\) \+ BRIDGE_RETRY_MS/)
  assert.match(source, /nextInsertAttemptAt = Date\.now\(\) \+ BRIDGE_RETRY_MS/)
  assert.match(source, /lastBridgeErrorAt/)
  assert.match(source, /new AbortController\(\)/)
  assert.match(source, /controller\.abort\(\)/)
})

test("Photoshop generated output names stay ASCII", async () => {
  const psjs = await readFile(path.join(root, "adapters/adobe/photoshop/agent.psjs"), "utf8")
  const jsx = await readFile(path.join(root, "adapters/adobe/photoshop/agent.jsx"), "utf8")
  const uxp = await readFile(path.join(root, "adobe-context-shelf/photoshop-uxp/index.js"), "utf8")
  assert.match(psjs, /replace\(\/\[\^a-z0-9 _-\]\//)
  assert.match(jsx, /replace\(\/\[\^a-z0-9 _-\]\//)
  assert.match(uxp, /function asciiName\(value, fallback\)/)
  assert.match(uxp, /pasted\.name = isAnalysisLayer \? "CS - analysis"/)
})

test("Photoshop UXP queue wraps document mutations in modal scopes", async () => {
  const source = await readFile(path.join(root, "adapters/adobe/photoshop/agent.psjs"), "utf8")
  assert.match(source, /async function importSvg[\s\S]*core\.executeAsModal\([\s\S]*app\.open\(source\)/)
  assert.match(source, /core\.executeAsModal\(\(\) => saveDocument\(document, options\.psdOutput\)/)
  assert.match(source, /core\.executeAsModal\(\(\) => document\.closeWithoutSaving\(\)/)
})

test("Companion applies a local-only content policy and realpath asset guard", async () => {
  const html = await readFile(path.join(root, "companion/index.html"), "utf8")
  const main = await readFile(path.join(root, "companion/main.cjs"), "utf8")
  assert.match(html, /Content-Security-Policy/)
  assert.match(html, /connect-src http:\/\/127\.0\.0\.1:47921/)
  assert.match(main, /realpathSync/)
  assert.match(main, /Asset path is outside the package/)
})

test("Companion proxies remote SVG previews through an HTTPS host allowlist", async () => {
  const main = await readFile(path.join(root, "companion/main.cjs"), "utf8")
  const preload = await readFile(path.join(root, "companion/preload.cjs"), "utf8")
  const renderer = await readFile(path.join(root, "companion/renderer.js"), "utf8")
  assert.match(main, /REMOTE_PREVIEW_HOSTS/)
  assert.match(main, /MAX_REMOTE_PREVIEW_BYTES = 1_000_000/)
  assert.match(main, /parsed\.protocol !== "https:"/)
  assert.match(main, /Remote preview response is not an allowed SVG/)
  assert.match(preload, /previewRemote\(url\)/)
  assert.match(renderer, /previewRemote\(item\.previewUrl\)/)
  assert.doesNotMatch(renderer, /: item\.previewUrl\s*$/m)
})

test("Companion bounds bridge response accumulation", async () => {
  const main = await readFile(path.join(root, "companion/main.cjs"), "utf8")
  assert.match(main, /MAX_BRIDGE_RESPONSE_BYTES = 4_000_000/)
  assert.match(main, /bytes \+= Buffer\.byteLength\(chunk\)/)
  assert.match(main, /Bridge response is too large/)
})

test("Companion keeps bridge health, renderer routes and error handlers aligned", async () => {
  const main = await readFile(path.join(root, "companion/main.cjs"), "utf8")
  const renderer = await readFile(path.join(root, "companion/renderer.js"), "utf8")
  const bridgeStatus = main.slice(main.indexOf("function bridgeStatus()"), main.indexOf("function startBridgeProcess()"))
  assert.match(main, /new Promise\(\(resolve\) => \{/)
  assert.doesNotMatch(bridgeStatus, /response\.on\("error", reject\)/)
  assert.match(main, /"\/analysis\/layer"/)
  assert.match(renderer, /request\("\/analysis\/layer"/)
})

test("Companion labels textual matches, related concepts and geometric-space limits", async () => {
  const renderer = await readFile(path.join(root, "companion/renderer.js"), "utf8")
  assert.match(renderer, /appendMatchEvidence\(results\)/)
  assert.match(renderer, /matchedTokenCount/)
  assert.match(renderer, /relatedTokenCount/)
  assert.match(renderer, /Coincidencia textual en metadatos/)
  assert.match(renderer, /relacionados, no equivalentes/)
  assert.match(renderer, /bounds; sin análisis de transparencia\/píxeles/)
  assert.match(renderer, /hueco geométrico/)
  assert.match(renderer, /Búsqueda visual MobileCLIP no activa/)
})

test("Companion renders weak semantic relations as related, not exact", async () => {
  const source = await readFile(path.join(root, "companion/renderer.js"), "utf8")
  const start = source.indexOf("function appendMatchEvidence(results) {")
  const end = source.indexOf("\nasync function loadPreview", start)
  assert.ok(start >= 0 && end > start)
  const functionSource = source.slice(start, end)
  const appended = []
  const meta = { title: "", append(...nodes) { appended.push(...nodes) } }
  const card = { dataset: { assetId: "protection-symbol" }, querySelector: () => meta }
  const results = [{
    assetId: "protection-symbol", matchCoverage: 0, matchedTokenCount: 0,
    relatedTokenCount: 1, queryTokenCount: 1,
    reasons: ["coincide con: condon ~ protection (relacionado)"],
  }]
  const rootElement = { querySelectorAll: () => [card] }
  const context = {
    $: (selector) => selector === "#results" ? rootElement : null,
    document: { createElement: (tagName) => ({ tagName, textContent: "" }) },
    results,
  }
  vm.runInNewContext(`${functionSource}\nappendMatchEvidence(results);`, context)
  assert.match(meta.title, /Coincidencia textual en metadatos/)
  assert.match(meta.title, /0\/1 términos/)
  assert.equal(appended[1].textContent, "Texto 0/1 + 1 relacionado, no equivalente · condon ~ protection (relacionado)")
})

test("Companion distinguishes unknown geometry from no geometric gap", async () => {
  const source = await readFile(path.join(root, "companion/renderer.js"), "utf8")
  const start = source.indexOf("function showContext(context) {")
  const end = source.indexOf("\nfunction renderSignalSurface", start)
  assert.ok(start >= 0 && end > start)
  const functionSource = source.slice(start, end)
  const makeView = (input) => {
    const nodes = new Map(["#document", "#selection", "#copy", "#analysis"].map((selector) => [selector, { textContent: "" }]))
    vm.runInNewContext(`${functionSource}\nshowContext(input);`, {
      $: (selector) => nodes.get(selector),
      renderSelectionScope() {},
      input,
    })
    return nodes.get("#analysis").textContent
  }
  const base = { document: { name: "FLYERS.psb" }, selection: { name: "MAGNESIO" }, analysis: { content: { primaryTopic: { label: "suplementos" } }, layers: { score: 80 } } }
  const bounded = makeView({ ...base, analysis: { ...base.analysis, layout: { basis: "visible-layer-bounds", placementCandidates: [] } } })
  assert.match(bounded, /no se encontró un hueco en los bounds/)
  assert.match(bounded, /sin análisis de transparencia\/píxeles/)
  const unavailable = makeView({ ...base, analysis: { ...base.analysis, layout: { basis: "unavailable", placementCandidates: [] } } })
  assert.match(unavailable, /sin bounds espaciales suficientes/)
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

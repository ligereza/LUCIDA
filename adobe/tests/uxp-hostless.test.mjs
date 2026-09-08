import test from "node:test"
import assert from "node:assert/strict"
import vm from "node:vm"
import { readFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = fileURLToPath(new URL("..", import.meta.url))

function element() {
  return { className: "", textContent: "", dataset: {}, addEventListener() {} }
}

test("Photoshop UXP producer bounds a hostile document snapshot", async () => {
  const source = await readFile(path.join(root, "adobe-context-shelf/photoshop-uxp/index.js"), "utf8")
  const elements = new Map(["#status", "#documentName", "#selectionName", "#selectionText", "#log", "#refresh", "#send"].map((id) => [id, element()]))
  const layers = Array.from({ length: 260 }, (_, index) => ({
    id: `layer-${index}`,
    name: `Layer ${index} ${"x".repeat(400)}`,
    kind: "text",
    visible: true,
    bounds: { left: index, top: index, right: index + 10, bottom: index + 10 },
    textItem: { contents: "y".repeat(3_000) },
  }))
  const app = {
    activeDocument: { id: "doc-1", name: "sample.psd", width: 1_920, height: 1_080, layers },
    activeLayers: [layers[0]],
  }
  const requests = []
  const entrypoints = { setup(value) { this.panel = value.panels.contextShelf } }
  const fakeFetch = async (url, options = {}) => {
    requests.push({ url, options })
    return {
      ok: true,
      status: 200,
      async json() { return url.endsWith("/context") ? { contextHash: "sha256:test" } : { request: null } },
    }
  }
  const context = vm.createContext({
    AbortController,
    clearInterval,
    clearTimeout,
    console,
    document: { querySelector(selector) { return elements.get(selector) || element() } },
    fetch: fakeFetch,
    require(name) {
      if (name === "photoshop") return { app, action: { addNotificationListener() {} }, core: {} }
      if (name === "uxp") return { entrypoints, storage: {} }
      throw new Error(`Unexpected module: ${name}`)
    },
    setInterval,
    setTimeout,
  })
  vm.runInContext(source, context, { filename: "photoshop-uxp/index.js" })
  entrypoints.panel.show()
  await new Promise((resolve) => setImmediate(resolve))
  entrypoints.panel.hide()

  const contextRequest = requests.find((request) => request.url.endsWith("/context"))
  assert.ok(contextRequest)
  const payload = JSON.parse(contextRequest.options.body)
  assert.equal(payload.document.path, null)
  assert.equal(payload.layers.length, 200)
  assert.equal(payload.layers[0].text.length, 1_000)
  assert.ok(contextRequest.options.signal)
  assert.equal(requests.some((request) => request.url.includes("/insert/next")), true)
})

test("Photoshop UXP converts a hung context request into a recoverable timeout", async () => {
  const source = await readFile(path.join(root, "adobe-context-shelf/photoshop-uxp/index.js"), "utf8")
  const elements = new Map(["#status", "#documentName", "#selectionName", "#selectionText", "#log", "#refresh", "#send"].map((id) => [id, element()]))
  const app = { activeDocument: { id: "doc-1", name: "sample.psd", width: 100, height: 100, layers: [] }, activeLayers: [] }
  const entrypoints = { setup(value) { this.panel = value.panels.contextShelf } }
  const fakeFetch = async (url, options = {}) => {
    if (url.endsWith("/insert/next")) return { ok: true, status: 200, async json() { return { request: null } } }
    if (options.signal?.aborted) return Promise.reject(new Error("aborted"))
    return new Promise((resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true })
    })
  }
  const context = vm.createContext({
    AbortController,
    clearInterval() {},
    clearTimeout() {},
    console,
    document: { querySelector(selector) { return elements.get(selector) || element() } },
    fetch: fakeFetch,
    require(name) {
      if (name === "photoshop") return { app, action: { addNotificationListener() {} }, core: {} }
      if (name === "uxp") return { entrypoints, storage: {} }
      throw new Error(`Unexpected module: ${name}`)
    },
    setInterval() { return 1 },
    setTimeout(callback, delay) {
      if (delay === 3_000) callback()
      return 1
    },
  })
  vm.runInContext(source, context, { filename: "photoshop-uxp-timeout.js" })
  entrypoints.panel.show()
  await new Promise((resolve) => setImmediate(resolve))
  entrypoints.panel.hide()

  assert.equal(elements.get("#status").textContent, "offline")
  assert.match(elements.get("#log").textContent, /timed out after 3000ms/)
})

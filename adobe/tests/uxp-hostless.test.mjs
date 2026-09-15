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

test("Photoshop UXP sends only a bounded pixel summary and reuses the history-state cache", async () => {
  const source = await readFile(path.join(root, "adobe-context-shelf/photoshop-uxp/index.js"), "utf8")
  const listeners = new Map()
  const refresh = {
    ...element(),
    addEventListener(type, handler) { listeners.set(`refresh:${type}`, handler) },
  }
  const elements = new Map(["#status", "#documentName", "#selectionName", "#selectionText", "#log", "#send"].map((id) => [id, element()]))
  elements.set("#refresh", refresh)
  const app = {
    activeDocument: { id: 7, name: "flyer.psd", width: 1080, height: 1440, activeHistoryState: { id: 11 }, layers: [] },
    activeLayers: [],
  }
  const requests = []
  const imagingCalls = []
  let disposed = 0
  const imageData = {
    width: 2,
    height: 2,
    components: 3,
    componentSize: 8,
    hasAlpha: false,
    async getData(options) {
      assert.equal(options.chunky, true)
      return new Uint8Array([0, 0, 0, 255, 255, 255, 0, 0, 0, 255, 255, 255])
    },
    dispose() { disposed += 1 },
  }
  const imaging = {
    async getPixels(options) {
      imagingCalls.push(options)
      return { imageData }
    },
  }
  const entrypoints = { setup(value) { this.panel = value.panels.contextShelf } }
  const fakeFetch = async (url, options = {}) => {
    requests.push({ url, options })
    return { ok: true, status: 200, async json() { return url.endsWith("/context") ? { contextHash: "sha256:visual" } : { request: null } } }
  }
  const context = vm.createContext({
    AbortController,
    clearInterval,
    clearTimeout,
    console,
    document: { querySelector(selector) { return elements.get(selector) || element() } },
    fetch: fakeFetch,
    require(name) {
      if (name === "photoshop") return { app, action: { addNotificationListener() {} }, core: {}, imaging }
      if (name === "uxp") return { entrypoints, storage: {} }
      throw new Error(`Unexpected module: ${name}`)
    },
    setInterval,
    setTimeout,
  })
  vm.runInContext(source, context, { filename: "photoshop-uxp-visual-grid.js" })
  entrypoints.panel.show()
  await new Promise((resolve) => setImmediate(resolve))
  listeners.get("refresh:click")()
  await new Promise((resolve) => setImmediate(resolve))
  entrypoints.panel.hide()

  const contextRequests = requests.filter((request) => request.url.endsWith("/context"))
  const payload = JSON.parse(contextRequests[0].options.body)
  assert.equal(contextRequests.length, 2)
  assert.equal(imagingCalls.length, 1)
  assert.equal(imagingCalls[0].documentID, 7)
  assert.equal(imagingCalls[0].historyStateID, 11)
  assert.equal(imagingCalls[0].targetSize.height, 192)
  assert.equal(imagingCalls[0].componentSize, 8)
  assert.equal(payload.visualGrid.columns, 24)
  assert.equal(payload.visualGrid.rows, 24)
  assert.equal(payload.visualGrid.detail.length, 576)
  assert.equal(payload.visualGrid.sampleWidth, 2)
  assert.equal(payload.visualGrid.sampleHeight, 2)
  assert.equal(payload.visualGrid.historyStateId, 11)
  assert.equal(payload.visualGrid.method, "edge-alpha-grid-v1")
  assert.equal(disposed, 1)
  assert.equal(JSON.stringify(payload).includes("255,255,255"), false)
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

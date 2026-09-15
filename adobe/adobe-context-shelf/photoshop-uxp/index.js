const { app, action, core, imaging } = require("photoshop")
const { entrypoints } = require("uxp")
const { storage } = require("uxp")

const BRIDGE = "http://127.0.0.1:47921"
const SESSION_ID = `photoshop-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
const MAX_LAYERS = 200
const MAX_LAYER_DEPTH = 64
const MAX_LAYER_TEXT = 1000
const VISUAL_SAMPLE_SIZE = 192
const VISUAL_SAMPLE_INTERVAL_MS = 5000
const VISUAL_SAMPLE_COLUMNS = 24
const VISUAL_SAMPLE_ROWS = 24
const CONTEXT_POLL_MS = 1200
const INSERT_POLL_MS = 700
const BRIDGE_RETRY_MS = 5000
const BRIDGE_TIMEOUT_MS = 3000
const BRIDGE_LONG_TIMEOUT_MS = 30000
let syncing = false
let consuming = false
let lastContextSignature = null
let bridgeOnline = false
let contextPoller = null
let insertPoller = null
let nextContextAttemptAt = 0
let nextInsertAttemptAt = 0
let lastBridgeError = null
let lastBridgeErrorAt = 0
let visualSampleCacheKey = null
let visualSampleCache = null
let visualSampleAttemptAt = 0
let visualSampleInFlight = false

entrypoints.setup({
  panels: {
    contextShelf: {
      show() { startPolling() },
      hide() { stopPolling() },
      destroy() { stopPolling() },
    },
  },
})

function log(value) {
  const target = document.querySelector("#log")
  if (target) target.textContent = String(value?.message || value)
}

function logBridgeError(prefix, error) {
  const message = `${prefix}: ${error?.message || error}`
  const now = Date.now()
  if (message === lastBridgeError && now - lastBridgeErrorAt < BRIDGE_RETRY_MS) return
  lastBridgeError = message
  lastBridgeErrorAt = now
  log(message)
}

function number(value) {
  const raw = value && typeof value === "object" && "value" in value ? value.value : value
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

function asciiName(value, fallback) {
  const normalized = String(value || "")
    .normalize("NFKD")
    .replace(/[^\x00-\x7F]/g, "")
    .replace(/[^a-zA-Z0-9 _-]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 160)
  return normalized || fallback
}

function plainBounds(value) {
  if (!value) return null
  const result = { left: number(value.left), top: number(value.top), right: number(value.right), bottom: number(value.bottom) }
  return Object.values(result).every((item) => item !== null) ? result : null
}

function layerText(layer) {
  try {
    return layer?.textItem?.contents ? String(layer.textItem.contents).slice(0, MAX_LAYER_TEXT) : null
  } catch (_) { return null }
}

function layersOf(collection, limit = MAX_LAYERS) {
  try {
    const result = []
    for (const layer of collection || []) {
      result.push(layer)
      if (result.length >= limit) break
    }
    return result
  } catch (_) {
    try { return Array.from(collection || []).slice(0, limit) } catch (error) { return [] }
  }
}

function flattenLayers(collection, output = [], parentId = null, depth = 0) {
  if (output.length >= MAX_LAYERS || depth > MAX_LAYER_DEPTH) return output
  for (const [index, layer] of layersOf(collection, MAX_LAYERS - output.length).entries()) {
    if (output.length >= MAX_LAYERS) break
    output.push({ layer, parentId, depth, index })
    if (layer.layers && depth < MAX_LAYER_DEPTH) {
      flattenLayers(layer.layers, output, layer?.id == null ? null : String(layer.id), depth + 1)
    }
  }
  return output
}

function serialiseLayer(layer, metadata = {}) {
  return {
    id: layer?.id == null ? null : String(layer.id).slice(0, 160),
    parentId: metadata.parentId == null ? null : String(metadata.parentId),
    depth: Number.isFinite(Number(metadata.depth)) ? Number(metadata.depth) : 0,
    order: Number.isFinite(Number(metadata.order)) ? Number(metadata.order) : null,
    name: layer?.name ? String(layer.name).slice(0, 300) : null,
    kind: layer?.kind ? String(layer.kind).slice(0, 120) : null,
    visible: layer?.visible !== false,
    locked: layer?.allLocked === true || layer?.locked === true,
    opacity: number(layer?.opacity),
    bounds: plainBounds(layer?.bounds),
    text: layerText(layer),
  }
}

function colorHex(value) {
  try {
    const rgb = value?.rgb || value
    const red = number(rgb?.red)
    const green = number(rgb?.green)
    const blue = number(rgb?.blue)
    if ([red, green, blue].some((channel) => channel === null)) return null
    return `#${[red, green, blue].map((channel) => Math.max(0, Math.min(255, Math.round(channel))).toString(16).padStart(2, "0")).join("")}`
  } catch (_) { return null }
}

function paletteOf(layers) {
  const colors = []
  for (const layer of layers) {
    for (const candidate of [
      (() => { try { return layer?.textItem?.color } catch (_) { return null } })(),
      (() => { try { return layer?.fillColor } catch (_) { return null } })(),
      (() => { try { return layer?.strokeColor } catch (_) { return null } })(),
    ]) {
      const hex = colorHex(candidate)
      if (hex && !colors.includes(hex)) colors.push(hex)
    }
  }
  return colors.slice(0, 12)
}

function slideIndexFrom(...values) {
  for (const value of values) {
    const match = String(value || "").match(/(?:lamina|lámina|slide)[\s_-]*(\d{1,2})/i)
    if (match) return Number(match[1])
  }
  return null
}

function pixelLuminance(data, offset) {
  return (0.2126 * data[offset] + 0.7152 * data[offset + 1] + 0.0722 * data[offset + 2]) / 255
}

function visualGridFromPixels(imageData, data, historyStateId) {
  const width = Number(imageData?.width)
  const height = Number(imageData?.height)
  const components = Number(imageData?.components)
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1) return null
  if (components !== 3 && components !== 4) return null
  if (Number(imageData.componentSize) !== 8 || data?.length !== width * height * components) return null
  const hasAlpha = imageData.hasAlpha === true && components === 4
  const columns = width >= height ? VISUAL_SAMPLE_COLUMNS : Math.max(8, Math.round(VISUAL_SAMPLE_COLUMNS * width / height))
  const rows = height >= width ? VISUAL_SAMPLE_ROWS : Math.max(8, Math.round(VISUAL_SAMPLE_ROWS * height / width))
  const detail = []
  const alphaCoverage = []
  const pixelAt = (x, y) => {
    const offset = (y * width + x) * components
    return { luminance: pixelLuminance(data, offset), alpha: hasAlpha ? data[offset + 3] / 255 : 1 }
  }
  for (let gridY = 0; gridY < rows; gridY += 1) {
    const top = Math.floor(gridY * height / rows)
    const bottom = Math.max(top + 1, Math.floor((gridY + 1) * height / rows))
    for (let gridX = 0; gridX < columns; gridX += 1) {
      const left = Math.floor(gridX * width / columns)
      const right = Math.max(left + 1, Math.floor((gridX + 1) * width / columns))
      let edgeTotal = 0
      let edgeCount = 0
      let alphaTotal = 0
      let pixelCount = 0
      for (let y = top; y < Math.min(height, bottom); y += 1) {
        for (let x = left; x < Math.min(width, right); x += 1) {
          const pixel = pixelAt(x, y)
          alphaTotal += pixel.alpha
          pixelCount += 1
          for (const [nextX, nextY] of [[x + 1, y], [x, y + 1]]) {
            if (nextX >= width || nextY >= height) continue
            const next = pixelAt(nextX, nextY)
            edgeTotal += Math.max(Math.abs(pixel.luminance - next.luminance), Math.abs(pixel.alpha - next.alpha))
            edgeCount += 1
          }
        }
      }
      detail.push(edgeCount ? Number((edgeTotal / edgeCount).toFixed(4)) : 0)
      alphaCoverage.push(pixelCount ? Number((alphaTotal / pixelCount).toFixed(4)) : 0)
    }
  }
  return {
    schemaVersion: 1,
    columns,
    rows,
    detail,
    alphaCoverage,
    sampleWidth: width,
    sampleHeight: height,
    historyStateId,
    method: "edge-alpha-grid-v1",
  }
}

async function visualGridForDocument(documentValue) {
  if (typeof imaging?.getPixels !== "function") return null
  const documentId = number(documentValue?.id)
  const historyStateId = number(documentValue?.activeHistoryState?.id)
  if (documentId === null || historyStateId === null) return null
  const cacheKey = String(documentId) + ":" + String(historyStateId)
  if (cacheKey === visualSampleCacheKey) return visualSampleCache
  if (visualSampleInFlight || Date.now() - visualSampleAttemptAt < VISUAL_SAMPLE_INTERVAL_MS) return null
  visualSampleAttemptAt = Date.now()
  visualSampleInFlight = true
  let imageData = null
  try {
    const targetSize = Number(documentValue.width) >= Number(documentValue.height)
      ? { width: VISUAL_SAMPLE_SIZE }
      : { height: VISUAL_SAMPLE_SIZE }
    const result = await imaging.getPixels({
      documentID: documentId,
      historyStateID: historyStateId,
      targetSize,
      componentSize: 8,
      colorSpace: "RGB",
    })
    imageData = result?.imageData || null
    if (!imageData) return null
    const pixels = await imageData.getData({ chunky: true })
    const summary = visualGridFromPixels(imageData, pixels, historyStateId)
    visualSampleCacheKey = cacheKey
    visualSampleCache = summary
    return summary
  } catch (error) {
    visualSampleCacheKey = null
    visualSampleCache = null
    logBridgeError("Muestra visual no disponible", error)
    return null
  } finally {
    try { imageData?.dispose?.() } catch (_) {}
    visualSampleInFlight = false
  }
}

async function currentContext() {
  const documentValue = app.activeDocument
  if (!documentValue) {
    return {
      schemaVersion: 1, sessionId: SESSION_ID, host: "photoshop", hostVersion: null,
      project: { id: null, name: null, root: null },
      document: { id: null, name: null, path: null, width: null, height: null, unit: "px" },
      location: { kind: "document", index: null, label: null },
      selection: { kind: null, id: null, name: null, text: null, bounds: null },
      layers: [], palette: [], occupiedRegions: [], safeRegions: [], visualGrid: null, time: null,
    }
  }
  const flattenedLayers = flattenLayers(documentValue.layers)
  const allLayers = flattenedLayers.map((entry) => entry.layer)
  const activeLayers = layersOf(app.activeLayers, 4)
  const selected = activeLayers[0] || allLayers[0] || null
  const serialised = flattenedLayers.map((entry, order) => serialiseLayer(entry.layer, { ...entry, order }))
  const visualGrid = await visualGridForDocument(documentValue)
  return {
    schemaVersion: 1, sessionId: SESSION_ID, host: "photoshop", hostVersion: null,
    project: { id: null, name: null, root: null },
    document: {
      id: documentValue.id == null ? null : String(documentValue.id),
      name: documentValue.name ? String(documentValue.name) : null,
      path: null,
      width: number(documentValue.width), height: number(documentValue.height), unit: "px",
    },
    location: { kind: "slide", index: slideIndexFrom(documentValue.name, selected?.name), label: documentValue.name ? String(documentValue.name) : null },
    selection: selected ? serialiseLayer(selected) : { kind: null, id: null, name: null, text: null, bounds: null },
    layers: serialised,
    palette: paletteOf(allLayers),
    occupiedRegions: serialised.map((layer) => layer.bounds).filter(Boolean),
    safeRegions: [],
    visualGrid,
    time: null,
  }
}

async function request(path, options = {}) {
  const { timeoutMs = BRIDGE_TIMEOUT_MS, ...fetchOptions } = options
  const controller = new AbortController()
  let timedOut = false
  const timeout = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  try {
    const response = await fetch(`${BRIDGE}${path}`, {
      ...fetchOptions,
      signal: controller.signal,
      headers: { "content-type": "application/json", ...(fetchOptions.headers || {}) },
    })
    const value = await response.json()
    if (!response.ok) throw new Error(value.error || `Bridge HTTP ${response.status}`)
    return value
  } catch (error) {
    if (timedOut) throw new Error(`Bridge request timed out after ${timeoutMs}ms`)
    throw error
  } finally {
    clearTimeout(timeout)
  }
}

async function syncContext({ force = false } = {}) {
  if (syncing) return
  if (!force && Date.now() < nextContextAttemptAt) return
  syncing = true
  try {
    const context = await currentContext()
    const signature = JSON.stringify(context)
    if (!force && bridgeOnline && signature === lastContextSignature) return
    const result = await request("/context", { method: "POST", body: JSON.stringify(context) })
    lastContextSignature = signature
    bridgeOnline = true
    nextContextAttemptAt = 0
    lastBridgeError = null
    document.querySelector("#status").className = "status online"
    document.querySelector("#status").textContent = "online"
    document.querySelector("#documentName").textContent = context.document.name || "Sin documento"
    document.querySelector("#selectionName").textContent = context.selection.name || "Sin capa seleccionada"
    document.querySelector("#selectionText").textContent = context.selection.text || "Sin texto; usa el nombre de la capa o del documento."
    log(`Contexto sincronizado\n${context.host} · ${context.document.name || "sin documento"}\n${context.selection.name || "sin selección"}\n${result.contextHash}`)
  } catch (error) {
    bridgeOnline = false
    nextContextAttemptAt = Date.now() + BRIDGE_RETRY_MS
    document.querySelector("#status").className = "status offline"
    document.querySelector("#status").textContent = "offline"
    logBridgeError("Bridge no disponible", error)
  } finally {
    syncing = false
  }
}

function startPolling() {
  if (contextPoller || insertPoller) return
  nextContextAttemptAt = 0
  nextInsertAttemptAt = 0
  syncContext({ force: true }).catch((error) => logBridgeError("Bridge no disponible", error))
  consumeInsert().catch((error) => logBridgeError("Inserción fallida", error))
  contextPoller = setInterval(() => syncContext().catch((error) => logBridgeError("Bridge no disponible", error)), CONTEXT_POLL_MS)
  insertPoller = setInterval(() => consumeInsert().catch((error) => logBridgeError("Inserción fallida", error)), INSERT_POLL_MS)
}

function stopPolling() {
  if (contextPoller) clearInterval(contextPoller)
  if (insertPoller) clearInterval(insertPoller)
  contextPoller = null
  insertPoller = null
  nextContextAttemptAt = 0
  nextInsertAttemptAt = 0
}

function fileUrl(file) {
  return `file:///${encodeURI(String(file).replace(/\\/g, "/"))}`
}

async function consumeInsert() {
  if (consuming) return
  if (Date.now() < nextInsertAttemptAt) return
  consuming = true
  let requestValue = null
  try {
    const response = await request(`/insert/next?sessionId=${encodeURIComponent(SESSION_ID)}`)
    nextInsertAttemptAt = 0
    lastBridgeError = null
    requestValue = response.request
    if (!requestValue) return
    let file = requestValue.asset?.file || null
    if (!file && requestValue.asset?.provider && requestValue.asset?.id) {
      const fetched = await request("/run", {
        method: "POST",
        timeoutMs: BRIDGE_LONG_TIMEOUT_MS,
        body: JSON.stringify({ tool: "asset.fetch", params: { provider: requestValue.asset.provider, id: requestValue.asset.id } }),
      })
      file = fetched.result?.output || fetched.files?.[0] || null
    }
    if (!file) throw new Error("La orden no tiene un SVG local")
    if (requestValue.mode !== "unitary") throw new Error("layer-stack aún no está implementado en Photoshop")
    await insertSvg(file, requestValue)
    await request("/insert/result", {
      method: "POST",
      body: JSON.stringify({ requestId: requestValue.requestId, sessionId: SESSION_ID, state: "completed", data: { assetId: requestValue.asset?.assetId || null } }),
    })
    log(`Insertado: ${requestValue.asset?.assetId || file}`)
  } catch (error) {
    nextInsertAttemptAt = Date.now() + BRIDGE_RETRY_MS
    logBridgeError("Inserción fallida", error)
    if (requestValue?.requestId) {
      await request("/insert/result", {
        method: "POST",
        body: JSON.stringify({ requestId: requestValue.requestId, sessionId: SESSION_ID, state: "failed", error: error.message }),
      }).catch(() => {})
    }
  } finally {
    consuming = false
  }
}

async function insertSvg(file, requestValue) {
  const target = app.activeDocument
  if (!target) throw new Error("Photoshop no tiene un documento activo")
  const source = await storage.localFileSystem.getEntryWithUrl(fileUrl(file))
  await core.executeAsModal(async () => {
    const imported = await app.open(source)
    try {
      const layer = layersOf(imported.layers, 1)[0]
      if (!layer) throw new Error("El SVG importado no contiene una capa")
      await layer.copy(true)
      const pasted = await target.paste()
      if (pasted && requestValue.asset?.assetId) {
        const isAnalysisLayer = String(requestValue.asset.assetId).startsWith("analysis:")
        pasted.name = isAnalysisLayer ? "CS - analysis" : `Shelf - ${asciiName(requestValue.asset.assetId, "asset")}`
        if (isAnalysisLayer) {
          try { pasted.allLocked = true } catch (_) {}
        }
      }
    } finally {
      await imported.closeWithoutSaving()
    }
  }, { commandName: "Context Shelf: insertar asset" })
}

document.querySelector("#refresh").addEventListener("click", () => syncContext({ force: true }))
document.querySelector("#send").addEventListener("click", () => syncContext({ force: true }))
try {
  action.addNotificationListener(["select", "open"], () => {
    if (contextPoller) syncContext().catch((error) => log(error))
  })
} catch (error) {
  log(`Eventos no disponibles; se usa polling: ${error.message}`)
}

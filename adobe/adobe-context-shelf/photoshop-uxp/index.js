const { app, action, core } = require("photoshop")
const { entrypoints } = require("uxp")
const { storage } = require("uxp")

const BRIDGE = "http://127.0.0.1:47921"
const SESSION_ID = `photoshop-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
let syncing = false
let consuming = false
let lastContextSignature = null
let bridgeOnline = false

entrypoints.setup({
  panels: {
    contextShelf: {
      show() { syncContext().catch((error) => log(error)) },
    },
  },
})

function log(value) {
  const target = document.querySelector("#log")
  if (target) target.textContent = String(value?.message || value)
}

function number(value) {
  const raw = value && typeof value === "object" && "value" in value ? value.value : value
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

function plainBounds(value) {
  if (!value) return null
  const result = { left: number(value.left), top: number(value.top), right: number(value.right), bottom: number(value.bottom) }
  return Object.values(result).every((item) => item !== null) ? result : null
}

function layerText(layer) {
  try { return layer?.textItem?.contents ? String(layer.textItem.contents) : null } catch (_) { return null }
}

function layersOf(collection) {
  try { return Array.from(collection || []) } catch (_) { return [] }
}

function flattenLayers(collection, output = [], parentId = null, depth = 0) {
  for (const [index, layer] of layersOf(collection).entries()) {
    output.push({ layer, parentId, depth, index })
    if (layer.layers) flattenLayers(layer.layers, output, layer?.id == null ? null : String(layer.id), depth + 1)
  }
  return output
}

function serialiseLayer(layer, metadata = {}) {
  return {
    id: layer?.id == null ? null : String(layer.id),
    parentId: metadata.parentId == null ? null : String(metadata.parentId),
    depth: Number.isFinite(Number(metadata.depth)) ? Number(metadata.depth) : 0,
    order: Number.isFinite(Number(metadata.order)) ? Number(metadata.order) : null,
    name: layer?.name ? String(layer.name) : null,
    kind: layer?.kind ? String(layer.kind) : null,
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

function currentContext() {
  const documentValue = app.activeDocument
  if (!documentValue) {
    return {
      schemaVersion: 1, sessionId: SESSION_ID, host: "photoshop", hostVersion: null,
      project: { id: null, name: null, root: null },
      document: { id: null, name: null, path: null, width: null, height: null, unit: "px" },
      location: { kind: "document", index: null, label: null },
      selection: { kind: null, id: null, name: null, text: null, bounds: null },
      layers: [], palette: [], occupiedRegions: [], safeRegions: [], time: null,
    }
  }
  const flattenedLayers = flattenLayers(documentValue.layers)
  const allLayers = flattenedLayers.map((entry) => entry.layer)
  const activeLayers = layersOf(app.activeLayers)
  const selected = activeLayers[0] || allLayers[0] || null
  const serialised = flattenedLayers.map((entry, order) => serialiseLayer(entry.layer, { ...entry, order }))
  return {
    schemaVersion: 1, sessionId: SESSION_ID, host: "photoshop", hostVersion: null,
    project: { id: null, name: null, root: null },
    document: {
      id: documentValue.id == null ? null : String(documentValue.id),
      name: documentValue.name ? String(documentValue.name) : null,
      path: documentValue.path ? String(documentValue.path) : null,
      width: number(documentValue.width), height: number(documentValue.height), unit: "px",
    },
    location: { kind: "slide", index: slideIndexFrom(documentValue.name, selected?.name), label: documentValue.name ? String(documentValue.name) : null },
    selection: selected ? serialiseLayer(selected) : { kind: null, id: null, name: null, text: null, bounds: null },
    layers: serialised,
    palette: paletteOf(allLayers),
    occupiedRegions: serialised.map((layer) => layer.bounds).filter(Boolean),
    safeRegions: [],
    time: null,
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${BRIDGE}${path}`, {
    ...options,
    headers: { "content-type": "application/json", ...(options.headers || {}) },
  })
  const value = await response.json()
  if (!response.ok) throw new Error(value.error || `Bridge HTTP ${response.status}`)
  return value
}

async function syncContext({ force = false } = {}) {
  if (syncing) return
  syncing = true
  try {
    const context = currentContext()
    const signature = JSON.stringify(context)
    if (!force && bridgeOnline && signature === lastContextSignature) return
    const result = await request("/context", { method: "POST", body: JSON.stringify(context) })
    lastContextSignature = signature
    bridgeOnline = true
    document.querySelector("#status").className = "status online"
    document.querySelector("#status").textContent = "online"
    document.querySelector("#documentName").textContent = context.document.name || "Sin documento"
    document.querySelector("#selectionName").textContent = context.selection.name || "Sin capa seleccionada"
    document.querySelector("#selectionText").textContent = context.selection.text || "Sin texto; usa el nombre de la capa o del documento."
    log(`Contexto sincronizado\n${context.host} · ${context.document.name || "sin documento"}\n${context.selection.name || "sin selección"}\n${result.contextHash}`)
  } catch (error) {
    bridgeOnline = false
    document.querySelector("#status").className = "status offline"
    document.querySelector("#status").textContent = "offline"
    log(`Bridge no disponible: ${error.message}`)
  } finally {
    syncing = false
  }
}

function fileUrl(file) {
  return `file:///${encodeURI(String(file).replace(/\\/g, "/"))}`
}

async function consumeInsert() {
  if (consuming) return
  consuming = true
  let requestValue = null
  try {
    const response = await request(`/insert/next?sessionId=${encodeURIComponent(SESSION_ID)}`)
    requestValue = response.request
    if (!requestValue) return
    let file = requestValue.asset?.file || null
    if (!file && requestValue.asset?.provider && requestValue.asset?.id) {
      const fetched = await request("/run", {
        method: "POST",
        body: JSON.stringify({ tool: "asset.fetch", params: { provider: requestValue.asset.provider, id: requestValue.asset.id } }),
      })
      file = fetched.result?.output || fetched.files?.[0] || null
    }
    if (!file) throw new Error("La orden no tiene un SVG local")
    if (requestValue.mode !== "unitary") throw new Error("layer-stack aún no está implementado en Photoshop")
    await insertSvg(file, requestValue)
    await request("/insert/result", {
      method: "POST",
      body: JSON.stringify({ requestId: requestValue.requestId, sessionId: SESSION_ID, state: "completed", data: { file } }),
    })
    log(`Insertado: ${requestValue.asset?.assetId || file}`)
  } catch (error) {
    log(`Inserción fallida: ${error.message}`)
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
      const layer = layersOf(imported.layers)[0]
      if (!layer) throw new Error("El SVG importado no contiene una capa")
      await layer.copy(true)
      const pasted = await target.paste()
      if (pasted && requestValue.asset?.assetId) {
        const isAnalysisLayer = String(requestValue.asset.assetId).startsWith("analysis:")
        pasted.name = isAnalysisLayer ? "CS — análisis" : `Shelf · ${requestValue.asset.assetId}`
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
setInterval(() => syncContext(), 1200)
setInterval(() => consumeInsert(), 700)
try {
  action.addNotificationListener(["select", "open"], () => syncContext())
} catch (error) {
  log(`Eventos no disponibles; se usa polling: ${error.message}`)
}

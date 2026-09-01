import { deterministicId, sha256, stable } from "../contracts/stable.mjs"

const MAX_LAYERS = 200
const MAX_REGIONS = 200
const MAX_PALETTE = 24

function numberOrNull(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function stringOrNull(value, max = 500) {
  if (value === undefined || value === null || String(value).trim() === "") return null
  return String(value).trim().slice(0, max)
}

function bounds(value) {
  if (!value || typeof value !== "object") return null
  const source = {
    left: value.left ?? value.x,
    top: value.top ?? value.y,
    right: value.right ?? (numberOrNull(value.x) !== null && numberOrNull(value.width) !== null ? Number(value.x) + Number(value.width) : undefined),
    bottom: value.bottom ?? (numberOrNull(value.y) !== null && numberOrNull(value.height) !== null ? Number(value.y) + Number(value.height) : undefined),
  }
  const result = { left: numberOrNull(source.left), top: numberOrNull(source.top), right: numberOrNull(source.right), bottom: numberOrNull(source.bottom) }
  return Object.values(result).every((item) => item !== null) && result.right > result.left && result.bottom > result.top ? result : null
}

function objectOrEmpty(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {}
}

function missing(unknown, path, value, reason = "not-provided-by-source") {
  if (value === null || value === undefined || value === "") unknown[path] = { value: null, reason }
}

function normalizePalette(value) {
  return (Array.isArray(value) ? value : []).map((item) => String(item).trim().toLowerCase()).filter((item) => /^#[0-9a-f]{3,8}$/i.test(item)).slice(0, MAX_PALETTE)
}

function normalizeDocument(input, unknown) {
  const source = objectOrEmpty(input)
  const document = {
    id: stringOrNull(source.id, 200), name: stringOrNull(source.name, 240), path: stringOrNull(source.path, 500),
    width: numberOrNull(source.width), height: numberOrNull(source.height), unit: stringOrNull(source.unit, 16),
  }
  for (const key of Object.keys(document)) missing(unknown, `document.${key}`, document[key])
  return document
}

function normalizeSelection(input, unknown) {
  const source = objectOrEmpty(input)
  const selection = { id: stringOrNull(source.id, 200), name: stringOrNull(source.name, 240), kind: stringOrNull(source.kind, 80), text: stringOrNull(source.text, 4000), bounds: bounds(source.bounds) }
  for (const key of Object.keys(selection)) missing(unknown, `selection.${key}`, selection[key])
  return selection
}

function normalizeLayer(input, index, unknown) {
  const source = objectOrEmpty(input)
  const layer = {
    id: stringOrNull(source.id, 200), parentId: stringOrNull(source.parentId, 200),
    name: stringOrNull(source.name, 240), kind: stringOrNull(source.kind, 80),
    visible: source.visible !== false, locked: source.locked === true, bounds: bounds(source.bounds), text: stringOrNull(source.text, 2000),
  }
  if (layer.id === null) missing(unknown, `layers.${index}.id`, null, "layer-id-not-provided")
  return layer
}

function normalizeRegions(value) {
  return (Array.isArray(value) ? value : []).slice(0, MAX_REGIONS).map(bounds).filter(Boolean)
}

export function normalizeContext(input = {}, { source = "unknown" } = {}) {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new TypeError("Context must be an object")
  const unknown = {}
  const sessionId = stringOrNull(input.sessionId, 160)
  const host = stringOrNull(input.host, 80)
  const context = {
    schemaVersion: 1,
    contextId: stringOrNull(input.contextId, 200),
    sessionId,
    host,
    hostVersion: stringOrNull(input.hostVersion, 64),
    source: stringOrNull(input.source, 80) || source,
    document: normalizeDocument(input.document, unknown),
    selection: normalizeSelection(input.selection, unknown),
    layers: (Array.isArray(input.layers) ? input.layers : []).slice(0, MAX_LAYERS).map((layer, index) => normalizeLayer(layer, index, unknown)),
    palette: normalizePalette(input.palette),
    occupiedRegions: normalizeRegions(input.occupiedRegions),
    safeRegions: normalizeRegions(input.safeRegions),
    capturedAt: stringOrNull(input.capturedAt, 80),
    unknown,
  }
  for (const [key, value] of [["contextId", context.contextId], ["sessionId", context.sessionId], ["host", context.host], ["hostVersion", context.hostVersion], ["capturedAt", context.capturedAt]]) missing(unknown, key, value)
  const hashable = stable({ ...context, contextHash: undefined })
  context.contextHash = sha256(hashable)
  if (context.contextId === null) context.contextId = deterministicId("context", { sessionId: context.sessionId, contextHash: context.contextHash })
  return context
}

export function contextCompleteness(context) {
  const unknownCount = Object.keys(context?.unknown || {}).length
  const known = Math.max(0, 1 - Math.min(1, unknownCount / 12))
  return { score: Number(known.toFixed(2)), unknownCount, complete: unknownCount === 0 }
}

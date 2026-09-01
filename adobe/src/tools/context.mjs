import crypto from "node:crypto"
import fs from "node:fs/promises"
import path from "node:path"
import { assertAllowedInput, ensureDir, TOOLKIT_ROOT } from "../utils.mjs"
import { searchAssets } from "./asset-search.mjs"
import { searchLocalAssets } from "./local-catalog.mjs"
import { analyzeContext } from "./context-analysis.mjs"

const HOSTS = new Set(["photoshop", "illustrator", "after-effects", "premiere"])
const MODES = new Set(["unitary", "layer-stack"])
const PLACEMENTS = new Set(["safe-region", "cursor", "center"])
const COLORS = new Set(["original", "palette", "monochrome"])
const MAX_CONTEXT_ARRAY = 200
const MAX_QUEUE_SIZE = 20
const INSERT_TTL_MS = 60_000
const RECOMMENDATION_TTL_MS = 10 * 60_000
const ANALYSIS_LAYER_ROOT = path.join(TOOLKIT_ROOT, "jobs", "context-analysis")

const contexts = new Map()
const insertQueues = new Map()
const inflightInserts = new Map()
const insertResults = new Map()
const recommendationCache = new Map()

function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue)
  if (value && typeof value === "object") {
    return Object.keys(value).sort().reduce((result, key) => {
      result[key] = stableValue(value[key])
      return result
    }, {})
  }
  return value
}

function hashContext(value) {
  return `sha256:${crypto.createHash("sha256").update(JSON.stringify(stableValue(value))).digest("hex")}`
}

function boundedArray(value) {
  return Array.isArray(value) ? value.slice(0, MAX_CONTEXT_ARRAY) : []
}

function numberOrNull(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function bounds(value) {
  if (!value || typeof value !== "object") return null
  const result = {
    left: numberOrNull(value.left),
    top: numberOrNull(value.top),
    right: numberOrNull(value.right),
    bottom: numberOrNull(value.bottom),
  }
  return Object.values(result).every((item) => item !== null) ? result : null
}

function normalizePalette(value) {
  return boundedArray(value)
    .map((item) => String(item).trim())
    .filter((item) => /^#[0-9a-f]{3,8}$/i.test(item))
    .slice(0, 24)
}

function normalizeContext(input = {}) {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new Error("Context must be an object")
  const host = String(input.host || "").toLowerCase()
  if (!HOSTS.has(host)) throw new Error(`Unsupported Adobe host: ${host || "missing"}`)
  const sessionId = String(input.sessionId || "")
  if (!/^[a-z0-9][a-z0-9._:-]{2,120}$/i.test(sessionId)) throw new Error("Context sessionId is invalid")
  const document = input.document && typeof input.document === "object" ? input.document : {}
  const selection = input.selection && typeof input.selection === "object" ? input.selection : {}
  const location = input.location && typeof input.location === "object" ? input.location : {}
  const project = input.project && typeof input.project === "object" ? input.project : {}
  const normalized = {
    schemaVersion: 1,
    sessionId,
    host,
    hostVersion: input.hostVersion ? String(input.hostVersion).slice(0, 32) : null,
    project: {
      id: project.id ? String(project.id).slice(0, 160) : null,
      name: project.name ? String(project.name).slice(0, 200) : null,
      root: null,
    },
    document: {
      id: document.id ? String(document.id).slice(0, 200) : null,
      name: document.name ? String(document.name).slice(0, 200) : null,
      path: document.path ? String(document.path).slice(0, 500) : null,
      width: numberOrNull(document.width),
      height: numberOrNull(document.height),
      unit: document.unit ? String(document.unit).slice(0, 12) : "px",
    },
    location: {
      kind: location.kind ? String(location.kind).slice(0, 32) : "document",
      index: numberOrNull(location.index),
      label: location.label ? String(location.label).slice(0, 200) : null,
    },
    selection: {
      kind: selection.kind ? String(selection.kind).slice(0, 64) : null,
      id: selection.id ? String(selection.id).slice(0, 200) : null,
      name: selection.name ? String(selection.name).slice(0, 200) : null,
      text: selection.text ? String(selection.text).slice(0, 4000) : null,
      bounds: bounds(selection.bounds),
    },
    layers: boundedArray(input.layers).map((layer) => ({
      id: layer?.id ? String(layer.id).slice(0, 200) : null,
      parentId: layer?.parentId ? String(layer.parentId).slice(0, 200) : null,
      depth: Number.isFinite(Number(layer?.depth)) ? Math.max(0, Math.min(64, Number(layer.depth))) : 0,
      order: numberOrNull(layer?.order),
      name: layer?.name ? String(layer.name).slice(0, 200) : null,
      kind: layer?.kind ? String(layer.kind).slice(0, 64) : null,
      visible: layer?.visible !== false,
      locked: layer?.locked === true,
      opacity: numberOrNull(layer?.opacity),
      bounds: bounds(layer?.bounds),
      text: layer?.text ? String(layer.text).slice(0, 1000) : null,
    })),
    palette: normalizePalette(input.palette),
    occupiedRegions: boundedArray(input.occupiedRegions).map((region) => bounds(region)).filter(Boolean),
    safeRegions: boundedArray(input.safeRegions).map((region) => bounds(region)).filter(Boolean),
    time: input.time && typeof input.time === "object" ? {
      frame: numberOrNull(input.time.frame),
      seconds: numberOrNull(input.time.seconds),
      duration: numberOrNull(input.time.duration),
    } : null,
  }
  normalized.contextHash = hashContext(normalized)
  normalized.receivedAt = new Date().toISOString()
  return normalized
}

function findContext({ sessionId = null, host = null } = {}) {
  if (sessionId && contexts.has(sessionId)) return contexts.get(sessionId)
  return [...contexts.values()]
    .filter((value) => !host || value.host === host)
    .sort((left, right) => String(right.receivedAt).localeCompare(String(left.receivedAt)))[0] || null
}

export function publishContext(input) {
  const context = normalizeContext(input)
  context.analysis = analyzeContext(context)
  contexts.set(context.sessionId, context)
  return context
}

export function currentContext(options = {}) {
  return findContext(options)
}

function queryForContext(context) {
  return [
    context.selection?.text,
    context.selection?.name,
    context.location?.label,
    context.document?.name,
    context.project?.name,
  ].filter(Boolean).join(" ").trim()
}

function visualQueryForContext(context) {
  return [
    queryForContext(context),
    ...(context.analysis?.content?.visualTerms || []),
  ].filter(Boolean).join(" ").trim()
}

function preferredAssetTerms(context) {
  const index = context.location?.index
  if (!Number.isFinite(index)) return []
  const number = String(Math.round(index))
  const padded = number.padStart(2, "0")
  return [`slide ${number}`, `slide ${padded}`, `lamina ${number}`, `lamina ${padded}`, `slide-${number}`, `slide-${padded}`]
}

export async function recommendContext({ context: rawContext = null, sessionId = null, host = null, limit = 8 } = {}) {
  const context = rawContext ? normalizeContext(rawContext) : findContext({ sessionId, host })
  if (!context) return { context: null, contextHash: null, results: [], errors: ["No current Adobe context"] }
  const safeLimit = Math.min(12, Math.max(1, Number(limit) || 8))
  const cacheKey = `${context.contextHash}:${safeLimit}`
  const cached = recommendationCache.get(cacheKey)
  if (cached && Date.now() - cached.createdAt < RECOMMENDATION_TTL_MS) return { ...cached.value, cached: true }
  const query = visualQueryForContext(context)
  if (!query) return { contextHash: context.contextHash, query: "", results: [], errors: ["Context has no searchable text"] }
  const terms = [
    context.location?.label,
    context.project?.name,
    ...(context.analysis?.content?.visualTerms || []),
    ...(context.analysis?.content?.suggestedRoles || []),
  ].filter(Boolean)
  const localQuery = queryForContext(context)
  const local = await searchLocalAssets({ query: localQuery || query, terms, preferredTerms: preferredAssetTerms(context), excludePatterns: ["generated/", "_rejected/"], limit: safeLimit, semantic: true }).catch((error) => ({ results: [], errors: [`Local catalog: ${error.message}`] }))
  const remote = await searchAssets({
    query,
    terms,
    providers: "visual",
    limit: safeLimit,
    ancla: context.selection?.text || context.selection?.name || null,
    role: "illustration",
    useGdkb: false,
  })
  const bestArea = context.analysis?.layout?.placementCandidates?.[0]
  const localResults = (local.results || []).map((item, index) => ({
    rank: index + 1,
    assetId: item.assetId,
    provider: "local",
    id: item.relativePath,
    file: item.file,
    label: item.label || item.name || item.relativePath,
    license: item.license || null,
    sourceUrl: null,
    local: true,
    format: item.format,
    width: item.width,
    height: item.height,
    aspectRatio: item.aspectRatio,
    reasons: [
      item.matchReasons?.length ? `coincide con: ${item.matchReasons.slice(0, 4).join(", ")}` : "recurso de la biblioteca local",
      ...(bestArea ? [`candidato para ${bestArea.position}`] : []),
    ],
    formats: [item.format],
  }))
  const remoteResults = (remote.visual?.results || []).map((item) => ({
    assetId: `${item.provider}:${item.id}`,
    provider: item.provider,
    id: item.id,
    label: item.label || item.name || item.id,
    license: item.license || null,
    previewUrl: item.previewUrl || null,
    sourceUrl: item.sourceUrl || null,
    local: false,
    reasons: ["coincide con el contexto textual"],
    formats: ["svg"],
  }))
  const merged = [...localResults, ...remoteResults]
    .filter((item, index, all) => all.findIndex((candidate) => candidate.assetId === item.assetId) === index)
    .slice(0, safeLimit)
  const value = {
    contextHash: context.contextHash,
    query,
    results: merged.map((item, index) => ({ ...item, rank: index + 1 })),
    analysis: context.analysis,
    errors: [...(local.errors || []), ...(remote.errors || [])],
    generatedAt: new Date().toISOString(),
  }
  recommendationCache.set(cacheKey, { createdAt: Date.now(), value })
  return { ...value, cached: false }
}

function escapeXml(value) {
  return String(value || "").replace(/[&<>\"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&apos;" }[character]))
}

function svgNumber(value, fallback = 0) {
  const number = Number(value)
  return Number.isFinite(number) ? Number(number.toFixed(2)) : fallback
}

function analysisLayerSvg(context) {
  const analysis = context.analysis || {}
  const canvas = analysis.layout?.canvas || { width: 1080, height: 1080 }
  const width = Math.max(1, svgNumber(canvas.width, 1080))
  const height = Math.max(1, svgNumber(canvas.height, 1080))
  const score = Number(analysis.layers?.score) || 0
  const issues = analysis.layers?.issues || []
  const issueMarkup = issues.flatMap((issue) => (issue.bounds || []).map((bounds, index) => {
    const left = svgNumber(bounds.left)
    const top = svgNumber(bounds.top)
    const right = svgNumber(bounds.right, left + 1)
    const bottom = svgNumber(bounds.bottom, top + 1)
    const boxWidth = Math.max(1, right - left)
    const boxHeight = Math.max(1, bottom - top)
    const color = issue.severity === "warning" ? "#ff756b" : "#ffd166"
    const label = escapeXml(`${issue.severity === "warning" ? "!" : "i"} ${issue.title}`.slice(0, 96))
    const labelWidth = Math.min(Math.max(180, label.length * 10), Math.max(180, width - left - 20))
    return `<rect x="${left}" y="${top}" width="${boxWidth}" height="${boxHeight}" fill="none" stroke="${color}" stroke-width="4" stroke-dasharray="12 8" opacity=".9"/><rect x="${left}" y="${Math.max(0, top - 30)}" width="${labelWidth}" height="26" rx="5" fill="#111318" fill-opacity=".9" stroke="${color}" stroke-width="2"/><text x="${left + 9}" y="${Math.max(18, top - 12)}" fill="${color}" font-family="Arial, sans-serif" font-size="16" font-weight="700">${label}</text>`
  })).join("")
  const placementMarkup = (analysis.layout?.placementCandidates || []).slice(0, 3).map((candidate) => {
    const bounds = candidate.bounds
    if (!bounds) return ""
    const left = svgNumber(bounds.left)
    const top = svgNumber(bounds.top)
    const right = svgNumber(bounds.right, left + 1)
    const bottom = svgNumber(bounds.bottom, top + 1)
    return `<rect x="${left}" y="${top}" width="${Math.max(1, right - left)}" height="${Math.max(1, bottom - top)}" fill="#d6ff43" fill-opacity=".04" stroke="#d6ff43" stroke-width="3" stroke-dasharray="18 12" opacity=".72"/>`
  }).join("")
  const title = escapeXml(context.document?.name || "Documento")
  return `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" data-context-shelf="analysis" data-context-hash="${escapeXml(context.contextHash)}"><rect width="${width}" height="${height}" fill="none"/>${placementMarkup}${issueMarkup}<g><rect x="20" y="20" width="390" height="58" rx="9" fill="#111318" fill-opacity=".9" stroke="#d6ff43" stroke-width="2"/><text x="38" y="47" fill="#f3f3f3" font-family="Arial, sans-serif" font-size="20" font-weight="700">CONTEXT SHELF · ANÁLISIS ${score}/100</text><text x="38" y="67" fill="#aeb1b7" font-family="Arial, sans-serif" font-size="13">${title}</text></g></svg>`
}

export async function queueAnalysisLayer({ sessionId } = {}) {
  const context = currentContext({ sessionId })
  if (!context) throw new Error("Analysis layer requires a live context session")
  const safeSession = String(context.sessionId).replace(/[^a-z0-9_-]+/gi, "-")
  const safeHash = String(context.contextHash || Date.now()).replace(/[^a-z0-9_-]+/gi, "-").slice(-48)
  const file = path.join(ANALYSIS_LAYER_ROOT, `${safeSession}-${safeHash}.svg`)
  await ensureDir(ANALYSIS_LAYER_ROOT)
  await fs.writeFile(file, analysisLayerSvg(context), "utf8")
  return queueInsert({
    sessionId: context.sessionId,
    asset: { assetId: `analysis:${safeHash}`, file },
    mode: "unitary",
    placement: "center",
    colorPolicy: "original",
  })
}

function normalizeInsert(input = {}) {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new Error("Insert request must be an object")
  const sessionId = String(input.sessionId || "")
  if (!contexts.has(sessionId)) throw new Error("Insert request requires a live context session")
  const asset = input.asset && typeof input.asset === "object" ? input.asset : input
  const file = asset.file ? assertAllowedInput(asset.file) : null
  const assetId = asset.assetId || (asset.provider && asset.id ? `${asset.provider}:${asset.id}` : null)
  if (!assetId && !file) throw new Error("Insert request requires assetId or an allowed file")
  const mode = String(input.mode || "unitary")
  const placement = String(input.placement || "safe-region")
  const colorPolicy = String(input.colorPolicy || "original")
  if (!MODES.has(mode)) throw new Error(`Unsupported insert mode: ${mode}`)
  if (!PLACEMENTS.has(placement)) throw new Error(`Unsupported placement: ${placement}`)
  if (!COLORS.has(colorPolicy)) throw new Error(`Unsupported color policy: ${colorPolicy}`)
  return {
    requestId: String(input.requestId || crypto.randomUUID()),
    sessionId,
    asset: { assetId, file, provider: asset.provider || null, id: asset.id || null },
    mode,
    placement,
    scale: input.scale || "fit",
    colorPolicy,
    createdAt: new Date().toISOString(),
    state: "queued",
  }
}

export function queueInsert(input) {
  const request = normalizeInsert(input)
  const queue = insertQueues.get(request.sessionId) || []
  if (queue.length >= MAX_QUEUE_SIZE) throw new Error("Insert queue is full")
  queue.push(request)
  insertQueues.set(request.sessionId, queue)
  return request
}

export function claimInsert(sessionId) {
  const key = String(sessionId || "")
  const now = Date.now()
  for (const [requestId, request] of inflightInserts) {
    if (now - Date.parse(request.createdAt) > INSERT_TTL_MS) {
      inflightInserts.delete(requestId)
      const queue = insertQueues.get(request.sessionId) || []
      queue.unshift({ ...request, state: "queued" })
      insertQueues.set(request.sessionId, queue)
    }
  }
  const queue = insertQueues.get(key) || []
  const request = queue.shift() || null
  if (!request) return null
  const claimed = { ...request, state: "claimed", claimedAt: new Date().toISOString() }
  inflightInserts.set(claimed.requestId, claimed)
  insertQueues.set(key, queue)
  return claimed
}

export function recordInsertResult(input = {}) {
  const requestId = String(input.requestId || "")
  const request = inflightInserts.get(requestId)
  if (!request) throw new Error("Unknown insert request")
  if (String(input.sessionId || request.sessionId) !== request.sessionId) throw new Error("Insert session mismatch")
  const state = String(input.state || "failed")
  if (!["completed", "failed"].includes(state)) throw new Error(`Unsupported insert result state: ${state}`)
  const result = {
    requestId,
    sessionId: request.sessionId,
    state,
    data: input.data && typeof input.data === "object" ? input.data : {},
    error: input.error ? String(input.error).slice(0, 2000) : null,
    finishedAt: new Date().toISOString(),
  }
  inflightInserts.delete(requestId)
  insertResults.set(requestId, result)
  return result
}

export function contextDiagnostics() {
  return {
    contexts: contexts.size,
    queuedInserts: [...insertQueues.values()].reduce((total, queue) => total + queue.length, 0),
    inflightInserts: inflightInserts.size,
    cachedRecommendations: recommendationCache.size,
  }
}

import { clone, deterministicId, sha256, stable } from "../../generic-interface-layer/core/contracts/stable.mjs"

const SOURCES = new Set(["xio", "vizz", "pupila"])
const MAX_HISTORY = 96
const MAX_METADATA = 20
const SIGNAL_TTL_MS = 45_000
const EVENT_PATTERN = /^[a-z0-9]+(?:[._-][a-z0-9]+)+$/
const SESSION_PATTERN = /^[a-z0-9][a-z0-9._:-]{2,120}$/i
const ID_PATTERN = /^[a-z0-9][a-z0-9._:-]{0,159}$/i
const ALLOWED_METADATA = new Set([
  "app", "host", "channel", "action", "state", "phase", "region", "mode", "status", "workflow",
  "eventClass", "intent", "kind", "target", "revision", "count", "participantCount", "confidence",
  "focusScore", "attentionScore", "latencyMs", "pointerMode", "sourceVersion", "transport", "protocol",
  "signalPercent", "lossPercent", "receiveMbps", "transmitMbps", "radioType", "cellChannel",
])
const METADATA_ALIASES = Object.freeze({
  signal_percent: "signalPercent",
  wifi_signal_percent: "signalPercent",
  loss_percent: "lossPercent",
  gateway_loss_percent: "lossPercent",
  receive_mbps: "receiveMbps",
  wifi_receive_mbps: "receiveMbps",
  transmit_mbps: "transmitMbps",
  wifi_transmit_mbps: "transmitMbps",
  cell_rat: "radioType",
  cell_channel: "cellChannel",
  transport_type: "transport",
  focus_score: "focusScore",
  attention_score: "attentionScore",
  participant_count: "participantCount",
  source_version: "sourceVersion",
})
const FORBIDDEN_KEYS = new Set([
  "command", "content", "data", "executable", "file", "frame", "html", "image", "key", "keys",
  "path", "payload", "process", "raw", "script", "shell", "text", "url",
])
const SOURCE_NAMES = { xio: "XIO", vizz: "VIZZ", pupila: "PUPILA" }

const sessions = new Map()
let lastSessionId = null

function objectOrEmpty(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {}
}

function ascii(value, max = 160) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9._:/ -]+/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, max)
}

function token(value, fallback = "") {
  return ascii(value, 120).toLowerCase().replace(/\s+/g, "-") || fallback
}

function sourceOf(value) {
  const source = token(value)
  if (!SOURCES.has(source)) throw new Error(`Unsupported signal source: ${source || "missing"}`)
  return source
}

function sessionOf(value) {
  const sessionId = ascii(value, 120)
  if (!SESSION_PATTERN.test(sessionId)) throw new Error("Signal sessionId is invalid")
  return sessionId
}

function idOf(value) {
  const id = ascii(value, 160)
  if (id && !ID_PATTERN.test(id)) throw new Error("Signal id is invalid")
  return id || null
}

function eventTypeOf(value) {
  const eventType = token(String(value || "").replace(/^\/+/, "").replaceAll("/", "."))
  if (!EVENT_PATTERN.test(eventType) || FORBIDDEN_KEYS.has(eventType.split(".").at(-1))) {
    throw new Error("Signal eventType is invalid")
  }
  return eventType
}

function isoTimestamp(value, fallback = new Date()) {
  if (value === undefined || value === null || value === "") return fallback.toISOString()
  const parsed = new Date(value)
  if (!Number.isFinite(parsed.getTime())) throw new Error("Signal timestamp is invalid")
  return parsed.toISOString()
}

function boundedNumber(key, value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return null
  if (["confidence", "focusScore", "attentionScore"].includes(key)) return Number(Math.max(0, Math.min(1, number)).toFixed(4))
  if (["signalPercent", "lossPercent"].includes(key)) return Number(Math.max(0, Math.min(100, number)).toFixed(2))
  if (["count", "participantCount"].includes(key)) return Math.max(0, Math.min(100_000, Math.round(number)))
  if (["receiveMbps", "transmitMbps"].includes(key)) return Number(Math.max(0, Math.min(100_000, number)).toFixed(2))
  if (key === "latencyMs") return Number(Math.max(0, Math.min(600_000, number)).toFixed(2))
  if (key === "revision") return Math.max(0, Math.round(number))
  return Number(number.toFixed(4))
}

function safeMetadataValue(key, value) {
  if (typeof value === "boolean") return value
  if (typeof value === "number") return boundedNumber(key, value)
  if (typeof value === "string") return ascii(value, 160)
  return null
}

function collectMetadata(input) {
  const metadata = {}
  const droppedKeys = []
  const candidates = [objectOrEmpty(input.metadata), objectOrEmpty(input.meta), objectOrEmpty(input.payload), input]
  for (const candidate of candidates) {
    for (const [rawKey, rawValue] of Object.entries(candidate)) {
      const originalKey = String(rawKey)
      const key = METADATA_ALIASES[originalKey] || originalKey
      if (!ALLOWED_METADATA.has(key)) {
        if (FORBIDDEN_KEYS.has(originalKey.toLowerCase())) droppedKeys.push(originalKey)
        continue
      }
      if (key in metadata) continue
      const value = safeMetadataValue(key, rawValue)
      if (value === null || value === "") {
        droppedKeys.push(key)
        continue
      }
      metadata[key] = value
      if (Object.keys(metadata).length >= MAX_METADATA) break
    }
    if (Object.keys(metadata).length >= MAX_METADATA) break
  }
  return { metadata, droppedKeys: [...new Set(droppedKeys)].slice(0, 24) }
}

function normalizeProposal(value, source) {
  if (!value || !["vizz", "pupila"].includes(source)) return null
  const input = objectOrEmpty(value)
  const proposalId = idOf(input.proposalId || input.id) || deterministicId("proposal", { source, value: stable(input) })
  const normalized = {
    proposalId,
    kind: token(input.kind, "visual-proposal"),
    title: ascii(input.title || input.label, 180) || null,
    reason: ascii(input.reason, 400) || null,
    target: token(input.target) || null,
    reversible: input.reversible !== false,
    requiresConfirmation: true,
    proposalOnly: true,
    expiresAt: input.expiresAt ? isoTimestamp(input.expiresAt) : null,
  }
  if (!normalized.title && !normalized.reason) return null
  return normalized
}

function stateFor(sessionId) {
  let state = sessions.get(sessionId)
  if (!state) {
    state = { history: [], latest: new Map(), lastSequence: new Map(), seen: new Map() }
    sessions.set(sessionId, state)
  }
  return state
}

export function normalizeSignal(input = {}, { sequence = null, now = new Date() } = {}) {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new Error("Signal must be an object")
  const source = sourceOf(input.source || input.producer)
  const sessionId = sessionOf(input.sessionId || input.session_id)
  const eventType = eventTypeOf(input.eventType || input.event_type || input.event || input.type)
  const normalizedSequence = sequence === null
    ? (Number.isInteger(Number(input.sequence)) && Number(input.sequence) >= 0 ? Number(input.sequence) : 0)
    : sequence
  if (!Number.isInteger(normalizedSequence) || normalizedSequence < 0) throw new Error("Signal sequence is invalid")
  const { metadata, droppedKeys } = collectMetadata(input)
  const signalId = idOf(input.signalId || input.signal_id || input.eventId || input.event_id)
    || deterministicId("signal", { source, sessionId, sequence: normalizedSequence, eventType, metadata, proposal: input.proposal || null })
  const proposal = normalizeProposal(input.proposal, source)
  const signal = {
    schemaVersion: 1,
    signalId,
    source,
    sourceName: SOURCE_NAMES[source],
    sessionId,
    sequence: normalizedSequence,
    eventType,
    timestamp: isoTimestamp(input.timestamp || input.timestamp_utc, now),
    receivedAt: now.toISOString(),
    metadata,
    proposal,
    redaction: { rawContentForwarded: false, droppedKeys },
  }
  signal.signalHash = sha256(stable(signal))
  return signal
}

function signalFromState(state, source) {
  return state?.latest?.get(source) || null
}

function sourceSummary(signal, nowMs) {
  if (!signal) return { source: null, state: "missing", signalHash: null, eventType: null, sequence: null, metadata: {}, ageMs: null, receivedAt: null }
  const ageMs = Math.max(0, nowMs - Date.parse(signal.receivedAt))
  return {
    source: signal.source,
    state: ageMs <= SIGNAL_TTL_MS ? "active" : "stale",
    signalHash: signal.signalHash,
    eventType: signal.eventType,
    sequence: signal.sequence,
    metadata: clone(signal.metadata),
    ageMs: Math.round(ageMs),
    receivedAt: signal.receivedAt,
  }
}

export function currentSurface({ sessionId = null, context = null, contextHash = null, now = new Date() } = {}) {
  const resolvedSession = sessionId || context?.sessionId || lastSessionId || null
  const state = resolvedSession ? sessions.get(resolvedSession) : null
  const nowMs = now.getTime()
  const sources = Object.fromEntries([...SOURCES].map((source) => [source, sourceSummary(signalFromState(state, source), nowMs)]))
  const proposals = (state?.history || [])
    .filter((signal) => signal.proposal)
    .slice(-8)
    .reverse()
    .map((signal) => ({ ...clone(signal.proposal), source: signal.source, signalId: signal.signalId, createdAt: signal.receivedAt }))
  const surfaceBasis = {
    schemaVersion: 1,
    sessionId: resolvedSession,
    contextHash: contextHash || context?.contextHash || null,
    sources: Object.fromEntries(Object.entries(sources).map(([source, value]) => [source, { ...value, ageMs: undefined }])),
    proposals,
  }
  return {
    schemaVersion: 1,
    surfaceId: deterministicId("surface", surfaceBasis),
    surfaceHash: sha256(stable(surfaceBasis)),
    sessionId: resolvedSession,
    context: {
      contextHash: contextHash || context?.contextHash || null,
      host: context?.host || null,
      documentId: context?.document?.id || null,
    },
    sources,
    proposals,
    safety: { proposalOnly: true, hostActions: false, rawContentForwarded: false, externalNetwork: false },
    generatedAt: now.toISOString(),
  }
}

export function publishSignal(input = {}) {
  const source = sourceOf(input.source || input.producer)
  const sessionId = sessionOf(input.sessionId || input.session_id)
  const state = stateFor(sessionId)
  const suppliedId = idOf(input.signalId || input.signal_id || input.eventId || input.event_id)
  const duplicate = suppliedId ? state.seen.get(`${source}:${suppliedId}`) : null
  if (duplicate) return { accepted: true, duplicate: true, signal: clone(duplicate), surface: currentSurface({ sessionId }) }

  const previousSequence = state.lastSequence.get(source) ?? -1
  const requestedSequence = Number.isInteger(Number(input.sequence)) && Number(input.sequence) >= 0 ? Number(input.sequence) : previousSequence + 1
  if (requestedSequence <= previousSequence) throw new Error(`Signal sequence must increase for ${source}`)
  const signal = normalizeSignal(input, { sequence: requestedSequence })
  state.lastSequence.set(source, signal.sequence)
  state.seen.set(`${source}:${signal.signalId}`, signal)
  state.latest.set(source, signal)
  state.history.push(signal)
  if (state.history.length > MAX_HISTORY) state.history.splice(0, state.history.length - MAX_HISTORY)
  lastSessionId = sessionId
  return { accepted: true, duplicate: false, signal: clone(signal), surface: currentSurface({ sessionId }) }
}

export function currentSignals({ sessionId = null, limit = 24 } = {}) {
  const resolvedSession = sessionId || lastSessionId || null
  const state = resolvedSession ? sessions.get(resolvedSession) : null
  const safeLimit = Math.min(96, Math.max(1, Number(limit) || 24))
  return {
    schemaVersion: 1,
    sessionId: resolvedSession,
    count: state?.history?.length || 0,
    signals: (state?.history || []).slice(-safeLimit).reverse().map(clone),
  }
}

export function signalDiagnostics() {
  return {
    sessions: sessions.size,
    signals: [...sessions.values()].reduce((total, state) => total + state.history.length, 0),
    latestSources: [...SOURCES].filter((source) => [...sessions.values()].some((state) => state.latest.has(source))),
    lastSessionId,
  }
}

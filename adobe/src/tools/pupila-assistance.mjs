const SIGNAL_TTL_MS = 45_000
const HELP_EVENTS = new Set([
  "interaction.blocked",
  "interaction.uncertain",
  "workflow.repeated",
  "learning.help-needed",
  "learning.transfer-request",
])
const HELP_STATES = new Set(["blocked", "uncertain", "needs-help", "help-needed"])

function text(value, max = 180) {
  return String(value || "").trim().slice(0, max) || null
}

function numberOrNull(value) {
  const number = Number(value)
  return Number.isFinite(number) ? Number(number.toFixed(4)) : null
}

function evidenceFrom(signal) {
  const metadata = signal?.metadata || {}
  return {
    eventType: text(signal?.eventType, 80),
    state: text(metadata.state, 80),
    intent: text(metadata.intent, 120),
    target: text(metadata.target, 120),
    focusScore: numberOrNull(metadata.focusScore),
    attentionScore: numberOrNull(metadata.attentionScore),
  }
}

function baseState(state, signal, ageMs, reason, title) {
  return {
    source: "pupila",
    state,
    mode: state === "assist" ? "assist" : "observe",
    title,
    reason,
    eventType: text(signal?.eventType, 80),
    signalId: text(signal?.signalId, 160),
    ageMs: Number.isFinite(ageMs) ? Math.round(Math.max(0, ageMs)) : null,
    evidence: evidenceFrom(signal),
  }
}

function activeProposal(signal, nowMs) {
  if (!signal?.proposal) return null
  const expiresAt = Date.parse(signal.proposal.expiresAt || "")
  return Number.isFinite(expiresAt) && expiresAt <= nowMs ? null : signal.proposal
}

function hasExplicitHelpEvidence(signal, nowMs) {
  const eventType = String(signal?.eventType || "").toLowerCase()
  const state = String(signal?.metadata?.state || "").toLowerCase()
  return Boolean(activeProposal(signal, nowMs)) || HELP_EVENTS.has(eventType) || HELP_STATES.has(state)
}

export function derivePupilaAssistance(signal = null, nowMs = Date.now()) {
  if (!signal) return baseState("missing", null, null, "PUPILA no está publicando una observación para esta sesión.", "PUPILA sin señal")

  const receivedAt = Date.parse(signal.receivedAt || "")
  const ageMs = Number.isFinite(receivedAt) ? Math.max(0, nowMs - receivedAt) : SIGNAL_TTL_MS + 1
  if (ageMs > SIGNAL_TTL_MS) {
    return baseState("stale", signal, ageMs, "La observación de PUPILA expiró; no se reutiliza como ayuda actual.", "Observación PUPILA vencida")
  }

  if (!hasExplicitHelpEvidence(signal, nowMs)) {
    return baseState("observing", signal, ageMs, "PUPILA observa el flujo; una señal aislada no se interpreta como necesidad de ayuda.", "PUPILA observando")
  }

  const proposal = activeProposal(signal, nowMs)
    ? {
        proposalId: signal.proposal.proposalId,
        kind: signal.proposal.kind,
        title: signal.proposal.title,
        reason: signal.proposal.reason,
        target: signal.proposal.target,
        reversible: signal.proposal.reversible,
        requiresConfirmation: true,
        proposalOnly: true,
        expiresAt: signal.proposal.expiresAt,
      }
    : {
        proposalId: `pupila-assistance:${signal.signalId}`,
        kind: "assistance.contextual",
        title: "Mostrar ayuda contextual",
        reason: signal.metadata?.intent
          ? `PUPILA detectó una posible dificultad con ${text(signal.metadata.intent, 120)}.`
          : `PUPILA detectó una señal explícita de ayuda: ${text(signal.eventType, 80)}.`,
        target: text(signal.metadata?.target, 120) || "adobe",
        reversible: true,
        requiresConfirmation: true,
        proposalOnly: true,
        expiresAt: new Date((Number.isFinite(receivedAt) ? receivedAt : nowMs) + SIGNAL_TTL_MS).toISOString(),
      }

  return {
    ...baseState("assist", signal, ageMs, proposal.reason || "PUPILA propone ayuda contextual.", proposal.title || "Ayuda contextual disponible"),
    proposal,
  }
}

export function assistanceForSurface(assistance = {}) {
  const { ageMs: _ageMs, ...stableAssistance } = assistance
  return stableAssistance
}

import { deterministicId, sha256, stable } from "../contracts/stable.mjs"

export function appendAuditEvent(events = [], { type, payload = {}, timestamp = null } = {}) {
  const sequence = events.length
  const previousHash = events.at(-1)?.eventHash || null
  const eventId = deterministicId("event", { sequence, type, payload, previousHash })
  const unsigned = { schemaVersion: 1, sequence, eventId, type: String(type), payload: stable(payload), timestamp, previousHash }
  return [...events, { ...unsigned, eventHash: sha256(unsigned) }]
}

export function verifyAuditChain(events = []) {
  let previousHash = null
  for (const [sequence, event] of events.entries()) {
    if (event.sequence !== sequence || event.previousHash !== previousHash) return { valid: false, sequence, reason: "sequence-or-link-mismatch" }
    const { eventHash, ...unsigned } = event
    if (eventHash !== sha256(unsigned)) return { valid: false, sequence, reason: "hash-mismatch" }
    previousHash = eventHash
  }
  return { valid: true, count: events.length, head: previousHash }
}

import { clone, deterministicId } from "../contracts/stable.mjs"

const TERMINAL = new Set(["completed", "failed", "cancelled", "rolled-back"])

function requireObject(value, label) { if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError(`${label} must be an object`) }

export function createAction(input = {}) {
  requireObject(input, "Action")
  const idempotencyKey = String(input.idempotencyKey || "").trim() || deterministicId("idem", { type: input.type, payload: input.payload || {}, destination: input.destination || {} })
  const type = String(input.type || "").trim().toLowerCase()
  if (!/^[a-z0-9._-]+$/.test(type)) throw new Error("Action type is invalid")
  const action = {
    schemaVersion: 1,
    actionId: String(input.actionId || deterministicId("action", { idempotencyKey, type, payload: input.payload || {}, destination: input.destination || {} })),
    idempotencyKey,
    type,
    state: "proposed",
    origin: clone(input.origin || { component: "unknown", actor: "unknown" }),
    destination: clone(input.destination || { kind: "unknown", id: null }),
    permissions: [...new Set((Array.isArray(input.permissions) ? input.permissions : []).map(String))].sort(),
    risk: clone(input.risk || { level: "unknown", reason: "not-assessed" }),
    payload: clone(input.payload || {}),
    rollback: clone(input.rollback || { supported: false, token: null }),
    approval: null,
    result: null,
    error: null,
    createdAt: input.createdAt ?? null,
    updatedAt: input.createdAt ?? null,
  }
  return action
}

export function authorizeAction(action, approval = {}) {
  if (!action || action.state !== "proposed") throw new Error("Only proposed actions can be authorized")
  if (approval.confirmed !== true) throw new Error("Explicit confirmation is required")
  if (!approval.actor) throw new Error("Approval actor is required")
  return { ...clone(action), state: "authorized", approval: { confirmed: true, actor: String(approval.actor), at: approval.at ?? null }, updatedAt: approval.at ?? action.updatedAt }
}

export function startAction(action, { at = null } = {}) {
  if (!action || action.state !== "authorized") throw new Error("Only authorized actions can start")
  return { ...clone(action), state: "running", updatedAt: at }
}

export function completeAction(action, result = {}, { at = null } = {}) {
  if (!action || action.state !== "running") throw new Error("Only running actions can complete")
  return { ...clone(action), state: "completed", result: clone(result), updatedAt: at }
}

export function failAction(action, error, { at = null } = {}) {
  if (!action || action.state === "completed" || action.state === "cancelled" || action.state === "rolled-back") throw new Error("Action cannot fail in its current state")
  return { ...clone(action), state: "failed", error: String(error || "unknown error"), updatedAt: at }
}

export function cancelAction(action, { actor = "unknown", reason = "cancelled-by-user", at = null } = {}) {
  if (!action || TERMINAL.has(action.state)) throw new Error("Action cannot be cancelled in its current state")
  return { ...clone(action), state: "cancelled", cancellation: { actor, reason }, updatedAt: at }
}

export function rollbackAction(action, { actor = "unknown", at = null } = {}) {
  if (!action || action.state !== "completed") throw new Error("Only completed actions can be rolled back")
  if (action.rollback?.supported !== true) throw new Error("Action is not reversible according to its contract")
  return { ...clone(action), state: "rolled-back", rollbackResult: { actor, at, token: action.rollback.token || null }, updatedAt: at }
}

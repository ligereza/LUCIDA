import { normalizeContext } from "../../core/context/normalize.mjs"
import { createAction } from "../../core/actions/lifecycle.mjs"

const ALLOWED = new Set(["context.update", "action.result", "health"])

export function acceptPluginMessage(message = {}) {
  if (!message || typeof message !== "object" || !ALLOWED.has(message.type)) throw new Error("Plugin message type is not allowlisted")
  if (message.type === "context.update") return { type: message.type, context: normalizeContext(message.context || {}, { source: "plugin" }) }
  if (message.type === "action.result") return { type: message.type, action: createAction({ ...(message.action || {}), type: message.action?.type || "action.result" }), result: message.result || null }
  return { type: "health", ok: true }
}

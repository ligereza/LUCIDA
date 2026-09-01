import { clone } from "../../core/contracts/stable.mjs"

export function createCompanionState() {
  return { mode: "explore", context: null, analysis: null, proposals: [], selection: [], loading: false, error: null, connected: false }
}

export function reduceCompanionState(state = createCompanionState(), event = {}) {
  const next = clone(state)
  switch (event.type) {
    case "connection.changed": next.connected = event.connected === true; break
    case "context.received": next.context = clone(event.context); next.analysis = clone(event.analysis); next.mode = "suggested"; break
    case "proposals.received": next.proposals = clone(event.proposals || []); next.loading = false; next.error = null; break
    case "selection.changed": next.selection = [...new Set((event.assetIds || []).map(String))].sort(); break
    case "mode.changed": if (["explore", "suggested"].includes(event.mode)) next.mode = event.mode; break
    case "loading": next.loading = event.value !== false; next.error = null; break
    case "error": next.loading = false; next.error = String(event.message || "Unknown error"); break
    default: break
  }
  return next
}

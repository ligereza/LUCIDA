import { sha256, stable } from "../contracts/stable.mjs"

export function replaySession(events = []) {
  const state = { context: null, analysis: null, proposals: [], actions: {}, results: [], applied: 0 }
  for (const event of [...events].sort((a, b) => a.sequence - b.sequence)) {
    const payload = event.payload || {}
    if (event.type === "context.received") { state.context = payload.context || null; state.analysis = payload.analysis || null }
    if (event.type === "proposal.created") state.proposals.push(payload.proposal)
    if (event.type === "action.created" || event.type === "action.updated") if (payload.action?.actionId) state.actions[payload.action.actionId] = payload.action
    if (event.type === "action.result") state.results.push(payload)
    state.applied += 1
  }
  return { ...state, sessionHash: sha256(stable({ context: state.context, analysis: state.analysis, proposals: state.proposals, actions: state.actions, results: state.results })) }
}

import { deterministicId } from "../contracts/stable.mjs"

function normalize(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim() }
function tokenSet(value) { return new Set(normalize(value).split(/\s+/).filter(Boolean)) }
function aspect(entry) { return Number(entry?.width) > 0 && Number(entry?.height) > 0 ? Number(entry.width) / Number(entry.height) : null }

export function rankProposals({ candidates = [], context = null, analysis = null, query = "", limit = 12 } = {}) {
  const contextTerms = [query, analysis?.content?.text, ...(analysis?.content?.visualTerms || []), context?.selection?.name, context?.document?.name].filter(Boolean).join(" ")
  const queryTokens = tokenSet(contextTerms)
  const placement = analysis?.layout?.placementCandidates?.[0]
  const targetAspect = placement?.bounds ? (placement.bounds.right - placement.bounds.left) / Math.max(1, placement.bounds.bottom - placement.bounds.top) : null
  return candidates.map((candidate) => {
    const text = [candidate.label, candidate.name, candidate.path, ...(candidate.tags || []), candidate.kind, candidate.format].filter(Boolean).join(" ")
    const matches = [...tokenSet(text)].filter((token) => queryTokens.has(token))
    const lexical = queryTokens.size ? matches.length / queryTokens.size : 0
    const ratio = aspect(candidate)
    const shape = targetAspect && ratio ? Math.max(0, 1 - Math.abs(Math.log(ratio / targetAspect))) : 0
    const score = Number((lexical * 0.72 + shape * 0.18 + (candidate.local === false ? 0.02 : 0.1)).toFixed(6))
    return { ...candidate, proposalId: deterministicId("proposal", { assetId: candidate.assetId || candidate.path || candidate.id, contextHash: context?.contextHash || null, query }), score, state: "proposed", reasons: [...(matches.length ? [`coincide: ${matches.slice(0, 5).join(", ")}`] : []), ...(shape > 0.5 ? ["proporción compatible con el espacio"] : []), ...(candidate.local !== false ? ["recurso local"] : [])] }
  }).sort((a, b) => b.score - a.score || String(a.assetId || a.path || a.id).localeCompare(String(b.assetId || b.path || b.id))).slice(0, Math.max(1, Math.min(100, Number(limit) || 12))).map((item, index) => ({ ...item, rank: index + 1 }))
}

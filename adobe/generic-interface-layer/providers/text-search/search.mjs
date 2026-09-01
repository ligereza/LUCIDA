function normalize(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim() }

export function searchText(entries = [], query = "", { limit = 20 } = {}) {
  const terms = normalize(query).split(/\s+/).filter(Boolean)
  return entries.map((entry) => {
    const searchable = normalize([entry.label, entry.name, entry.path, entry.format, entry.sourceKind, ...(entry.tags || []), ...(entry.dominantColors || [])].join(" "))
    const matches = terms.filter((term) => searchable.includes(term))
    return { ...entry, score: terms.length ? matches.length / terms.length : 0, matches }
  }).filter((entry) => !terms.length || entry.score > 0).sort((a, b) => b.score - a.score || String(a.assetId).localeCompare(String(b.assetId))).slice(0, Math.max(1, Number(limit) || 20))
}

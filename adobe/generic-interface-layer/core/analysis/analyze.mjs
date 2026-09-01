import { sha256 } from "../contracts/stable.mjs"

function normalizeText(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim()
}

function tokens(value) {
  return normalizeText(value).split(" ").filter((token) => token.length > 1)
}

function rectArea(rect) { return Math.max(0, rect.right - rect.left) * Math.max(0, rect.bottom - rect.top) }

function overlap(a, b) {
  const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left))
  const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top))
  return width * height
}

function canvasOf(context) {
  const width = Number(context?.document?.width)
  const height = Number(context?.document?.height)
  return Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0 ? { width, height } : null
}

function contextText(context) {
  return [context?.selection?.name, context?.selection?.text, context?.document?.name, context?.project?.name, ...(context?.layers || []).flatMap((layer) => [layer?.name, layer?.text])].filter(Boolean).join(" ").slice(0, 8000)
}

function occupiedOf(context) {
  const layers = (context?.layers || []).filter((layer) => layer.visible !== false).map((layer) => layer.bounds).filter(Boolean)
  const regions = layers.length ? layers : (context?.occupiedRegions || [])
  return [...regions, ...(context?.selection?.bounds ? [context.selection.bounds] : [])]
}

function blankAreas(occupied, canvas, columns = 12, rows = 12) {
  if (!canvas) return []
  const free = Array.from({ length: rows }, () => Array(columns).fill(true))
  for (let y = 0; y < rows; y += 1) for (let x = 0; x < columns; x += 1) {
    const cell = { left: x * canvas.width / columns, top: y * canvas.height / rows, right: (x + 1) * canvas.width / columns, bottom: (y + 1) * canvas.height / rows }
    if (occupied.some((region) => overlap(cell, region) / rectArea(cell) >= 0.2)) free[y][x] = false
  }
  const seen = new Set(), areas = []
  for (let y = 0; y < rows; y += 1) for (let x = 0; x < columns; x += 1) {
    const key = `${x}:${y}`
    if (!free[y][x] || seen.has(key)) continue
    const queue = [[x, y]], cells = [], directions = [[1, 0], [-1, 0], [0, 1], [0, -1]]
    seen.add(key)
    while (queue.length) {
      const [cx, cy] = queue.shift(); cells.push([cx, cy])
      for (const [dx, dy] of directions) {
        const nx = cx + dx, ny = cy + dy, nextKey = `${nx}:${ny}`
        if (nx >= 0 && nx < columns && ny >= 0 && ny < rows && free[ny][nx] && !seen.has(nextKey)) { seen.add(nextKey); queue.push([nx, ny]) }
      }
    }
    if (cells.length < 2) continue
    const xs = cells.map(([cx]) => cx), ys = cells.map(([, cy]) => cy)
    const bounds = { left: Math.min(...xs) * canvas.width / columns, top: Math.min(...ys) * canvas.height / rows, right: (Math.max(...xs) + 1) * canvas.width / columns, bottom: (Math.max(...ys) + 1) * canvas.height / rows }
    const area = rectArea(bounds)
    areas.push({ bounds, area: Number(area.toFixed(2)), areaRatio: Number((area / (canvas.width * canvas.height)).toFixed(4)), cells: cells.length, position: `${(bounds.top + bounds.bottom) / 2 < canvas.height / 2 ? "top" : "bottom"}-${(bounds.left + bounds.right) / 2 < canvas.width / 2 ? "left" : "right"}` })
  }
  return areas.sort((a, b) => b.area - a.area).slice(0, 12).map((area, index) => ({ ...area, rank: index + 1 }))
}

export function analyzeContext(context = {}, { vocabulary = [] } = {}) {
  const rawText = contextText(context)
  const normalizedText = normalizeText(rawText)
  const counts = new Map()
  for (const token of tokens(rawText)) counts.set(token, (counts.get(token) || 0) + 1)
  const visualTerms = [...new Set([...vocabulary, ...[...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 12).map(([token]) => token)])].slice(0, 24)
  const canvas = canvasOf(context)
  const occupied = occupiedOf(context)
  const blank = blankAreas(occupied, canvas)
  const completeness = Object.keys(context?.unknown || {}).length
  return {
    schemaVersion: 1,
    source: "deterministic-local",
    contextHash: context?.contextHash || null,
    content: { text: rawText, normalizedText, visualTerms, confidence: Number(Math.max(0, Math.min(0.98, normalizedText ? 0.45 + Math.min(0.5, visualTerms.length / 24) : 0)).toFixed(2)) },
    palette: Array.isArray(context?.palette) ? context.palette : [],
    layout: { canvas, occupied, blankAreas: blank, placementCandidates: context?.safeRegions?.length ? context.safeRegions.map((bounds, index) => ({ bounds, source: "host", rank: index + 1, area: rectArea(bounds) })) : blank.slice(0, 5).map((area) => ({ ...area, source: "detected" })), occupiedRatio: canvas ? Number(Math.min(1, occupied.reduce((sum, region) => sum + rectArea(region), 0) / (canvas.width * canvas.height)).toFixed(4)) : null, method: canvas ? "grid-12x12-connected-components" : "unavailable-missing-canvas" },
    completeness: { score: Number(Math.max(0, 1 - Math.min(1, completeness / 12)).toFixed(2)), unknownFields: completeness },
    analysisHash: sha256({ rawText, visualTerms, palette: context?.palette || [], layout: { canvas, occupied, blank } }),
  }
}

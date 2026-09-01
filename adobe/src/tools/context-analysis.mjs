const TOPICS = [
  { id: "chemsex", label: "chemsex", terms: ["chemsex", "chem sex", "sexo y drogas"], visualTerms: ["sexual health", "substance", "care", "consent"], roles: ["illustration", "symbol", "diagram"] },
  { id: "sexual-health", label: "salud sexual", terms: ["salud sexual", "sexual health", "its", "vih", "hiv", "condon", "condom", "sexo seguro", "reproductive"], visualTerms: ["sexual health", "condom", "care", "protection"], roles: ["health", "care", "symbol"] },
  { id: "substances", label: "sustancias", terms: ["sustancia", "sustancias", "droga", "drogas", "mdma", "extasis", "ghb", "ketamina", "cocaina", "popper", "metanfetamina", "capsula", "pastilla", "polvo", "alcohol"], visualTerms: ["substance", "pill", "bottle", "powder", "molecule"], roles: ["illustration", "icon", "diagram"] },
  { id: "risk", label: "riesgo", terms: ["riesgo", "riesgos", "warning", "peligro", "sobredosis", "overdose", "mezcla", "interaccion", "interacciones", "emergency"], visualTerms: ["warning", "risk", "interaction", "emergency", "care"], roles: ["warning", "diagram", "symbol"] },
  { id: "care", label: "cuidado", terms: ["cuidado", "cuidados", "reduccion de danos", "reduccion", "salud", "proteccion", "ayuda", "apoyo", "care", "harm reduction"], visualTerms: ["care", "protection", "health", "support", "heart"], roles: ["care", "health", "symbol"] },
  { id: "consent", label: "consentimiento", terms: ["consentimiento", "consent", "limites", "limite", "acuerdo", "pareja", "parejas"], visualTerms: ["consent", "people", "communication", "care"], roles: ["people", "symbol", "illustration"] },
  { id: "mental-health", label: "salud mental", terms: ["salud mental", "mental health", "ansiedad", "depresion", "panico", "bienestar"], visualTerms: ["mental health", "brain", "support", "care"], roles: ["care", "symbol", "illustration"] },
  { id: "context", label: "contexto", terms: ["contexto", "context", "lamina", "slide", "encuentro", "cruising", "fiesta", "party", "aplicacion", "app"], visualTerms: ["people", "context", "communication", "space"], roles: ["illustration", "people", "symbol"] },
]

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

function contextText(context = {}) {
  const values = [
    context.selection?.text,
    context.selection?.name,
    context.location?.label,
    context.document?.name,
    context.project?.name,
    ...(context.layers || []).flatMap((layer) => [layer?.name, layer?.text]),
  ]
  return values.filter(Boolean).map(String).join(" ").trim()
}

function countTerm(text, term) {
  const normalizedTerm = normalizeText(term)
  if (!normalizedTerm) return 0
  const matches = text.match(new RegExp(`(?:^|\\s)${normalizedTerm.replace(/\s+/g, "\\s+")}(?=\\s|$)`, "g"))
  return matches?.length || 0
}

export function analyzeContent(context = {}) {
  const rawText = contextText(context)
  const text = normalizeText(rawText)
  const topics = TOPICS.map((topic) => {
    const hits = topic.terms.reduce((sum, term) => sum + countTerm(text, term), 0)
    return { id: topic.id, label: topic.label, score: Number(Math.min(1, hits * 0.24).toFixed(2)), hits }
  }).filter((topic) => topic.hits > 0).sort((left, right) => right.score - left.score || right.hits - left.hits)
  const selectedTopics = topics.slice(0, 4)
  const topicById = new Map(TOPICS.map((topic) => [topic.id, topic]))
  const visualTerms = [...new Set(selectedTopics.flatMap((topic) => topicById.get(topic.id)?.visualTerms || []))]
  const suggestedRoles = [...new Set(selectedTopics.flatMap((topic) => topicById.get(topic.id)?.roles || []))]
  return {
    source: "deterministic-local",
    text: rawText.slice(0, 6000),
    normalizedText: text.slice(0, 6000),
    topics: selectedTopics,
    primaryTopic: selectedTopics[0] || null,
    visualTerms,
    suggestedRoles,
    confidence: Number(Math.min(0.98, selectedTopics.reduce((sum, topic) => sum + topic.score, 0) / 2 || 0).toFixed(2)),
  }
}

function numeric(value, fallback = 0) {
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function clamp(value, min, max) { return Math.max(min, Math.min(max, value)) }

function normalizeBounds(value, width, height) {
  if (!value || typeof value !== "object") return null
  const left = clamp(numeric(value.left), 0, width)
  const top = clamp(numeric(value.top), 0, height)
  const right = clamp(numeric(value.right, width), 0, width)
  const bottom = clamp(numeric(value.bottom, height), 0, height)
  if (right <= left || bottom <= top) return null
  return { left: Number(left.toFixed(2)), top: Number(top.toFixed(2)), right: Number(right.toFixed(2)), bottom: Number(bottom.toFixed(2)) }
}

function rectArea(rect) { return Math.max(0, rect.right - rect.left) * Math.max(0, rect.bottom - rect.top) }

function rectOverlap(a, b) {
  const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left))
  const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top))
  return width * height
}

function deriveCanvas(context) {
  const width = numeric(context.document?.width, 1080)
  const height = numeric(context.document?.height, 1080)
  return { width: Math.max(1, width), height: Math.max(1, height) }
}

function deriveOccupied(context, canvas) {
  const layerRegions = (context.layers || [])
    .filter((layer) => layer.visible !== false && layer.bounds)
    .map((layer) => ({ bounds: layer.bounds, name: normalizeText(layer.name), kind: normalizeText(layer.kind) }))
    .filter((layer) => {
      const region = normalizeBounds(layer.bounds, canvas.width, canvas.height)
      if (!region) return false
      const ratio = rectArea(region) / (canvas.width * canvas.height)
      const backgroundName = /background|fondo|base|artboard|canvas|color fill|relleno/.test(layer.name)
      // Full-canvas backgrounds sit underneath the artwork and should not
      // prevent the shelf from suggesting an overlay placement.
      return !(ratio >= 0.9 && (backgroundName || layer.kind !== "text"))
    })
  const source = Array.isArray(context.layers) && context.layers.length
    ? [...layerRegions.map((layer) => layer.bounds), ...(context.selection?.bounds ? [context.selection.bounds] : [])]
    : [...(context.occupiedRegions || []), ...(context.selection?.bounds ? [context.selection.bounds] : [])]
  const seen = new Set()
  return source.map((region) => normalizeBounds(region, canvas.width, canvas.height)).filter((region) => {
    if (!region) return false
    const key = JSON.stringify(region)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function cellIndex(x, y, columns) { return y * columns + x }

function analyzeBlankAreas(occupied, canvas, columns = 24, rows = 24) {
  const occupiedCells = new Set()
  for (let y = 0; y < rows; y += 1) {
    for (let x = 0; x < columns; x += 1) {
      const cell = {
        left: (x / columns) * canvas.width,
        top: (y / rows) * canvas.height,
        right: ((x + 1) / columns) * canvas.width,
        bottom: ((y + 1) / rows) * canvas.height,
      }
      if (occupied.some((region) => rectOverlap(cell, region) / rectArea(cell) >= 0.16)) occupiedCells.add(cellIndex(x, y, columns))
    }
  }
  const candidates = []
  const free = (x, y) => !occupiedCells.has(cellIndex(x, y, columns))
  // Enumerate maximal axis-aligned rectangles of free cells. This prevents a
  // connected U-shaped perimeter from becoming a false rectangle through a layer.
  for (let top = 0; top < rows; top += 1) {
    const validColumns = Array(columns).fill(true)
    for (let bottom = top; bottom < rows; bottom += 1) {
      for (let x = 0; x < columns; x += 1) validColumns[x] = validColumns[x] && free(x, bottom)
      let start = null
      for (let x = 0; x <= columns; x += 1) {
        if (x < columns && validColumns[x]) {
          if (start === null) start = x
          continue
        }
        if (start !== null) {
          const cellCount = (bottom - top + 1) * (x - start)
          if (cellCount >= 2) candidates.push({ minX: start, maxX: x, minY: top, maxY: bottom + 1, cellCount })
          start = null
        }
      }
    }
  }
  const unique = new Map(candidates.map((candidate) => [`${candidate.minX}:${candidate.minY}:${candidate.maxX}:${candidate.maxY}`, candidate]))
  const maximal = [...unique.values()].filter((candidate, _, all) => !all.some((other) => {
    const strictlyLarger = other.cellCount > candidate.cellCount
    const contains = other.minX <= candidate.minX && other.minY <= candidate.minY && other.maxX >= candidate.maxX && other.maxY >= candidate.maxY
    return strictlyLarger && contains
  }))
  return maximal
    .filter((candidate) => candidate.cellCount >= Math.max(2, Math.ceil(columns * rows * 0.02)))
    .sort((left, right) => right.cellCount - left.cellCount)
    .slice(0, 12)
    .map((candidate, index) => {
      const bounds = { left: Number(((candidate.minX / columns) * canvas.width).toFixed(2)), top: Number(((candidate.minY / rows) * canvas.height).toFixed(2)), right: Number(((candidate.maxX / columns) * canvas.width).toFixed(2)), bottom: Number(((candidate.maxY / rows) * canvas.height).toFixed(2)) }
      const area = candidate.cellCount * (canvas.width / columns) * (canvas.height / rows)
      return { bounds, area: Number(area.toFixed(2)), areaRatio: Number((area / (canvas.width * canvas.height)).toFixed(4)), aspectRatio: Number(((bounds.right - bounds.left) / (bounds.bottom - bounds.top)).toFixed(4)), cellCount: candidate.cellCount, edge: candidate.minX === 0 || candidate.minY === 0 || candidate.maxX === columns || candidate.maxY === rows, rank: index + 1 }
    })
}

function positionFor(bounds, canvas) {
  const centerX = (bounds.left + bounds.right) / 2
  const centerY = (bounds.top + bounds.bottom) / 2
  const horizontal = centerX < canvas.width / 3 ? "left" : centerX > (canvas.width * 2) / 3 ? "right" : "center"
  const vertical = centerY < canvas.height / 3 ? "top" : centerY >= (canvas.height * 2) / 3 ? "bottom" : "middle"
  return `${vertical}-${horizontal}`
}

export function analyzeLayout(context = {}) {
  const canvas = deriveCanvas(context)
  const occupied = deriveOccupied(context, canvas)
  const blankAreas = analyzeBlankAreas(occupied, canvas)
  const hostSafeRegions = (context.safeRegions || []).map((region) => normalizeBounds(region, canvas.width, canvas.height)).filter(Boolean)
  const placementCandidates = (hostSafeRegions.length ? hostSafeRegions.map((bounds, index) => ({ bounds, source: "host", rank: index + 1, area: rectArea(bounds), areaRatio: rectArea(bounds) / (canvas.width * canvas.height) })) : blankAreas.slice(0, 5).map((area) => ({ ...area, source: "detected" })))
    .sort((left, right) => right.area - left.area)
    .map((candidate, index) => ({ ...candidate, rank: index + 1, position: positionFor(candidate.bounds, canvas) }))
  const occupiedArea = occupied.reduce((total, region) => total + rectArea(region), 0)
  const canvasArea = canvas.width * canvas.height
  return {
    canvas,
    occupied,
    occupiedArea: Number(occupiedArea.toFixed(2)),
    occupiedRatio: Number(Math.min(1, occupiedArea / canvasArea).toFixed(4)),
    blankRatio: Number(Math.max(0, 1 - Math.min(1, occupiedArea / canvasArea)).toFixed(4)),
    blankAreas,
    safeRegions: hostSafeRegions,
    placementCandidates,
    method: "grid-24x24",
  }
}

const GENERIC_LAYER_NAME = /^(?:layer|capa|group|grupo|copy|copia|untitled|sin titulo)(?:[\s_-]*(?:\d+|copy\s*\d+|\(\d+\)))?$/i

function layerNameText(layer) { return normalizeText(layer?.name) }

function layerKindText(layer) { return normalizeText(layer?.kind) }

function layerId(layer, index) { return layer?.id ? String(layer.id) : `index:${index}` }

function isGroupLayer(layer) { return /group|grupo/.test(layerKindText(layer)) }

function isTextLayer(layer) { return /text|texto/.test(layerKindText(layer)) }

function isBackgroundLayer(layer) { return /background|fondo|base|artboard|canvas|colorfill|relleno/.test(layerNameText(layer)) }

function layerBucket(layer) {
  const name = layerNameText(layer)
  const kind = layerKindText(layer)
  if (isBackgroundLayer(layer)) return "background"
  if (isTextLayer(layer)) return "text"
  if (/icon|icono|logo|svg|vector|shape|forma/.test(name) || /shape|vector/.test(kind)) return "icons"
  if (/image|imagen|photo|foto|pixel|raster|smart|bitmap/.test(`${name} ${kind}`)) return "images"
  if (/effect|efecto|adjustment|ajuste|filter|filtro|shadow|sombra/.test(`${name} ${kind}`)) return "effects"
  return "other"
}

export function analyzeLayerStructure(context = {}) {
  const canvas = deriveCanvas(context)
  const source = Array.isArray(context.layers) ? context.layers : []
  const layers = source.map((layer, index) => ({
    ...layer,
    index,
    id: layerId(layer, index),
    name: String(layer?.name || "").trim(),
    nameText: layerNameText(layer),
    kindText: layerKindText(layer),
    bounds: normalizeBounds(layer?.bounds, canvas.width, canvas.height),
  }))
  const issues = []
  const addIssue = (severity, code, title, reason, affectedLayers = [], affectedBounds = []) => {
    issues.push({
      id: `${code}:${issues.length + 1}`,
      severity,
      code,
      title,
      reason,
      layerIds: affectedLayers.map((layer) => layer.id || layerId(layer, layer.index)),
      layerNames: affectedLayers.map((layer) => layer.name || `Capa ${layer.index + 1}`),
      bounds: affectedBounds.filter(Boolean).slice(0, 4),
    })
  }

  const genericLayers = layers.filter((layer) => !layer.nameText || GENERIC_LAYER_NAME.test(layer.name))
  for (const layer of genericLayers.slice(0, 12)) {
    addIssue("warning", "generic-name", layer.name ? `Nombre genérico: ${layer.name}` : "Capa sin nombre", "Usa un nombre que describa la función o el contenido de la capa.", [layer], [layer.bounds])
  }

  const names = new Map()
  for (const layer of layers) {
    if (!layer.nameText) continue
    if (!names.has(layer.nameText)) names.set(layer.nameText, [])
    names.get(layer.nameText).push(layer)
  }
  const duplicateNameGroups = [...names.values()].filter((group) => group.length > 1)
  for (const group of duplicateNameGroups.slice(0, 8)) {
    addIssue("warning", "duplicate-name", `Nombre repetido: ${group[0].name}`, `${group.length} capas comparten el mismo nombre y pueden confundirse al editar.`, group)
  }

  const knownIds = new Set(layers.map((layer) => layer.id))
  for (const layer of layers.filter((candidate) => candidate.parentId && !knownIds.has(String(candidate.parentId))).slice(0, 6)) {
    addIssue("warning", "orphan-layer", `Jerarquía incompleta: ${layer.name || "capa"}`, "La capa declara un grupo padre que no está presente en el contexto recibido.", [layer], [layer.bounds])
  }

  const visibleLayers = layers.filter((layer) => layer.visible !== false)
  const drawableLayers = visibleLayers.filter((layer) => !isGroupLayer(layer) && !isBackgroundLayer(layer))
  const possibleEmptyLayers = drawableLayers.filter((layer) => !layer.bounds)
  for (const layer of possibleEmptyLayers.slice(0, 8)) {
    addIssue("info", "missing-bounds", `Contenido no detectable: ${layer.name || "capa"}`, "Puede estar vacía, ser sólo un ajuste o no exponer límites geométricos al plugin.", [layer])
  }

  const outsideLayers = layers.filter((layer) => {
    const value = layer?.bounds
    if (!value || ![value.left, value.top, value.right, value.bottom].every((item) => Number.isFinite(Number(item)))) return false
    return Number(value.right) <= 0 || Number(value.bottom) <= 0 || Number(value.left) >= canvas.width || Number(value.top) >= canvas.height
  })
  for (const layer of outsideLayers.slice(0, 8)) {
    addIssue("warning", `outside-canvas`, `Fuera del lienzo: ${layer.name || "capa"}`, "La capa no intersecta el área visible del documento y puede dificultar la composición.", [layer], [layer.bounds])
  }

  const overlaps = []
  for (let left = 0; left < drawableLayers.length; left += 1) {
    for (let right = left + 1; right < drawableLayers.length; right += 1) {
      const first = drawableLayers[left]
      const second = drawableLayers[right]
      if (!first.bounds || !second.bounds || (isTextLayer(first) && isTextLayer(second))) continue
      const overlap = rectOverlap(first.bounds, second.bounds)
      const smallerArea = Math.min(rectArea(first.bounds), rectArea(second.bounds))
      const ratio = smallerArea ? overlap / smallerArea : 0
      if (ratio >= 0.45) overlaps.push({ first, second, ratio })
    }
  }
  overlaps.sort((left, right) => right.ratio - left.ratio)
  for (const pair of overlaps.slice(0, 8)) {
    const percentage = Math.round(pair.ratio * 100)
    addIssue(pair.ratio >= 0.75 ? "warning" : "info", "overlap", `Solapamiento: ${pair.first.name || "capa"} · ${pair.second.name || "capa"}`, `${percentage}% del área de la capa menor queda cubierta por otra capa; revisa si es intencional.`, [pair.first, pair.second], [pair.first.bounds, pair.second.bounds])
  }

  const topLevel = layers.filter((layer) => Number(layer.depth || 0) === 0)
  if (topLevel.length >= 6 && !layers.some((layer) => isGroupLayer(layer))) {
    addIssue("info", "flat-stack", "Pila sin grupos temáticos", `${topLevel.length} capas están en el nivel raíz; agrupar texto, imágenes, íconos y efectos facilitaría futuras ediciones.`, topLevel.slice(0, 12))
  }

  const proposal = [
    ["background", "01 · Fondo"],
    ["images", "02 · Imágenes"],
    ["icons", "03 · Íconos"],
    ["text", "04 · Texto"],
    ["effects", "05 · Efectos"],
    ["other", "99 · Otros"],
  ].map(([id, label]) => ({ id, label, layerIds: layers.filter((layer) => layerBucket(layer) === id).map((layer) => layer.id), layerNames: layers.filter((layer) => layerBucket(layer) === id).map((layer) => layer.name || `Capa ${layer.index + 1}`).slice(0, 12) })).filter((group) => group.layerIds.length)

  const severityWeight = { warning: 10, info: 3 }
  const score = Math.max(0, Math.min(100, 100 - issues.reduce((total, issue) => total + (severityWeight[issue.severity] || 0), 0)))
  const summary = {
    total: layers.length,
    visible: visibleLayers.length,
    hidden: layers.length - visibleLayers.length,
    groups: layers.filter(isGroupLayer).length,
    genericNames: genericLayers.length,
    duplicateNameGroups: duplicateNameGroups.length,
    possibleEmpty: possibleEmptyLayers.length,
    outsideCanvas: outsideLayers.length,
    overlapPairs: overlaps.length,
  }

  return {
    version: 1,
    score,
    summary,
    issues: issues.sort((left, right) => (severityWeight[right.severity] || 0) - (severityWeight[left.severity] || 0)).slice(0, 24),
    orderProposal: proposal,
    method: "layer-structure-v1",
  }
}

export function analyzeContext(context = {}) {
  const content = analyzeContent(context)
  const layout = analyzeLayout(context)
  const layers = analyzeLayerStructure(context)
  const palette = Array.isArray(context.palette) && context.palette.length
    ? { source: "host", colors: context.palette.slice(0, 12), available: true }
    : { source: "not-provided", colors: [], available: false, note: "El adaptador todavía no envió una muestra de píxeles o paleta." }
  const primary = content.primaryTopic?.label || "el contenido actual"
  const bestArea = layout.placementCandidates[0]
  return {
    version: 1,
    content,
    layout,
    layers,
    palette,
    suggestions: [
      { type: "content", priority: 1, title: `Buscar recursos para ${primary}`, reason: content.visualTerms.length ? `Términos visuales: ${content.visualTerms.slice(0, 5).join(", ")}.` : "No hay texto semántico suficiente; se usará el nombre de la capa/documento." },
      ...(bestArea ? [{ type: "placement", priority: 1, title: `Probar en ${bestArea.position}`, reason: `Es la zona libre más grande detectada (${Math.round(bestArea.areaRatio * 100)}% del lienzo).`, bounds: bestArea.bounds }] : []),
      ...(palette.available ? [{ type: "palette", priority: 2, title: "Conservar la paleta del documento", reason: `${palette.colors.length} colores recibidos desde el host.` }] : []),
    ],
  }
}

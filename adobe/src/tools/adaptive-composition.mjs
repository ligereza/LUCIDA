const DEFAULT_CONFIG = {
  canvas: { width: 1080, height: 1440 },
  margins: { top: 80, right: 88, bottom: 80, left: 88 },
  previewWidths: [360, 390, 430],
  grid: { columns: 24, rows: 32 },
  minBodySourcePx: 44,
  preferredBodySourcePx: 50,
  maxBodySourcePx: 60,
  minimumPreviewBodyPx: 16,
  paragraphGapRatio: 0.75,
  lineHeightRatio: 1.45,
  maxProposals: 6,
}

const TYPE_RANGES = {
  title: { min: 96, ideal: 120, max: 144, lineHeight: 1.05, widthFactor: 0.6 },
  subtitle: { min: 56, ideal: 64, max: 80, lineHeight: 1.2, widthFactor: 0.55 },
  body: { min: 44, ideal: 50, max: 60, lineHeight: 1.45, widthFactor: 0.52 },
  label: { min: 36, ideal: 40, max: 44, lineHeight: 1.2, widthFactor: 0.5 },
}

const VARIANTS = [
  { id: "single-column", label: "Columna única", weight: 1 },
  { id: "side-by-side", label: "Texto e ilustración lateral", weight: 0.96 },
  { id: "top-text-bottom-art", label: "Texto arriba e ilustración abajo", weight: 0.94 },
  { id: "bottom-text-top-art", label: "Ilustración arriba y texto abajo", weight: 0.92 },
]

function number(value, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function clamp(value, min, max) { return Math.max(min, Math.min(max, value)) }

function round(value, digits = 2) {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

function area(rect) {
  return Math.max(0, rect.right - rect.left) * Math.max(0, rect.bottom - rect.top)
}

function overlap(first, second) {
  return Math.max(0, Math.min(first.right, second.right) - Math.max(first.left, second.left))
    * Math.max(0, Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top))
}

function normalizeRect(value, canvas) {
  if (!value || typeof value !== "object") return null
  const left = clamp(number(value.left), 0, canvas.width)
  const top = clamp(number(value.top), 0, canvas.height)
  const right = clamp(number(value.right, canvas.width), 0, canvas.width)
  const bottom = clamp(number(value.bottom, canvas.height), 0, canvas.height)
  if (right <= left || bottom <= top) return null
  return { left: round(left), top: round(top), right: round(right), bottom: round(bottom) }
}

function inset(rect, value) {
  const left = rect.left + value
  const top = rect.top + value
  const right = rect.right - value
  const bottom = rect.bottom - value
  return right > left && bottom > top ? { left, top, right, bottom } : rect
}

function mergeConfig(options = {}) {
  return {
    ...DEFAULT_CONFIG,
    ...options,
    canvas: { ...DEFAULT_CONFIG.canvas, ...(options.canvas || {}) },
    margins: { ...DEFAULT_CONFIG.margins, ...(options.margins || {}) },
    grid: { ...DEFAULT_CONFIG.grid, ...(options.grid || {}) },
    previewWidths: Array.isArray(options.previewWidths) && options.previewWidths.length
      ? options.previewWidths.map((value) => Math.max(1, number(value))).slice(0, 6)
      : DEFAULT_CONFIG.previewWidths,
  }
}

function roleFromBlock(block = {}) {
  const text = `${block.role || ""} ${block.name || ""} ${block.kind || ""}`.toLowerCase()
  if (/title|titulo|heading|headline/.test(text)) return "title"
  if (/subtitle|subtitulo|subheading|bajada/.test(text)) return "subtitle"
  if (/label|tag|eyebrow|etiqueta|cta/.test(text)) return "label"
  return "body"
}

function roleFromName(name, index) {
  const role = roleFromBlock({ name })
  if (role !== "body") return role
  return index === 0 ? "title" : "body"
}

function layerIsText(layer = {}) {
  return /text|texto|type|typography/.test(String(layer.kind || "").toLowerCase()) || typeof layer.text === "string"
}

function layerIsBackground(layer = {}) {
  return /background|fondo|base|artboard|canvas|color.?fill|relleno/.test(`${layer.name || ""} ${layer.kind || ""}`.toLowerCase())
}

function sourceTextBlocks(context = {}) {
  if (Array.isArray(context.textBlocks) && context.textBlocks.length) {
    return context.textBlocks
      .filter((block) => typeof block?.text === "string" && block.text.length > 0)
      .map((block, index) => ({
        id: String(block.id || `text:${index}`),
        name: String(block.name || ""),
        role: roleFromBlock(block),
        text: block.text,
        order: number(block.order, index),
        bounds: block.bounds || null,
        source: "provided",
      }))
      .sort((left, right) => left.order - right.order || left.id.localeCompare(right.id))
  }
  const layers = Array.isArray(context.layers) ? context.layers : []
  const blocks = layers
    .filter((layer) => layerIsText(layer) && typeof layer.text === "string" && layer.text.length > 0)
    .map((layer, index) => ({
      id: String(layer.id || `layer:${index}`),
      name: String(layer.name || ""),
      role: roleFromName(layer.name, index),
      text: layer.text,
      order: number(layer.order, index),
      bounds: layer.bounds || null,
      source: "layer",
    }))
    .sort((left, right) => left.order - right.order || left.id.localeCompare(right.id))
  if (blocks.length) return blocks
  if (typeof context.selection?.text === "string" && context.selection.text.length) {
    return [{ id: "selection", name: context.selection.name || "", role: "body", text: context.selection.text, order: 0, bounds: context.selection.bounds || null, source: "selection" }]
  }
  return []
}

export function extractTextBlocks(context = {}) {
  return sourceTextBlocks(context).map((block) => ({ ...block, role: roleFromBlock(block) }))
}

function sourceOccupied(context, canvas) {
  const explicit = Array.isArray(context.occupiedRegions) ? context.occupiedRegions : []
  const layers = Array.isArray(context.layers) ? context.layers : []
  const fromLayers = layers
    .filter((layer) => layer.visible !== false && layer.bounds && !layerIsBackground(layer))
    .map((layer) => layer.bounds)
  const regions = [...explicit, ...fromLayers, ...(context.selection?.bounds ? [context.selection.bounds] : [])]
    .map((value) => normalizeRect(value, canvas))
    .filter(Boolean)
  const seen = new Set()
  return regions.filter((region) => {
    const key = JSON.stringify(region)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function cellKey(x, y, columns) { return y * columns + x }

function cellRect(x, y, columns, rows, canvas) {
  return {
    left: (x / columns) * canvas.width,
    top: (y / rows) * canvas.height,
    right: ((x + 1) / columns) * canvas.width,
    bottom: ((y + 1) / rows) * canvas.height,
  }
}

function freeGrid(occupied, canvas, columns, rows) {
  const free = Array.from({ length: rows }, () => Array(columns).fill(true))
  for (let y = 0; y < rows; y += 1) {
    for (let x = 0; x < columns; x += 1) {
      const cell = cellRect(x, y, columns, rows, canvas)
      if (occupied.some((region) => overlap(cell, region) / area(cell) >= 0.16)) free[y][x] = false
    }
  }
  return free
}

function connectedFreeComponents(free, columns, rows) {
  const visited = new Set()
  const components = []
  for (let y = 0; y < rows; y += 1) {
    for (let x = 0; x < columns; x += 1) {
      const start = cellKey(x, y, columns)
      if (!free[y][x] || visited.has(start)) continue
      const queue = [[x, y]]
      const cells = []
      visited.add(start)
      while (queue.length) {
        const [currentX, currentY] = queue.shift()
        cells.push([currentX, currentY])
        for (const [nextX, nextY] of [[currentX - 1, currentY], [currentX + 1, currentY], [currentX, currentY - 1], [currentX, currentY + 1]]) {
          if (nextX < 0 || nextY < 0 || nextX >= columns || nextY >= rows) continue
          const key = cellKey(nextX, nextY, columns)
          if (free[nextY][nextX] && !visited.has(key)) {
            visited.add(key)
            queue.push([nextX, nextY])
          }
        }
      }
      components.push(cells)
    }
  }
  return components
}

function largestRectangles(free, columns, rows) {
  const candidates = []
  for (let top = 0; top < rows; top += 1) {
    const valid = Array(columns).fill(true)
    for (let bottom = top; bottom < rows; bottom += 1) {
      for (let x = 0; x < columns; x += 1) valid[x] = valid[x] && free[bottom][x]
      let start = null
      for (let x = 0; x <= columns; x += 1) {
        if (x < columns && valid[x]) {
          if (start === null) start = x
        } else if (start !== null) {
          const width = x - start
          const height = bottom - top + 1
          if (width * height >= 2) candidates.push({ minX: start, maxX: x, minY: top, maxY: bottom + 1, cellCount: width * height })
          start = null
        }
      }
    }
  }
  return candidates
    .sort((left, right) => right.cellCount - left.cellCount)
    .filter((candidate, index, all) => index === all.findIndex((other) => other.minX === candidate.minX && other.maxX === candidate.maxX && other.minY === candidate.minY && other.maxY === candidate.maxY))
    .filter((candidate, _, all) => !all.some((other) => other.cellCount > candidate.cellCount && other.minX <= candidate.minX && other.minY <= candidate.minY && other.maxX >= candidate.maxX && other.maxY >= candidate.maxY))
}

export function detectWhiteSpace({ canvas: rawCanvas = DEFAULT_CONFIG.canvas, occupiedRegions = [], safeRegions = [], columns = 24, rows = 32 } = {}) {
  const canvas = { width: Math.max(1, number(rawCanvas.width, 1080)), height: Math.max(1, number(rawCanvas.height, 1440)) }
  const occupied = occupiedRegions.map((value) => normalizeRect(value, canvas)).filter(Boolean)
  const explicit = safeRegions.map((value) => normalizeRect(value, canvas)).filter(Boolean)
  const free = freeGrid(occupied, canvas, columns, rows)
  const components = connectedFreeComponents(free, columns, rows)
  const rectangles = largestRectangles(free, columns, rows)
  const componentByCell = new Map(components.flatMap((component, index) => component.map(([x, y]) => [cellKey(x, y, columns), index])))
  const detected = rectangles.map((candidate) => {
    const bounds = {
      left: round((candidate.minX / columns) * canvas.width),
      top: round((candidate.minY / rows) * canvas.height),
      right: round((candidate.maxX / columns) * canvas.width),
      bottom: round((candidate.maxY / rows) * canvas.height),
    }
    const cells = []
    for (let y = candidate.minY; y < candidate.maxY; y += 1) for (let x = candidate.minX; x < candidate.maxX; x += 1) cells.push(cellKey(x, y, columns))
    const componentIds = new Set(cells.map((key) => componentByCell.get(key)).filter((value) => value !== undefined))
    const componentSize = Math.max(1, ...[...componentIds].map((id) => components[id]?.length || 1))
    const rectangleArea = area(bounds)
    const cellArea = (canvas.width / columns) * (canvas.height / rows)
    return {
      bounds,
      area: round(rectangleArea),
      areaRatio: round(rectangleArea / (canvas.width * canvas.height), 4),
      aspectRatio: round((bounds.right - bounds.left) / (bounds.bottom - bounds.top), 4),
      fillRatio: round((candidate.cellCount * cellArea) / Math.max(rectangleArea, 1), 4),
      componentSize,
      source: "detected",
    }
  })
  const candidates = [...explicit.map((bounds) => ({ bounds, area: area(bounds), areaRatio: area(bounds) / (canvas.width * canvas.height), aspectRatio: (bounds.right - bounds.left) / (bounds.bottom - bounds.top), fillRatio: 1, source: "host" })), ...detected]
  const seen = new Set()
  return candidates
    .filter((candidate) => {
      const key = JSON.stringify(candidate.bounds)
      if (seen.has(key)) return false
      seen.add(key)
      return candidate.areaRatio >= 0.02
    })
    .sort((left, right) => right.area - left.area)
    .slice(0, 12)
    .map((candidate, index) => ({ ...candidate, rank: index + 1 }))
}

function charWidth(character, fontSize, factor) {
  if (/\s/.test(character)) return fontSize * 0.28
  if (/[ilI1.,:;!'|]/.test(character)) return fontSize * 0.26
  if (/[MW@#%&Q]/.test(character)) return fontSize * 0.82
  if (/[A-ZÁÉÍÓÚÑ]/.test(character)) return fontSize * 0.66
  return fontSize * factor
}

function estimatedWidth(value, fontSize, factor) {
  return [...String(value)].reduce((total, character) => total + charWidth(character, fontSize, factor), 0)
}

function wrapLine(source, width, fontSize, factor) {
  const words = String(source).trim().split(/\s+/).filter(Boolean)
  if (!words.length) return [""]
  const lines = []
  let current = ""
  for (const word of words) {
    const next = current ? `${current} ${word}` : word
    if (current && estimatedWidth(next, fontSize, factor) > width) {
      lines.push(current)
      current = word
      continue
    }
    if (!current && estimatedWidth(word, fontSize, factor) > width) {
      let piece = ""
      for (const character of word) {
        if (piece && estimatedWidth(piece + character, fontSize, factor) > width) {
          lines.push(piece)
          piece = character
        } else piece += character
      }
      current = piece
      continue
    }
    current = next
  }
  if (current) lines.push(current)
  return lines
}

export function typographyFor(role, options = {}) {
  const range = TYPE_RANGES[role] || TYPE_RANGES.body
  const configuredBody = role === "body" ? number(options.bodySize, range.ideal) : null
  const size = clamp(configuredBody || number(options.size, range.ideal), range.min, range.max)
  const lineHeight = size * number(options.lineHeightRatio, range.lineHeight)
  return { role, size: round(size), lineHeight: round(lineHeight), widthFactor: number(options.widthFactor, range.widthFactor) }
}

export function estimateDisplayPx(sourcePx, canvasWidth = 1080, previewWidth = 390) {
  return round(number(sourcePx) * number(previewWidth) / Math.max(1, number(canvasWidth, 1080)), 2)
}

export function measureTextBlock(text, { width, role = "body", size, lineHeightRatio, paragraphGapRatio, widthFactor } = {}) {
  const typography = typographyFor(role, { size, lineHeightRatio, widthFactor })
  const safeWidth = Math.max(1, number(width, 1))
  const paragraphs = String(text ?? "").split(/\n/)
  const lines = []
  for (const paragraph of paragraphs) {
    const wrapped = wrapLine(paragraph, safeWidth, typography.size, typography.widthFactor)
    lines.push(...wrapped)
  }
  const paragraphGap = typography.size * number(paragraphGapRatio, role === "body" ? DEFAULT_CONFIG.paragraphGapRatio : 0.25)
  const height = lines.length * typography.lineHeight + Math.max(0, paragraphs.length - 1) * paragraphGap
  return {
    text: String(text ?? ""),
    role,
    width: round(safeWidth),
    fontSize: typography.size,
    lineHeight: typography.lineHeight,
    lineCount: lines.length,
    paragraphCount: paragraphs.length,
    height: round(height),
    lines,
    overflow: false,
    method: "deterministic-font-metrics-v1",
  }
}

function textZoneForVariant(region, variant) {
  const width = region.right - region.left
  const height = region.bottom - region.top
  if (variant === "side-by-side" && width / height >= 0.75) {
    const textWidth = width * 0.58
    return {
      text: { left: region.left, top: region.top, right: region.left + textWidth, bottom: region.bottom },
      illustration: { left: region.left + width * 0.66, top: region.top + height * 0.08, right: region.right, bottom: region.bottom - height * 0.08 },
    }
  }
  if (variant === "top-text-bottom-art") {
    return {
      text: { left: region.left, top: region.top, right: region.right, bottom: region.top + height * 0.43 },
      illustration: { left: region.left + width * 0.08, top: region.top + height * 0.52, right: region.right - width * 0.08, bottom: region.bottom },
    }
  }
  if (variant === "bottom-text-top-art") {
    return {
      text: { left: region.left, top: region.top + height * 0.58, right: region.right, bottom: region.bottom },
      illustration: { left: region.left + width * 0.08, top: region.top, right: region.right - width * 0.08, bottom: region.top + height * 0.48 },
    }
  }
  return { text: region, illustration: null }
}

function layoutTextBlocks(blocks, region, bodySize, config) {
  const gap = 24
  let cursor = region.top
  const placements = []
  let totalHeight = 0
  for (const block of blocks) {
    const typography = typographyFor(block.role, { bodySize, lineHeightRatio: block.role === "body" ? config.lineHeightRatio : undefined })
    const measured = measureTextBlock(block.text, { width: region.right - region.left, role: block.role, size: typography.size, lineHeightRatio: block.role === "body" ? config.lineHeightRatio : undefined })
    const placement = {
      id: block.id,
      role: block.role,
      text: block.text,
      bounds: { left: round(region.left), top: round(cursor), right: round(region.right), bottom: round(cursor + measured.height) },
      fontSize: measured.fontSize,
      lineHeight: measured.lineHeight,
      lineCount: measured.lineCount,
      height: measured.height,
    }
    placements.push(placement)
    cursor += measured.height + gap
    totalHeight += measured.height
  }
  const usedHeight = Math.max(0, cursor - region.top - (placements.length ? gap : 0))
  return { placements, usedHeight: round(usedHeight), fits: cursor - (placements.length ? gap : 0) <= region.bottom, remaining: round(region.bottom - (cursor - (placements.length ? gap : 0))) }
}

function splitTextPreservingSource(text, width, role, maxHeight, bodySize, config) {
  const raw = String(text ?? "")
  if (!raw) return []
  const tokens = [...raw.matchAll(/\S+/g)]
  if (!tokens.length) return [raw]
  const typography = typographyFor(role, { bodySize, lineHeightRatio: role === "body" ? config.lineHeightRatio : undefined })
  const maxLines = Math.max(1, Math.floor(number(maxHeight, typography.lineHeight) / typography.lineHeight))
  const parts = []
  let start = 0
  let lastEnd = 0
  for (const token of tokens) {
    const candidateEnd = token.index + token[0].length
    const candidate = raw.slice(start, candidateEnd)
    const measured = measureTextBlock(candidate, { width, role, size: typography.size, lineHeightRatio: role === "body" ? config.lineHeightRatio : undefined })
    if (lastEnd > start && measured.lineCount > maxLines) {
      parts.push(raw.slice(start, lastEnd))
      start = lastEnd
    }
    lastEnd = candidateEnd
  }
  if (start < raw.length) parts.push(raw.slice(start))
  return parts.filter((part) => part.length > 0)
}

function paginateBlocks(blocks, region, bodySize, config) {
  const pages = [[]]
  let pageHeight = 0
  for (const block of blocks) {
    const measured = measureTextBlock(block.text, { width: region.right - region.left, role: block.role, size: typographyFor(block.role, { bodySize }).size, lineHeightRatio: block.role === "body" ? config.lineHeightRatio : undefined })
    const available = Math.max(1, region.bottom - region.top - pageHeight)
    const parts = measured.height <= available ? [block.text] : splitTextPreservingSource(block.text, region.right - region.left, block.role, available, bodySize, config)
    for (const [index, part] of parts.entries()) {
      const partMeasured = measureTextBlock(part, { width: region.right - region.left, role: block.role, size: typographyFor(block.role, { bodySize }).size, lineHeightRatio: block.role === "body" ? config.lineHeightRatio : undefined })
      if (pageHeight && pageHeight + partMeasured.height > region.bottom - region.top) {
        pages.push([])
        pageHeight = 0
      }
      pages.at(-1).push({ ...block, id: parts.length > 1 ? `${block.id}:part-${index + 1}` : block.id, text: part })
      pageHeight += partMeasured.height + 24
    }
  }
  return pages.filter((page) => page.length)
}

function variantScore({ fits, readable, density, whitespace, variant }) {
  return round(100 * ((fits ? 0.35 : 0.05) + readable * 0.3 + density * 0.15 + whitespace * 0.1 + variant.weight * 0.1))
}

function positionLabel(bounds, canvas) {
  const centerX = (bounds.left + bounds.right) / 2
  const centerY = (bounds.top + bounds.bottom) / 2
  return `${centerY < canvas.height / 3 ? "top" : centerY > canvas.height * 2 / 3 ? "bottom" : "middle"}-${centerX < canvas.width / 3 ? "left" : centerX > canvas.width * 2 / 3 ? "right" : "center"}`
}

function proposeForRegion(blocks, candidate, variant, config, visualCount) {
  const region = inset(candidate.bounds, 24)
  const zones = textZoneForVariant(region, variant.id)
  const attempts = [config.preferredBodySourcePx, config.preferredBodySourcePx - 4, config.minBodySourcePx]
  const options = []
  for (const bodySize of attempts) {
    const textLayout = layoutTextBlocks(blocks, zones.text, bodySize, config)
    const readableValues = config.previewWidths.map((width) => estimateDisplayPx(bodySize, config.canvas.width, width))
    const readable = readableValues.every((value) => value >= config.minimumPreviewBodyPx) ? 1 : readableValues.some((value) => value >= config.minimumPreviewBodyPx) ? 0.7 : 0.35
    const density = clamp(1 - Math.abs(0.68 - textLayout.usedHeight / Math.max(1, zones.text.bottom - zones.text.top)), 0, 1)
    const whitespace = clamp(candidate.fillRatio || 1, 0, 1)
    options.push({ bodySize, textLayout, readable, density, whitespace })
    if (textLayout.fits) break
  }
  const selected = options.find((option) => option.textLayout.fits) || options.at(-1)
  const pages = selected.textLayout.fits ? [blocks] : paginateBlocks(blocks, zones.text, selected.bodySize, config)
  const warnings = []
  if (!selected.textLayout.fits) warnings.push("El contenido no cabe en una sola lámina con el tamaño mínimo recomendado.")
  if (selected.bodySize < config.preferredBodySourcePx) warnings.push(`La propuesta reduce el cuerpo a ${selected.bodySize}px del lienzo.`)
  if (selected.readable < 1) warnings.push("El cuerpo queda por debajo del objetivo de lectura en al menos un ancho de teléfono.")
  if (!zones.illustration && visualCount === 0) warnings.push("No se recibió una zona de ilustración; la propuesta reserva espacio negativo.")
  const score = variantScore({ fits: selected.textLayout.fits, readable: selected.readable, density: selected.density, whitespace: selected.whitespace, variant })
  return {
    variant: variant.id,
    label: variant.label,
    score,
    sourceRegion: candidate.bounds,
    textRegion: zones.text,
    illustrationRegion: zones.illustration,
    position: positionLabel(zones.text, config.canvas),
    textBlocks: selected.textLayout.placements,
    pages: pages.map((page, index) => ({ index: index + 1, blockIds: page.map((block) => block.id), textPreserved: page.map((block) => block.text).join("") })),
    metrics: {
      bodySourcePx: selected.bodySize,
      bodyPreviewPx: Object.fromEntries(config.previewWidths.map((width) => [String(width), estimateDisplayPx(selected.bodySize, config.canvas.width, width)])),
      usedTextHeight: selected.textLayout.usedHeight,
      availableTextHeight: round(zones.text.bottom - zones.text.top),
      remainingTextHeight: selected.textLayout.remaining,
      density: round(selected.textLayout.usedHeight / Math.max(1, zones.text.bottom - zones.text.top), 4),
      whiteSpaceFill: candidate.fillRatio || 1,
    },
    reasons: [
      `Zona ${candidate.source === "host" ? "declarada por el host" : "detectada por retícula"}.`,
      `${Math.round(candidate.areaRatio * 100)}% del lienzo disponible para la composición.`,
      `Cuerpo visible estimado: ${Math.round(Math.min(...config.previewWidths.map((width) => estimateDisplayPx(selected.bodySize, config.canvas.width, width))))}px en el teléfono más pequeño.`,
    ],
    warnings,
    method: "constraint-search-v1",
  }
}

export function proposeAdaptiveComposition(context = {}, options = {}) {
  const config = mergeConfig(options)
  const canvas = {
    width: Math.max(1, number(context.document?.width, config.canvas.width)),
    height: Math.max(1, number(context.document?.height, config.canvas.height)),
  }
  const localConfig = { ...config, canvas }
  const blocks = extractTextBlocks(context)
  if (!blocks.length) {
    return { version: 1, status: "no-text", canvas, textBlocks: [], whiteSpace: { candidates: [] }, proposals: [], constraints: { textPreserved: true, automaticHostActions: false }, method: "adaptive-composition-v1" }
  }
  const occupied = sourceOccupied(context, canvas)
  const candidates = detectWhiteSpace({ canvas, occupiedRegions: occupied, safeRegions: context.safeRegions || [], ...config.grid })
  const fallback = normalizeRect({ left: config.margins.left, top: config.margins.top, right: canvas.width - config.margins.right, bottom: canvas.height - config.margins.bottom }, canvas)
  const regions = candidates.length ? candidates : [{ bounds: fallback, area: area(fallback), areaRatio: area(fallback) / (canvas.width * canvas.height), aspectRatio: (fallback.right - fallback.left) / (fallback.bottom - fallback.top), fillRatio: 1, source: "fallback", rank: 1 }]
  const visualCount = (Array.isArray(context.visualBlocks) ? context.visualBlocks : (context.layers || []).filter((layer) => !layerIsText(layer) && layer.visible !== false)).length
  const proposals = regions.flatMap((candidate) => VARIANTS.map((variant) => proposeForRegion(blocks, candidate, variant, localConfig, visualCount)))
    .sort((left, right) => right.score - left.score || left.variant.localeCompare(right.variant))
    .slice(0, config.maxProposals)
    .map((proposal, index) => ({ ...proposal, rank: index + 1 }))
  return {
    version: 1,
    status: "proposed",
    canvas,
    textBlocks: blocks.map(({ id, role, text, source }) => ({ id, role, text, source, preservedExactly: true })),
    whiteSpace: { method: "grid-components-and-maximal-rectangles-v1", occupiedRegions: occupied, candidates: regions.slice(0, 12) },
    typography: {
      sourceCanvasWidth: canvas.width,
      previewWidths: config.previewWidths,
      bodyRange: { min: config.minBodySourcePx, preferred: config.preferredBodySourcePx, max: config.maxBodySourcePx },
      displayFormula: "sourcePx * previewWidth / canvasWidth",
    },
    proposals,
    constraints: {
      textPreserved: true,
      splitOnlyAtSourceBoundaries: true,
      automaticHostActions: false,
      requiresHumanConfirmation: true,
    },
    method: "adaptive-composition-v1",
  }
}

export { DEFAULT_CONFIG as DEFAULT_ADAPTIVE_COMPOSITION_CONFIG, TYPE_RANGES }

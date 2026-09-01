const clamp = (value, min, max) => Math.max(min, Math.min(max, value))

const stripAccents = (value) => String(value || "")
  .toLowerCase()
  .normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "")

const clean = (value) => String(value || "").replace(/\s+/g, " ").trim()

const box = (x, y, width, height) => ({
  x: Number(x.toFixed(4)),
  y: Number(y.toFixed(4)),
  width: Number(width.toFixed(4)),
  height: Number(height.toFixed(4)),
})

const wrapCount = (value, charsPerLine) => {
  const limit = Math.max(8, Math.floor(charsPerLine))
  const paragraphs = String(value || "").split(/\n+/).filter(Boolean)
  if (!paragraphs.length) return 0
  return paragraphs.reduce((total, paragraph) => {
    const words = paragraph.trim().split(/\s+/).filter(Boolean)
    let line = 0
    let count = 1
    for (const word of words) {
      if (line && line + word.length + 1 > limit) {
        count += 1
        line = word.length
      } else line += word.length + (line ? 1 : 0)
    }
    return total + count
  }, 0)
}

export function wrapText(value, charsPerLine = 42) {
  const limit = Math.max(8, Math.floor(charsPerLine))
  const lines = []
  for (const paragraph of String(value || "").split(/\n+/).filter(Boolean)) {
    let line = ""
    for (const word of paragraph.trim().split(/\s+/).filter(Boolean)) {
      if (line && line.length + word.length + 1 > limit) {
        lines.push(line)
        line = word
      } else line += line ? ` ${word}` : word
    }
    if (line) lines.push(line)
  }
  return lines
}

export function estimateTextMetrics({ title = "", text = "", typography = {}, width = 720, height = 420 } = {}) {
  const titleText = clean(title)
  const bodyText = clean(text)
  const titleSize = Number(typography.titleSize) || 52
  const summarySize = Number(typography.summarySize) || 24
  const innerWidth = Math.max(80, Number(width) - 36)
  const titleCharsPerLine = Math.max(8, innerWidth / (titleSize * 0.54))
  const bodyCharsPerLine = Math.max(10, innerWidth / (summarySize * 0.52))
  const titleLines = wrapCount(titleText, titleCharsPerLine)
  const bodyLines = wrapCount(bodyText, bodyCharsPerLine)
  const wordCount = bodyText ? bodyText.split(/\s+/).length : 0
  const paragraphCount = String(text || "").split(/\n+/).filter((part) => part.trim()).length
  const listItemCount = (String(text || "").match(/(?:^|\n)\s*(?:[-*•]|\d+[.)])\s+/g) || []).length
  const estimatedHeight = titleLines * titleSize * 1.12 + bodyLines * summarySize * 1.36 + 18
  const capacityLines = Math.max(1, Math.floor((Number(height) - 24 - titleLines * titleSize * 1.12) / (summarySize * 1.36)))
  const density = clamp((estimatedHeight / Math.max(1, Number(height))) * 0.92, 0, 1.5)
  const load = clamp((bodyText.length + titleText.length * 2.2) / 620, 0, 1.35)
  return {
    titleChars: titleText.length,
    bodyChars: bodyText.length,
    wordCount,
    paragraphCount,
    listItemCount,
    estimatedTitleLines: titleLines,
    estimatedBodyLines: bodyLines,
    estimatedLines: titleLines + bodyLines,
    estimatedHeight: Math.round(estimatedHeight),
    capacityLines,
    density: Number(density.toFixed(3)),
    load: Number(load.toFixed(3)),
    overflow: bodyLines > capacityLines,
    recommendedSummarySize: Math.round(clamp(summarySize * Math.min(1, capacityLines / Math.max(1, bodyLines)), 14, summarySize)),
  }
}

function containsAny(value, terms) {
  return terms.some((term) => value.includes(term))
}

export function inferTheme({ title = "", sourceText = "", keywords = [], index = 0, total = 1, theme = "auto" } = {}) {
  if (theme && theme !== "auto") return theme
  const value = stripAccents(`${title} ${sourceText} ${keywords.join(" ")}`)
  const titleValue = stripAccents(title)
  if (index === 0 && /portada|chemsex|orgullo/.test(titleValue)) return "cover"
  if (containsAny(titleValue, ["que es", "definicion", "se refiere"])) return "definition"
  if (containsAny(titleValue, ["cierre", "comunidad", "apoyo"])) return "close"
  if (containsAny(titleValue, ["interaccion", "mezcla"])) return "interactions"
  if (containsAny(titleValue, ["riesgo", "peligro", "sobredosis"])) return "risks"
  if (containsAny(titleValue, ["sustancia", "droga", "mdma", "cocaina", "ketamina", "metanf"])) return "substances"
  if (containsAny(titleValue, ["contexto", "chile", "datos", "realidad"])) return "context"
  if (containsAny(titleValue, ["cuid", "reduccion", "hidrat", "consentimiento"])) return "care"
  if (index === total - 1 && containsAny(value, ["comunidad", "comunitar", "acompana", "apoyo", "orgullo", "ayuda", "cierre"])) return "close"
  if (containsAny(value, ["interaccion", "mezcla", "mezclar", "alcohol", "viagra", "ketamina"])) return "interactions"
  if (containsAny(value, ["riesgo", "peligro", "sobredosis", "emergencia", "senal de alerta", "crisis"])) return "risks"
  if (containsAny(value, ["sustancia", "droga", "mdma", "cocaina", "metanf", "mephedrone", "ghb", "gbh"])) return "substances"
  if (containsAny(value, ["contexto", "chile", "estudio", "datos", "realidad", "investigacion"])) return "context"
  if (containsAny(value, ["cuidarnos", "cuidado", "reduccion de danos", "hidrat", "descanso", "consentimiento", "condon", "hablar"])) return "care"
  if (containsAny(value, ["que es", "definicion", "se refiere", "consiste en"])) return "definition"
  return "general"
}

const tagsByTheme = {
  cover: ["community", "identity", "care"],
  definition: ["communication", "body", "context"],
  context: ["context", "community", "data"],
  substances: ["substance", "pill", "body"],
  risks: ["warning", "emergency", "body"],
  care: ["care", "water", "consent", "communication"],
  interactions: ["substance", "warning", "heart", "body"],
  close: ["community", "care", "communication"],
  general: ["community", "care", "context"],
}

function safeRegion(design) {
  const width = Number(design?.canvas?.width) || 1080
  const height = Number(design?.canvas?.height) || 1350
  const margins = design?.margins || { top: 96, right: 96, bottom: 96, left: 96 }
  return {
    x: margins.left / width,
    y: margins.top / height,
    width: 1 - (margins.left + margins.right) / width,
    height: 1 - (margins.top + margins.bottom) / height,
  }
}

function geometry(variant, region, load) {
  const { x, y, width, height } = region
  const gap = Math.min(width, height) * 0.035
  const textHeight = height * clamp(0.19 + load * 0.19, 0.19, 0.4)
  const textWidth = width * clamp(0.4 + load * 0.1, 0.4, 0.54)
  if (variant === "side-left") {
    return { text: box(x, y, textWidth, height), illustration: box(x + textWidth + gap, y, width - textWidth - gap, height) }
  }
  if (variant === "side-right") {
    return { illustration: box(x, y, width - textWidth - gap, height), text: box(x + width - textWidth, y, textWidth, height) }
  }
  if (variant === "diagonal") {
    return { illustration: box(x + width * 0.25, y, width * 0.75, height * 0.56), text: box(x, y + height * 0.62, width * 0.72, height * 0.34) }
  }
  if (variant === "bottom-band") {
    return { illustration: box(x, y, width, height * 0.62), text: box(x, y + height * 0.68, width, height * 0.28) }
  }
  if (variant === "center-card") {
    return { illustration: box(x, y, width, height), text: box(x + width * 0.1, y + height * 0.22, width * 0.8, height * 0.54) }
  }
  if (variant === "full-bleed-art") {
    return { illustration: box(x, y, width, height), text: box(x + width * 0.06, y + height * 0.05, width * 0.76, height * 0.2) }
  }
  return { text: box(x, y, width, textHeight), illustration: box(x, y + textHeight + gap, width, height - textHeight - gap) }
}

export const VECTOR_AXES = ["care", "community", "context", "risk", "substance", "interaction", "urgency", "textLoad"]

// Chemsex content is represented in this fixed semantic space. Values are normalized 0..1.
export const THEME_VECTORS = {
  cover: [0.8, 1, 0.2, 0.1, 0.1, 0.1, 0.1, 0.15],
  definition: [0.6, 0.5, 0.8, 0.2, 0.4, 0.2, 0.2, 0.65],
  context: [0.4, 0.7, 1, 0.3, 0.8, 0.4, 0.3, 0.65],
  substances: [0.3, 0.3, 0.6, 0.5, 1, 0.5, 0.4, 0.6],
  risks: [0.3, 0.3, 0.4, 1, 0.5, 0.6, 0.9, 0.75],
  care: [1, 0.9, 0.4, 0.4, 0.2, 0.3, 0.4, 0.8],
  interactions: [0.2, 0.2, 0.4, 0.9, 1, 1, 0.9, 0.75],
  close: [1, 1, 0.2, 0.2, 0.1, 0.1, 0.1, 0.25],
  general: [0.5, 0.5, 0.5, 0.4, 0.4, 0.4, 0.3, 0.6],
}

// Layout vectors describe what each geometry is good at, in the same semantic space.
export const LAYOUT_VECTORS = {
  "full-bleed-art": [0.8, 1, 0.3, 0.2, 0.1, 0.1, 0.1, 0.15],
  "center-card": [0.8, 0.8, 0.7, 0.3, 0.2, 0.2, 0.2, 0.45],
  "side-left": [0.6, 0.4, 0.6, 0.8, 0.7, 0.8, 0.7, 0.95],
  "side-right": [0.6, 0.4, 0.6, 0.8, 0.7, 0.8, 0.7, 0.95],
  diagonal: [0.3, 0.3, 0.5, 1, 1, 1, 0.9, 0.7],
  "bottom-band": [1, 0.8, 0.5, 0.4, 0.2, 0.3, 0.4, 0.8],
  "top-text-bottom-art": [0.6, 0.7, 0.5, 0.4, 0.2, 0.2, 0.2, 0.9],
}

// Editorial prior for this carousel. It is a deterministic matrix, not randomness:
// rows are Chemsex themes and columns are candidate geometries.
export const THEME_LAYOUT_PRIORS = {
  cover: { "full-bleed-art": 1, "center-card": 0.6, "top-text-bottom-art": 0.5, "bottom-band": 0.35, "side-left": 0.25, "side-right": 0.25, diagonal: 0.4 },
  definition: { "center-card": 0.95, "side-left": 0.8, "top-text-bottom-art": 0.65, "side-right": 0.55, diagonal: 0.4, "bottom-band": 0.35, "full-bleed-art": 0.3 },
  context: { diagonal: 0.95, "side-right": 0.88, "center-card": 0.55, "side-left": 0.45, "bottom-band": 0.4, "top-text-bottom-art": 0.35, "full-bleed-art": 0.25 },
  substances: { "side-right": 0.9, diagonal: 0.82, "side-left": 0.65, "center-card": 0.45, "top-text-bottom-art": 0.4, "bottom-band": 0.3, "full-bleed-art": 0.2 },
  risks: { diagonal: 0.98, "side-left": 0.82, "side-right": 0.72, "center-card": 0.4, "top-text-bottom-art": 0.35, "bottom-band": 0.25, "full-bleed-art": 0.15 },
  care: { "bottom-band": 0.98, "side-left": 0.75, "center-card": 0.6, "top-text-bottom-art": 0.5, "side-right": 0.45, diagonal: 0.35, "full-bleed-art": 0.3 },
  interactions: { "side-right": 0.94, diagonal: 0.9, "side-left": 0.72, "bottom-band": 0.35, "center-card": 0.3, "top-text-bottom-art": 0.25, "full-bleed-art": 0.1 },
  close: { "center-card": 1, "full-bleed-art": 0.35, "bottom-band": 0.6, "side-left": 0.45, "side-right": 0.4, "top-text-bottom-art": 0.35, diagonal: 0.25 },
  general: { "top-text-bottom-art": 0.75, "side-left": 0.7, "side-right": 0.65, "bottom-band": 0.55, "center-card": 0.5, diagonal: 0.45, "full-bleed-art": 0.35 },
}

const vectorLength = (vector) => Math.sqrt(vector.reduce((sum, value) => sum + value ** 2, 0)) || 1
const cosineSimilarity = (a, b) => a.reduce((sum, value, index) => sum + value * (b[index] || 0), 0) / (vectorLength(a) * vectorLength(b))

export function semanticVector(theme, load = null, override = null) {
  const vector = [...(THEME_VECTORS[theme] || THEME_VECTORS.general)]
  if (Array.isArray(override)) {
    for (let index = 0; index < VECTOR_AXES.length; index += 1) if (Number.isFinite(Number(override[index]))) vector[index] = clamp(Number(override[index]), 0, 1)
  }
  if (load != null) vector[VECTOR_AXES.indexOf("textLoad")] = clamp(Number(load) || 0, 0, 1)
  return vector
}

export function scoreLayoutCandidate({ theme = "general", variant, load = 0, metrics = {}, index = 0, vectorOverride = null } = {}) {
  const content = semanticVector(theme, load, vectorOverride)
  const layout = LAYOUT_VECTORS[variant] || LAYOUT_VECTORS["top-text-bottom-art"]
  const semanticFit = cosineSimilarity(content, layout)
  const editorialPrior = THEME_LAYOUT_PRIORS[theme]?.[variant] ?? THEME_LAYOUT_PRIORS.general[variant] ?? 0
  const textFit = metrics.overflow ? -0.8 : clamp(1 - Math.abs((metrics.density || 0) - 0.55) * 0.55, 0.45, 1)
  const repetitionPenalty = variant === "side-left" && index % 2 === 0 ? 0.012 : variant === "side-right" && index % 2 === 1 ? 0.012 : 0
  return Number((semanticFit * 0.52 + editorialPrior * 0.23 + textFit * 0.25 + repetitionPenalty).toFixed(5))
}

function chooseVariant(theme, load, index, design, region, title, sourceText, vectorOverride = null) {
  const candidates = Object.keys(LAYOUT_VECTORS).map((variant) => {
    const candidateGeometry = geometry(variant, region, load)
    const metrics = estimateTextMetrics({
      title,
      text: sourceText,
      typography: design.typography,
      width: candidateGeometry.text.width * (design.canvas?.width || 1080),
      height: candidateGeometry.text.height * (design.canvas?.height || 1350),
    })
    return { variant, score: scoreLayoutCandidate({ theme, variant, load, metrics, index, vectorOverride }) }
  })
  candidates.sort((a, b) => b.score - a.score || a.variant.localeCompare(b.variant))
  return candidates[0]
}

export function chooseLayout({ title = "", text = "", sourceText = text, keywords = [], theme = "auto", index = 0, total = 1, design = {} } = {}) {
  const resolvedTheme = inferTheme({ title, sourceText, keywords, index, total, theme })
  const vectorOverride = design.themeVectors?.[resolvedTheme] || design.themeVectors?.all || null
  const typography = design.typography || {}
  const region = safeRegion(design)
  const baseline = estimateTextMetrics({ title, text: sourceText, typography, width: region.width * (design.canvas?.width || 1080), height: region.height * (design.canvas?.height || 1350) * 0.36 })
  const selection = chooseVariant(resolvedTheme, baseline.load, index, design, region, title, sourceText, vectorOverride)
  let variant = selection.variant
  let geometryResult = geometry(variant, region, baseline.load)
  let metrics = estimateTextMetrics({ title, text: sourceText, typography, width: geometryResult.text.width * (design.canvas?.width || 1080), height: geometryResult.text.height * (design.canvas?.height || 1350) })
  if (metrics.overflow && !["side-left", "side-right"].includes(variant) && resolvedTheme !== "cover") {
    variant = "side-left"
    geometryResult = geometry(variant, region, Math.max(baseline.load, 0.75))
    metrics = estimateTextMetrics({ title, text: sourceText, typography, width: geometryResult.text.width * (design.canvas?.width || 1080), height: geometryResult.text.height * (design.canvas?.height || 1350) })
  }
  const contentVector = semanticVector(resolvedTheme, baseline.load, vectorOverride)
  const layoutVector = LAYOUT_VECTORS[variant] || LAYOUT_VECTORS["top-text-bottom-art"]
  const layoutScore = scoreLayoutCandidate({ theme: resolvedTheme, variant, load: baseline.load, metrics, index, vectorOverride })
  return {
    mode: "auto",
    variant,
    text: geometryResult.text,
    illustration: geometryResult.illustration,
    textSide: geometryResult.text.x < geometryResult.illustration.x ? "left" : "right",
    textAlignment: variant === "center-card" ? "center" : "left",
    visualRole: {
      cover: "community-led title image",
      definition: "conversation and shared context",
      context: "social context and connected people",
      substances: "substance constellation with clear associations",
      risks: "warning system and body signals",
      care: "peer care, water, consent and practical support",
      interactions: "interacting substances and amplified risk",
      close: "network of support and collective care",
      general: "thematic editorial illustration",
    }[resolvedTheme],
    theme: resolvedTheme,
    semanticTags: tagsByTheme[resolvedTheme] || tagsByTheme.general,
    textMetrics: metrics,
    overlap: ["center-card", "full-bleed-art"].includes(variant),
    contentVector,
    layoutVector,
    layoutScore,
  }
}

export function planLayouts(parts = [], design = {}, { theme = design.theme || "auto" } = {}) {
  const auto = design.autoLayout !== false && design.layout?.mode !== "manual"
  return parts.map((part, index) => {
    if (!auto) {
      const fallback = design.layout || {}
      const metrics = estimateTextMetrics({
        title: part.title,
        text: part.sourceText,
        typography: design.typography,
        width: (fallback.text?.width || 0.84) * (design.canvas?.width || 1080),
        height: (fallback.text?.height || 0.22) * (design.canvas?.height || 1350),
      })
      return { ...part, theme: inferTheme({ title: part.title, sourceText: part.sourceText, keywords: part.keywords, index, total: parts.length, theme }), semanticTags: tagsByTheme[inferTheme({ title: part.title, sourceText: part.sourceText, keywords: part.keywords, index, total: parts.length, theme })] || tagsByTheme.general, textMetrics: metrics, layout: { ...fallback, mode: "manual", variant: fallback.mode || "manual" } }
    }
    const layout = chooseLayout({ title: part.title, text: part.sourceText, sourceText: part.sourceText, keywords: part.keywords, theme, index, total: parts.length, design })
    return { ...part, theme: layout.theme, semanticTags: layout.semanticTags, textMetrics: layout.textMetrics, contentVector: layout.contentVector, layoutVector: layout.layoutVector, layoutScore: layout.layoutScore, layout }
  })
}

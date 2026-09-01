import fs from "node:fs/promises"
import path from "node:path"
import zlib from "node:zlib"
import { analyzeContent } from "./context-analysis.mjs"
import { ensureLocalCatalog, DEFAULT_CATALOG_ROOTS, normalizeText, scoreEntry, tokensFor } from "./local-catalog.mjs"
import { ensureDir, TOOLKIT_ROOT } from "../utils.mjs"

const GROUP_INDEX_PATH = path.join(TOOLKIT_ROOT, "cache", "context-shelf", "groups.json")
const COLOR_NAMES = {
  black: [0, 0, 0], white: [255, 255, 255], red: [220, 30, 45], orange: [245, 130, 30], yellow: [240, 200, 30], green: [45, 170, 85], cyan: [35, 185, 190], blue: [45, 105, 210], purple: [125, 70, 190], pink: [220, 70, 150],
}
const COLOR_LABELS = { black: "Negro", white: "Blanco", red: "Rojo", orange: "Naranja", yellow: "Amarillo", green: "Verde", cyan: "Cian", blue: "Azul", purple: "Morado", pink: "Rosado", gray: "Gris", unknown: "Color no disponible" }
const THEME_LABELS = { substances: "Sustancias", "sexual-health": "Salud sexual", care: "Cuidado", risk: "Riesgo", consent: "Consentimiento", "mental-health": "Salud mental", context: "Contexto", chemsex: "Chemsex", uncategorized: "Sin clasificar" }

function clamp(value, min, max) { return Math.max(min, Math.min(max, value)) }

function rgbToHex(red, green, blue) {
  return `#${[red, green, blue].map((value) => clamp(Math.round(value), 0, 255).toString(16).padStart(2, "0")).join("")}`
}

function rgbToHsl(red, green, blue) {
  const r = red / 255; const g = green / 255; const b = blue / 255
  const max = Math.max(r, g, b); const min = Math.min(r, g, b); const delta = max - min
  let hue = 0
  if (delta) {
    if (max === r) hue = ((g - b) / delta) % 6
    else if (max === g) hue = (b - r) / delta + 2
    else hue = (r - g) / delta + 4
    hue = (hue * 60 + 360) % 360
  }
  const lightness = (max + min) / 2
  const saturation = delta ? delta / (1 - Math.abs(2 * lightness - 1)) : 0
  return { hue, saturation: Number.isFinite(saturation) ? saturation : 0, lightness }
}

function colorBucket(red, green, blue) {
  const { hue, saturation, lightness } = rgbToHsl(red, green, blue)
  if (lightness <= 0.12) return "black"
  if (lightness >= 0.92 && saturation <= 0.18) return "white"
  if (saturation <= 0.14) return "gray"
  if (hue < 15 || hue >= 345) return "red"
  if (hue < 45) return "orange"
  if (hue < 70) return "yellow"
  if (hue < 165) return "green"
  if (hue < 195) return "cyan"
  if (hue < 255) return "blue"
  if (hue < 315) return "purple"
  return "pink"
}

function parseColor(value) {
  const raw = String(value || "").trim().toLowerCase()
  if (COLOR_NAMES[raw]) return COLOR_NAMES[raw]
  const hex = raw.replace(/^#/, "")
  if (/^[0-9a-f]{3,8}$/i.test(hex)) {
    const normalized = hex.length <= 4 ? hex.slice(0, 3).split("").map((digit) => `${digit}${digit}`).join("") : hex.slice(0, 6)
    return [parseInt(normalized.slice(0, 2), 16), parseInt(normalized.slice(2, 4), 16), parseInt(normalized.slice(4, 6), 16)]
  }
  const rgb = raw.match(/^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/)
  return rgb ? [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])] : null
}

function colorProfileFromValues(values) {
  const counts = new Map()
  for (const value of values) {
    const rgb = Array.isArray(value) ? value : parseColor(value)
    if (!rgb || rgb.some((channel) => !Number.isFinite(channel))) continue
    const hex = rgbToHex(...rgb)
    counts.set(hex, (counts.get(hex) || 0) + 1)
  }
  const dominant = [...counts.entries()].sort((left, right) => right[1] - left[1]).slice(0, 5).map(([hex]) => hex)
  const buckets = [...new Set(dominant.map((hex) => colorBucket(...parseColor(hex))))]
  return { dominantColors: dominant, colorBuckets: buckets.length ? buckets : ["unknown"], sampled: counts.size > 0 }
}

function svgColors(source) {
  const values = []
  for (const match of source.matchAll(/(?:fill|stroke|color|stop-color)\s*[:=]\s*["']?([^;"'\s]+)/gi)) values.push(match[1])
  for (const match of source.matchAll(/#[0-9a-f]{3,8}\b|rgba?\([^)]*\)/gi)) values.push(match[0])
  return colorProfileFromValues(values.filter((value) => !["none", "currentcolor", "inherit", "transparent"].includes(String(value).toLowerCase())))
}

function paeth(left, above, upperLeft) {
  const estimate = left + above - upperLeft
  const leftDistance = Math.abs(estimate - left); const aboveDistance = Math.abs(estimate - above); const upperLeftDistance = Math.abs(estimate - upperLeft)
  return leftDistance <= aboveDistance && leftDistance <= upperLeftDistance ? left : aboveDistance <= upperLeftDistance ? above : upperLeft
}

function pngColors(buffer) {
  if (buffer.length < 33 || buffer.toString("ascii", 1, 4) !== "PNG") return { dominantColors: [], colorBuckets: ["unknown"], sampled: false }
  let offset = 8; let width = 0; let height = 0; let bitDepth = 0; let colorType = 0; let interlace = 0; const idat = []; let palette = []; let transparency = []
  while (offset + 12 <= buffer.length) {
    const length = buffer.readUInt32BE(offset); const type = buffer.toString("ascii", offset + 4, offset + 8); const dataStart = offset + 8; const dataEnd = dataStart + length
    if (dataEnd + 4 > buffer.length) break
    if (type === "IHDR") { width = buffer.readUInt32BE(dataStart); height = buffer.readUInt32BE(dataStart + 4); bitDepth = buffer[dataStart + 8]; colorType = buffer[dataStart + 9]; interlace = buffer[dataStart + 12] }
    if (type === "PLTE") for (let index = 0; index + 2 < length; index += 3) palette.push([buffer[dataStart + index], buffer[dataStart + index + 1], buffer[dataStart + index + 2]])
    if (type === "tRNS") transparency = [...buffer.subarray(dataStart, dataEnd)]
    if (type === "IDAT") idat.push(buffer.subarray(dataStart, dataEnd))
    offset = dataEnd + 4
    if (type === "IEND") break
  }
  const channels = { 2: 3, 3: 1, 6: 4, 0: 1, 4: 2 }[colorType]
  if (!width || !height || bitDepth !== 8 || !channels || interlace !== 0 || colorType === 3 && !palette.length) return { dominantColors: [], colorBuckets: ["unknown"], sampled: false }
  let inflated
  try { inflated = zlib.inflateSync(Buffer.concat(idat)) } catch { return { dominantColors: [], colorBuckets: ["unknown"], sampled: false } }
  const rowBytes = width * channels; const counts = new Map(); let cursor = 0; let previous = Buffer.alloc(rowBytes)
  const stride = Math.max(1, Math.floor(Math.sqrt((width * height) / 1500)))
  for (let y = 0; y < height && cursor < inflated.length; y += 1) {
    const filter = inflated[cursor++]; const row = Buffer.alloc(rowBytes)
    for (let x = 0; x < rowBytes && cursor < inflated.length; x += 1) {
      const raw = inflated[cursor++]; const left = x >= channels ? row[x - channels] : 0; const above = previous[x] || 0; const upperLeft = x >= channels ? previous[x - channels] || 0 : 0
      row[x] = filter === 1 ? (raw + left) & 255 : filter === 2 ? (raw + above) & 255 : filter === 3 ? (raw + Math.floor((left + above) / 2)) & 255 : filter === 4 ? (raw + paeth(left, above, upperLeft)) & 255 : raw
    }
    if (y % stride === 0) for (let x = 0; x < width; x += stride) {
      const index = x * channels; const paletteColor = colorType === 3 ? palette[row[index]] : null; const alpha = colorType === 3 ? transparency[row[index]] ?? 255 : channels === 4 ? row[index + 3] : channels === 2 ? row[index + 1] : 255
      if (alpha < 40) continue
      const red = paletteColor?.[0] ?? row[index]; const green = paletteColor?.[1] ?? (channels >= 3 ? row[index + 1] : red); const blue = paletteColor?.[2] ?? (channels >= 3 ? row[index + 2] : red)
      const hex = rgbToHex(red, green, blue); counts.set(hex, (counts.get(hex) || 0) + 1)
    }
    previous = row
  }
  return colorProfileFromValues([...counts.keys()].flatMap((hex) => Array(counts.get(hex)).fill(hex)))
}

async function colorProfile(entry) {
  try {
    if (entry.format === "svg") return svgColors(await fs.readFile(entry.file, "utf8"))
    if (entry.format === "png" && entry.bytes <= 12_000_000) return pngColors(await fs.readFile(entry.file))
  } catch {}
  return { dominantColors: [], colorBuckets: ["unknown"], sampled: false }
}

function sizeGroup(bytes) {
  if (bytes <= 4_096) return ["tiny", "Tiny · hasta 4 KB"]
  if (bytes <= 50_000) return ["small", "Pequeño · hasta 50 KB"]
  if (bytes <= 500_000) return ["medium", "Mediano · hasta 500 KB"]
  if (bytes <= 2_000_000) return ["large", "Grande · hasta 2 MB"]
  return ["huge", "Muy grande · más de 2 MB"]
}

function dimensionGroup(entry) {
  if (entry.format === "svg") return ["vector", "Vector SVG"]
  if (!entry.width || !entry.height) return ["unknown", "Dimensión desconocida"]
  if (entry.width <= 128 && entry.height <= 128) return ["small-raster", "Raster pequeño · hasta 128 px"]
  if (entry.width <= 1024 && entry.height <= 1024) return ["standard-raster", "Raster estándar · hasta 1024 px"]
  return ["large-raster", "Raster grande · más de 1024 px"]
}

function aspectGroup(entry) {
  if (!entry.aspectRatio) return ["unknown", "Proporción desconocida"]
  if (entry.aspectRatio >= 0.92 && entry.aspectRatio <= 1.08) return ["square", "Cuadrado"]
  return entry.aspectRatio < 0.92 ? ["portrait", "Vertical"] : ["landscape", "Horizontal"]
}

function styleGroup(entry) {
  const match = entry.relativePath.match(/(?:^|\/)(filled|outline)(?:\/|$)/i)
  return match ? [match[1].toLowerCase(), match[1].toLowerCase() === "filled" ? "Filled" : "Outline"] : ["default", "Sin variante"]
}

function addGroup(groups, type, key, label, assetId) {
  groups[type] ||= {}
  groups[type][key] ||= { key, label, count: 0, assetIds: [] }
  groups[type][key].count += 1
  groups[type][key].assetIds.push(assetId)
}

function themeProfile(entry) {
  const semanticText = `${entry.name} ${entry.relativePath.split("/").slice(-4).join(" ")}`
  const analysis = analyzeContent({ selection: { text: semanticText } })
  const hints = {
    substances: ["chemical", "drug", "drugs", "pill", "tablet", "capsule", "powder", "cocaine", "mdma", "ghb", "ketamine", "amphetamine", "methamphetamine", "cannabis", "opioid", "molecule", "alcohol"],
    "sexual-health": ["sexual", "condom", "vih", "hiv", "its", "reproductive", "prep", "pep", "doxy", "sex"],
    care: ["care", "health", "protection", "support", "testeo", "heart", "salud"],
    risk: ["risk", "warning", "overdose", "sobredosis", "interaction", "complication", "emergency"],
    consent: ["consent", "consentimiento", "communication", "limit"],
    "mental-health": ["mental", "brain", "anxiety", "ansiedad", "panic", "panico", "wellbeing"],
    context: ["context", "people", "cruising", "encuentro", "application", "app", "party", "fiesta"],
  }
  const normalized = semanticText.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
  const inferred = Object.entries(hints).filter(([, terms]) => terms.some((term) => normalized.includes(term))).map(([id]) => id)
  const topics = [...new Set([...analysis.topics.map((topic) => topic.id), ...inferred])]
  return topics.length ? topics : ["uncategorized"]
}

async function readGroupIndex(indexPath = GROUP_INDEX_PATH) {
  try { return JSON.parse(await fs.readFile(indexPath, "utf8")) } catch { return null }
}

export async function indexLocalGroups({ indexPath = GROUP_INDEX_PATH, refresh = false, roots = DEFAULT_CATALOG_ROOTS, cachePath } = {}) {
  const catalog = await ensureLocalCatalog({ roots, cachePath })
  const previous = !refresh ? await readGroupIndex(indexPath) : null
  const assets = {}; const groups = {}
  for (const entry of Object.values(catalog?.entries || {})) {
    const old = previous?.assets?.[entry.assetId]
    const visual = old?.signature === entry.signature ? old : await colorProfile(entry)
    const themes = old?.signature === entry.signature ? old.themes : themeProfile(entry)
    const [size, sizeLabel] = sizeGroup(entry.bytes)
    const [dimension, dimensionLabel] = dimensionGroup(entry)
    const [aspect, aspectLabel] = aspectGroup(entry)
    const [style, styleLabel] = styleGroup(entry)
    const record = {
      assetId: entry.assetId, file: entry.file, relativePath: entry.relativePath, name: entry.name, label: entry.label, kind: entry.kind, format: entry.format,
      width: entry.width, height: entry.height, aspectRatio: entry.aspectRatio, bytes: entry.bytes, license: entry.license || null,
      signature: entry.signature, size, dimension, aspect, style, themes, dominantColors: visual.dominantColors, colorBuckets: visual.colorBuckets, colorSampled: visual.sampled,
    }
    assets[entry.assetId] = record
    addGroup(groups, "size", size, sizeLabel, entry.assetId)
    addGroup(groups, "dimension", dimension, dimensionLabel, entry.assetId)
    addGroup(groups, "aspect", aspect, aspectLabel, entry.assetId)
    addGroup(groups, "format", entry.format, entry.format.toUpperCase(), entry.assetId)
    addGroup(groups, "kind", entry.kind, entry.kind === "icon" ? "Íconos" : "Imágenes", entry.assetId)
    addGroup(groups, "style", style, styleLabel, entry.assetId)
    for (const theme of themes) addGroup(groups, "theme", theme, THEME_LABELS[theme] || theme.replaceAll("-", " "), entry.assetId)
    for (const color of visual.colorBuckets) addGroup(groups, "color", color, COLOR_LABELS[color] || color, entry.assetId)
  }
  const result = { schemaVersion: 1, generatedAt: new Date().toISOString(), catalogGeneratedAt: catalog?.generatedAt || null, total: Object.keys(assets).length, assets, groups }
  await ensureDir(path.dirname(indexPath))
  await fs.writeFile(indexPath, `${JSON.stringify(result, null, 2)}\n`, "utf8")
  return summarizeGroups(result)
}

function summarizeGroups(index) {
  const groups = Object.fromEntries(Object.entries(index.groups || {}).map(([type, values]) => [type, Object.values(values).map(({ key, label, count, assetIds }) => ({ key, label, count, sampleAssetIds: assetIds.slice(0, 6) })).sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))]))
  return { indexPath: GROUP_INDEX_PATH, generatedAt: index.generatedAt, catalogGeneratedAt: index.catalogGeneratedAt, total: index.total, groups }
}

export async function catalogGroupSummary({ refresh = false, indexPath = GROUP_INDEX_PATH, roots, cachePath } = {}) {
  let index = await readGroupIndex(indexPath)
  if (!index || refresh) { await indexLocalGroups({ refresh, indexPath, roots, cachePath }); index = await readGroupIndex(indexPath) }
  return summarizeGroups(index || { groups: {}, assets: {}, total: 0 })
}

export async function listCatalogAssets({ type = null, key = null, query = "", assetIds = null, page = 1, pageSize = 24, indexPath = GROUP_INDEX_PATH, roots, cachePath, semantic = false, semanticIndexPath } = {}) {
  let index = await readGroupIndex(indexPath)
  if (!index) { await indexLocalGroups({ indexPath, roots, cachePath }); index = await readGroupIndex(indexPath) }
  const safePage = Math.max(1, Number(page) || 1); const safePageSize = Math.min(100, Math.max(1, Number(pageSize) || 24)); const normalizedQuery = normalizeText(query); const queryTokens = tokensFor(query)
  const requestedAssetIds = new Set((Array.isArray(assetIds) ? assetIds : String(assetIds || "").split(",")).map((value) => String(value).trim()).filter(Boolean))
  let candidateAssetIds = Object.keys(index?.assets || {})
  if (type && key) candidateAssetIds = index?.groups?.[type]?.[key]?.assetIds || []
  if (requestedAssetIds.size) candidateAssetIds = candidateAssetIds.filter((assetId) => requestedAssetIds.has(assetId))
  let filtered = candidateAssetIds.map((assetId) => index.assets[assetId]).map((asset) => ({
    asset,
    score: scoreEntry(asset, queryTokens, normalizedQuery),
  })).filter(({ score }) => !queryTokens.length || score > 0).sort((left, right) => right.score - left.score || left.asset.name.localeCompare(right.asset.name)).map(({ asset, score }) => ({ ...asset, score }))
  let semanticSearch = { ready: false, reason: "Semantic search is disabled." }
  if (semantic && normalizedQuery) {
    try {
      const { semanticScoresForQuery } = await import("./mobileclip.mjs")
      semanticSearch = await semanticScoresForQuery({ query, indexPath: semanticIndexPath, candidateAssetIds })
      if (semanticSearch.ready) {
        const lexicalById = new Map(filtered.map((asset) => [asset.assetId, asset.score]))
        filtered = candidateAssetIds.map((assetId) => index.assets[assetId]).filter(Boolean).map((asset) => {
          const similarity = semanticSearch.scores.get(asset.assetId)
          return { ...asset, score: (Number.isFinite(similarity) ? similarity : -1) * 10 + (lexicalById.get(asset.assetId) || 0), semanticScore: Number.isFinite(similarity) ? Number(similarity.toFixed(5)) : null }
        }).sort((left, right) => right.score - left.score || left.name.localeCompare(right.name))
      }
    } catch (error) {
      semanticSearch = { ready: false, reason: error.message }
    }
  }
  const start = (safePage - 1) * safePageSize
  return { generatedAt: index?.generatedAt || null, type, key, query, page: safePage, pageSize: safePageSize, total: filtered.length, semantic: semanticSearch, results: filtered.slice(start, start + safePageSize).map((asset, position) => ({ ...asset, score: Number(asset.score.toFixed(2)), provider: "local", id: asset.relativePath, local: true, rank: start + position + 1 })) }
}

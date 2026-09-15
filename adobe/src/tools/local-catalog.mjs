import fs from "node:fs/promises"
import crypto from "node:crypto"
import path from "node:path"
import { assertAllowedInput, ensureDir, readFilePrefix, TOOLKIT_ROOT } from "../utils.mjs"
import { AUTHORED_CATALOG_ROOTS } from "../asset-provenance.mjs"

const REPO_ROOT = path.resolve(TOOLKIT_ROOT, "..")
const CACHE_PATH = path.join(TOOLKIT_ROOT, "cache", "context-shelf", "catalog.json")
const ASSET_EXTENSIONS = new Set([".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"])
const SEARCH_STOP_WORDS = new Set(["de", "del", "la", "el", "los", "las", "y", "o", "para", "con", "sin", "un", "una", "on", "in", "at", "of", "to", "is", "an", "as", "by", "text", "texto", "principal", "document", "documento", "psd", "lamina", "slide"])
const PATH_NOISE = new Set(["rd", "database", "complete", "agent", "toolkit", "projects", "public", "libraries", "extracted", "static", "assets", "icons", "icon", "healthicons", "bioicons", "generated", "filled", "outline", "cc", "by", "4", "0"])
const IGNORED_DIRECTORIES = new Set([
  ".git", "node_modules", "cache", "jobs", "_rejected", "__MACOSX", ".next", "dist", "build", "coverage",
])

const SEARCH_ALIASES = new Map([
  ["pulmon", ["pulmones", "lung", "lungs"]],
  ["pulmones", ["pulmon", "lung", "lungs"]],
  ["lung", ["lungs", "pulmon", "pulmones"]],
  ["lungs", ["lung", "pulmon", "pulmones"]],
  ["vih", ["hiv"]],
  ["hiv", ["vih"]],
  ["its", ["sti"]],
  ["sti", ["its"]],
  ["condon", ["condom"]],
  ["condom", ["condon"]],
  ["prevencion", ["prevention"]],
  ["prevention", ["prevencion"]],
  ["proteccion", ["protection"]],
  ["protection", ["proteccion"]],
  ["reduccion", ["reduction"]],
  ["reduction", ["reduccion"]],
  ["danos", ["harm"]],
  ["harm", ["danos"]],
  ["sustancia", ["sustancias", "substance", "substances"]],
  ["sustancias", ["sustancia", "substance", "substances"]],
  ["substance", ["sustancia", "sustancias", "substances"]],
  ["substances", ["sustancia", "sustancias", "substance"]],
  ["droga", ["drogas", "drug", "drugs"]],
  ["drogas", ["droga", "drug", "drugs"]],
  ["drug", ["drugs", "droga", "drogas"]],
  ["drugs", ["drug", "droga", "drogas"]],
  ["pastilla", ["pastillas", "pill", "pills"]],
  ["pastillas", ["pastilla", "pill", "pills"]],
  ["pill", ["pills", "pastilla", "pastillas"]],
  ["pills", ["pill", "pastilla", "pastillas"]],
  ["tableta", ["tabletas", "tablet", "tablets"]],
  ["tabletas", ["tableta", "tablet", "tablets"]],
  ["tablet", ["tablets", "tableta", "tabletas"]],
  ["tablets", ["tablet", "tableta", "tabletas"]],
  ["capsula", ["capsulas", "capsule", "capsules"]],
  ["capsulas", ["capsula", "capsule", "capsules"]],
  ["capsule", ["capsules", "capsula", "capsulas"]],
  ["capsules", ["capsule", "capsula", "capsulas"]],
  ["jeringa", ["jeringas", "syringe", "syringes"]],
  ["jeringas", ["jeringa", "syringe", "syringes"]],
  ["syringe", ["syringes", "jeringa", "jeringas"]],
  ["syringes", ["syringe", "jeringa", "jeringas"]],
  ["corazon", ["heart"]],
  ["heart", ["corazon"]],
  ["cerebro", ["brain"]],
  ["brain", ["cerebro"]],
  ["boca", ["mouth"]],
  ["mouth", ["boca"]],
  ["labio", ["lips"]],
  ["labios", ["lips"]],
  ["lips", ["labio", "labios"]],
  ["persona", ["person", "people", "personas"]],
  ["personas", ["person", "people", "persona"]],
  ["person", ["people", "persona", "personas"]],
  ["people", ["person", "persona", "personas"]],
  ["hombre", ["man"]],
  ["man", ["hombre"]],
  ["mujer", ["woman"]],
  ["woman", ["mujer"]],
  ["fiesta", ["party"]],
  ["party", ["fiesta"]],
  ["comunidad", ["community"]],
  ["community", ["comunidad"]],
  ["consentimiento", ["consent"]],
  ["consent", ["consentimiento"]],
  ["cuidado", ["care"]],
  ["care", ["cuidado"]],
  ["salud", ["health"]],
  ["health", ["salud"]],
  ["ayuda", ["help"]],
  ["help", ["ayuda"]],
  ["asistencia", ["assistance"]],
  ["assistance", ["asistencia"]],
  ["apoyo", ["support"]],
  ["support", ["apoyo"]],
  ["comunicacion", ["communication"]],
  ["communication", ["comunicacion"]],
  ["limite", ["limit"]],
  ["limits", ["limite"]],
  ["riesgo", ["risk"]],
  ["risk", ["riesgo"]],
  ["seguridad", ["safety"]],
  ["safety", ["seguridad"]],
])

const SEARCH_RELATIONS = new Map([
  ["pulmon", ["respiratory", "pulmonary"]],
  ["pulmones", ["respiratory", "pulmonary"]],
  ["lung", ["respiratory", "pulmonary"]],
  ["lungs", ["respiratory", "pulmonary"]],
  ["vih", ["virus", "viral"]],
  ["hiv", ["virus", "viral"]],
  ["its", ["std", "infection", "sexual"]],
  ["sti", ["std", "infection", "sexual"]],
  ["condon", ["protection"]],
  ["condom", ["protection"]],
  ["prevencion", ["protection", "safety"]],
  ["prevention", ["protection", "safety"]],
  ["proteccion", ["prevention", "safety"]],
  ["protection", ["prevention", "safety"]],
  ["reduccion", ["harm", "risk"]],
  ["reduction", ["harm", "risk"]],
  ["sustancia", ["drug"]],
  ["sustancias", ["drugs"]],
  ["droga", ["substance"]],
  ["drogas", ["substances"]],
  ["pastilla", ["tablet", "capsule"]],
  ["pastillas", ["tablets", "capsules"]],
  ["pill", ["tablet", "capsule"]],
  ["pills", ["tablets", "capsules"]],
  ["jeringa", ["needle"]],
  ["jeringas", ["needles"]],
  ["corazon", ["cardiac"]],
  ["cerebro", ["neural", "mental"]],
  ["boca", ["oral", "lips"]],
  ["labios", ["mouth", "oral"]],
  ["persona", ["human"]],
  ["personas", ["human"]],
  ["hombre", ["male"]],
  ["mujer", ["female"]],
  ["fiesta", ["event", "community"]],
  ["comunidad", ["people", "social"]],
  ["consentimiento", ["communication", "limits"]],
  ["cuidado", ["health", "support", "protection"]],
  ["ayuda", ["support", "care", "assistance"]],
  ["asistencia", ["help", "support", "care"]],
  ["riesgo", ["warning", "danger", "emergency"]],
])

const REVERSE_SEARCH_RELATIONS = new Map()
for (const [source, relatedTerms] of SEARCH_RELATIONS) {
  for (const relatedTerm of relatedTerms) {
    const reverseTerms = REVERSE_SEARCH_RELATIONS.get(relatedTerm) || []
    reverseTerms.push(source)
    REVERSE_SEARCH_RELATIONS.set(relatedTerm, reverseTerms)
  }
}

export const DEFAULT_CATALOG_ROOTS = AUTHORED_CATALOG_ROOTS

export function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
}

export function tokensFor(...values) {
  return [...new Set(values.flatMap((value) => normalizeText(value).split(/\s+/).filter((token) => token.length > 1 && !SEARCH_STOP_WORDS.has(token))))]
}

function numberFromAttribute(value) {
  const match = String(value || "").match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

function svgMetadata(source) {
  const svgTag = source.match(/<svg\b[^>]*>/i)?.[0] || ""
  const viewBox = svgTag.match(/\bviewBox\s*=\s*["']([^"']+)["']/i)?.[1]
  const viewBoxValues = viewBox ? viewBox.trim().split(/[\s,]+/).map(Number) : []
  const width = numberFromAttribute(svgTag.match(/\bwidth\s*=\s*["']([^"']+)["']/i)?.[1])
  const height = numberFromAttribute(svgTag.match(/\bheight\s*=\s*["']([^"']+)["']/i)?.[1])
  const viewWidth = Number.isFinite(viewBoxValues[2]) ? viewBoxValues[2] : null
  const viewHeight = Number.isFinite(viewBoxValues[3]) ? viewBoxValues[3] : null
  const resolvedWidth = width || viewWidth
  const resolvedHeight = height || viewHeight
  const title = source.match(/<(?:title|desc)\b[^>]*>([^<]{1,300})<\/(?:title|desc)>/i)?.[1]?.trim() || null
  const ariaLabel = svgTag.match(/\baria-label\s*=\s*["']([^"']+)["']/i)?.[1] || null
  return {
    width: resolvedWidth,
    height: resolvedHeight,
    aspectRatio: resolvedWidth && resolvedHeight ? Number((resolvedWidth / resolvedHeight).toFixed(4)) : null,
    viewBox: viewBoxValues.length === 4 ? viewBoxValues : null,
    embeddedLabel: title || ariaLabel,
  }
}

function rasterMetadata(buffer, format) {
  if (format === "png" && buffer.length >= 24 && buffer.readUInt32BE(0) === 0x89504e47) {
    return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20), aspectRatio: Number((buffer.readUInt32BE(16) / buffer.readUInt32BE(20)).toFixed(4)) }
  }
  if (format === "gif" && buffer.length >= 10 && buffer.toString("ascii", 0, 3) === "GIF") {
    const width = buffer.readUInt16LE(6)
    const height = buffer.readUInt16LE(8)
    return { width, height, aspectRatio: width && height ? Number((width / height).toFixed(4)) : null }
  }
  if (format === "webp" && buffer.length >= 30 && buffer.toString("ascii", 0, 4) === "RIFF" && buffer.toString("ascii", 8, 12) === "WEBP") {
    const chunk = buffer.toString("ascii", 12, 16)
    if (chunk === "VP8X" && buffer.length >= 30) {
      const width = 1 + buffer[24] + (buffer[25] << 8) + (buffer[26] << 16)
      const height = 1 + buffer[27] + (buffer[28] << 8) + (buffer[29] << 16)
      return { width, height, aspectRatio: Number((width / height).toFixed(4)) }
    }
  }
  if (["jpg", "jpeg"].includes(format)) {
    let offset = 2
    while (offset + 9 < buffer.length) {
      if (buffer[offset] !== 0xff) { offset += 1; continue }
      const marker = buffer[offset + 1]
      const length = buffer.readUInt16BE(offset + 2)
      if (marker >= 0xc0 && marker <= 0xc3 && offset + 8 < buffer.length) {
        const height = buffer.readUInt16BE(offset + 5)
        const width = buffer.readUInt16BE(offset + 7)
        return { width, height, aspectRatio: width && height ? Number((width / height).toFixed(4)) : null }
      }
      if (!length) break
      offset += 2 + length
    }
  }
  return { width: null, height: null, aspectRatio: null }
}

function cleanName(file, embeddedLabel = null) {
  if (embeddedLabel) return embeddedLabel.replace(/\s+/g, " ").trim().slice(0, 200)
  return path.basename(file, path.extname(file))
    .replace(/^(?:iconify|bioicons|healthicons|svgrepo)[-_]/i, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

function inferLicense(file) {
  const normalized = normalizeText(file)
  if (/\bcc0\b|cc 0|public domain/.test(normalized)) return "CC0"
  if (/\bmit\b/.test(normalized)) return "MIT"
  if (/\bbs[d]?\b/.test(normalized)) return "BSD"
  if (/apache/.test(normalized)) return "Apache-2.0"
  return null
}

function formatFor(file) {
  return path.extname(file).slice(1).toLowerCase()
}

function assetId(file) {
  const relative = path.relative(REPO_ROOT, file).replaceAll("\\", "/")
  return `local:${relative}`
}

function relativePath(file) {
  return path.relative(REPO_ROOT, file).replaceAll("\\", "/")
}

function rootLabel(root) {
  return path.relative(REPO_ROOT, root).replaceAll("\\", "/") || "."
}

async function collectFiles(root, files, maxFiles) {
  let entries
  try {
    entries = await fs.readdir(root, { withFileTypes: true })
  } catch (error) {
    if (error.code === "ENOENT" || error.code === "ENOTDIR") return
    throw error
  }
  for (const entry of entries) {
    if (files.length >= maxFiles) return
    if (entry.isSymbolicLink()) continue
    const fullPath = path.join(root, entry.name)
    if (entry.isDirectory()) {
      if (!IGNORED_DIRECTORIES.has(entry.name)) await collectFiles(fullPath, files, maxFiles)
    } else if (entry.isFile() && ASSET_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) {
      files.push(fullPath)
    }
  }
}

async function buildEntry(file, previous = null, sourceRoot = REPO_ROOT) {
  const stat = await fs.stat(file)
  const signature = `${stat.size}:${stat.mtimeMs}`
  if (previous?.signature === signature) return previous
  const format = formatFor(file)
  let metadata = rasterMetadata(Buffer.alloc(0), format)
  let embeddedLabel = null
  if (format === "svg") {
    const source = (await readFilePrefix(file, 2_000_000)).toString("utf8")
    const parsed = svgMetadata(source.slice(0, 2_000_000))
    metadata = parsed
    embeddedLabel = parsed.embeddedLabel
  } else {
    const header = await readFilePrefix(file, 256 * 1024)
    metadata = rasterMetadata(header, format)
  }
  const relative = relativePath(file)
  const name = cleanName(file, embeddedLabel)
  const tokens = tokensFor(name, relative)
  const compositionLike = stat.size > 150_000 && /generated|_rejected|iteracion|candidata|slide[-_ ]?\d+/i.test(relative)
  const iconLike = !compositionLike && (tokens.includes("icon") || tokens.includes("icons") || format === "svg")
  return {
    assetId: assetId(file),
    file,
    relativePath: relative,
    root: rootLabel(sourceRoot),
    name,
    label: name,
    tokens,
    kind: iconLike ? "icon" : "image",
    format,
    width: metadata.width,
    height: metadata.height,
    aspectRatio: metadata.aspectRatio,
    viewBox: metadata.viewBox || null,
    bytes: stat.size,
    mtimeMs: stat.mtimeMs,
    signature,
    license: inferLicense(relative),
  }
}

function normalizedRoots(roots = DEFAULT_CATALOG_ROOTS) {
  return [...new Set(roots.map((root) => assertAllowedInput(root)).map((root) => path.resolve(root)))]
}

async function writeJsonAtomic(file, value) {
  const temporary = `${file}.${process.pid}.${crypto.randomUUID()}.tmp`
  try {
    await fs.writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8")
    await fs.rename(temporary, file)
  } finally {
    await fs.rm(temporary, { force: true }).catch(() => {})
  }
}

async function indexLocalCatalogInternal({ roots = DEFAULT_CATALOG_ROOTS, cachePath = CACHE_PATH, maxFiles = 30_000, refresh = false } = {}) {
  const safeRoots = normalizedRoots(roots)
  let previous = { entries: {} }
  if (!refresh) {
    try { previous = JSON.parse(await fs.readFile(cachePath, "utf8")) } catch {}
  }
  const files = []
  for (const root of safeRoots) await collectFiles(root, files, Number(maxFiles) || 30_000)
  const entries = {}
  let reused = 0
  for (const file of files) {
    const key = path.resolve(file)
    const old = previous.entries?.[key]
    const sourceRoot = safeRoots.find((root) => {
      const relative = path.relative(root, key)
      return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative))
    }) || REPO_ROOT
    const entry = await buildEntry(key, old, sourceRoot)
    if (entry === old) reused += 1
    entries[key] = entry
  }
  const catalog = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    roots: safeRoots,
    entries,
  }
  await ensureDir(path.dirname(cachePath))
  await writeJsonAtomic(cachePath, catalog)
  const assets = Object.values(entries)
  return {
    cachePath,
    generatedAt: catalog.generatedAt,
    roots: safeRoots,
    files: assets.length,
    reused,
    addedOrChanged: assets.length - reused,
    byFormat: assets.reduce((result, item) => { result[item.format] = (result[item.format] || 0) + 1; return result }, {}),
    byKind: assets.reduce((result, item) => { result[item.kind] = (result[item.kind] || 0) + 1; return result }, {}),
  }
}

let catalogIndexQueue = Promise.resolve()

export function indexLocalCatalog(options = {}) {
  const run = catalogIndexQueue.then(() => indexLocalCatalogInternal(options), () => indexLocalCatalogInternal(options))
  catalogIndexQueue = run.catch(() => {})
  return run
}

async function readCatalog(cachePath = CACHE_PATH) {
  try { return JSON.parse(await fs.readFile(cachePath, "utf8")) } catch { return null }
}

let catalogPromise = null
let catalogExpiresAt = 0
let catalogOptionsKey = null

function catalogKey(options = {}) {
  const cachePath = path.resolve(options.cachePath || CACHE_PATH)
  const roots = (options.roots || DEFAULT_CATALOG_ROOTS).map((root) => path.resolve(root)).join("|")
  return `${cachePath}|${roots}`
}

export async function ensureLocalCatalog(options = {}) {
  const cachePath = options.cachePath || CACHE_PATH
  const key = catalogKey(options)
  if (options.refresh || !catalogPromise || catalogOptionsKey !== key || Date.now() > catalogExpiresAt) {
    catalogOptionsKey = key
    catalogPromise = (async () => {
      const existing = await readCatalog(cachePath)
      if (existing?.entries && !options.refresh && !options.roots) return existing
      await indexLocalCatalog(options)
      return readCatalog(cachePath)
    })().catch((error) => {
      catalogPromise = null
      catalogOptionsKey = null
      throw error
    })
    catalogExpiresAt = Date.now() + 60_000
  }
  return catalogPromise
}

function searchTextTokens(entry) {
  return tokensFor(
    entry.name,
    entry.label,
    entry.relativePath,
    entry.kind,
    entry.format,
    entry.style,
    entry.aspect,
    entry.dimension,
    ...(entry.themes || []),
    ...(entry.colorBuckets || []),
  )
}

function tokenVariants(token) {
  const normalized = normalizeText(token)
  return [...new Set([normalized, ...(SEARCH_ALIASES.get(normalized) || [])])].filter(Boolean)
}

function relationVariants(token) {
  const normalized = normalizeText(token)
  return [...new Set([...(SEARCH_RELATIONS.get(normalized) || []), ...(REVERSE_SEARCH_RELATIONS.get(normalized) || [])])]
}

function tokenMatch(token, nameTokenSet, pathTokenSet, allTokenSet) {
  const normalized = normalizeText(token)
  let best = { score: 0, variant: normalized, related: false }
  for (const variant of tokenVariants(token)) {
    const alias = variant !== normalized
    let score = 0
    if (nameTokenSet.has(variant)) score = alias ? 2.5 : 5
    else if (pathTokenSet.has(variant)) score = alias ? 1.5 : 3.5
    else if (allTokenSet.has(variant)) score = alias ? 0.9 : 1.5
    else if (!alias && variant.length >= 4 && [...nameTokenSet].some((value) => value.length >= 4 && (value.includes(variant) || variant.includes(value)))) score = 1.5
    if (score > best.score) best = { score, variant, related: false }
  }
  for (const variant of relationVariants(token)) {
    const score = nameTokenSet.has(variant) ? 1.1 : pathTokenSet.has(variant) ? 0.65 : allTokenSet.has(variant) ? 0.3 : 0
    if (score > best.score) best = { score, variant, related: true }
  }
  return best
}

export function scoreEntry(entry, queryTokens, exactQuery, preferredTerms = []) {
  if (!queryTokens.length) return 0
  const nameTokenSet = new Set(tokensFor(entry.name))
  const pathTokenSet = new Set(tokensFor(entry.relativePath).filter((token) => !PATH_NOISE.has(token)))
  const allTokenSet = new Set(searchTextTokens(entry))
  let score = 0
  let matchedTokens = 0
  let relatedTokens = 0
  for (const token of queryTokens) {
    const match = tokenMatch(token, nameTokenSet, pathTokenSet, allTokenSet)
    if (match.score > 0) {
      score += match.score
      if (match.related) relatedTokens += 1
      else matchedTokens += 1
    }
  }
  const searchable = normalizeText([entry.name, entry.label, entry.relativePath, entry.kind, entry.format, entry.style, entry.aspect, entry.dimension, ...(entry.themes || []), ...(entry.colorBuckets || [])].filter(Boolean).join(" "))
  if (exactQuery && searchable.includes(exactQuery)) score += 5
  for (const preferred of preferredTerms) {
    const normalizedPreferred = normalizeText(preferred)
    if (!normalizedPreferred) continue
    const preferredTokens = normalizedPreferred.split(/\s+/).filter(Boolean)
    if (searchable.includes(normalizedPreferred) || preferredTokens.length && preferredTokens.every((token) => nameTokenSet.has(token) || pathTokenSet.has(token))) score += 4
  }
  if (!matchedTokens && !relatedTokens && !(exactQuery && searchable.includes(exactQuery))) return 0
  if (queryTokens.length > 1) {
    score *= 0.35 + (0.65 * (matchedTokens + relatedTokens * 0.2) / queryTokens.length)
    if (matchedTokens === queryTokens.length) score += 1.5
  }
  if (entry.kind === "icon") score += 0.4
  return score
}

function matchReasonsFor(entry, queryTokens) {
  const nameTokens = new Set(tokensFor(entry.name))
  const pathTokens = new Set(tokensFor(entry.relativePath).filter((token) => !PATH_NOISE.has(token)))
  const allTokens = new Set(searchTextTokens(entry))
  return queryTokens.flatMap((token) => {
    const match = tokenMatch(token, nameTokens, pathTokens, allTokens)
    if (!match.score) return []
    if (match.related) return [normalizeText(token) + " ~ " + match.variant + " (relacionado)"]
    return [match.variant === normalizeText(token) ? normalizeText(token) : `${normalizeText(token)} -> ${match.variant}`]
  }).slice(0, 6)
}

function matchCoverageFor(entry, queryTokens) {
  const nameTokens = new Set(tokensFor(entry.name))
  const pathTokens = new Set(tokensFor(entry.relativePath).filter((token) => !PATH_NOISE.has(token)))
  const allTokens = new Set(searchTextTokens(entry))
  const matches = queryTokens.map((token) => tokenMatch(token, nameTokens, pathTokens, allTokens))
  const matchedTokenCount = matches.filter((match) => match.score > 0 && !match.related).length
  const relatedTokenCount = matches.filter((match) => match.score > 0 && match.related).length
  return {
    matchedTokenCount,
    relatedTokenCount,
    queryTokenCount: queryTokens.length,
    matchCoverage: queryTokens.length ? Number((matchedTokenCount / queryTokens.length).toFixed(4)) : 0,
  }
}

export async function searchLocalAssets({ query = "", terms = [], preferredTerms = [], excludePatterns = [], limit = 8, refresh = false, cachePath, roots, semantic = false, semanticIndexPath } = {}) {
  const catalog = await ensureLocalCatalog({ refresh, cachePath, roots })
  const exactQuery = normalizeText(query)
  const queryTokens = tokensFor(query, ...terms)
  const seenVariants = new Set()
  const lexicalResults = Object.values(catalog?.entries || {})
    .filter((entry) => !excludePatterns.some((pattern) => entry.relativePath.toLowerCase().includes(String(pattern).toLowerCase())))
    .map((entry) => ({ entry, score: scoreEntry(entry, queryTokens, exactQuery, preferredTerms) }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || left.entry.name.localeCompare(right.entry.name))
    .filter(({ entry }) => {
      const style = /(?:^|\/)(filled|outline)(?:\/|$)/i.exec(entry.relativePath)?.[1]?.toLowerCase() || "default"
      const key = `${normalizeText(entry.name)}:${entry.format}:${style}`
      if (seenVariants.has(key)) return false
      seenVariants.add(key)
      return true
    })
    .slice(0, Math.min(30, Math.max(1, Number(limit) || 8)))
  let results = lexicalResults.map(({ entry, score }) => ({
    ...entry,
    score: Number(score.toFixed(2)),
    matchReasons: matchReasonsFor(entry, queryTokens),
    ...matchCoverageFor(entry, queryTokens),
    local: true,
    searchMode: "lexical",
  }))
  let semanticSearch = { ready: false, reason: "Semantic search is disabled." }
  if (semantic && (query || terms.length)) {
    try {
      const { semanticScoresForQuery } = await import("./mobileclip.mjs")
      semanticSearch = await semanticScoresForQuery({ query, terms, indexPath: semanticIndexPath })
      if (semanticSearch.ready) {
        const lexicalById = new Map(lexicalResults.map(({ entry, score }) => [entry.assetId, { score, entry }]))
        const candidateEntries = Object.values(catalog?.entries || {}).filter((entry) => !excludePatterns.some((pattern) => entry.relativePath.toLowerCase().includes(String(pattern).toLowerCase())))
        const ranked = candidateEntries.map((entry) => {
          const lexical = lexicalById.get(entry.assetId)?.score || 0
          const similarity = semanticSearch.scores.get(entry.assetId)
          return { entry, lexical, similarity: Number.isFinite(similarity) ? similarity : null }
        }).filter(({ lexical, similarity }) => lexical > 0 || similarity !== null).sort((left, right) => {
          const leftScore = (left.similarity ?? -1) * 10 + left.lexical
          const rightScore = (right.similarity ?? -1) * 10 + right.lexical
          return rightScore - leftScore || left.entry.name.localeCompare(right.entry.name)
        })
        const semanticSeen = new Set()
        results = ranked.filter(({ entry }) => {
          const style = /(?:^|\/)(filled|outline)(?:\/|$)/i.exec(entry.relativePath)?.[1]?.toLowerCase() || "default"
          const key = `${normalizeText(entry.name)}:${entry.format}:${style}`
          if (semanticSeen.has(key)) return false
          semanticSeen.add(key)
          return true
        }).slice(0, Math.min(30, Math.max(1, Number(limit) || 8))).map(({ entry, lexical, similarity }) => ({
          ...entry,
          score: Number(((similarity ?? -1) * 10 + lexical).toFixed(2)),
          semanticScore: similarity === null ? null : Number(similarity.toFixed(5)),
          matchReasons: matchReasonsFor(entry, queryTokens),
          ...matchCoverageFor(entry, queryTokens),
          local: true,
          searchMode: "mobileclip+lexical",
        }))
      }
    } catch (error) {
      semanticSearch = { ready: false, reason: error.message }
    }
  }
  return { query, terms, results, total: results.length, semantic: semanticSearch, catalogGeneratedAt: catalog?.generatedAt || null }
}

export async function catalogStats(options = {}) {
  const catalog = await ensureLocalCatalog(options)
  const assets = Object.values(catalog?.entries || {})
  return {
    generatedAt: catalog?.generatedAt || null,
    roots: catalog?.roots || [],
    files: assets.length,
    byFormat: assets.reduce((result, item) => { result[item.format] = (result[item.format] || 0) + 1; return result }, {}),
    byKind: assets.reduce((result, item) => { result[item.kind] = (result[item.kind] || 0) + 1; return result }, {}),
  }
}

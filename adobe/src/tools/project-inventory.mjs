import fs from "node:fs/promises"
import path from "node:path"
import { TOOLKIT_ROOT } from "../utils.mjs"
import { AUTHORED_PROJECT_VARIATION_ROOTS } from "../asset-provenance.mjs"

const REPO_ROOT = path.resolve(TOOLKIT_ROOT, "..")
const PROJECTS_ROOT = path.join(TOOLKIT_ROOT, "projects")
const STRUCTURE_ROOT = path.join(TOOLKIT_ROOT, "experiments", "svg-structure")
const PROJECT_VARIATION_ROOTS = {
  chemsex: AUTHORED_PROJECT_VARIATION_ROOTS,
}
const VISUAL_EXTENSIONS = new Set([".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"])
const JSON_EXTENSIONS = new Set([".json"])
const MAX_SVG_METADATA_BYTES = 1_500_000
const MAX_PREVIEW_BYTES = 1_900_000
const IGNORED_DIRECTORIES = new Set([
  // `assets/` contains imported Iconify/Bioicons selections. Generated and
  // editable project work lives in `generated/` and `editable/` instead.
  ".git", "node_modules", "__pycache__", "cache", "jobs", "assets", "libraries", "rasterized-assets", "context-shelf-library",
])
const MANIFEST_NAME = /(?:layers?|manifest|storyboard|project)\.json$/i
const inventoryCache = new Map()

const GROUP_LABELS = {
  cover_people: "Personas / comunidad",
  cover_heart: "Corazón / cuidado",
  cover_molecule: "Molécula / conexión",
  definition_molecule: "Molécula / alteración",
  definition_pill: "Pastilla / sustancia",
  definition_people: "Personas / comunidad",
  context_applications_encounters: "Aplicaciones y encuentros",
  context_cruising_public_space: "Cruising / espacio público",
  context_private_party: "Fiesta privada / orgía",
  context_protection_risks: "Protección y riesgos",
  context_mental_health: "Salud mental",
  context_sexual_health_its: "Salud sexual / ITS",
  substance_amphetamine: "Éxtasis / pastilla",
  substance_mdma: "MDMA",
  substance_cannabis: "Marihuana / cannabis",
  substance_alkyl_nitrites: "Popper / nitritos",
  substance_cocaine: "Cocaína / polvo",
  substance_ketamine: "Ketamina",
  substance_methamphetamine: "Metanfetamina / cristal",
  substance_ghb_gbl: "GHB / GBL",
  risk_overdose_mix: "Sobredosis y mezclas",
  risk_viagra_drugs: "Viagra e interacción farmacológica",
  risk_hiv_its_partners: "VIH / ITS y parejas",
  risk_mental_health: "Salud mental / dependencia",
  "slide06-care-layer-stack": "Pila completa · cuidado",
  "slide07-interactions-layer-stack": "Pila completa · interacciones",
  "slide08-close-layer-stack": "Pila completa · cierre",
}

const GROUP_ALIASES = [
  ["applications_encounters", "context_applications_encounters"],
  ["cruising_public_space", "context_cruising_public_space"],
  ["private_party", "context_private_party"],
  ["protection_risks", "context_protection_risks"],
  ["mental_health", "context_mental_health"],
  ["sexual_health_its", "context_sexual_health_its"],
  ["overdose_mix_cardiovascular", "risk_overdose_mix"],
  ["medication_interaction", "risk_viagra_drugs"],
  ["hiv_sti_partners", "risk_hiv_its_partners"],
  ["mental_health_dependence", "risk_mental_health"],
  ["amphetamine", "substance_amphetamine"],
  ["mdma", "substance_mdma"],
  ["cannabis", "substance_cannabis"],
  ["alkyl_nitrites", "substance_alkyl_nitrites"],
  ["cocaine", "substance_cocaine"],
  ["ketamine", "substance_ketamine"],
  ["methamphetamine", "substance_methamphetamine"],
  ["ghb_gbl", "substance_ghb_gbl"],
]

const GENERIC_GROUP_TOKENS = new Set([
  "slide", "lamina", "layer", "layers", "stack", "asset", "icon", "substance", "risk", "context", "care", "close", "general",
])

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
}

function tokens(...values) {
  return [...new Set(values.flatMap((value) => normalize(value).split(/\s+/).filter((item) => item.length > 1)))]
}

function keyFor(file) {
  return path.normalize(path.resolve(file)).toLowerCase()
}

function relativePath(file) {
  return path.relative(REPO_ROOT, file).replaceAll("\\", "/")
}

function resolveReference(value, baseDirectory) {
  if (!value || typeof value !== "string") return null
  return path.resolve(path.isAbsolute(value) ? value : path.join(baseDirectory, value))
}

function numberFromAttribute(value) {
  const match = String(value || "").match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

function svgMetadata(source) {
  const svgTag = source.match(/<svg\b[^>]*>/i)?.[0] || ""
  const viewBox = svgTag.match(/\bviewBox\s*=\s*["']([^"']+)["']/i)?.[1]
  const values = viewBox ? viewBox.trim().split(/[\s,]+/).map(Number) : []
  const width = numberFromAttribute(svgTag.match(/\bwidth\s*=\s*["']([^"']+)["']/i)?.[1])
  const height = numberFromAttribute(svgTag.match(/\bheight\s*=\s*["']([^"']+)["']/i)?.[1])
  const resolvedWidth = width || (Number.isFinite(values[2]) ? values[2] : null)
  const resolvedHeight = height || (Number.isFinite(values[3]) ? values[3] : null)
  const embeddedLabel = source.match(/<(?:title|desc)\b[^>]*>([^<]{1,300})<\/(?:title|desc)>/i)?.[1]?.trim() || null
  return {
    width: resolvedWidth,
    height: resolvedHeight,
    aspectRatio: resolvedWidth && resolvedHeight ? Number((resolvedWidth / resolvedHeight).toFixed(4)) : null,
    viewBox: values.length === 4 ? values : null,
    embeddedLabel,
  }
}

function rasterMetadata(buffer, format) {
  if (format === "png" && buffer.length >= 24 && buffer.readUInt32BE(0) === 0x89504e47) {
    const width = buffer.readUInt32BE(16)
    const height = buffer.readUInt32BE(20)
    return { width, height, aspectRatio: width && height ? Number((width / height).toFixed(4)) : null }
  }
  if (format === "gif" && buffer.length >= 10 && buffer.toString("ascii", 0, 3) === "GIF") {
    const width = buffer.readUInt16LE(6)
    const height = buffer.readUInt16LE(8)
    return { width, height, aspectRatio: width && height ? Number((width / height).toFixed(4)) : null }
  }
  if (format === "webp" && buffer.length >= 30 && buffer.toString("ascii", 0, 4) === "RIFF" && buffer.toString("ascii", 8, 12) === "WEBP") {
    if (buffer.toString("ascii", 12, 16) === "VP8X") {
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

function cleanLabel(file, embeddedLabel = null) {
  if (embeddedLabel) return embeddedLabel.replace(/\s+/g, " ").trim().slice(0, 220)
  return path.basename(file, path.extname(file))
    .replace(/[_-]+/g, " ")
    .replace(/\b(?:true regenerated|regenerated|layers|layer stack|composite|integrated|sober|local|flat|open palette|reference|attempt|option)\b/gi, " ")
    .replace(/\s+/g, " ")
    .trim()
}

function statusFor(file) {
  const value = normalize(relativePath(file))
  if (value.includes("rejected") || value.includes("invalid")) return "rejected"
  if (value.includes("legacy") || value.includes("backup") || value.includes("old")) return "legacy"
  if (/(?:draft|pilot|attempt|option|variant|v1|v2|v3|v4|v5|v6|texture)/.test(value)) return "variant"
  return "asset"
}

function slideIndexesFrom(...values) {
  const result = new Set()
  for (const value of values) {
    const source = String(value || "")
    const transparentIcon = normalize(source).match(/iconos transparentes 23 (\d{2})\b/)
    if (transparentIcon) {
      const number = Number(transparentIcon[1])
      if (number >= 1 && number <= 3) result.add(8)
      else if (number >= 4 && number <= 11) result.add(5)
      else if (number >= 12 && number <= 23) result.add(7)
    }
    for (const match of source.matchAll(/(?:slide|lamina|pagina|page)[-_ ]?0*(\d{1,2})/gi)) result.add(Number(match[1]))
  }
  return [...result].filter((value) => value > 0 && value < 100)
}

function displayProjectName(id) {
  return String(id || "project")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

async function collectFiles(root, output) {
  let entries
  try { entries = await fs.readdir(root, { withFileTypes: true }) } catch (error) {
    if (["ENOENT", "ENOTDIR"].includes(error.code)) return
    throw error
  }
  for (const entry of entries) {
    if (entry.isSymbolicLink()) continue
    const fullPath = path.join(root, entry.name)
    if (entry.isDirectory()) {
      if (!IGNORED_DIRECTORIES.has(entry.name.toLowerCase())) await collectFiles(fullPath, output)
      continue
    }
    const extension = path.extname(entry.name).toLowerCase()
    if (VISUAL_EXTENSIONS.has(extension) || (JSON_EXTENSIONS.has(extension) && MANIFEST_NAME.test(entry.name))) output.push(fullPath)
  }
}

async function mapConcurrent(values, limit, mapper) {
  const results = new Array(values.length)
  let cursor = 0
  const worker = async () => {
    while (cursor < values.length) {
      const index = cursor
      cursor += 1
      results[index] = await mapper(values[index], index)
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, values.length) }, () => worker()))
  return results
}

async function buildRecord(file, sourceArea) {
  const stat = await fs.stat(file)
  const extension = path.extname(file).slice(1).toLowerCase()
  let metadata = { width: null, height: null, aspectRatio: null, viewBox: null, embeddedLabel: null }
  if (extension === "svg") {
    const source = await fs.readFile(file, "utf8")
    metadata = svgMetadata(source.slice(0, MAX_SVG_METADATA_BYTES))
  } else {
    metadata = rasterMetadata(await fs.readFile(file).then((value) => value.subarray(0, 256 * 1024)), extension)
  }
  const relative = relativePath(file)
  const label = cleanLabel(file, metadata.embeddedLabel)
  return {
    assetId: `local:${relative}`,
    provider: "local",
    id: relative,
    file,
    relativePath: relative,
    label,
    name: label,
    format: extension,
    kind: extension === "svg" || /icon|layer|asset/.test(normalize(relative)) ? "icon" : "image",
    width: metadata.width,
    height: metadata.height,
    aspectRatio: metadata.aspectRatio,
    viewBox: metadata.viewBox,
    bytes: stat.size,
    mtimeMs: stat.mtimeMs,
    sourceArea,
    status: statusFor(file),
    local: true,
    previewFile: stat.size <= MAX_PREVIEW_BYTES ? file : null,
    slideIndexes: slideIndexesFrom(relative, label),
  }
}

async function readJson(file) {
  try { return JSON.parse(await fs.readFile(file, "utf8")) } catch { return null }
}

function layerReferences(layer, baseDirectory) {
  return [layer?.source_png, layer?.registered_png, layer?.svg, layer?.mask]
    .map((value) => resolveReference(value, baseDirectory))
    .filter(Boolean)
}

async function readLayerInfo(file) {
  const value = await readJson(file)
  if (!value || !Array.isArray(value.layers)) return null
  const baseDirectory = path.dirname(file)
  return {
    file,
    layers: value.layers.map((layer, index) => ({
      id: String(layer.id || `${path.basename(file, ".json")}-${index + 1}`),
      label: String(layer.name || layer.id || `Capa ${index + 1}`),
      role: layer.role || layer.semantic_status || "visual layer",
      references: layerReferences(layer, baseDirectory),
    })),
    outputs: Object.values(value.outputs || {}).map((entry) => resolveReference(entry, baseDirectory)).filter(Boolean),
  }
}

function labelForGroup(id) {
  if (GROUP_LABELS[id]) return GROUP_LABELS[id]
  return String(id || "grupo")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function groupTokens(group) {
  const aliases = GROUP_ALIASES.filter(([, groupId]) => groupId === group.id).flatMap(([alias]) => alias.split("_"))
  return tokens(group.id, group.label, group.iconId, aliases).filter((value) => !GENERIC_GROUP_TOKENS.has(value))
}

function groupIdFromLayerFile(file, slideIndex) {
  const normalizedPath = normalize(file)
  const paddedPath = ` ${normalizedPath} `
  const alias = [...GROUP_ALIASES]
    .sort((left, right) => normalize(right[0]).length - normalize(left[0]).length)
    .find(([value]) => paddedPath.includes(` ${normalize(value)} `))
  if (alias) return alias[1]
  if (slideIndex === 6) return "slide06-care-layer-stack"
  if (slideIndex === 7) return "slide07-interactions-layer-stack"
  if (slideIndex === 8) return "slide08-close-layer-stack"
  if (slideIndex === 3 && normalizedPath.includes("slide03 layer package")) return "slide03-art-object-layer-package"
  if (slideIndex === 4 && normalizedPath.includes("slide04 layer package")) return "slide04-substance-layer-pilot"
  return null
}

function inferredSlideForGroup(groupId) {
  if (groupId?.startsWith("context_")) return 3
  if (groupId?.startsWith("substance_")) return 4
  if (groupId?.startsWith("risk_")) return 5
  const match = String(groupId || "").match(/slide0*(\d+)/i)
  return match ? Number(match[1]) : 0
}

function mergeLayerInfo(group, layerInfo) {
  const existingLayers = new Map((group.layers || []).map((layer) => [layer.id, layer]))
  for (const layer of layerInfo.layers || []) {
    const existing = existingLayers.get(layer.id)
    if (existing) {
      existing.references = [...new Set([...(existing.references || []), ...layer.references.map(keyFor)])]
    } else {
      group.layers.push({ ...layer, references: [...new Set(layer.references.map(keyFor))] })
    }
  }
  group.references = [...new Set([...(group.references || []), layerInfo.file, ...layerInfo.outputs].map(keyFor))]
}

async function canonicalGroups(projectRoot, manifestFiles, slideCount) {
  const manifestCandidates = [
    path.join(projectRoot, "editable", "blender", "chemsex-carousel-all-slides", "chemsex_carousel_blender_manifest.json"),
    path.join(STRUCTURE_ROOT, "chemsex_carousel_blender_manifest.json"),
    ...manifestFiles,
  ]
  let manifestFile = null
  let manifest = null
  for (const candidate of manifestCandidates) {
    if (!candidate || manifestFile) continue
    const value = await readJson(candidate)
    if (value?.slides && Array.isArray(value.slides)) { manifestFile = candidate; manifest = value }
  }
  const result = []
  if (manifest) {
    for (const slide of manifest.slides) {
      const slideIndex = Number(slide.index || 0)
      if (!slideIndex) continue
      for (const asset of slide.assets || []) {
        const id = String(asset.id || asset.icon_id || `slide-${slideIndex}-asset-${result.length + 1}`)
        const refs = [asset.source_svg, asset.source_png, asset.raster_png, asset.file, asset.path]
          .map((value) => resolveReference(value, path.dirname(manifestFile)))
          .filter(Boolean)
        let layers = []
        const layerManifestPath = resolveReference(asset.layer_manifest, path.dirname(manifestFile))
        if (layerManifestPath) {
          const layerInfo = await readLayerInfo(layerManifestPath)
          if (layerInfo) {
            layers = layerInfo.layers
            refs.push(layerManifestPath, ...layerInfo.outputs)
            for (const layer of layerInfo.layers) refs.push(...layer.references)
          }
        }
        if (!layers.length) layers = [{ id: `${id}-svg`, label: "SVG editable", role: "editable icon", references: refs }]
        result.push({
          id,
          label: labelForGroup(id),
          iconId: asset.icon_id || null,
          slideIndex,
          canonical: true,
          references: [...new Set(refs.map(keyFor))],
          tokens: groupTokens({ id, label: labelForGroup(id), iconId: asset.icon_id }),
          layers: layers.map(({ references, ...layer }) => ({ ...layer, references: [...new Set(references.map(keyFor))] })),
          manifestFile,
          sourceKind: asset.kind || "manifest asset",
        })
      }
    }
  }
  const existingGroups = new Map(result.map((group) => [`${group.slideIndex}:${group.id}`, group]))
  for (const candidate of manifestFiles) {
    const layerInfo = await readLayerInfo(candidate)
    if (!layerInfo) continue
    let slideIndex = slideIndexesFrom(candidate)[0] || 0
    const groupId = groupIdFromLayerFile(candidate, slideIndex)
    if (!groupId) continue
    slideIndex ||= inferredSlideForGroup(groupId)
    if (!slideIndex) continue
    const key = `${slideIndex}:${groupId}`
    let group = existingGroups.get(key)
    if (!group) {
      group = {
        id: groupId,
        label: labelForGroup(groupId),
        iconId: null,
        slideIndex,
        canonical: true,
        references: [],
        tokens: groupTokens({ id: groupId, label: labelForGroup(groupId) }),
        layers: [],
        manifestFile: candidate,
        sourceKind: "discovered layer manifest",
        variants: [],
      }
      result.push(group)
      existingGroups.set(key, group)
    }
    mergeLayerInfo(group, layerInfo)
  }
  const maxSlide = Math.max(slideCount, ...result.map((group) => group.slideIndex), 0)
  return { groups: result, manifestFile, slideCount: maxSlide }
}

function groupMatches(record, group) {
  const recordKey = keyFor(record.file)
  if (group.references.includes(recordKey)) return true
  const explicitSlides = record.slideIndexes || []
  if (explicitSlides.length && !explicitSlides.includes(group.slideIndex)) return false
  const normalizedPath = normalize(record.relativePath)
  const searchable = ` ${normalizedPath} ${normalize(record.label)} `
  const exactId = normalize(group.id)
  if (exactId.length > 4 && searchable.includes(` ${exactId} `)) return true
  const distinctive = group.tokens.filter((value) => value.length >= 4)
  const overlap = distinctive.filter((value) => searchable.includes(` ${value} `))
  if (overlap.length >= 2) return true
  if (overlap.length === 1 && (group.id.startsWith("substance_") || group.id.startsWith("risk_") || group.id.startsWith("context_"))) return true
  if (explicitSlides.includes(group.slideIndex) && group.id.includes("layer-stack")) return true
  return false
}

function layerForRecord(record, group) {
  const recordKey = keyFor(record.file)
  return group.layers.find((layer) => layer.references.includes(recordKey)) || null
}

function fallbackGroup(slideIndex) {
  return {
    id: `slide-${String(slideIndex).padStart(2, "0")}-unmapped`,
    label: "Variaciones no mapeadas",
    slideIndex,
    canonical: false,
    references: [],
    tokens: [],
    layers: [{ id: `slide-${slideIndex}-unmapped-layer`, label: "Capa/archivo detectado", role: "unmapped", references: [] }],
    variants: [],
  }
}

function projectSlides(storyboard, count) {
  const slides = (storyboard?.parts || []).map((part) => ({
    index: Number(part.index || 0) + 1,
    id: part.id || `slide-${Number(part.index || 0) + 1}`,
    title: part.title || `Lámina ${Number(part.index || 0) + 1}`,
    theme: part.theme || "general",
    text: part.text || "",
  }))
  const known = new Set(slides.map((slide) => slide.index))
  for (let index = 1; index <= count; index += 1) {
    if (!known.has(index)) slides.push({ index, id: `slide-${String(index).padStart(2, "0")}`, title: `Lámina ${index}`, theme: "detectada", text: "" })
  }
  return slides.sort((left, right) => left.index - right.index)
}

function publicVariant(record, group, layer, canonical) {
  const status = canonical ? "canonical" : record.status === "rejected" ? "rejected" : record.status === "legacy" ? "legacy" : "variant"
  return {
    assetId: record.assetId,
    provider: record.provider,
    id: record.id,
    file: record.file,
    previewFile: record.previewFile,
    relativePath: record.relativePath,
    label: record.label,
    name: record.name,
    format: record.format,
    kind: record.kind,
    width: record.width,
    height: record.height,
    aspectRatio: record.aspectRatio,
    bytes: record.bytes,
    status,
    inventoryStatus: status === "canonical" ? "canónico" : status === "rejected" ? "rechazado" : status === "legacy" ? "histórico" : "variación",
    sourceArea: record.sourceArea,
    groupId: group.id,
    groupLabel: group.label,
    layerId: layer?.id || null,
    layerName: layer?.label || null,
    local: true,
    canonical,
  }
}

async function buildProjectInventory(projectId, refresh = false) {
  const cacheKey = String(projectId)
  if (!refresh && inventoryCache.has(cacheKey)) return inventoryCache.get(cacheKey)
  const projectRoot = path.join(PROJECTS_ROOT, cacheKey)
  const projectConfig = await readJson(path.join(projectRoot, "PROJECT.json")) || {}
  const storyboard = await readJson(path.join(projectRoot, "storyboard.json")) || {}
  const allFiles = []
  await collectFiles(projectRoot, allFiles)
  const sourceRoots = [{ root: projectRoot, area: "project" }]
  if (cacheKey.toLowerCase() === "chemsex") sourceRoots.push({ root: STRUCTURE_ROOT, area: "experiments" })
  for (const source of PROJECT_VARIATION_ROOTS[cacheKey.toLowerCase()] || []) sourceRoots.push(source)
  if (cacheKey.toLowerCase() === "chemsex") await collectFiles(STRUCTURE_ROOT, allFiles)
  for (const source of PROJECT_VARIATION_ROOTS[cacheKey.toLowerCase()] || []) await collectFiles(source.root, allFiles)
  const manifestFiles = allFiles.filter((file) => /\.json$/i.test(file) && MANIFEST_NAME.test(path.basename(file)))
  const visualFiles = allFiles.filter((file) => VISUAL_EXTENSIONS.has(path.extname(file).toLowerCase()))
  const records = (await mapConcurrent(visualFiles, 16, async (file) => {
    const area = sourceRoots.find(({ root }) => {
      const relative = path.relative(root, file)
      return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative))
    })?.area || "project"
    try { return await buildRecord(file, area) } catch (_) { return null }
  })).filter(Boolean)
  const storySlides = projectSlides(storyboard, 0)
  const canonical = await canonicalGroups(projectRoot, manifestFiles, storySlides.length)
  const slides = projectSlides(storyboard, Math.max(canonical.slideCount || 0, ...records.flatMap((record) => record.slideIndexes || []), 0))
  const groupsBySlide = new Map(slides.map((slide) => [slide.index, []]))
  const groupById = new Map()
  for (const group of canonical.groups) {
    group.variants = []
    groupById.set(`${group.slideIndex}:${group.id}`, group)
    if (!groupsBySlide.has(group.slideIndex)) groupsBySlide.set(group.slideIndex, [])
    groupsBySlide.get(group.slideIndex).push(group)
  }
  const unassigned = []
  for (const record of records) {
    const matches = canonical.groups.filter((group) => groupMatches(record, group))
    if (matches.length) {
      for (const group of matches) {
        const layer = layerForRecord(record, group)
        const canonicalMatch = group.references.includes(keyFor(record.file))
        group.variants.push(publicVariant(record, group, layer, canonicalMatch))
      }
      continue
    }
    const slideMatches = record.slideIndexes || []
    if (slideMatches.length) {
      for (const slideIndex of slideMatches) {
        const fallbackId = `${slideIndex}:unmapped`
        let group = groupById.get(fallbackId)
        if (!group) {
          group = fallbackGroup(slideIndex)
          groupById.set(fallbackId, group)
          if (!groupsBySlide.has(slideIndex)) groupsBySlide.set(slideIndex, [])
          groupsBySlide.get(slideIndex).push(group)
        }
        group.variants.push(publicVariant(record, group, group.layers[0], false))
      }
    } else unassigned.push(record)
  }
  for (const group of canonical.groups) {
    group.variants.sort((left, right) => Number(right.canonical) - Number(left.canonical) || left.label.localeCompare(right.label))
  }
  const slideValues = slides.map((slide) => ({
    ...slide,
    groups: (groupsBySlide.get(slide.index) || [])
      .filter((group) => group.variants.length)
      .sort((left, right) => Number(right.canonical) - Number(left.canonical) || left.label.localeCompare(right.label))
      .map(({ references, tokens, manifestFile, sourceKind, ...group }) => group),
  }))
  const inventory = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    project: {
      id: cacheKey,
      name: projectConfig.name || displayProjectName(cacheKey),
      root: projectRoot,
      manifest: canonical.manifestFile,
      sourceRoots: sourceRoots.map(({ root, area }) => ({ root, area })),
    },
    projects: await listProjectSummaries(),
    slides: slideValues,
    unassigned: unassigned.map((record) => publicVariant(record, { id: "unassigned", label: "Sin lámina", slideIndex: null }, null, false)),
    stats: {
      visualFiles: records.length,
      assignedFiles: records.length - unassigned.length,
      unassignedFiles: unassigned.length,
      groups: slideValues.reduce((total, slide) => total + slide.groups.length, 0),
      variants: slideValues.reduce((total, slide) => total + slide.groups.reduce((subtotal, group) => subtotal + group.variants.length, 0), 0) + unassigned.length,
      rejected: records.filter((record) => record.status === "rejected").length,
      legacy: records.filter((record) => record.status === "legacy").length,
    },
  }
  inventoryCache.set(cacheKey, inventory)
  return inventory
}

async function listProjectSummaries() {
  let entries = []
  try { entries = await fs.readdir(PROJECTS_ROOT, { withFileTypes: true }) } catch { return [] }
  return entries.filter((entry) => entry.isDirectory() && !IGNORED_DIRECTORIES.has(entry.name.toLowerCase())).map((entry) => ({
    id: entry.name,
    name: displayProjectName(entry.name),
  }))
}

export async function listProjectInventory({ projectId = null, refresh = false } = {}) {
  const summaries = await listProjectSummaries()
  if (!summaries.length) return { schemaVersion: 1, generatedAt: new Date().toISOString(), projects: [], project: null, slides: [], unassigned: [], stats: {} }
  const requested = String(projectId || summaries[0].id)
  const selected = summaries.find((project) => project.id === requested) || summaries[0]
  const inventory = await buildProjectInventory(selected.id, refresh)
  inventory.projects = summaries
  return inventory
}

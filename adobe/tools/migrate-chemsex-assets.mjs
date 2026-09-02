import crypto from "node:crypto"
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const SOURCE_ROOT = path.resolve(process.env.LUCIDA_SOURCE_ROOT || "C:/IA/svg")
const PACKAGE_ROOT = path.resolve(fileURLToPath(new URL("..", import.meta.url)))
const DEST_ROOT = path.resolve(process.env.LUCIDA_ADOBE_ROOT || PACKAGE_ROOT)
const PROJECT_ROOT = path.join(SOURCE_ROOT, "agent-toolkit", "projects", "chemsex")
const OUTPUT_ROOT = path.join(DEST_ROOT, "ICONOS", "CHEMSEX")
const VISUAL_EXTENSIONS = new Set([".png", ".svg", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff"])

const included = []
const records = []
const byHash = new Map()
const usedNames = new Map()
const sourceAssetManifest = new Map()

function slash(value) { return value.replaceAll("\\", "/") }
function relativeSource(file) { return slash(path.relative(SOURCE_ROOT, file)) }
function hashBuffer(buffer) { return `sha256:${crypto.createHash("sha256").update(buffer).digest("hex")}` }
function isVisual(file) { return VISUAL_EXTENSIONS.has(path.extname(file).toLowerCase()) }
function isWithin(file, root) { const rel = path.relative(root, file); return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel)) }

async function walk(directory) {
  const output = []
  const entries = await fs.readdir(directory, { withFileTypes: true }).catch(() => [])
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const file = path.join(directory, entry.name)
    if (entry.isDirectory()) output.push(...await walk(file))
    else if (entry.isFile() && isVisual(file)) output.push(file)
  }
  return output
}

function originFor(file, kind) {
  const rel = relativeSource(file).toLowerCase()
  if (rel.includes("iconos-transparentes-23")) return { provenance: "codex-generated-transparent-export", mixedExternal: false, evidence: "plan.json + manifest.json" }
  if (rel.includes("true-regenerated-pilot")) return { provenance: "codex-ai-regenerated-layer-asset", mixedExternal: true, evidence: "chemsex_carousel_blender_manifest.json" }
  if (rel.includes("slide03-layer-package") || rel.includes("slide04-layer-package")) return { provenance: "codex-layer-package", mixedExternal: true, evidence: "layer-package manifest/files" }
  if (rel.includes("context-shelf-library/01-generated/02-slides")) return { provenance: "codex-rendered-project-output", mixedExternal: true, evidence: "library-manifest.json" }
  if (rel.includes("projects/chemsex/generated")) return { provenance: "codex-rendered-project-output", mixedExternal: true, evidence: "generated project path" }
  if (rel.includes("experiments/svg-structure") && rel.includes("regenerated-layers")) return { provenance: "codex-ai-regenerated-layer-asset", mixedExternal: true, evidence: "regenerated layer package path" }
  return { provenance: kind || "unverified", mixedExternal: false, evidence: "path only" }
}

function displayOrigin(file) {
  const rel = relativeSource(file)
  if (rel && !rel.startsWith("..")) return rel
  return "outside-source-tree"
}

function slideFromName(file) {
  const rel = relativeSource(file)
  const lower = rel.toLowerCase()
  const icon = path.basename(file).toLowerCase()
  if (lower.includes("iconos-transparentes-23")) {
    const match = icon.match(/^(\d+)-/)
    const number = match ? Number(match[1]) : null
    if (number >= 1 && number <= 3) return 8
    if (number >= 4 && number <= 11) return 5
    if (number >= 12 && number <= 23) return 7
  }
  for (let number = 1; number <= 8; number += 1) {
    const padded = String(number).padStart(2, "0")
    if (new RegExp(`slide[-_ ]?0?${number}(?:\\D|$)`, "i").test(rel) || new RegExp(`slide${padded}`, "i").test(rel)) return number
  }
  if (lower.includes("experiments/svg-structure") && /(?:alkyl-nitrites|amphetamine|cannabis|ghb-gbl|mdma|methamphetamine)-regenerated-layers/i.test(lower)) return 4
  return null
}

function explicitDisposition(file) {
  const rel = relativeSource(file).toLowerCase()
  const base = path.basename(file).toLowerCase()
  if (rel.includes("_rejected")) return { disposition: "discarded", reason: "source path marks the variant as rejected" }
  if (base.includes("layer_sheet") || base.includes("contact_sheet") || base.includes("svg_raster") || base.includes("svg-render") || base.includes("layers_pilot")) return { disposition: "discarded", reason: "technical preview/contact sheet, not a reusable icon or layer" }
  if (rel.includes("generated/slide-04-substances") && /composition-v[23]/i.test(base)) return { disposition: "discarded", reason: "superseded by slide-04 composition-v4" }
  if (rel.includes("generated/slide-04-substances") && /substances-v1/i.test(base)) return { disposition: "discarded", reason: "superseded by slide-04 substances-sober-v1" }
  if (rel.includes("generated/slide-06-care") && /flat-v[123]/i.test(base)) return { disposition: "discarded", reason: "superseded by slide-06 open-palette-v4" }
  if (rel.includes("generated/slide-07-interactions") && /flat-v[12]/i.test(base)) return { disposition: "discarded", reason: "superseded by slide-07 open-palette-v3" }
  if (rel.includes("generated/slide-08-close") && /flat-v[1-6]/i.test(base)) return { disposition: "discarded", reason: "superseded by slide-08 close-sober-v3" }
  return null
}

function candidateKind(file) {
  const rel = relativeSource(file).toLowerCase()
  const base = path.basename(file).toLowerCase()
  if (rel.includes("context-shelf-library/01-generated/02-slides")) return "curated-generated-slide-copy"
  if (rel.includes("projects/chemsex/generated")) return "generated-project-output"
  if (rel.includes("true-regenerated-pilot") || rel.includes("slide03-layer-package") || rel.includes("slide04-layer-package") || (rel.includes("experiments/svg-structure") && rel.includes("regenerated-layers"))) {
    if (rel.includes("\\masks\\") || rel.includes("/masks/") || base.includes("mask")) return null
    if (rel.includes("/aligned_layers/") || rel.includes("/raw_layers/") || rel.includes("/svg/") || base.includes("_composite") || base.endsWith("_layers.svg") || base.endsWith("_layered.svg")) return "generated-layer-asset"
    return null
  }
  return null
}

function targetStem(file, slide, kind) {
  const base = path.basename(file).replace(/[^a-zA-Z0-9._-]+/g, "-")
  const rel = relativeSource(file).toLowerCase()
  if (rel.includes("iconos-transparentes-23")) return base
  if (rel.includes("true-regenerated-pilot")) {
    const icon = relativeSource(file).split("/").find((part) => /^icon\d+_/i.test(part))
    return `${icon || "regenerated"}__${base}`
  }
  if (rel.includes("slide03-layer-package") || rel.includes("slide04-layer-package")) {
    const icon = relativeSource(file).split("/").find((part) => /^(icon\d+_|[a-z-]+$)/i.test(part) && !/^slide0?\d/i.test(part))
    return `layerpackage-${icon || `slide-${slide}`}__${base}`
  }
  if (kind === "curated-generated-slide-copy") return `curated__${base}`
  return `generated__${base}`
}

function pngDimensions(buffer) {
  if (buffer.length < 24 || !buffer.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) return { valid: false, width: null, height: null }
  return { valid: true, width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) }
}

function svgDimensions(buffer) {
  const text = buffer.toString("utf8", 0, Math.min(buffer.length, 50000))
  const root = text.match(/<svg\b[^>]*>/i)?.[0] || ""
  const viewBox = root.match(/viewBox\s*=\s*["']\s*[-+\d.eE]+\s+[-+\d.eE]+\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s*["']/i)
  const width = root.match(/\bwidth\s*=\s*["']\s*([\d.]+)/i)?.[1]
  const height = root.match(/\bheight\s*=\s*["']\s*([\d.]+)/i)?.[1]
  return { valid: Boolean(root), width: Number(width || viewBox?.[1]) || null, height: Number(height || viewBox?.[2]) || null }
}

async function describe(file, buffer) {
  const format = path.extname(file).slice(1).toLowerCase()
  const dimensions = format === "png" ? pngDimensions(buffer) : format === "svg" ? svgDimensions(buffer) : { valid: false, width: null, height: null }
  return { format, bytes: buffer.length, width: dimensions.width, height: dimensions.height, formatValid: dimensions.valid }
}

function addExcludedGroup(source, reason, count, extra = {}) {
  records.push({ disposition: "excluded-group", source, count, reason, ...extra })
}

async function loadSourceManifest() {
  const file = path.join(PROJECT_ROOT, "generated", "iconos-transparentes-23", "manifest.json")
  const raw = JSON.parse(await fs.readFile(file, "utf8").catch(() => "{}"))
  for (const asset of raw.assets || []) sourceAssetManifest.set(path.basename(asset.file).toLowerCase(), asset)
}

async function consider(file, slide, kind, forcedReason = null) {
  const buffer = await fs.readFile(file)
  const source = displayOrigin(file)
  const sourceMeta = originFor(file, kind)
  const description = await describe(file, buffer)
  const baseRecord = { source, slide, kind, hash: hashBuffer(buffer), ...description, provenance: sourceMeta.provenance, mixedExternal: sourceMeta.mixedExternal, evidence: sourceMeta.evidence, target: null, mergedFrom: [], reason: null }
  if (!slide) {
    baseRecord.disposition = "pending"
    baseRecord.reason = forcedReason || "no reliable slide assignment from name/path/manifest"
    records.push(baseRecord)
    return
  }
  const disposition = explicitDisposition(file)
  if (forcedReason || disposition) {
    baseRecord.disposition = "discarded"
    baseRecord.reason = forcedReason || disposition.reason
    records.push(baseRecord)
    return
  }
  if (!description.formatValid) {
    baseRecord.disposition = "discarded"
    baseRecord.reason = "invalid or unsupported visual file format"
    records.push(baseRecord)
    return
  }
  const existing = byHash.get(baseRecord.hash)
  if (existing) {
    baseRecord.disposition = "duplicate"
    baseRecord.target = existing.target
    baseRecord.reason = `same content hash as ${existing.source}`
    existing.mergedFrom.push(source)
    records.push(baseRecord)
    return
  }
  const folder = path.join(OUTPUT_ROOT, String(slide))
  await fs.mkdir(folder, { recursive: true })
  const stem = targetStem(file, slide, kind)
  let targetName = stem
  const names = usedNames.get(slide) || new Set()
  let suffix = 1
  while (names.has(targetName)) targetName = `${path.parse(stem).name}--${suffix++}${path.parse(stem).ext}`
  names.add(targetName)
  usedNames.set(slide, names)
  const targetFile = path.join(folder, targetName)
  await fs.copyFile(file, targetFile)
  baseRecord.disposition = "included"
  baseRecord.target = slash(path.relative(DEST_ROOT, targetFile))
  byHash.set(baseRecord.hash, baseRecord)
  included.push(baseRecord)
  records.push(baseRecord)
}

async function addGeneratedProjectOutputs() {
  const root = path.join(PROJECT_ROOT, "generated")
  for (const file of await walk(root)) {
    const slide = slideFromName(file)
    await consider(file, slide, "generated-project-output")
  }
}

async function addCuratedSlideCopies() {
  const root = path.join(PROJECT_ROOT, "context-shelf-library", "01-generated", "02-slides")
  for (const file of await walk(root)) {
    const slide = slideFromName(file)
    await consider(file, slide, "curated-generated-slide-copy")
  }
}

async function addLayerAssets(root) {
  for (const file of await walk(root)) {
    const kind = candidateKind(file)
    const slide = slideFromName(file)
    if (kind) await consider(file, slide, kind)
    else if (isVisual(file)) {
      const disposition = explicitDisposition(file)
      if (disposition || relativeSource(file).toLowerCase().includes("/masks/")) {
        const buffer = await fs.readFile(file)
        const description = await describe(file, buffer)
        records.push({ source: displayOrigin(file), slide, kind: "technical-layer-file", hash: hashBuffer(buffer), ...description, disposition: "discarded", target: null, mergedFrom: [], reason: disposition?.reason || "mask is a technical extraction aid, not a reusable icon" })
      }
    }
  }
}

async function recordUncertainSources() {
  const externalRoots = [
    [path.join(PROJECT_ROOT, "context-shelf-library", "01-generated", "01-selected-icons"), "selected third-party icons; public source/license exists but they are not Codex-generated"],
    [path.join(PROJECT_ROOT, "context-shelf-library", "01-generated", "03-editable-previews"), "all-slides preview has no reliable single-slide assignment"],
    [path.join(PROJECT_ROOT, "context-shelf-library", "01-generated", "04-history"), "historical resources originate from rd_database_complete and are not verified as Codex-generated"],
    [path.join(PROJECT_ROOT, "assets"), "project assets are external/public library resources, not Codex-generated"],
    [path.join(SOURCE_ROOT, "rd_database_complete", "assets", "generated_icons"), "origin is not identified as Codex-generated; excluded to avoid copying private/third-party corpus"],
    [path.join(SOURCE_ROOT, "_tmp_chemsex_render"), "temporary render output has no reliable source/provenance or slide assignment"],
  ]
  for (const [root, reason] of externalRoots) {
    const files = await walk(root)
    if (files.length) addExcludedGroup(relativeSource(root), reason, files.length)
  }
}

async function main() {
  if (!isWithin(OUTPUT_ROOT, DEST_ROOT)) throw new Error("CHEMSEX output escaped destination")
  await loadSourceManifest()
  for (let slide = 1; slide <= 8; slide += 1) await fs.mkdir(path.join(OUTPUT_ROOT, String(slide)), { recursive: true })

  await addGeneratedProjectOutputs()
  await addCuratedSlideCopies()
  await addLayerAssets(path.join(SOURCE_ROOT, "agent-toolkit", "experiments", "svg-structure", "true-regenerated-pilot", "slides"))
  await addLayerAssets(path.join(SOURCE_ROOT, "agent-toolkit", "experiments", "svg-structure", "slide03-layer-package"))
  await addLayerAssets(path.join(SOURCE_ROOT, "agent-toolkit", "experiments", "svg-structure", "slide04-layer-package"))
  for (const name of ["alkyl-nitrites-regenerated-layers", "amphetamine-regenerated-layers", "cannabis-regenerated-layers", "ghb-gbl-regenerated-layers", "mdma-regenerated-layers", "methamphetamine-regenerated-layers"]) {
    await addLayerAssets(path.join(SOURCE_ROOT, "agent-toolkit", "experiments", "svg-structure", name))
  }
  await recordUncertainSources()

  const canonical = Object.fromEntries(Array.from({ length: 8 }, (_, index) => {
    const slide = index + 1
    return [String(slide), included.filter((item) => item.slide === slide).map((item) => item.target)]
  }))
  const pending = records.filter((item) => item.disposition === "pending" || item.disposition === "excluded-group")
  const manifest = {
    schemaVersion: 1,
    product: "LUCIDA",
    project: "CHEMSEX",
    policy: {
      sourceRoot: "C:/IA/svg",
      outputRoot: "ICONOS/CHEMSEX",
      generatedOnly: true,
      noOriginalsDeleted: true,
      exactSlideFolders: ["1", "2", "3", "4", "5", "6", "7", "8"],
      deduplication: "sha256-content-hash",
      semanticVariantMerging: "explicit-filename-evidence-only",
    },
    stats: {
      included: included.length,
      duplicates: records.filter((item) => item.disposition === "duplicate").length,
      discarded: records.filter((item) => item.disposition === "discarded").length,
      pendingGroups: pending.length,
      bySlide: Object.fromEntries(Object.entries(canonical).map(([slide, files]) => [slide, files.length])),
    },
    files: records,
    canonical,
    pendingReview: pending,
    sourceManifestEvidence: sourceAssetManifest.size ? "generated/iconos-transparentes-23/manifest.json" : null,
  }
  await fs.writeFile(path.join(OUTPUT_ROOT, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8")
  await fs.writeFile(path.join(OUTPUT_ROOT, "review-pending.json"), `${JSON.stringify({ schemaVersion: 1, project: "CHEMSEX", pending }, null, 2)}\n`, "utf8")
  console.log(JSON.stringify({ ok: true, output: slash(path.relative(DEST_ROOT, OUTPUT_ROOT)), ...manifest.stats }, null, 2))
}

await main()

import fs from "node:fs/promises"
import path from "node:path"
import { deterministicId, sha256 } from "../../core/contracts/stable.mjs"
import { assertAllowedPath, createSecurityPolicy } from "../../core/security/policy.mjs"

export const SUPPORTED_EXTENSIONS = new Set([".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff"])

function formatFor(file) { return path.extname(file).slice(1).toLowerCase() }
function sourceKind(file) { return /generated|created|authored/i.test(file) ? "generated" : "local" }

export function normalizeCatalogEntry(input = {}) {
  const file = String(input.path || input.file || "").trim()
  if (!file) throw new Error("Catalog entry path is required")
  const bytes = Number.isFinite(Number(input.bytes)) ? Number(input.bytes) : null
  const format = String(input.format || formatFor(file)).toLowerCase()
  const identity = { path: file.replaceAll("\\", "/"), bytes, fingerprint: input.fingerprint || null }
  return {
    assetId: String(input.assetId || deterministicId("asset", identity)),
    path: identity.path,
    label: String(input.label || path.basename(file, path.extname(file))),
    format,
    bytes,
    width: Number.isFinite(Number(input.width)) ? Number(input.width) : null,
    height: Number.isFinite(Number(input.height)) ? Number(input.height) : null,
    hasAlpha: input.hasAlpha === true ? true : input.hasAlpha === false ? false : null,
    tags: [...new Set((Array.isArray(input.tags) ? input.tags : []).map(String))].sort(),
    dominantColors: [...new Set((Array.isArray(input.dominantColors) ? input.dominantColors : []).map(String))].sort(),
    sourceKind: String(input.sourceKind || sourceKind(file)),
    fingerprint: input.fingerprint || null,
    provenance: input.provenance || null,
  }
}

async function walk(directory, output, maxFiles) {
  if (output.length >= maxFiles) return
  const entries = await fs.readdir(directory, { withFileTypes: true }).catch(() => [])
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (output.length >= maxFiles) break
    const file = path.join(directory, entry.name)
    if (entry.isDirectory()) await walk(file, output, maxFiles)
    else if (entry.isFile() && SUPPORTED_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) output.push(file)
  }
}

export async function scanLocalCatalog({ roots = [], policy = null, maxFiles = 10_000 } = {}) {
  const safePolicy = policy || createSecurityPolicy({ inputRoots: roots })
  const files = []
  for (const root of roots) {
    const safeRoot = assertAllowedPath(root, safePolicy.inputRoots, safePolicy)
    await walk(safeRoot, files, Math.max(1, Number(maxFiles) || 10_000))
  }
  const entries = []
  for (const file of [...new Set(files)].sort()) {
    assertAllowedPath(file, safePolicy.inputRoots, safePolicy)
    const stat = await fs.stat(file)
    const relative = path.relative(path.resolve(roots[0] || path.dirname(file)), file).replaceAll("\\", "/")
    entries.push(normalizeCatalogEntry({ path: file, label: relative, bytes: stat.size, fingerprint: sha256({ file: relative, bytes: stat.size, modified: stat.mtimeMs }), sourceKind: sourceKind(relative) }))
  }
  return { schemaVersion: 1, count: entries.length, roots: roots.map((root) => path.resolve(root)), entries }
}

export function groupCatalog(entries = []) {
  const groups = { sourceKind: {}, format: {}, tag: {}, color: {} }
  const add = (kind, key, assetId) => { if (!groups[kind][key]) groups[kind][key] = []; groups[kind][key].push(assetId) }
  for (const raw of entries) {
    const entry = normalizeCatalogEntry(raw)
    add("sourceKind", entry.sourceKind, entry.assetId)
    add("format", entry.format, entry.assetId)
    for (const tag of entry.tags) add("tag", tag, entry.assetId)
    for (const color of entry.dominantColors) add("color", color, entry.assetId)
  }
  return Object.fromEntries(Object.entries(groups).map(([kind, values]) => [kind, Object.fromEntries(Object.entries(values).map(([key, assetIds]) => [key, [...new Set(assetIds)].sort()]))]))
}

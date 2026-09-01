import fs from "node:fs/promises"
import path from "node:path"
import { TOOLKIT_ROOT, readJson } from "../utils.mjs"

const INVENTORY_PATH = path.join(TOOLKIT_ROOT, "integrations", "tool-sources.json")
const SCRIPTING_MAP_PATH = path.join(TOOLKIT_ROOT, "integrations", "scripting-map.json")
const PARENT_ROOT = path.resolve(TOOLKIT_ROOT, "..")

async function statKind(file) {
  try {
    const value = await fs.stat(file)
    return value.isDirectory() ? "directory" : value.isFile() ? "file" : "other"
  } catch {
    return null
  }
}

function sourceRoot(source) {
  const base = source.location === "parent" ? PARENT_ROOT : TOOLKIT_ROOT
  return path.resolve(base, source.path)
}

function relativeDisplay(file) {
  const relative = path.relative(TOOLKIT_ROOT, file)
  return relative.startsWith("..") ? path.relative(PARENT_ROOT, file) : relative
}

async function readDirectMetadata(root, source) {
  const metadata = {}
  for (const name of source.metadataFiles || []) {
    if (!name.endsWith(".json")) continue
    const file = path.join(root, name)
    if (await statKind(file) !== "file") continue
    try {
      const value = await readJson(file)
      metadata[name] = {
        name: value.name || null,
        version: value.version || null,
        packageManager: value.packageManager || null,
      }
    } catch {
      metadata[name] = { readable: false }
    }
  }
  return metadata
}

export async function integrationSources() {
  const inventory = await readJson(INVENTORY_PATH)
  const sources = []
  for (const source of inventory.sources || []) {
    const root = sourceRoot(source)
    const kind = await statKind(root)
    sources.push({
      ...source,
      root: relativeDisplay(root),
      exists: Boolean(kind),
      rootKind: kind,
      metadata: kind === "directory" ? await readDirectMetadata(root, source) : {},
      entrypointStatus: await Promise.all((source.entrypoints || []).map(async (entrypoint) => ({
        path: entrypoint,
        exists: Boolean(await statKind(path.join(root, entrypoint))),
      }))),
      runtimeAdapterStatus: await Promise.all((source.runtimeAdapters || []).map(async (adapter) => ({
        path: adapter,
        exists: Boolean(await statKind(path.resolve(TOOLKIT_ROOT, adapter))),
      }))),
    })
  }
  return {
    version: inventory.version,
    name: inventory.name,
    description: inventory.description,
    toolkitRoot: TOOLKIT_ROOT,
    parentRoot: PARENT_ROOT,
    sources,
  }
}

export async function integrationScriptingMap() {
  return readJson(SCRIPTING_MAP_PATH)
}

async function checkPath(relativePath) {
  const file = path.resolve(TOOLKIT_ROOT, relativePath)
  return { path: relativePath, exists: Boolean(await statKind(file)), kind: await statKind(file) }
}

export async function validateIntegration() {
  const inventory = await readJson(INVENTORY_PATH)
  const scripting = await readJson(SCRIPTING_MAP_PATH)
  const issues = []
  const checked = []

  for (const source of inventory.sources || []) {
    const root = sourceRoot(source)
    const required = source.required !== false
    const rootKind = await statKind(root)
    checked.push({ source: source.id, path: relativeDisplay(root), exists: Boolean(rootKind), kind: rootKind })
    if (required && rootKind !== "directory") issues.push({ type: "missing-source-root", source: source.id, path: root })
    for (const entrypoint of source.entrypoints || []) {
      const target = path.join(root, entrypoint)
      const kind = await statKind(target)
      checked.push({ source: source.id, path: relativeDisplay(target), exists: Boolean(kind), kind })
      if (required && !kind) issues.push({ type: "missing-entrypoint", source: source.id, path: target })
    }
    for (const adapter of source.runtimeAdapters || []) {
      const target = path.resolve(TOOLKIT_ROOT, adapter)
      const kind = await statKind(target)
      checked.push({ source: source.id, runtimeAdapter: true, path: relativeDisplay(target), exists: Boolean(kind), kind })
      if (required && !kind) issues.push({ type: "missing-runtime-adapter", source: source.id, path: target })
    }
  }

  for (const surface of scripting.surfaces || []) {
    const scripts = surface.scripts || (surface.script ? [surface.script] : [])
    for (const script of scripts) {
      const result = await checkPath(script)
      checked.push({ surface: surface.id, ...result })
      if (!result.exists) issues.push({ type: "missing-script", surface: surface.id, path: script })
    }
  }

  const requiredContracts = ["asset", "storyboard", "separation-manifest"]
  for (const contract of requiredContracts) {
    if (!scripting.contracts?.[contract]) issues.push({ type: "missing-contract", contract })
  }

  return {
    ok: issues.length === 0,
    version: inventory.version,
    sources: inventory.sources?.length || 0,
    surfaces: scripting.surfaces?.length || 0,
    issues,
    checked,
    files: { inventory: INVENTORY_PATH, scriptingMap: SCRIPTING_MAP_PATH },
  }
}

export async function integrationPlan(options = {}) {
  const validation = await validateIntegration()
  if (!validation.ok) throw new Error(`Integration inventory is invalid: ${validation.issues.map((issue) => issue.path || issue.contract).join(", ")}`)
  const useAdobe = options.useAdobe !== false
  const useGeometryNodes = options.useGeometryNodes !== false
  const useCycles = options.useCycles !== false
  const stages = [
    { id: "source", operation: "document.extract|asset.search", owner: "toolkit", input: options.source || "document or concept", output: "source text and asset candidates" },
    { id: "storyboard", operation: "document.segment|document.storyboard", owner: "toolkit", input: options.storyboard || "source", output: "exact-text slide manifest" },
    { id: "assets", operation: useAdobe ? "photoshop.separate-objects|asset.fetch" : "asset.fetch", owner: useAdobe ? "Adobe + toolkit" : "toolkit", input: "illustrations, SVG and regions", output: "editable asset manifest" },
    { id: "support-runtimes", operation: "svg.thi-ng-geom|data.d3-chart|math.stdlib-stats|workflow.rxjs-events|workflow.effect-retry", owner: "toolkit source adapters", input: "geometry, data and event manifests", output: "derived SVG, metrics and controlled execution events" },
    { id: "composition", operation: useGeometryNodes ? "blender.layout-scene (Geometry Nodes)" : "blender.layout-scene", owner: "Blender", input: "storyboard + asset manifest", output: "editable slide scene" },
    { id: "render", operation: useCycles ? "blender.render-cycles" : "blender.render", owner: "Blender", input: "editable slide scene", output: "PNG/EXR review or delivery renders" },
  ]
  return {
    version: 1,
    name: options.name || "multi-app-composition",
    status: "planned",
    constraints: { useAdobe, useGeometryNodes, useCycles },
    stages,
    contracts: ["asset", "storyboard", "separation-manifest"],
    validation,
  }
}

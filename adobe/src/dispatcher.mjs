import fs from "node:fs/promises"
import path from "node:path"
import { createJob, updateJob, writeSummary } from "./jobs.mjs"
import { enqueueAdobe, adobeStatus } from "./adapters/adobe.mjs"
import { renderAfterEffects } from "./adapters/after-effects.mjs"
import { runBlender } from "./adapters/blender.mjs"
import { animateChart, barChart } from "./tools/chart.mjs"
import { d3BarChart } from "./tools/d3.mjs"
import { removeIconBackground, splitRaster } from "./tools/image.mjs"
import { animateSvg, createSvg, embedImage, particles, previewSvg, rasterizeSvg, validateSvg } from "./tools/svg.mjs"
import { vectorizeRaster } from "./tools/vectorize.mjs"
import { imageToSvgBlenderIllustrator, imageToSvgPreview } from "./orchestrator.mjs"
import { documentToAnimatedPost } from "./document-workflow.mjs"
import { multiAppComposition } from "./multi-app-workflow.mjs"
import { fetchAsset, searchAssets, selectAssets } from "./tools/asset-search.mjs"
import { catalogStats, indexLocalCatalog, searchLocalAssets } from "./tools/local-catalog.mjs"
import { catalogGroupSummary, indexLocalGroups, listCatalogAssets } from "./tools/catalog-groups.mjs"
import { indexMobileClip, mobileClipStatus, searchMobileClip } from "./tools/mobileclip.mjs"
import { analyzeContext } from "./tools/context-analysis.mjs"
import { gdkbHealth, gdkbImport, gdkbImportJsonl, gdkbMergeEvent, gdkbNormalize, gdkbReplay, gdkbResolve } from "./tools/gdkb.mjs"
import { integrationPlan, integrationScriptingMap, integrationSources, validateIntegration } from "./tools/integration.mjs"
import { effectRetrySimulation, rxjsEventTimeline, stdlibStatistics, thiNgSvg, threeScenePreview } from "./tools/source-runtime.mjs"
import { ensureDir, readJson, resolveInput, resolveOutput, TOOLKIT_ROOT, writeJson } from "./utils.mjs"

export const WEB_RUN_TOOLS = new Set([
  "job.create",
  "svg.create",
  "svg.embed-image",
  "svg.rasterize",
  "svg.vectorize",
  "svg.animate",
  "svg.particles",
  "svg.validate",
  "svg.preview",
  "svg.thi-ng-geom",
  "data.chart",
  "data.d3-chart",
  "data.animate",
  "image.split",
  "image.extract-checkerboard-matte",
  "blender.run",
  "scene3d.create",
  "blender.create-scene",
  "blender.render",
  "blender.import-svg",
  "blender.import-glb",
  "blender.export-glb",
  "blender.layout-scene",
  "photoshop.separate-objects",
  "adobe.enqueue",
  "adobe.status",
  "workflow.image-to-svg-preview",
  "workflow.image-to-svg-blender-illustrator",
  "workflow.document-to-animated-post",
  "workflow.multi-app-composition",
  "asset.search",
  "asset.fetch",
  "asset.select",
  "asset.catalog-index",
  "asset.search-local",
  "asset.catalog-groups",
  "asset.catalog-assets",
  "asset.semantic-status",
  "asset.semantic-index",
  "asset.semantic-search",
  "context.analyze",
  "gdkb.health",
  "gdkb.normalize",
  "gdkb.resolve",
  "gdkb.import",
  "gdkb.replay",
  "gdkb.merge-event",
  "math.stdlib-stats",
  "workflow.rxjs-events",
  "workflow.effect-retry",
  "integration.sources",
  "integration.scripting-map",
  "integration.validate",
  "integration.plan",
])

function overwriteOptions(params) {
  if (params.overwrite === true && params.confirmOverwrite !== true) {
    throw new Error("overwrite requires confirmOverwrite=true")
  }
  return { overwrite: params.overwrite === true }
}

function outputPath(job, requested, fallback, params) {
  const value = requested
    ? path.isAbsolute(requested) ? requested : path.join(job.directory, "output", requested)
    : path.join(job.directory, "output", fallback)
  const target = resolveOutput(value, overwriteOptions(params))
  const relative = path.relative(job.directory, target)
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`Web tool output must stay inside ${job.directory}`)
  }
  return target
}

async function stageInput(job, value, label) {
  const source = resolveInput(value)
  const target = path.join(job.directory, "input", `${label}-${path.basename(source)}`)
  await ensureDir(path.dirname(target))
  await fs.copyFile(source, target)
  return target
}

async function stageBlenderLayoutSpec(job, value) {
  const sourceSpec = resolveInput(value)
  const stagedSpec = await stageInput(job, sourceSpec, "blender-storyboard")
  const document = await readJson(stagedSpec)
  const stagedAssets = path.join(job.directory, "input", "assets")
  await ensureDir(stagedAssets)
  const copied = new Map()
  let counter = 0

  async function stageAssetFile(rawPath, baseDirectory) {
    if (!rawPath || typeof rawPath !== "string") return rawPath
    const source = resolveInput(path.isAbsolute(rawPath) ? rawPath : path.resolve(baseDirectory, rawPath))
    if (copied.has(source)) return copied.get(source)
    const target = path.join(stagedAssets, `${String(counter++).padStart(4, "0")}-${path.basename(source)}`)
    await fs.copyFile(source, target)
    copied.set(source, target)
    return target
  }

  async function stageAssetList(items, baseDirectory) {
    if (!Array.isArray(items)) return
    for (const asset of items) {
      if (!asset || typeof asset !== "object") continue
      const key = asset.file ? "file" : asset.path ? "path" : null
      if (key) asset[key] = await stageAssetFile(asset[key], baseDirectory)
    }
  }

  async function stageManifestReference(reference, baseDirectory) {
    if (!reference || typeof reference !== "string") return reference
    const sourceManifest = resolveInput(path.isAbsolute(reference) ? reference : path.resolve(baseDirectory, reference))
    const manifest = await readJson(sourceManifest)
    await stageAssetList(manifest.assets, path.dirname(sourceManifest))
    const target = path.join(job.directory, "input", `asset-manifest-${String(counter++).padStart(4, "0")}.json`)
    await writeJson(target, manifest)
    return target
  }

  const specDirectory = path.dirname(sourceSpec)
  if (typeof document.assetManifest === "string") document.assetManifest = await stageManifestReference(document.assetManifest, specDirectory)
  if (Array.isArray(document.assetManifests)) {
    document.assetManifests = await Promise.all(document.assetManifests.map((item) => stageManifestReference(item, specDirectory)))
  }
  await stageAssetList(document.assets, specDirectory)
  await stageAssetList(document.design?.assets, specDirectory)
  for (const part of document.parts || []) await stageAssetList(part.assets, specDirectory)
  await writeJson(stagedSpec, document)
  return stagedSpec
}

function specFromParams(params) {
  if (params.spec && typeof params.spec === "object") return params.spec
  const specPath = params.specPath || (typeof params.spec === "string" ? params.spec : null)
  if (!specPath) throw new Error("spec or specPath is required")
  return resolveInput(specPath)
}

async function runInJob(tool, params, task) {
  const job = await createJob(`web-${tool}`, { tool, params })
  try {
    await updateJob(job.id, { state: "running", currentTool: tool })
    const value = await task(job)
    const result = value?.result ?? value
    const files = value?.files || []
    const state = value?.pending ? "waiting-for-adobe" : "completed"
    await updateJob(job.id, { state, files, currentTool: null })
    await writeSummary(job.id, `# ${tool}\n\n- Estado: ${state}\n- Herramienta: ${tool}\n${value?.pending ? "- Adobe: waiting for host consumer\n" : ""}\n## Archivos\n\n${files.map((file) => `- ${file}`).join("\n")}`)
    return { jobId: job.id, directory: job.directory, result, files }
  } catch (error) {
    await updateJob(job.id, { state: "failed", errors: [error.message], currentTool: null })
    await writeSummary(job.id, `# ${tool}\n\n- Estado: failed\n- Error: ${error.message}`)
    throw error
  }
}

function blenderOperation(tool, params) {
  return tool === "blender.run" ? params.operation : tool.replace("blender.", "")
}

export async function runTool(tool, params = {}) {
  if (!WEB_RUN_TOOLS.has(tool)) throw new Error(`Tool is not enabled for web execution: ${tool}`)
  if (tool === "workflow.image-to-svg-preview") return imageToSvgPreview(params)
  if (tool === "workflow.image-to-svg-blender-illustrator") return imageToSvgBlenderIllustrator(params)
  if (tool === "workflow.document-to-animated-post") return documentToAnimatedPost(params)
  if (tool === "workflow.multi-app-composition") return multiAppComposition(params)
  if (tool === "job.create") return createJob(params.name || "web-job", params.request || {})
  if (tool === "adobe.status") return adobeStatus(params.jobId)
  if (tool === "gdkb.health") return gdkbHealth()
  if (tool === "gdkb.normalize") return gdkbNormalize(params.value)
  if (tool === "gdkb.resolve") return gdkbResolve(params.query, params.candidates || [])
  if (tool === "gdkb.merge-event") return gdkbMergeEvent(params)
  if (tool === "integration.sources") return integrationSources()
  if (tool === "integration.scripting-map") return integrationScriptingMap()
  if (tool === "integration.validate") return validateIntegration()
  if (tool === "integration.plan") return integrationPlan(params)
  if (tool === "asset.catalog-index") {
    const catalog = await indexLocalCatalog(params)
    const groups = await indexLocalGroups(params)
    return { ...catalog, groups }
  }
  if (tool === "asset.search-local") return searchLocalAssets(params)
  if (tool === "asset.catalog-groups") return catalogGroupSummary(params)
  if (tool === "asset.catalog-assets") return listCatalogAssets(params)
  if (tool === "asset.semantic-status") return mobileClipStatus(params)
  if (tool === "asset.semantic-index") return indexMobileClip(params)
  if (tool === "asset.semantic-search") return searchMobileClip(params)
  if (tool === "context.analyze") return analyzeContext(params.context || params)

  return runInJob(tool, params, async (job) => {
    if (tool === "svg.create") {
      const rawSpec = specFromParams(params)
      const spec = typeof rawSpec === "string"
        ? await readJson(await stageInput(job, rawSpec, "spec"))
        : rawSpec
      const output = outputPath(job, params.output, "created.svg", params)
      const value = await createSvg(spec, output, overwriteOptions(params))
      return { result: value, files: [output] }
    }
    if (tool === "asset.search") {
      const output = outputPath(job, params.output, "asset-search.json", params)
      const result = await searchAssets(params)
      await fs.writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8")
      return { result, files: [output] }
    }
    if (tool === "asset.fetch") {
      const output = outputPath(job, params.output, `${params.provider || "asset"}.svg`, params)
      const result = await fetchAsset({ ...params, output, overwrite: true })
      return { result, files: [output] }
    }
    if (tool === "asset.select") {
      const selectionPath = params.selectionPath ? await stageInput(job, params.selectionPath, "selection") : null
      const output = outputPath(job, params.output, "asset-manifest.json", params)
      const result = await selectAssets({ ...params, selectionPath, output, overwrite: true })
      return { result, files: result.files }
    }
    if (tool === "gdkb.import") {
      const input = params.input ? await stageInput(job, params.input, "gdkb-import") : null
      const output = outputPath(job, params.output, "gdkb-import.json", params)
      const result = input ? await gdkbImportJsonl(input) : await gdkbImport(params.records || [])
      await fs.writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8")
      return { result, files: [output] }
    }
    if (tool === "gdkb.replay") {
      const input = params.input ? await stageInput(job, params.input, "gdkb-events") : null
      const events = input ? await readJson(input) : (params.events || [])
      const output = outputPath(job, params.output, "gdkb-replay.json", params)
      const result = await gdkbReplay(events.events || events, { snapshot_id: params.snapshotId, compare_state: params.compareState })
      await fs.writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8")
      return { result, files: [output] }
    }
    if (tool === "svg.embed-image") {
      const input = await stageInput(job, params.image, "image")
      const output = outputPath(job, params.output, "embedded.svg", params)
      const value = await embedImage(input, output, { ...params, ...overwriteOptions(params) })
      return { result: value, files: [output] }
    }
    if (tool === "svg.rasterize") {
      const input = await stageInput(job, params.input || params.svg, "svg")
      const output = outputPath(job, params.output, "rasterized.png", params)
      const value = await rasterizeSvg(input, output, { ...params, ...overwriteOptions(params) })
      return { result: value, files: [output] }
    }
    if (tool === "svg.vectorize") {
      const input = await stageInput(job, params.image, "image")
      const output = outputPath(job, params.output, "vectorized.svg", params)
      const value = await vectorizeRaster(input, output, { ...params, ...overwriteOptions(params) })
      return { result: value, files: [output] }
    }
    if (tool === "image.split") {
      const input = await stageInput(job, params.input || params.image, "image")
      const output = outputPath(job, params.output, "image-split.json", params)
      const value = await splitRaster(input, output, { ...params, ...overwriteOptions(params) })
      return { result: value, files: value.files || [output] }
    }
    if (tool === "image.extract-checkerboard-matte") {
      const input = await stageInput(job, params.input || params.image, "image")
      const output = outputPath(job, params.output, "icon-background-removal.json", params)
      const value = await removeIconBackground({
        input,
        output,
        assetsDir: path.dirname(output),
        rows: params.rows,
        columns: params.columns,
        overlap: params.overlap,
        prefix: params.prefix,
        lightThreshold: params.lightThreshold,
        neutralThreshold: params.neutralThreshold,
        orphanArea: params.orphanArea,
        grabcutIterations: params.grabcutIterations,
        padding: params.padding,
        ...overwriteOptions(params),
      })
      return { result: value, files: value.files || [output] }
    }
    if (tool === "svg.animate") {
      const input = await stageInput(job, params.input, "svg")
      const output = outputPath(job, params.output, "animated.svg", params)
      const value = await animateSvg(input, output, params.animation || "float", params.durationMs || 2400, overwriteOptions(params))
      return { result: value, files: [output] }
    }
    if (tool === "svg.particles") {
      const output = outputPath(job, params.output, "particles.svg", params)
      const value = await particles(output, { ...params, ...overwriteOptions(params) })
      return { result: value, files: [output] }
    }
    if (tool === "svg.validate") {
      const input = await stageInput(job, params.input, "svg")
      return { result: await validateSvg(input), files: [] }
    }
    if (tool === "svg.preview") {
      const input = await stageInput(job, params.input, "svg")
      const output = outputPath(job, params.output, "preview.html", params)
      const value = await previewSvg(input, output, overwriteOptions(params))
      return { result: value, files: [output] }
    }
    if (tool === "svg.thi-ng-geom") {
      const rawSpec = params.spec && typeof params.spec === "object" ? params.spec : params.specPath || params.spec
      const spec = typeof rawSpec === "string" ? await readJson(await stageInput(job, rawSpec, "thi-ng-spec")) : (rawSpec || {})
      const output = outputPath(job, params.output, "thi-ng-geom.svg", params)
      const value = await thiNgSvg(spec, output, { ...params, ...overwriteOptions(params) })
      return { result: value, files: [output] }
    }
    if (tool === "data.chart") {
      const input = await stageInput(job, params.input, "data")
      const output = outputPath(job, params.output, "chart.svg", params)
      const value = await barChart(input, output, { ...params, ...overwriteOptions(params) })
      return { result: value, files: [output] }
    }
    if (tool === "data.d3-chart") {
      const input = await stageInput(job, params.input, "data")
      const output = outputPath(job, params.output, "d3-chart.svg", params)
      const value = await d3BarChart(input, output, { ...params, ...overwriteOptions(params) })
      return { result: value, files: [output] }
    }
    if (tool === "scene3d.create") {
      const rawSpec = params.spec && typeof params.spec === "object" ? params.spec : params.specPath || params.spec
      const spec = typeof rawSpec === "string" ? await readJson(await stageInput(job, rawSpec, "three-spec")) : (rawSpec || {})
      const output = outputPath(job, params.output, "scene.html", params)
      const value = await threeScenePreview(spec, output, { ...params, ...overwriteOptions(params) })
      return { result: value, files: [value.html, value.threeModule] }
    }
    if (tool === "math.stdlib-stats") {
      const values = params.input
        ? await readJson(await stageInput(job, params.input, "stdlib-values"))
        : params.values
      const output = outputPath(job, params.output, "stdlib-stats.json", params)
      const result = await stdlibStatistics(values, params)
      await writeJson(output, result)
      return { result, files: [output] }
    }
    if (tool === "workflow.rxjs-events") {
      const events = params.input
        ? await readJson(await stageInput(job, params.input, "rxjs-events"))
        : (params.events || [])
      const output = outputPath(job, params.output, "rxjs-events.json", params)
      const result = await rxjsEventTimeline(events)
      await writeJson(output, result)
      return { result, files: [output] }
    }
    if (tool === "workflow.effect-retry") {
      const output = outputPath(job, params.output, "effect-retry.json", params)
      const result = await effectRetrySimulation(params)
      await writeJson(output, result)
      return { result, files: [output] }
    }
    if (tool === "data.animate") {
      const input = await stageInput(job, params.input, "chart")
      const output = outputPath(job, params.output, "chart-animated.svg", params)
      const value = await animateChart(input, output, params.durationMs || 1200, overwriteOptions(params))
      return { result: value, files: [output] }
    }
    if (tool.startsWith("blender.")) {
      const operation = blenderOperation(tool, params)
      const spec = operation === "layout-scene"
        ? await stageBlenderLayoutSpec(job, params.spec || params.glb || params.svg)
        : await stageInput(job, params.spec || params.glb || params.svg, "blender")
      const output = outputPath(job, params.output, operation === "export-glb" ? "scene.glb" : "scene.blend", params)
      const renderOutput = params.renderOutput ? outputPath(job, params.renderOutput, "scene.png", params) : null
      const value = await runBlender({ operation, spec, output, renderOutput, ...overwriteOptions(params) })
      return { result: value, files: value.files || [output] }
    }
    if (tool === "photoshop.separate-objects") {
      const input = await stageInput(job, params.input, "photoshop-source")
      const manifest = outputPath(job, params.output, "separated/manifest.json", params)
      const outputDir = path.dirname(manifest)
      await ensureDir(outputDir)
      let objects = params.objects ?? params.regions ?? params.options?.objects ?? null
      if (typeof objects === "string") {
        const regionsFile = await stageInput(job, objects, "photoshop-regions")
        objects = await readJson(regionsFile)
        if (objects && !Array.isArray(objects) && Array.isArray(objects.objects)) objects = objects.objects
      }
      const options = {
        ...(params.options || {}),
        output: manifest,
        outputDir,
        mode: params.mode || params.options?.mode || (objects ? "regions" : "subject"),
        objects: Array.isArray(objects) ? objects : undefined,
        padding: Number(params.padding ?? params.options?.padding ?? 8),
      }
      if (params.psdOutput || params.options?.psdOutput) {
        options.psdOutput = outputPath(job, params.psdOutput || params.options.psdOutput, "separated/separated.psd", params)
      }
      const value = await enqueueAdobe({ app: "photoshop", operation: "separate-objects", input, jobId: job.id, options })
      return { result: value, files: [value.command, manifest], pending: true }
    }
    if (tool === "adobe.enqueue") {
      const input = params.input ? await stageInput(job, params.input, "adobe") : null
      const requestedOutput = params.options?.output || params.output
      const options = { ...(params.options || {}) }
      if (requestedOutput) options.output = outputPath(job, requestedOutput, "adobe-output", params)
      const value = await enqueueAdobe({ app: params.app, operation: params.operation, input, jobId: job.id, options })
      return { result: value, files: [value.command], pending: true }
    }
    if (tool === "adobe.after-effects-render") {
      const project = await stageInput(job, params.project, "project")
      const output = outputPath(job, params.output, "after-effects-render", params)
      const value = await renderAfterEffects({ project, output, composition: params.composition, start: params.start, end: params.end, ...overwriteOptions(params) })
      return { result: value, files: [output] }
    }
    throw new Error(`Dispatcher has no implementation for: ${tool}`)
  })
}

export function webToolList() {
  return [...WEB_RUN_TOOLS]
}

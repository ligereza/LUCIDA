import fs from "node:fs/promises"
import path from "node:path"
import { createJob } from "./jobs.mjs"
import { adobeStatus, enqueueAdobe } from "./adapters/adobe.mjs"
import { renderAfterEffects } from "./adapters/after-effects.mjs"
import { runBlender } from "./adapters/blender.mjs"
import { imageToSvgBlenderIllustrator, imageToSvgPreview } from "./orchestrator.mjs"
import { removeIconBackground } from "./tools/image.mjs"
import { createSvg, animateSvg, embedImage, particles, previewSvg, validateSvg } from "./tools/svg.mjs"
import { vectorizeRaster } from "./tools/vectorize.mjs"
import { documentToAnimatedPost } from "./document-workflow.mjs"
import { multiAppComposition } from "./multi-app-workflow.mjs"
import { animateChart, barChart } from "./tools/chart.mjs"
import { d3BarChart } from "./tools/d3.mjs"
import { fetchAsset, searchAssets, selectAssets } from "./tools/asset-search.mjs"
import { catalogStats, indexLocalCatalog, searchLocalAssets } from "./tools/local-catalog.mjs"
import { catalogGroupSummary, indexLocalGroups, listCatalogAssets } from "./tools/catalog-groups.mjs"
import { closeMobileClipWorker, indexMobileClip, installMobileClipModel, mobileClipStatus, searchMobileClip } from "./tools/mobileclip.mjs"
import { analyzeContext } from "./tools/context-analysis.mjs"
import { gdkbHealth, gdkbImport, gdkbImportJsonl, gdkbMergeEvent, gdkbNormalize, gdkbReplay, gdkbResolve } from "./tools/gdkb.mjs"
import { integrationPlan, integrationScriptingMap, integrationSources, validateIntegration } from "./tools/integration.mjs"
import { effectRetrySimulation, rxjsEventTimeline, stdlibStatistics, thiNgSvg, threeScenePreview } from "./tools/source-runtime.mjs"
import { TOOLKIT_ROOT, readJson, resolveInput, resolveOutput } from "./utils.mjs"
import { runTool } from "./dispatcher.mjs"

const args = process.argv.slice(2)
const command = args[0]
const subcommand = args[1]

function flag(name, fallback = undefined) {
  const index = args.indexOf(`--${name}`)
  return index >= 0 ? args[index + 1] : fallback
}

function hasFlag(name) {
  return args.includes(`--${name}`)
}

function json(value) {
  console.log(JSON.stringify(value, null, 2))
}

function csvFlag(name) {
  const value = flag(name)
  return value ? value.split(",").map((item) => item.trim()).filter(Boolean) : undefined
}

function selectedFlag() {
  return csvFlag("selected")?.map((value) => {
    const separator = value.indexOf(":")
    if (separator < 1) throw new Error(`Invalid --selected value: ${value}. Use provider:id`)
    return { provider: value.slice(0, separator), id: value.slice(separator + 1) }
  })
}

async function main() {
  const overwrite = hasFlag("force")
  if (command === "list") return json(await readJson(path.join(TOOLKIT_ROOT, "registry.json")))
  if (command === "job" && subcommand === "create") return json(await createJob(flag("name", "agent-job"), { source: "cli" }))
  if (command === "svg" && subcommand === "create") {
    const spec = await readJson(resolveInput(flag("spec")))
    return json(await createSvg(spec, flag("output", "jobs/manual/output/created.svg"), { overwrite }))
  }
  if (command === "image" && ["remove-background", "extract-checkerboard-matte"].includes(subcommand)) {
    return json(await removeIconBackground({
      input: flag("input"),
      plan: flag("plan"),
      output: flag("output", "jobs/manual/output/icon-background-removal.json"),
      assetsDir: flag("assets-dir"),
      rows: Number(flag("rows", 1)),
      columns: Number(flag("columns", 1)),
      overlap: Number(flag("overlap", 0)),
      prefix: flag("prefix", "icon"),
      lightThreshold: Number(flag("light-threshold", 185)),
      neutralThreshold: Number(flag("neutral-threshold", 18)),
      orphanArea: Number(flag("orphan-area", 64)),
      grabcutIterations: Number(flag("grabcut-iterations", 5)),
      padding: Number(flag("padding", 16)),
      overwrite,
    }))
  }
  if (command === "svg" && subcommand === "embed-image") return json(await embedImage(flag("image"), flag("output", "jobs/manual/output/embedded.svg"), { width: flag("width"), height: flag("height"), overwrite }))
  if (command === "svg" && subcommand === "vectorize") return json(await vectorizeRaster(flag("image"), flag("output", "jobs/manual/output/vectorized.svg"), { maxSize: flag("max-size", 160), threshold: flag("threshold", 8), overwrite }))
  if (command === "svg" && subcommand === "animate") return json(await animateSvg(flag("input"), flag("output", "jobs/manual/output/animated.svg"), flag("animation", "float"), flag("duration-ms", 2400), { overwrite }))
  if (command === "svg" && subcommand === "particles") return json(await particles(flag("output", "jobs/manual/output/particles.svg"), { width: flag("width"), height: flag("height"), count: flag("count"), seed: flag("seed"), color: flag("color"), background: flag("background"), overwrite }))
  if (command === "svg" && subcommand === "validate") return json(await validateSvg(flag("input")))
  if (command === "svg" && subcommand === "preview") return json(await previewSvg(flag("input"), flag("output", "jobs/manual/output/preview.html"), { overwrite }))
  if (command === "svg" && subcommand === "thi-ng-geom") {
    const spec = flag("spec") ? await readJson(resolveInput(flag("spec"))) : JSON.parse(flag("scene", "{}"))
    return json(await thiNgSvg(spec, resolveOutput(flag("output", "jobs/manual/output/thi-ng-geom.svg"), { overwrite }), { overwrite }))
  }
  if (command === "data" && subcommand === "chart") return json(await barChart(flag("input"), flag("output", "jobs/manual/output/chart.svg"), { x: flag("x"), y: flag("y"), title: flag("title"), color: flag("color"), overwrite }))
  if (command === "data" && subcommand === "d3-chart") return json(await d3BarChart(flag("input"), flag("output", "jobs/manual/output/d3-chart.svg"), { x: flag("x"), y: flag("y"), title: flag("title"), color: flag("color"), overwrite }))
  if (command === "data" && subcommand === "animate") return json(await animateChart(flag("input"), flag("output", "jobs/manual/output/chart-animated.svg"), flag("duration-ms", 1200), { overwrite }))
  if (command === "asset" && subcommand === "search") {
    const output = resolveOutput(flag("output", "jobs/manual/output/asset-search.json"), { overwrite })
    const result = await searchAssets({ query: flag("query"), terms: csvFlag("terms"), providers: csvFlag("providers"), limit: Number(flag("limit", 12)), ancla: flag("ancla"), role: flag("role") })
    await fs.mkdir(path.dirname(output), { recursive: true })
    await fs.writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8")
    return json({ ...result, output })
  }
  if (command === "asset" && subcommand === "fetch") return json(await fetchAsset({ provider: flag("provider"), id: flag("id"), output: resolveOutput(flag("output", `jobs/manual/output/${flag("provider", "asset")}.svg`), { overwrite }), overwrite: true }))
  if (command === "asset" && subcommand === "select") {
    const selectionPath = flag("selection") ? resolveInput(flag("selection")) : null
    const selection = selectionPath ? null : { selected: selectedFlag() || [], ancla: flag("ancla"), role: flag("role"), exactText: flag("exact-text"), project: flag("project") }
    return json(await selectAssets({ selection, selectionPath, selected: selectedFlag(), project: flag("project"), ancla: flag("ancla"), role: flag("role"), exactText: flag("exact-text"), output: resolveOutput(flag("output", "jobs/manual/output/asset-manifest.json"), { overwrite }), overwrite: true }))
  }
  if (command === "asset" && subcommand === "index-local") {
    const params = { roots: csvFlag("roots"), cachePath: flag("cache-path"), refresh: true, maxFiles: Number(flag("max-files", 30000)) }
    const catalog = await indexLocalCatalog(params)
    const groups = await indexLocalGroups({ roots: params.roots, cachePath: params.cachePath, refresh: false })
    return json({ ...catalog, groups })
  }
  if (command === "asset" && subcommand === "search-local") {
    try { return json(await searchLocalAssets({ query: flag("query", ""), terms: csvFlag("terms") || [], preferredTerms: csvFlag("preferred-terms") || [], limit: Number(flag("limit", 12)), refresh: hasFlag("refresh"), semantic: hasFlag("semantic"), semanticIndexPath: flag("index-path") })) } finally { closeMobileClipWorker() }
  }
  if (command === "asset" && subcommand === "catalog-stats") return json(await catalogStats())
  if (command === "asset" && subcommand === "catalog-groups") return json(await catalogGroupSummary({ refresh: hasFlag("refresh") }))
  if (command === "asset" && subcommand === "catalog-assets") {
    try { return json(await listCatalogAssets({ type: flag("type"), key: flag("key"), query: flag("query", ""), page: flag("page", 1), pageSize: flag("page-size", 24), semantic: hasFlag("semantic"), semanticIndexPath: flag("index-path") })) } finally { closeMobileClipWorker() }
  }
  if (command === "semantic" && subcommand === "status") {
    try { return json(await mobileClipStatus({ modelName: flag("model", "mobileclip_s2") })) } finally { closeMobileClipWorker() }
  }
  if (command === "semantic" && subcommand === "install") return json(await installMobileClipModel({ modelName: flag("model", "mobileclip_s2"), force: hasFlag("force") }))
  if (command === "semantic" && subcommand === "index") {
    try { return json(await indexMobileClip({ modelName: flag("model", "mobileclip_s2"), roots: csvFlag("roots"), cachePath: flag("cache-path"), indexPath: flag("index-path"), refresh: hasFlag("refresh"), batchSize: Number(flag("batch-size", 96)), preprocessWorkers: Number(flag("preprocess-workers", 1)), device: flag("device", "cuda"), renderer: flag("renderer", "auto"), preprocessBackend: flag("preprocess-backend", "cupy"), profilePath: flag("profile-path"), imageModelPath: flag("image-model-path") })) } finally { closeMobileClipWorker() }
  }
  if (command === "semantic" && subcommand === "search") {
    try { return json(await searchMobileClip({ modelName: flag("model", "mobileclip_s2"), query: flag("query", ""), terms: csvFlag("terms") || [], indexPath: flag("index-path"), limit: Number(flag("limit", 12)) })) } finally { closeMobileClipWorker() }
  }
  if (command === "context" && subcommand === "analyze") {
    const input = flag("input") ? await readJson(resolveInput(flag("input"))) : JSON.parse(flag("json", "{}"))
    return json(analyzeContext(input.context || input))
  }
  if (command === "gdkb" && subcommand === "health") return json(await gdkbHealth())
  if (command === "gdkb" && subcommand === "normalize") return json(await gdkbNormalize(flag("value", "")))
  if (command === "gdkb" && subcommand === "resolve") {
    const candidates = flag("candidates") ? await readJson(resolveInput(flag("candidates"))) : []
    return json(await gdkbResolve(flag("query", ""), candidates))
  }
  if (command === "gdkb" && subcommand === "import") {
    if (flag("input")) return json(await gdkbImportJsonl(resolveInput(flag("input"))))
    const records = flag("records") ? JSON.parse(flag("records")) : []
    return json(await gdkbImport(records))
  }
  if (command === "gdkb" && subcommand === "replay") {
    const input = flag("input") ? await readJson(resolveInput(flag("input"))) : []
    const events = input.events || input
    return json(await gdkbReplay(events, { snapshot_id: flag("snapshot-id"), compare_state: flag("compare-state") ? JSON.parse(flag("compare-state")) : undefined }))
  }
  if (command === "gdkb" && subcommand === "merge-event") {
    return json(await gdkbMergeEvent({ source_entity_id: flag("source"), target_entity_id: flag("target"), reason: flag("reason", ""), evidence_ids: csvFlag("evidence") || [] }))
  }
  if (command === "integration" && subcommand === "sources") return json(await integrationSources())
  if (command === "integration" && subcommand === "scripting-map") return json(await integrationScriptingMap())
  if (command === "integration" && subcommand === "validate") return json(await validateIntegration())
  if (command === "integration" && subcommand === "plan") return json(await integrationPlan({ name: flag("name"), source: flag("source"), storyboard: flag("storyboard"), useAdobe: !hasFlag("no-adobe"), useGeometryNodes: !hasFlag("no-geometry-nodes"), useCycles: !hasFlag("no-cycles") }))
  if (command === "scene3d" && subcommand === "create") {
    const specPath = flag("spec")
    const spec = specPath ? await readJson(resolveInput(specPath)) : (flag("scene") ? JSON.parse(flag("scene")) : {})
    return json(await threeScenePreview(spec, resolveOutput(flag("output", "jobs/manual/output/scene.html"), { overwrite }), { overwrite }))
  }
  if (command === "math" && subcommand === "stdlib-stats") {
    const input = flag("input") ? await readJson(resolveInput(flag("input"))) : JSON.parse(flag("values", "[]"))
    const result = await stdlibStatistics(input, { correction: flag("correction", 0) })
    const output = resolveOutput(flag("output", "jobs/manual/output/stdlib-stats.json"), { overwrite })
    await fs.mkdir(path.dirname(output), { recursive: true })
    await fs.writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8")
    return json({ ...result, output })
  }
  if (command === "workflow" && subcommand === "rxjs-events") {
    const events = flag("input") ? await readJson(resolveInput(flag("input"))) : JSON.parse(flag("events", "[]"))
    const result = await rxjsEventTimeline(events)
    const output = resolveOutput(flag("output", "jobs/manual/output/rxjs-events.json"), { overwrite })
    await fs.mkdir(path.dirname(output), { recursive: true })
    await fs.writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8")
    return json({ ...result, output })
  }
  if (command === "workflow" && subcommand === "effect-retry") {
    const result = await effectRetrySimulation({ failuresBeforeSuccess: flag("failures-before-success", 0), maxRetries: flag("max-retries"), value: flag("value", "ok") })
    const output = resolveOutput(flag("output", "jobs/manual/output/effect-retry.json"), { overwrite })
    await fs.mkdir(path.dirname(output), { recursive: true })
    await fs.writeFile(output, `${JSON.stringify(result, null, 2)}\n`, "utf8")
    return json({ ...result, output })
  }
  if (command === "blender" && subcommand === "run") return json(await runBlender({ operation: flag("operation", "create-scene"), spec: flag("spec"), output: flag("output", "jobs/manual/output/scene.blend"), renderOutput: flag("render-output"), overwrite }))
  if (command === "photoshop" && subcommand === "separate-objects") {
    const objectsInput = flag("objects")
    let objects = undefined
    if (objectsInput && /^[\[{]/.test(objectsInput.trim())) objects = JSON.parse(objectsInput)
    if (objects && !Array.isArray(objects) && Array.isArray(objects.objects)) objects = objects.objects
    return json(await runTool("photoshop.separate-objects", {
      input: flag("input"),
      output: flag("output", "separated/manifest.json"),
      psdOutput: flag("psd-output"),
      mode: flag("mode", objects || objectsInput ? "regions" : "subject"),
      objects: objects || objectsInput,
      padding: Number(flag("padding", 8)),
      overwrite,
      confirmOverwrite: hasFlag("confirm-overwrite"),
    }))
  }
  if (command === "adobe" && subcommand === "enqueue") return json(await enqueueAdobe({ app: flag("app"), operation: flag("operation"), input: flag("input"), options: { output: flag("output") } }))
  if (command === "adobe" && subcommand === "status") return json(await adobeStatus(flag("job")))
  if (command === "adobe" && subcommand === "render") return json(await renderAfterEffects({ project: flag("project"), output: flag("output", "jobs/manual/output/after-effects-render"), composition: flag("comp"), start: flag("start"), end: flag("end"), overwrite }))
  if (command === "workflow" && subcommand === "image-to-svg-preview") return json(await imageToSvgPreview({ image: flag("image"), animation: flag("animation", "float"), vectorize: hasFlag("vectorize") || flag("vectorize") === "true", blender: hasFlag("blender") || flag("blender") === "true", adobeApp: flag("adobe") || null }))
  if (command === "workflow" && subcommand === "image-to-svg-blender-illustrator") return json(await imageToSvgBlenderIllustrator({ image: flag("image"), animation: flag("animation", "float"), vectorize: !args.includes("--no-vectorize") }))
  if (command === "workflow" && subcommand === "document-to-animated-post") return json(await documentToAnimatedPost({ document: flag("document"), title: flag("title"), maxParts: Number(flag("max-parts", 12)), minChars: Number(flag("min-chars", 180)), blender: hasFlag("blender"), adobeApp: flag("adobe") || null, splitBy: flag("split-by", "auto"), splitPlan: flag("split-plan") || null, designPath: flag("design"), design: flag("preset") ? { preset: flag("preset") } : null, pdfProvider: flag("pdf-provider", "local") }))
  if (command === "workflow" && subcommand === "multi-app-composition") return json(await multiAppComposition({ storyboard: flag("storyboard"), adobeApp: flag("adobe") || null, adobeOperation: flag("adobe-operation", "import-svg"), adobeInput: flag("adobe-input") || null, projectRoot: flag("project-root") || null, render: !hasFlag("no-render"), name: flag("name", "multi-app-composition") }))
  if (command === "server") return await import("./server.mjs")
  throw new Error("Unknown command. Run: npm run tool -- list")
}

main().catch((error) => {
  console.error(JSON.stringify({ error: error.message }, null, 2))
  process.exitCode = 1
})

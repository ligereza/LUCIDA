import fs from "node:fs/promises"
import path from "node:path"
import { createJob, updateJob, writeSummary } from "./jobs.mjs"
import { enqueueAdobe } from "./adapters/adobe.mjs"
import { runBlender } from "./adapters/blender.mjs"
import { ensureDir, readJson, resolveInput, slugify, writeJson, TOOLKIT_ROOT } from "./utils.mjs"

async function stageFile(job, rawPath, label, baseDirectory, copied, counter) {
  if (!rawPath || typeof rawPath !== "string") return rawPath
  const source = resolveInput(path.isAbsolute(rawPath) ? rawPath : path.resolve(baseDirectory, rawPath))
  if (copied.has(source)) return copied.get(source)
  const target = path.join(job.directory, "input", "assets", `${String(counter.value++).padStart(4, "0")}-${path.basename(source)}`)
  await ensureDir(path.dirname(target))
  await fs.copyFile(source, target)
  copied.set(source, target)
  return target
}

async function stageStoryboard(job, storyboard) {
  const copied = new Map()
  const counter = { value: 0 }
  const sourceSpec = typeof storyboard === "string" ? resolveInput(storyboard) : null
  const specDirectory = sourceSpec ? path.dirname(sourceSpec) : TOOLKIT_ROOT
  const spec = sourceSpec ? await readJson(sourceSpec) : { ...(storyboard || {}) }

  async function stageAssetList(items, baseDirectory) {
    if (!Array.isArray(items)) return
    for (const asset of items) {
      if (!asset || typeof asset !== "object") continue
      const key = asset.file ? "file" : asset.path ? "path" : null
      if (key) asset[key] = await stageFile(job, asset[key], "asset", baseDirectory, copied, counter)
    }
  }

  async function stageManifestReference(reference, baseDirectory) {
    if (!reference || typeof reference !== "string") return reference
    const sourceManifest = resolveInput(path.isAbsolute(reference) ? reference : path.resolve(baseDirectory, reference))
    const manifest = await readJson(sourceManifest)
    await stageAssetList(manifest.assets, path.dirname(sourceManifest))
    const target = path.join(job.directory, "input", `asset-manifest-${String(counter.value++).padStart(4, "0")}.json`)
    await writeJson(target, manifest)
    return target
  }

  if (typeof spec.assetManifest === "string") spec.assetManifest = await stageManifestReference(spec.assetManifest, specDirectory)
  if (Array.isArray(spec.assetManifests)) spec.assetManifests = await Promise.all(spec.assetManifests.map((item) => stageManifestReference(item, specDirectory)))
  await stageAssetList(spec.assets, specDirectory)
  await stageAssetList(spec.design?.assets, specDirectory)
  for (const part of spec.parts || []) await stageAssetList(part.assets, specDirectory)
  const target = path.join(job.directory, "input", "storyboard.json")
  await writeJson(target, spec)
  return { spec, path: target, source: sourceSpec, assets: [...copied.values()] }
}

function adobeInputsFromSpec(spec) {
  const inputs = []
  for (const asset of spec.assets || []) {
    const value = asset?.file || asset?.path
    if (typeof value === "string" && /\.svg$/i.test(value)) inputs.push(value)
  }
  return [...new Set(inputs)]
}

export async function multiAppComposition({ storyboard, adobeApp = null, adobeOperation = "import-svg", adobeInput = null, adobeOptions = {}, projectRoot = null, render = true, name = "multi-app-composition" } = {}) {
  const job = await createJob(name, { storyboard, adobeApp, adobeOperation, adobeInput, projectRoot, render })
  const files = []
  try {
    const staged = await stageStoryboard(job, storyboard)
    files.push(staged.path)
    const projectDirectory = projectRoot ? resolveInput(projectRoot) : null
    const projectFiles = []
    const projectSlug = slugify(name)
    const projectArtifacts = projectDirectory ? {
      blend: path.join(projectDirectory, "editable", "blender", `${projectSlug}-${job.id}.blend`),
      render: render ? path.join(projectDirectory, "renders", `${projectSlug}-${job.id}.png`) : null,
      integrationManifest: path.join(projectDirectory, "manifests", `${projectSlug}-${job.id}.json`),
    } : null
    if (projectDirectory) await ensureDir(projectDirectory)
    await updateJob(job.id, { state: "running", inputs: [staged.path], currentTool: "blender.layout-scene" })
    const scene = path.join(job.directory, "output", "scene.blend")
    const renderOutput = render ? path.join(job.directory, "output", "scene.png") : null
    const blender = await runBlender({ operation: "layout-scene", spec: staged.path, output: scene, renderOutput })
    files.push(...blender.files)
    if (projectArtifacts) {
      await ensureDir(path.dirname(projectArtifacts.blend))
      await fs.copyFile(scene, projectArtifacts.blend)
      projectFiles.push(projectArtifacts.blend)
      if (projectArtifacts.render && renderOutput) {
        await ensureDir(path.dirname(projectArtifacts.render))
        await fs.copyFile(renderOutput, projectArtifacts.render)
        projectFiles.push(projectArtifacts.render)
      }
    }

    const rawAdobeCandidates = adobeInput
      ? (Array.isArray(adobeInput) ? adobeInput : [adobeInput])
      : adobeInputsFromSpec(staged.spec)
    const adobeCandidates = []
    const adobeCopied = new Map()
    const adobeCounter = { value: 0 }
    const sourceDirectory = staged.source ? path.dirname(staged.source) : TOOLKIT_ROOT
    for (const rawInput of rawAdobeCandidates) {
      if (typeof rawInput !== "string") throw new Error("adobeInput entries must be file paths")
      const candidate = path.isAbsolute(rawInput) ? rawInput : resolveInput(rawInput)
      const relative = path.relative(job.directory, candidate)
      const alreadyStaged = relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative))
      adobeCandidates.push(alreadyStaged ? candidate : await stageFile(job, candidate, "adobe", sourceDirectory, adobeCopied, adobeCounter))
    }
    const commands = []
    const adobeOptionsForJob = { ...adobeOptions }
    if (projectDirectory && adobeApp === "photoshop" && adobeOperation === "separate-objects") {
      adobeOptionsForJob.outputDir ||= path.join(projectDirectory, "editable", "photoshop", `${projectSlug}-${job.id}-objects`)
      adobeOptionsForJob.psdOutput ||= path.join(projectDirectory, "editable", "photoshop", `${projectSlug}-${job.id}.psd`)
      adobeOptionsForJob.output ||= path.join(projectDirectory, "manifests", `${projectSlug}-${job.id}-photoshop.json`)
      await ensureDir(adobeOptionsForJob.outputDir)
      await ensureDir(path.dirname(adobeOptionsForJob.psdOutput))
      await ensureDir(path.dirname(adobeOptionsForJob.output))
      projectFiles.push(adobeOptionsForJob.psdOutput, adobeOptionsForJob.output)
    }
    if (adobeApp && adobeCandidates.length) {
      for (const input of adobeCandidates) {
        const adobe = await enqueueAdobe({ app: adobeApp, operation: adobeOperation, input, jobId: job.id, options: adobeOptionsForJob })
        commands.push(adobe.command)
      }
      files.push(...commands)
    }

    const manifest = path.join(job.directory, "output", "integration-manifest.json")
    const result = {
      version: 1,
      jobId: job.id,
      status: adobeApp && commands.length ? "waiting-for-adobe" : "completed",
      source: staged.source || "inline-storyboard",
      stagedStoryboard: staged.path,
      projectRoot: projectDirectory,
      blender: { operation: "layout-scene", geometryNodes: true, cycles: true, files: blender.files },
      adobe: { app: adobeApp, operation: adobeApp ? adobeOperation : null, commands },
      assets: staged.assets,
      projectFiles,
      files,
    }
    await writeJson(manifest, result)
    files.push(manifest)
    if (projectArtifacts) {
      await ensureDir(path.dirname(projectArtifacts.integrationManifest))
      await writeJson(projectArtifacts.integrationManifest, result)
      projectFiles.push(projectArtifacts.integrationManifest)
      result.projectFiles = projectFiles
      await writeJson(manifest, result)
    }
    await updateJob(job.id, { state: result.status, files, currentTool: null, integration: result })
    await writeSummary(job.id, `# ${name}\n\n- Storyboard: ${staged.path}\n- Blender: layout-scene + Geometry Nodes + Cycles\n- Adobe: ${adobeApp ? `${adobeApp} (${commands.length} command(s))` : "none"}\n- State: ${result.status}\n\n## Outputs\n\n${files.map((file) => `- ${file}`).join("\n")}`)
    return { ...result, directory: job.directory }
  } catch (error) {
    await updateJob(job.id, { state: "failed", errors: [error.message], files, currentTool: null })
    await writeSummary(job.id, `# ${name}\n\n- State: failed\n- Error: ${error.message}`)
    throw error
  }
}

import fs from "node:fs/promises"
import path from "node:path"
import { createJob, updateJob, writeSummary } from "./jobs.mjs"
import { enqueueAdobe } from "./adapters/adobe.mjs"
import { runBlender } from "./adapters/blender.mjs"
import { animateSvg, embedImage, previewSvg, validateSvg } from "./tools/svg.mjs"
import { resolveInput } from "./utils.mjs"
import { vectorizeRaster } from "./tools/vectorize.mjs"

async function runImageToSvgWorkflow({ image, animation = "float", vectorize = false, blender = false, adobeApp = null, workflowName = "image-to-svg-preview" }) {
  const job = await createJob(workflowName, { image, animation, vectorize, blender, adobeApp })
  const source = resolveInput(image)
  const stagedInput = path.join(job.directory, "input", path.basename(source))
  const embedded = path.join(job.directory, "work", "embedded.svg")
  const vectorized = path.join(job.directory, "work", "vectorized.svg")
  const animated = path.join(job.directory, "output", "animated.svg")
  const preview = path.join(job.directory, "output", "preview.html")
  const adobeVectorized = path.join(job.directory, "work", "adobe-vectorized.svg")
  const adobeAnimated = path.join(job.directory, "output", "adobe-import.svg")
  let adobeInput = animated
  let adobeFallback = false
  try {
    await fs.copyFile(source, stagedInput)
    await updateJob(job.id, { state: "running", inputs: [stagedInput], currentTool: vectorize ? "svg.vectorize" : "svg.embed-image" })
    if (vectorize) await vectorizeRaster(stagedInput, vectorized)
    else await embedImage(stagedInput, embedded)
    await updateJob(job.id, { currentTool: "svg.animate" })
    await animateSvg(vectorize ? vectorized : embedded, animated, animation)
    const validation = await validateSvg(animated)
    await updateJob(job.id, { currentTool: "svg.preview" })
    await previewSvg(animated, preview)
    const files = [animated, preview]
    if (blender) {
      await updateJob(job.id, { currentTool: "blender.import-svg" })
      const blend = path.join(job.directory, "output", "scene.blend")
      const render = path.join(job.directory, "output", "scene.png")
      const blenderResult = await runBlender({ operation: "import-svg", spec: animated, output: blend, renderOutput: render })
      files.push(...blenderResult.files)
    }
    if (adobeApp) {
      if (adobeApp === "illustrator" && !vectorize && !/\.svg$/i.test(stagedInput)) {
        adobeFallback = true
        await updateJob(job.id, { currentTool: "svg.vectorize" })
        await vectorizeRaster(stagedInput, adobeVectorized)
        await animateSvg(adobeVectorized, adobeAnimated, animation)
        adobeInput = adobeAnimated
        files.push(adobeAnimated)
      }
      await updateJob(job.id, { currentTool: "adobe.enqueue" })
      const adobe = await enqueueAdobe({ app: adobeApp, operation: "import-svg", input: adobeInput, jobId: job.id, options: {} })
      files.push(adobe.command)
    }
    const state = validation.valid ? (adobeApp ? "waiting-for-adobe" : "completed") : "completed-with-warnings"
    await updateJob(job.id, { state, files, validation, currentTool: null })
    const outputList = files.map((file) => `- ${file}`).join("\n")
    await writeSummary(job.id, `# ${workflowName}\n\n- Input: ${image}\n- Vectorized: ${vectorize}\n- Animation: ${animation}\n- State: ${state}\n${adobeApp ? "- Adobe: waiting for host consumer\n" : ""}${adobeFallback ? "- Illustrator: auto-vectorized import variant\n" : ""}\n## Outputs\n\n${outputList}\n\n## Validation\n\n- Valid: ${validation.valid}\n- Warnings: ${validation.warnings.length}\n`)
    return { jobId: job.id, directory: job.directory, files, validation }
  } catch (error) {
    await updateJob(job.id, { state: "failed", errors: [error.message], currentTool: null })
    await writeSummary(job.id, `# ${workflowName}\n\n- State: failed\n- Error: ${error.message}`)
    throw error
  }
}

export async function imageToSvgPreview(options) {
  return runImageToSvgWorkflow({ ...options, workflowName: "image-to-svg-preview" })
}

export async function imageToSvgBlenderIllustrator({ image, animation = "float", vectorize = true }) {
  return runImageToSvgWorkflow({
    image,
    animation,
    vectorize,
    blender: true,
    adobeApp: "illustrator",
    workflowName: "image-to-svg-blender-illustrator",
  })
}

import fs from "node:fs/promises"
import path from "node:path"
import { spawn } from "node:child_process"
import { fileURLToPath } from "node:url"
import { readJson, resolveInput, resolveOutput, TOOLKIT_ROOT } from "../utils.mjs"

const adapterScript = fileURLToPath(new URL("../../adapters/blender/agent_blender.py", import.meta.url))

async function blenderExecutable() {
  const configFile = path.join(TOOLKIT_ROOT, "config.local.json")
  try {
    const config = await readJson(configFile)
    return config.blender?.executable || "blender"
  } catch {
    return process.env.BLENDER_EXE || "blender"
  }
}

export async function runBlender({ operation, spec, output, renderOutput, overwrite = false }) {
  if (!new Set(["create-scene", "render", "import-svg", "import-glb", "export-glb", "layout-scene"]).has(operation)) throw new Error(`Unsupported Blender operation: ${operation}`)
  const specPath = resolveInput(spec)
  const outputPath = resolveOutput(output, { overwrite })
  await fs.mkdir(path.dirname(outputPath), { recursive: true })
  const executable = await blenderExecutable()
  const args = ["--background", "--factory-startup", "--python", adapterScript, "--", "--operation", operation, "--spec", specPath, "--output", outputPath]
  if (renderOutput) args.push("--render-output", resolveOutput(renderOutput, { overwrite }))
  return await new Promise((resolve, reject) => {
    const child = spawn(executable, args, { cwd: TOOLKIT_ROOT, windowsHide: true })
    let stdout = ""
    let stderr = ""
    child.stdout.on("data", (chunk) => { stdout += chunk })
    child.stderr.on("data", (chunk) => { stderr += chunk })
    child.on("error", (error) => reject(new Error(`Could not start Blender at ${executable}: ${error.message}`)))
    child.on("close", (code) => {
      if (code !== 0) return reject(new Error(`Blender exited with ${code}\n${stderr.slice(-4000)}`))
      resolve({ files: [outputPath, ...(renderOutput ? [resolveOutput(renderOutput, { overwrite: true })] : [])], executable, stdout: stdout.slice(-4000), stderr: stderr.slice(-4000) })
    })
  })
}

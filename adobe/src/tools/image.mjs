import fs from "node:fs/promises"
import path from "node:path"
import { spawn } from "node:child_process"
import { fileURLToPath } from "node:url"
import { ensureDir, resolveInput, resolveOutput } from "../utils.mjs"

const splitScript = fileURLToPath(new URL("../../adapters/image/split.py", import.meta.url))
const removeBackgroundScript = fileURLToPath(new URL("../../adapters/image/remove_background.py", import.meta.url))

async function runPythonImageTool(script, args, message) {
  const python = process.env.PYTHON_EXE || "python"
  return await new Promise((resolve, reject) => {
    const child = spawn(python, [script, ...args], { cwd: path.dirname(script), windowsHide: true })
    let stdout = ""
    let stderr = ""
    child.stdout.on("data", (chunk) => { stdout += chunk })
    child.stderr.on("data", (chunk) => { stderr += chunk })
    child.on("error", (error) => reject(new Error(`Could not start Python: ${error.message}`)))
    child.on("close", (code) => {
      if (code !== 0) return reject(new Error(`${message} exited with ${code}\n${stderr}`))
      try { resolve(JSON.parse(stdout.trim().split(/\r?\n/).at(-1))) } catch (error) { reject(new Error(`${message} returned invalid output: ${error.message}\n${stdout}`)) }
    })
  })
}

export async function splitRaster(input, output, options = {}) {
  const inputPath = resolveInput(input)
  const outputPath = resolveOutput(output, options)
  await ensureDir(path.dirname(outputPath))
  const args = [
    "--input", inputPath,
    "--output", outputPath,
    "--rows", String(options.rows || 1),
    "--columns", String(options.columns || 1),
    "--mode", String(options.mode || "grid"),
    "--overlap", String(options.overlap || 0),
    "--prefix", String(options.prefix || "tile"),
  ]
  const result = await runPythonImageTool(splitScript, args, "Image splitter")
  const manifest = JSON.parse(await fs.readFile(outputPath, "utf8"))
  return { ...result, manifest, output: outputPath, files: [outputPath, ...(manifest.files || [])] }
}

export async function removeIconBackground({ input, plan, output, assetsDir, rows = 1, columns = 1, overlap = 0, prefix = "icon", lightThreshold = 185, neutralThreshold = 18, orphanArea = 64, grabcutIterations = 5, padding = 16, overwrite = false } = {}) {
  if (!input && !plan) throw new Error("removeIconBackground requires input or plan")
  const outputPath = resolveOutput(output, { overwrite })
  await ensureDir(path.dirname(outputPath))
  const args = [
    "--output", outputPath,
    "--rows", String(rows),
    "--columns", String(columns),
    "--overlap", String(overlap),
    "--prefix", String(prefix),
    "--light-threshold", String(lightThreshold),
    "--neutral-threshold", String(neutralThreshold),
    "--orphan-area", String(orphanArea),
    "--grabcut-iterations", String(grabcutIterations),
    "--padding", String(padding),
  ]
  if (assetsDir) args.push("--assets-dir", resolveOutput(assetsDir, { overwrite: true }))
  if (input) args.unshift("--input", resolveInput(input))
  else args.unshift("--plan", resolveInput(plan))
  if (overwrite) args.push("--force")
  const result = await runPythonImageTool(removeBackgroundScript, args, "Icon background remover")
  const manifest = JSON.parse(await fs.readFile(outputPath, "utf8"))
  return { ...result, manifest, output: outputPath, files: [outputPath, ...(manifest.files || [])] }
}

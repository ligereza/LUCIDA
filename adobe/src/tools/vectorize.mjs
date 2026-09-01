import path from "node:path"
import { spawn } from "node:child_process"
import { fileURLToPath } from "node:url"
import { ensureDir, resolveInput, resolveOutput } from "../utils.mjs"

const script = fileURLToPath(new URL("../../adapters/image/vectorize.py", import.meta.url))

export async function vectorizeRaster(input, output, options = {}) {
  const inputPath = resolveInput(input)
  const outputPath = resolveOutput(output, options)
  await ensureDir(path.dirname(outputPath))
  const python = process.env.PYTHON_EXE || "python"
  const args = [script, "--input", inputPath, "--output", outputPath, "--max-size", String(options.maxSize || 160), "--threshold", String(options.threshold || 8)]
  return await new Promise((resolve, reject) => {
    const child = spawn(python, args, { cwd: path.dirname(script), windowsHide: true })
    let stdout = ""
    let stderr = ""
    child.stdout.on("data", (chunk) => { stdout += chunk })
    child.stderr.on("data", (chunk) => { stderr += chunk })
    child.on("error", (error) => reject(new Error(`Could not start Python: ${error.message}`)))
    child.on("close", (code) => {
      if (code !== 0) return reject(new Error(`Vectorizer exited with ${code}\n${stderr}`))
      try { resolve(JSON.parse(stdout.trim())) } catch { resolve({ svg: outputPath, stdout: stdout.trim() }) }
    })
  })
}

import fs from "node:fs/promises"
import path from "node:path"
import { spawn } from "node:child_process"
import { readJson, resolveInput, resolveOutput, TOOLKIT_ROOT } from "../utils.mjs"

async function executable() {
  try {
    const config = await readJson(path.join(TOOLKIT_ROOT, "config.local.json"))
    return config.adobe?.["after-effects-render"] || "aerender"
  } catch {
    return process.env.AERENDER_EXE || "aerender"
  }
}

export async function renderAfterEffects({ project, output, composition, start, end, overwrite = false }) {
  const projectPath = resolveInput(project)
  const outputPath = resolveOutput(output, { overwrite })
  await fs.mkdir(path.dirname(outputPath), { recursive: true })
  const args = ["-project", projectPath, "-output", outputPath]
  if (composition) args.push("-comp", composition)
  if (start !== undefined) args.push("-s", String(start))
  if (end !== undefined) args.push("-e", String(end))
  const exe = await executable()
  return await new Promise((resolve, reject) => {
    const child = spawn(exe, args, { cwd: TOOLKIT_ROOT, windowsHide: true })
    let stdout = ""
    let stderr = ""
    child.stdout.on("data", (chunk) => { stdout += chunk })
    child.stderr.on("data", (chunk) => { stderr += chunk })
    child.on("error", (error) => reject(new Error(`Could not start aerender at ${exe}: ${error.message}`)))
    child.on("close", (code) => {
      if (code !== 0) return reject(new Error(`aerender exited with ${code}\n${stderr.slice(-4000)}`))
      resolve({ output: outputPath, executable: exe, stdout: stdout.slice(-4000), stderr: stderr.slice(-4000) })
    })
  })
}

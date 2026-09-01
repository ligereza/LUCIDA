import { spawn } from "node:child_process"
import { fileURLToPath } from "node:url"
import path from "node:path"

const bridge = fileURLToPath(new URL("../../adapters/gdkb/bridge.py", import.meta.url))

export function runGdkb(operation, payload = {}) {
  const python = process.env.GDKB_PYTHON || process.env.DOCUMENT_PYTHON || "python"
  return new Promise((resolve, reject) => {
    const child = spawn(python, [bridge, "--operation", operation], {
      cwd: path.dirname(bridge),
      windowsHide: true,
      env: { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" },
      stdio: ["pipe", "pipe", "pipe"],
    })
    let stdout = ""
    let stderr = ""
    child.stdout.setEncoding("utf8")
    child.stderr.setEncoding("utf8")
    child.stdout.on("data", (chunk) => { stdout += chunk })
    child.stderr.on("data", (chunk) => { stderr += chunk })
    child.on("error", (error) => reject(new Error(`GDKB Python bridge failed to start: ${error.message}`)))
    child.on("close", (code) => {
      let result
      try { result = JSON.parse(stdout) } catch { result = null }
      if (code !== 0) {
        const detail = result?.error || stderr.trim() || `exit code ${code}`
        reject(new Error(`GDKB ${operation} failed: ${detail}`))
        return
      }
      if (!result) {
        reject(new Error(`GDKB ${operation} returned invalid JSON`))
        return
      }
      resolve(result)
    })
    child.stdin.end(JSON.stringify(payload))
  })
}

export async function gdkbHealth() {
  return runGdkb("health")
}

export async function gdkbNormalize(value) {
  return runGdkb("normalize", { value })
}

export async function gdkbResolve(query, candidates) {
  return runGdkb("resolve", { query, candidates })
}

export async function gdkbImport(records) {
  return runGdkb("import", { records })
}

export async function gdkbImportJsonl(inputPath) {
  return runGdkb("import", { input_path: inputPath })
}

export async function gdkbReplay(events, options = {}) {
  return runGdkb("replay", { events, ...options })
}

export async function gdkbMergeEvent(plan) {
  return runGdkb("merge-event", plan)
}

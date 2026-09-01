import fs from "node:fs/promises"
import path from "node:path"
import { audit } from "./audit.mjs"
import { JOBS_ROOT, assertJobId, ensureDir, nowId, readJson, writeJson } from "./utils.mjs"

export async function createJob(name, request = {}) {
  const id = nowId(name)
  const directory = path.join(JOBS_ROOT, id)
  for (const folder of ["input", "work", "output", "adobe", "adobe/commands"]) {
    await ensureDir(path.join(directory, folder))
  }
  await writeJson(path.join(directory, "request.json"), request)
  await writeJson(path.join(directory, "status.json"), {
    id,
    name,
    state: "created",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    files: [],
    errors: []
  })
  await fs.writeFile(path.join(directory, "summary.md"), `# ${name}\n\nEstado: creado.\n`, "utf8")
  await audit("job.created", { jobId: id, name })
  return { id, directory }
}

export async function updateJob(id, patch) {
  const file = path.join(JOBS_ROOT, assertJobId(id), "status.json")
  const current = await readJson(file)
  const next = { ...current, ...patch, updatedAt: new Date().toISOString() }
  await writeJson(file, next)
  await audit("job.updated", { jobId: id, state: next.state, currentTool: next.currentTool || null })
  return next
}

export async function getJob(id) {
  const directory = path.join(JOBS_ROOT, assertJobId(id))
  const status = await readJson(path.join(directory, "status.json"))
  return { ...status, directory }
}

export async function writeSummary(id, markdown) {
  const file = path.join(JOBS_ROOT, assertJobId(id), "summary.md")
  await fs.writeFile(file, `${markdown.trim()}\n`, "utf8")
  return file
}

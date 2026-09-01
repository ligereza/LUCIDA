import fs from "node:fs/promises"
import path from "node:path"
import { deterministicId, clone } from "../contracts/stable.mjs"

function safeId(value) { const id = String(value || ""); if (!/^[a-z0-9][a-z0-9._-]{2,100}$/i.test(id)) throw new Error("Invalid job id"); return id }
function safeRelative(value) { const relative = String(value || "").replaceAll("\\", "/"); if (!relative || relative.startsWith("/") || relative.split("/").includes("..")) throw new Error("Invalid job-relative path"); return relative }
async function writeJson(file, value) { await fs.mkdir(path.dirname(file), { recursive: true }); await fs.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8") }

export async function createJob({ root, name = "job", request = {}, jobId = null, idempotencyKey = null } = {}) {
  if (!root) throw new Error("Job root is required")
  const id = safeId(jobId || deterministicId("job", { name, request, idempotencyKey }))
  const directory = path.join(path.resolve(root), id)
  for (const folder of ["input", "work", "output", "events"]) await fs.mkdir(path.join(directory, folder), { recursive: true })
  const status = { schemaVersion: 1, id, name: String(name), state: "created", request: clone(request), files: [], errors: [], createdAt: null, updatedAt: null }
  await writeJson(path.join(directory, "request.json"), request)
  await writeJson(path.join(directory, "status.json"), status)
  await fs.writeFile(path.join(directory, "summary.md"), `# ${name}\n\nEstado: creado.\n`, "utf8")
  return { id, directory, status }
}

export async function getJob(root, id) { const directory = path.join(path.resolve(root), safeId(id)); const status = JSON.parse(await fs.readFile(path.join(directory, "status.json"), "utf8")); return { ...status, directory } }

export async function updateJob(root, id, patch = {}) { const current = await getJob(root, id); const next = { ...current, ...clone(patch), directory: undefined }; delete next.directory; await writeJson(path.join(current.directory, "status.json"), next); return { ...next, directory: current.directory } }

export async function writeJobFile(root, id, relative, content) { const job = await getJob(root, id); const file = path.join(job.directory, safeRelative(relative)); await fs.mkdir(path.dirname(file), { recursive: true }); await fs.writeFile(file, content); return file }

export async function cancelJob(root, id, reason = "cancelled-by-user") { const job = await getJob(root, id); if (["completed", "failed", "cancelled"].includes(job.state)) throw new Error("Job cannot be cancelled in its current state"); return updateJob(root, id, { state: "cancelled", cancellation: { reason } }) }

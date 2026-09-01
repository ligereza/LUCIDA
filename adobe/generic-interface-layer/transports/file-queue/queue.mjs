import fs from "node:fs/promises"
import path from "node:path"
import { createAction } from "../../core/actions/lifecycle.mjs"

function safeId(value) { const id = String(value || ""); if (!/^[a-z0-9][a-z0-9._-]{2,100}$/i.test(id)) throw new Error("Invalid queue id"); return id }
function fileFor(root, id) { return path.join(path.resolve(root), `${safeId(id)}.json`) }

export async function enqueueAction(root, input) {
  const action = createAction(input)
  await fs.mkdir(path.resolve(root), { recursive: true })
  const file = fileFor(root, action.actionId)
  try { await fs.access(file); return { action, file, existing: true } } catch (_) {}
  await fs.writeFile(file, `${JSON.stringify(action, null, 2)}\n`, "utf8")
  return { action, file, existing: false }
}

export async function readQueuedAction(root, actionId) { return JSON.parse(await fs.readFile(fileFor(root, actionId), "utf8")) }

export async function cancelQueuedAction(root, actionId, reason = "cancelled-by-user") {
  const action = await readQueuedAction(root, actionId)
  const cancelled = { ...action, state: "cancelled", cancellation: { reason }, updatedAt: null }
  await fs.writeFile(fileFor(root, actionId), `${JSON.stringify(cancelled, null, 2)}\n`, "utf8")
  return cancelled
}

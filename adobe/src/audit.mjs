import fs from "node:fs/promises"
import path from "node:path"
import { TOOLKIT_ROOT, ensureDir } from "./utils.mjs"

export const AUDIT_FILE = path.join(TOOLKIT_ROOT, "logs", "audit.ndjson")

export async function audit(event, details = {}) {
  const record = { timestamp: new Date().toISOString(), event, ...details }
  await ensureDir(path.dirname(AUDIT_FILE))
  await fs.appendFile(AUDIT_FILE, `${JSON.stringify(record)}\n`, "utf8")
  return record
}

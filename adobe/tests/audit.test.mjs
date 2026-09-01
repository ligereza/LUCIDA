import test from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { createJob, updateJob } from "../src/jobs.mjs"
import { AUDIT_FILE } from "../src/audit.mjs"
import { JOBS_ROOT } from "../src/utils.mjs"

test("job lifecycle writes append-only audit events", async () => {
  const job = await createJob("audit-test", { source: "test" })
  await updateJob(job.id, { state: "running", currentTool: "test.tool" })
  const lines = (await fs.readFile(AUDIT_FILE, "utf8")).trim().split(/\r?\n/)
  const events = lines.map((line) => JSON.parse(line)).filter((event) => event.jobId === job.id)
  assert.deepEqual(events.map((event) => event.event), ["job.created", "job.updated"])
  assert.equal(events[0].jobId, job.id)
  assert.equal(events[1].currentTool, "test.tool")
  await fs.rm(path.join(JOBS_ROOT, job.id), { recursive: true, force: true })
})

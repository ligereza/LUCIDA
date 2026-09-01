import test from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { adobeStatus, enqueueAdobe } from "../src/adapters/adobe.mjs"
import { getJob } from "../src/jobs.mjs"
import { JOBS_ROOT, TOOLKIT_ROOT } from "../src/utils.mjs"

test("Adobe queue validates input and output roots", async () => {
  await assert.rejects(
    enqueueAdobe({ app: "premiere", operation: "import-media", input: "C:\\Windows\\win.ini" }),
    /outside configured roots/,
  )
  await assert.rejects(
    enqueueAdobe({ app: "premiere", operation: "import-media", input: path.join(TOOLKIT_ROOT, "adapters", "blender", "scene.example.json"), jobId: "missing-job" }),
    /ENOENT|no such file/i,
  )
  const queued = await enqueueAdobe({
    app: "premiere",
    operation: "import-media",
    input: path.join(TOOLKIT_ROOT, "adapters", "blender", "scene.example.json"),
    options: { output: "jobs/_test-adobe-queue/output.mp4" },
  })
  assert.equal(queued.status, "queued")
  assert.match(queued.command, /adobe[\\/]commands[\\/].+\.json$/)
  await fs.access(path.join(TOOLKIT_ROOT, "jobs", "_test-adobe-queue"))
  await fs.rm(path.join(JOBS_ROOT, queued.jobId), { recursive: true, force: true })
  await fs.rm(path.join(TOOLKIT_ROOT, "jobs", "_test-adobe-queue"), { recursive: true, force: true })
})

test("Adobe overwrite requires an explicit confirmation", async () => {
  await assert.rejects(
    enqueueAdobe({
      app: "illustrator",
      operation: "import-svg",
      input: path.join(TOOLKIT_ROOT, "adapters", "blender", "scene.example.json"),
      options: { output: "jobs/_test-adobe-overwrite/output.svg", overwrite: true },
    }),
    /confirmOverwrite=true/,
  )
})

test("Adobe result envelopes close the parent job", async () => {
  const queued = await enqueueAdobe({
    app: "illustrator",
    operation: "import-svg",
    input: path.join(TOOLKIT_ROOT, "adapters", "blender", "scene.example.json"),
  })
  const results = path.join(JOBS_ROOT, queued.jobId, "adobe", "results")
  await fs.mkdir(results, { recursive: true })
  await fs.writeFile(path.join(results, "result.json"), JSON.stringify({ id: "test", app: "illustrator", state: "completed" }), "utf8")
  const status = await adobeStatus(queued.jobId)
  assert.equal(status.results.length, 1)
  assert.equal((await getJob(queued.jobId)).state, "completed")
  await fs.rm(path.join(JOBS_ROOT, queued.jobId), { recursive: true, force: true })
})

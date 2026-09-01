import test from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { imageToSvgPreview } from "../src/orchestrator.mjs"
import { createJob, getJob } from "../src/jobs.mjs"
import { TOOLKIT_ROOT } from "../src/utils.mjs"

test("workflow stages its input inside the isolated job", async () => {
  const fixtureRoot = path.join(TOOLKIT_ROOT, "jobs", "_test-isolation-fixture")
  await fs.rm(fixtureRoot, { recursive: true, force: true })
  await fs.mkdir(fixtureRoot, { recursive: true })
  const source = path.join(fixtureRoot, "source.svg")
  await fs.writeFile(source, '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>\n', "utf8")

  const result = await imageToSvgPreview({ image: source })
  const staged = path.join(result.directory, "input", "source.svg")
  assert.equal((await fs.stat(staged)).isFile(), true)
  const status = await getJob(result.jobId)
  assert.deepEqual(status.inputs, [staged])
  await fs.rm(result.directory, { recursive: true, force: true })
  await fs.rm(fixtureRoot, { recursive: true, force: true })
})

test("job lookup rejects path-like identifiers", async () => {
  const job = await createJob("job-safety", {})
  await assert.rejects(getJob(".."), /Invalid job id/)
  await fs.rm(job.directory, { recursive: true, force: true })
})

test("workflow with Adobe stays waiting until the host consumes its command", async () => {
  const fixtureRoot = path.join(TOOLKIT_ROOT, "jobs", "_test-adobe-state-fixture")
  await fs.rm(fixtureRoot, { recursive: true, force: true })
  await fs.mkdir(fixtureRoot, { recursive: true })
  const source = path.join(fixtureRoot, "source.svg")
  await fs.writeFile(source, '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>\n', "utf8")
  const result = await imageToSvgPreview({ image: source, adobeApp: "illustrator" })
  const status = await getJob(result.jobId)
  assert.equal(status.state, "waiting-for-adobe")
  await fs.rm(result.directory, { recursive: true, force: true })
  await fs.rm(fixtureRoot, { recursive: true, force: true })
})

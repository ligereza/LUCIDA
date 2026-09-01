import fs from "node:fs/promises"
import path from "node:path"
import { audit } from "../audit.mjs"
import { createJob, updateJob } from "../jobs.mjs"
import { assertAllowedInput, assertJobId, ensureDir, resolveOutput, writeJson, readJson, JOBS_ROOT } from "../utils.mjs"

const apps = new Set(["photoshop", "illustrator", "after-effects", "premiere"])
const operations = {
  photoshop: new Set(["import-svg", "separate-objects"]),
  illustrator: new Set(["import-svg"]),
  "after-effects": new Set(["import-svg"]),
  premiere: new Set(["import-media", "create-sequence", "export-sequence"]),
}

export async function enqueueAdobe({ app, operation, input, jobId, options = {} }) {
  if (!apps.has(app)) throw new Error(`Unsupported Adobe app: ${app}`)
  if (!operations[app].has(operation)) throw new Error(`Unsupported ${app} operation: ${operation}`)
  if (options.overwrite && options.confirmOverwrite !== true) {
    throw new Error("Adobe overwrite requires options.confirmOverwrite=true")
  }
  let job
  if (jobId) {
    const safeJobId = assertJobId(jobId)
    const directory = path.join(JOBS_ROOT, safeJobId)
    await readJson(path.join(directory, "status.json"))
    job = { id: safeJobId, directory }
  } else {
    job = await createJob(`adobe-${app}`, { app, operation })
  }
  const commandDir = path.join(job.directory, "adobe", "commands")
  await ensureDir(commandDir)
  const output = options.output ? resolveOutput(options.output, { overwrite: Boolean(options.overwrite) }) : null
  if (output) await ensureDir(path.dirname(output))
  const command = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    jobId: job.id,
    app,
    operation,
    input: input ? assertAllowedInput(input) : null,
    options: {
      ...options,
      output,
    },
    createdAt: new Date().toISOString(),
    state: "queued"
  }
  const file = path.join(commandDir, `${command.id}.json`)
  await writeJson(file, command)
  await audit("adobe.command.queued", { jobId: job.id, commandId: command.id, app, operation })
  return { jobId: job.id, command: file, resultDirectory: path.join(job.directory, "adobe", "results"), status: "queued", note: "A host-specific Adobe script/plugin must consume this command." }
}

export async function adobeStatus(jobId) {
  const safeJobId = assertJobId(jobId)
  const jobDirectory = path.join(JOBS_ROOT, safeJobId)
  const directory = path.join(jobDirectory, "adobe", "results")
  const files = await fs.readdir(directory).catch(() => [])
  const results = []
  for (const file of files.filter((name) => name.endsWith(".json"))) {
    results.push(await readJson(path.join(directory, file)))
  }
  const commandDirectory = path.join(jobDirectory, "adobe", "commands")
  const commandFiles = await fs.readdir(commandDirectory).catch(() => [])
  const resultIds = new Set(results.map((result) => result.id))
  const commands = []
  for (const file of commandFiles.filter((name) => name.endsWith(".json"))) {
    commands.push(await readJson(path.join(commandDirectory, file)))
  }
  const trackedResults = results.some((result) => commands.some((command) => command.id === result.id))
  let queued = 0
  if (results.length === 0 || trackedResults) {
    for (const command of commands) {
      if (command.state === "queued" && !resultIds.has(command.id)) queued += 1
    }
  }
  if (results.length > 0) {
    const desiredState = results.some((result) => result.state === "failed")
      ? "failed"
      : queued > 0
        ? "waiting-for-adobe"
        : "completed"
    const statusFile = path.join(jobDirectory, "status.json")
    const current = await readJson(statusFile)
    if (current.state !== desiredState || !current.adobeResults) {
      await updateJob(safeJobId, { state: desiredState, adobeResults: results, currentTool: null })
    }
  }
  return { jobId: safeJobId, resultDirectory: directory, results, queued }
}

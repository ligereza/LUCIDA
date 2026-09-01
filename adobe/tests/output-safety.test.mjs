import test from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { createSvg } from "../src/tools/svg.mjs"
import { TOOLKIT_ROOT, resolveInput, resolveOutput } from "../src/utils.mjs"

test("file-producing tools reject overwrite unless explicitly enabled", async () => {
  const directory = path.join(TOOLKIT_ROOT, "jobs", "_test-output-safety", "output")
  const output = path.join(directory, "scene.svg")
  await fs.rm(path.join(TOOLKIT_ROOT, "jobs", "_test-output-safety"), { recursive: true, force: true })
  await createSvg({ width: 10, height: 10, elements: [] }, output)
  await assert.rejects(
    createSvg({ width: 10, height: 10, elements: [] }, output),
    /Output already exists/,
  )
  await createSvg({ width: 10, height: 10, elements: [] }, output, { overwrite: true })
  assert.equal(resolveOutput(output, { overwrite: true }), output)
  assert.throws(() => resolveInput("C:\\Windows\\win.ini"), /outside configured roots/)
  await fs.rm(path.join(TOOLKIT_ROOT, "jobs", "_test-output-safety"), { recursive: true, force: true })
})

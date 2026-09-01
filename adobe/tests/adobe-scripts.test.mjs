import test from "node:test"
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { spawn } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = fileURLToPath(new URL("..", import.meta.url))

function checkSyntax(source) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ["--check", "-"], { cwd: root })
    let stderr = ""
    child.stderr.on("data", (chunk) => { stderr += chunk })
    child.on("error", reject)
    child.on("close", (code) => code === 0 ? resolve() : reject(new Error(stderr)))
    readFile(source, "utf8").then((text) => child.stdin.end(text.replace(/^#include .*$/gm, "")), reject)
  })
}

test("Adobe host consumers have valid JavaScript syntax", async () => {
  for (const relative of [
    "adapters/adobe/json-compat.jsxinc",
    "adapters/adobe/illustrator/agent.jsx",
    "adapters/adobe/photoshop/agent.jsx",
    "adapters/adobe/after-effects/agent.jsx",
    "adapters/adobe/photoshop/agent.psjs",
    "adapters/adobe/premiere/agent.jsx",
  ]) {
    await checkSyntax(path.join(root, relative))
  }
  assert.ok(true)
})

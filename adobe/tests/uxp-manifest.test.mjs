import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"
import { validateUxpManifest } from "../src/tools/uxp-manifest.mjs"

const root = fileURLToPath(new URL("..", import.meta.url))

test("Photoshop UXP manifest satisfies the local bridge contract", async () => {
  const manifest = JSON.parse(await fs.readFile(path.join(root, "adobe-context-shelf/photoshop-uxp/manifest.json"), "utf8"))
  assert.deepEqual(validateUxpManifest(manifest), { ok: true, issues: [] })
})

test("Photoshop UXP manifest rejects a missing bridge permission", () => {
  const result = validateUxpManifest({
    manifestVersion: 5,
    main: "index.html",
    host: { app: "PS", minVersion: "23.3.0" },
    requiredPermissions: { localFileSystem: "fullAccess", network: { domains: [] } },
    entrypoints: [{ type: "panel", id: "contextShelf" }],
  })
  assert.equal(result.ok, false)
  assert.ok(result.issues.includes("bridge network permission is missing"))
})

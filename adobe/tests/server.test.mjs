import test from "node:test"
import assert from "node:assert/strict"
import { spawn } from "node:child_process"
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = fileURLToPath(new URL("..", import.meta.url))
const port = 47929
const token = "server-test-token"

async function waitForServer(baseUrl) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/health`, {
        headers: { authorization: `Bearer ${token}` },
      })
      if (response.ok) return
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error("Server did not become ready")
}

test("server enforces bearer auth and allowlisted CORS", async (t) => {
  const baseUrl = `http://127.0.0.1:${port}`
  const child = spawn(process.execPath, ["src/server.mjs"], {
    cwd: root,
    env: {
      ...process.env,
      AGENT_TOOLKIT_PORT: String(port),
      AGENT_TOOLKIT_TOKEN: token,
      AGENT_TOOLKIT_CORS_ORIGINS: "https://arena.ai",
    },
    stdio: "ignore",
  })
  const createdJobIds = []
  t.after(async () => {
    child.kill()
    await Promise.all(createdJobIds.map((id) => fs.rm(path.join(root, "jobs", id), { recursive: true, force: true })))
  })
  await waitForServer(baseUrl)

  const unauthorized = await fetch(`${baseUrl}/health`)
  assert.equal(unauthorized.status, 401)

  const preflight = await fetch(`${baseUrl}/run`, {
    method: "OPTIONS",
    headers: {
      origin: "https://arena.ai",
      "access-control-request-method": "POST",
      "access-control-request-headers": "authorization, content-type",
    },
  })
  assert.equal(preflight.status, 204)
  assert.equal(preflight.headers.get("access-control-allow-origin"), "https://arena.ai")

  const allowed = await fetch(`${baseUrl}/health`, {
    headers: {
      authorization: `Bearer ${token}`,
      origin: "https://arena.ai",
    },
  })
  assert.equal(allowed.status, 200)
  assert.equal(allowed.headers.get("access-control-allow-origin"), "https://arena.ai")

  const card = await fetch(`${baseUrl}/agent-card`, {
    headers: { authorization: `Bearer ${token}` },
  })
  assert.equal(card.status, 200)
  const cardBody = await card.json()
  assert.equal(cardBody.authentication, "Bearer token")
  assert.equal(cardBody.safety.arbitraryShell, false)
  assert.equal(cardBody.safety.maxBodyBytes, 2_000_000)
  assert.ok(cardBody.webTools.includes("svg.particles"))
  assert.ok(cardBody.webTools.includes("asset.search"))
  assert.ok(cardBody.webTools.includes("asset.select"))

  const gdkb = await fetch(`${baseUrl}/run`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify({ tool: "gdkb.normalize", params: { value: "Cocaína" } }),
  })
  assert.equal(gdkb.status, 200)
  assert.equal((await gdkb.json()).normalized, "cocaina")

  const openApi = await fetch(`${baseUrl}/openapi.json`, {
    headers: { authorization: `Bearer ${token}` },
  })
  assert.equal(openApi.status, 200)
  const openApiBody = await openApi.json()
  assert.equal(openApiBody.openapi, "3.1.0")
  assert.equal(openApiBody.components.securitySchemes.bearerAuth.scheme, "bearer")

  const particles = await fetch(`${baseUrl}/run`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify({ tool: "svg.particles", params: { count: 3 } }),
  })
  assert.equal(particles.status, 200)
  const particleBody = await particles.json()
  createdJobIds.push(particleBody.jobId)
  assert.equal(particleBody.result.count, 3)
  assert.equal(particleBody.files.length, 1)

  const createdSvg = await fetch(`${baseUrl}/run`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify({
      tool: "svg.create",
      params: { spec: { width: 32, height: 32, elements: [{ type: "circle", cx: 16, cy: 16, r: 8 }] } },
    }),
  })
  assert.equal(createdSvg.status, 200)
  const createdSvgBody = await createdSvg.json()
  createdJobIds.push(createdSvgBody.jobId)
  assert.equal(createdSvgBody.result.width, 32)
  assert.equal(createdSvgBody.files.length, 1)

  const deniedOrigin = await fetch(`${baseUrl}/health`, {
    headers: {
      authorization: `Bearer ${token}`,
      origin: "https://not-allowed.example",
    },
  })
  assert.equal(deniedOrigin.status, 200)
  assert.equal(deniedOrigin.headers.get("access-control-allow-origin"), null)

  const created = await fetch(`${baseUrl}/jobs`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify({ name: "server-adobe-test", request: {} }),
  })
  assert.equal(created.status, 201)
  const job = await created.json()
  createdJobIds.push(job.id)

  const queued = await fetch(`${baseUrl}/adobe/enqueue`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify({
      app: "premiere",
      operation: "import-media",
      input: path.join(root, "adapters", "blender", "scene.example.json"),
      jobId: job.id,
    }),
  })
  assert.equal(queued.status, 201)
  assert.equal((await queued.json()).status, "queued")

  const adobeStatus = await fetch(`${baseUrl}/jobs/${job.id}/adobe`, {
    headers: { authorization: `Bearer ${token}` },
  })
  assert.equal(adobeStatus.status, 200)
  assert.deepEqual((await adobeStatus.json()).results, [])

  const syncCreated = await fetch(`${baseUrl}/jobs`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify({ name: "server-sync-test", request: {} }),
  })
  assert.equal(syncCreated.status, 201)
  const syncJob = await syncCreated.json()
  createdJobIds.push(syncJob.id)
  const syncResults = path.join(root, "jobs", syncJob.id, "adobe", "results")
  await fs.mkdir(syncResults, { recursive: true })
  await fs.writeFile(path.join(syncResults, "result.json"), JSON.stringify({ id: "sync", app: "illustrator", state: "completed" }))
  await fs.writeFile(path.join(root, "jobs", syncJob.id, "status.json"), JSON.stringify({
    id: syncJob.id,
    name: "server-sync-test",
    state: "waiting-for-adobe",
    files: [],
    errors: [],
  }))
  const syncedJob = await fetch(`${baseUrl}/jobs/${syncJob.id}`, {
    headers: { authorization: `Bearer ${token}` },
  })
  assert.equal(syncedJob.status, 200)
  assert.equal((await syncedJob.json()).state, "completed")

  const oversized = await fetch(`${baseUrl}/run`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: "x".repeat(2_000_001),
  })
  assert.equal(oversized.status, 413)
})

test("server refuses a non-loopback bind without a token", async () => {
  const child = spawn(process.execPath, ["src/server.mjs"], {
    cwd: root,
    env: {
      ...process.env,
      AGENT_TOOLKIT_PORT: "47930",
      AGENT_TOOLKIT_HOST: "0.0.0.0",
      AGENT_TOOLKIT_TOKEN: "",
    },
    stdio: "ignore",
  })
  const code = await new Promise((resolve) => child.on("close", resolve))
  assert.notEqual(code, 0)
})

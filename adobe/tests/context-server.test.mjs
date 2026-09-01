import test from "node:test"
import assert from "node:assert/strict"
import { spawn } from "node:child_process"

const root = new URL("..", import.meta.url).pathname.replace(/^\/(\w):/, "$1:").replace(/\//g, "\\")
const port = 47931
const token = "context-server-test-token"
const headers = { authorization: `Bearer ${token}`, "content-type": "application/json" }

async function waitForServer(baseUrl) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/health`, { headers })
      if (response.ok) return
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error("Context server did not become ready")
}

test("context shelf endpoints publish, claim and complete an insertion", async (t) => {
  const baseUrl = `http://127.0.0.1:${port}`
  const child = spawn(process.execPath, ["src/server.mjs"], {
    cwd: root,
    env: { ...process.env, AGENT_TOOLKIT_PORT: String(port), AGENT_TOOLKIT_TOKEN: token },
    stdio: "ignore",
  })
  t.after(() => child.kill())
  await waitForServer(baseUrl)
  const sessionId = `server-context-${Date.now()}`
  const snapshot = {
    schemaVersion: 1,
    sessionId,
    host: "photoshop",
    document: { id: "doc-1", name: "lamina-03.psd", width: 1080, height: 1440 },
    location: { kind: "slide", index: 3, label: "Contexto" },
    selection: { kind: "text-layer", id: "layer-1", name: "Texto", text: "Contexto y cuidado" },
    layers: [], palette: [], occupiedRegions: [], safeRegions: [],
  }
  const published = await fetch(`${baseUrl}/context`, { method: "POST", headers, body: JSON.stringify(snapshot) })
  assert.equal(published.status, 200)
  const publishedBody = await published.json()
  assert.match(publishedBody.contextHash, /^sha256:/)
  assert.equal(publishedBody.analysis.content.topics.some((topic) => topic.id === "care"), true)

  const current = await fetch(`${baseUrl}/context/current?sessionId=${encodeURIComponent(sessionId)}`, { headers })
  assert.equal(current.status, 200)
  assert.equal((await current.json()).context.sessionId, sessionId)

  const analysis = await fetch(`${baseUrl}/analysis/current?sessionId=${encodeURIComponent(sessionId)}`, { headers })
  assert.equal(analysis.status, 200)
  assert.equal((await analysis.json()).analysis.version, 1)

  const queued = await fetch(`${baseUrl}/insert`, {
    method: "POST",
    headers,
    body: JSON.stringify({ sessionId, asset: { assetId: "iconify:test", provider: "iconify", id: "test:asset" } }),
  })
  assert.equal(queued.status, 201)
  const queuedBody = await queued.json()

  const claimed = await fetch(`${baseUrl}/insert/next?sessionId=${encodeURIComponent(sessionId)}`, { headers })
  assert.equal(claimed.status, 200)
  const claimedBody = await claimed.json()
  assert.equal(claimedBody.request.requestId, queuedBody.requestId)

  const result = await fetch(`${baseUrl}/insert/result`, {
    method: "POST",
    headers,
    body: JSON.stringify({ requestId: queuedBody.requestId, sessionId, state: "completed", data: { inserted: true } }),
  })
  assert.equal(result.status, 200)
  assert.equal((await result.json()).data.inserted, true)
})

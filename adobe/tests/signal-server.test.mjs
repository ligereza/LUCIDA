import test from "node:test"
import assert from "node:assert/strict"
import { spawn } from "node:child_process"
import { fileURLToPath } from "node:url"

const root = fileURLToPath(new URL("..", import.meta.url))
const port = 47933
const token = "signal-server-test-token"
const headers = { authorization: `Bearer ${token}`, "content-type": "application/json" }

async function waitForServer(baseUrl) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/health`, { headers })
      if (response.ok) return
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error("Signal server did not become ready")
}

test("server publishes a signal and exposes the derived surface", async (t) => {
  const baseUrl = `http://127.0.0.1:${port}`
  const child = spawn(process.execPath, ["src/server.mjs"], {
    cwd: root,
    env: { ...process.env, AGENT_TOOLKIT_PORT: String(port), AGENT_TOOLKIT_TOKEN: token },
    stdio: "ignore",
  })
  t.after(() => child.kill())
  await waitForServer(baseUrl)

  const sessionId = `server-signal-${Date.now()}`
  const published = await fetch(`${baseUrl}/signals`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      source: "xio",
      sessionId,
      eventType: "network.peer",
      metadata: { host: "linux", channel: "ethernet", status: "ready" },
      payload: { raw: "must not cross the bridge" },
    }),
  })
  assert.equal(published.status, 200)
  const publishedBody = await published.json()
  assert.equal(publishedBody.signal.source, "xio")
  assert.equal(publishedBody.signal.metadata.host, "linux")
  assert.equal(publishedBody.signal.metadata.raw, undefined)

  const surface = await fetch(`${baseUrl}/surface/current?sessionId=${encodeURIComponent(sessionId)}`, { headers })
  assert.equal(surface.status, 200)
  const surfaceBody = await surface.json()
  assert.equal(surfaceBody.surface.sources.xio.state, "active")
  assert.equal(surfaceBody.surface.safety.proposalOnly, true)
  assert.equal(surfaceBody.surface.safety.hostActions, false)
})

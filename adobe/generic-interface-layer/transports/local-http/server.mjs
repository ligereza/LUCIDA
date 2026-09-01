import http from "node:http"
import { normalizeContext } from "../../core/context/normalize.mjs"
import { analyzeContext } from "../../core/analysis/analyze.mjs"
import { createAction } from "../../core/actions/lifecycle.mjs"
import { assertNoShellPayload } from "../../core/security/policy.mjs"

function send(response, status, body) { response.writeHead(status, { "content-type": "application/json; charset=utf-8" }); response.end(JSON.stringify(body)) }
async function body(request, maxBytes) { let value = "", bytes = 0; for await (const chunk of request) { bytes += Buffer.byteLength(chunk); if (bytes > maxBytes) throw new Error("Request body exceeds limit"); value += chunk }; return value ? JSON.parse(value) : {} }

export function createLocalHttpServer({ host = "127.0.0.1", port = 0, maxBodyBytes = 1_000_000 } = {}) {
  const state = { contexts: new Map(), actions: new Map() }
  const server = http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, `http://${host}:${port}`)
      if (request.method === "GET" && url.pathname === "/health") return send(response, 200, { ok: true, arbitraryShell: false })
      if (request.method === "POST" && url.pathname === "/context") { const context = normalizeContext(await body(request, maxBodyBytes), { source: "local-http" }); const analysis = analyzeContext(context); state.contexts.set(context.contextId, { context, analysis }); return send(response, 200, { context, analysis }) }
      if (request.method === "GET" && url.pathname === "/context/current") { const value = [...state.contexts.values()].at(-1) || null; return send(response, 200, value) }
      if (request.method === "POST" && url.pathname === "/actions") { const input = await body(request, maxBodyBytes); assertNoShellPayload(input.payload || {}); const action = createAction(input); state.actions.set(action.actionId, action); return send(response, 201, { action }) }
      if (request.method === "POST" && url.pathname.startsWith("/actions/") && url.pathname.endsWith("/cancel")) { const actionId = url.pathname.split("/")[2]; const action = state.actions.get(actionId); if (!action) return send(response, 404, { error: "Action not found" }); action.state = "cancelled"; action.cancellation = { reason: "cancelled-by-user" }; return send(response, 200, { action }) }
      return send(response, 404, { error: "Route not found" })
    } catch (error) { return send(response, 400, { error: error.message }) }
  })
  return { server, state, listen() { return new Promise((resolve) => server.listen(port, host, () => resolve(server.address()))) }, close() { return new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())) } }
}

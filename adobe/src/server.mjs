import http from "node:http"
import fs from "node:fs/promises"
import path from "node:path"
import { getJob, createJob } from "./jobs.mjs"
import { adobeStatus, enqueueAdobe } from "./adapters/adobe.mjs"
import { runTool, webToolList, WEB_RUN_TOOLS } from "./dispatcher.mjs"
import { assertAllowedInput, TOOLKIT_ROOT, readJson } from "./utils.mjs"
import { renderPlanner } from "./planner.mjs"
import { extractDocument } from "./tools/document.mjs"
import { integrationScriptingMap, integrationSources, validateIntegration } from "./tools/integration.mjs"
import { claimInsert, contextDiagnostics, currentContext, publishContext, queueAnalysisLayer, queueInsert, recordInsertResult, recommendContext } from "./tools/context.mjs"
import { catalogStats, indexLocalCatalog } from "./tools/local-catalog.mjs"
import { catalogGroupSummary, indexLocalGroups, listCatalogAssets } from "./tools/catalog-groups.mjs"
import { listProjectInventory } from "./tools/project-inventory.mjs"
import { indexMobileClip, installMobileClipModel, mobileClipStatus } from "./tools/mobileclip.mjs"
import { currentSignals, currentSurface, publishSignal, signalDiagnostics } from "./tools/signal-bridge.mjs"
import { loadHostCapabilities } from "./tools/host-capabilities.mjs"

const registry = await readJson(path.join(TOOLKIT_ROOT, "registry.json"))
const hostCapabilities = await loadHostCapabilities()
const config = await readJson(path.join(TOOLKIT_ROOT, "config.local.json")).catch(() => ({ server: {} }))
const host = process.env.AGENT_TOOLKIT_HOST || config.server?.host || "127.0.0.1"
const port = Number(process.env.AGENT_TOOLKIT_PORT || config.server?.port || 47921)
const token = process.env.AGENT_TOOLKIT_TOKEN || ""
const MAX_BODY_BYTES = 2_000_000
if (!token && !["127.0.0.1", "localhost", "::1"].includes(host)) {
  throw new Error("AGENT_TOOLKIT_TOKEN is required when the bridge is not bound to loopback")
}
const corsOrigins = new Set(
  (process.env.AGENT_TOOLKIT_CORS_ORIGINS || "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean),
)

const agentCard = {
  name: "LUCIDA Adobe Local Bridge",
  version: "0.1.0",
  product: "LUCIDA",
  branch: "ADOBE",
  focus: "adobe",
  description: "Local allowlisted bridge for the transparent Adobe companion, context shelf, catalog and explicit host job envelopes.",
  scope: {
    primaryHosts: hostCapabilities.primaryHosts,
    companion: hostCapabilities.companion.surface,
    connectors: Object.fromEntries(Object.entries(hostCapabilities.connectors).map(([id, connector]) => [id, connector.mode])),
    excludedResponsibilities: hostCapabilities.excludedResponsibilities,
    hostActionPolicy: hostCapabilities.companion.actionPolicy,
  },
  authentication: token ? "Bearer token" : "localhost-only; bearer token not configured",
  safety: {
    localhostOnlyByDefault: true,
    bearerRequiredForNonLoopback: true,
    maxBodyBytes: MAX_BODY_BYTES,
    arbitraryShell: false,
    outputOverwrite: false,
  },
  tools: registry.tools.map(({ id, description, status, input, output }) => ({ id, description, status, input, output })),
  webTools: webToolList(),
  workflows: ["workflow.image-to-svg-preview", "workflow.image-to-svg-blender-illustrator"],
  integration: {
    inventory: "integration.sources",
    scriptingMap: "integration.scripting-map",
    validation: "integration.validate",
    guide: "INTEGRATION-GUIDE.md",
  },
  contextShelf: {
    schemaVersion: 1,
    endpoints: ["POST /catalog/index", "GET /catalog/stats", "GET /catalog/groups", "GET /catalog/assets", "GET /catalog/projects", "GET /semantic/status", "POST /semantic/index", "POST /semantic/install", "POST /context", "GET /context/current", "GET /analysis/current", "POST /recommendations", "POST /analysis/layer", "POST /insert", "GET /insert/next", "POST /insert/result", "POST /signals", "GET /signals/current", "GET /surface/current"],
    diagnostics: contextDiagnostics(),
  },
  signalBridge: {
    schemaVersion: 1,
    sources: ["xio", "vizz", "pupila"],
    endpoints: ["POST /signals", "GET /signals/current", "GET /surface/current"],
    diagnostics: signalDiagnostics(),
  },
  adobeOperations: {
    ...Object.fromEntries(Object.entries(hostCapabilities.hosts).map(([id, host]) => [id, host.operations])),
  },
  hostCapabilities: hostCapabilities.hosts,
  capabilitiesContract: "contracts/host-capabilities.json",
}

const openApi = {
  openapi: "3.1.0",
  info: { title: "Agent Toolkit Local Bridge", version: "0.1.0" },
  servers: [{ url: `http://${host}:${port}` }],
  security: [{ bearerAuth: [] }],
  components: { securitySchemes: { bearerAuth: { type: "http", scheme: "bearer" } } },
  paths: {
    "/health": { get: { operationId: "health", responses: { "200": { description: "Bridge health" } } } },
    "/capabilities": { get: { operationId: "capabilities", responses: { "200": { description: "Tool registry" } } } },
    "/agent-card": { get: { operationId: "agentCard", responses: { "200": { description: "Agent manifest" } } } },
    "/integration/sources": { get: { operationId: "integrationSources", responses: { "200": { description: "Local source inventory" } } } },
    "/integration/scripting-map": { get: { operationId: "integrationScriptingMap", responses: { "200": { description: "Cross-application scripting map" } } } },
    "/integration/validate": { get: { operationId: "integrationValidate", responses: { "200": { description: "Integration validation" } } } },
    "/jobs": { post: { operationId: "createJob", responses: { "201": { description: "Created job" } } } },
    "/run": { post: { operationId: "runTool", requestBody: { required: true, content: { "application/json": { schema: { type: "object", required: ["tool"], properties: { tool: { type: "string" }, params: { type: "object" } } } } } }, responses: { "200": { description: "Allowlisted tool result" } } } },
    "/assets/search": { post: { operationId: "assetSearch", description: "Search semantic sources and editable SVG catalogs through the allowlisted asset.search tool.", responses: { "200": { description: "Asset search result" } } } },
    "/assets/fetch": { post: { operationId: "assetFetch", description: "Fetch a selected editable SVG through the allowlisted asset.fetch tool.", responses: { "200": { description: "Fetched SVG" } } } },
    "/assets/select": { post: { operationId: "assetSelect", description: "Download selected SVG assets and write a provenance manifest.", responses: { "200": { description: "Asset manifest" } } } },
    "/catalog/index": { post: { operationId: "catalogIndex", description: "Index local SVG, PNG and image assets for Context Shelf.", responses: { "200": { description: "Catalog summary" } } } },
    "/catalog/stats": { get: { operationId: "catalogStats", description: "Read local Context Shelf catalog statistics.", responses: { "200": { description: "Catalog statistics" } } } },
    "/catalog/groups": { get: { operationId: "catalogGroups", description: "List local catalog groups by size, theme, color, format, aspect and kind.", responses: { "200": { description: "Catalog groups" } } } },
    "/catalog/assets": { get: { operationId: "catalogAssets", description: "Page through local catalog assets, optionally filtered by a group or query.", responses: { "200": { description: "Catalog assets" } } } },
    "/semantic/status": { get: { operationId: "semanticStatus", description: "Read MobileCLIP runtime, checkpoint and semantic index readiness.", responses: { "200": { description: "MobileCLIP status" } } } },
    "/semantic/index": { post: { operationId: "semanticIndex", description: "Generate or incrementally update the local MobileCLIP vector index.", responses: { "200": { description: "MobileCLIP index summary" } } } },
    "/semantic/install": { post: { operationId: "semanticInstall", description: "Download the pinned MobileCLIP checkpoint from the official Apple host after hash verification.", responses: { "200": { description: "MobileCLIP model" } } } },
    "/catalog/projects": { get: { operationId: "catalogProjects", description: "Discover project assets, visual variations, slide groups and layer manifests.", responses: { "200": { description: "Project inventory" } } } },
    "/context": { post: { operationId: "publishContext", description: "Publish a normalized context snapshot from an Adobe host adapter.", responses: { "200": { description: "Context snapshot" } } } },
    "/context/current": { get: { operationId: "currentContext", description: "Read the latest context snapshot for a session or host.", responses: { "200": { description: "Current context" } } } },
    "/analysis/current": { get: { operationId: "currentAnalysis", description: "Read semantic content and blank-area analysis for the latest Adobe context.", responses: { "200": { description: "Context analysis" } } } },
    "/recommendations": { post: { operationId: "recommendContext", description: "Rank visual assets against the latest Adobe context.", responses: { "200": { description: "Asset recommendations" } } } },
    "/analysis/layer": { post: { operationId: "analysisLayer", description: "Generate and queue a separate locked SVG analysis layer for the latest Adobe context.", responses: { "201": { description: "Analysis layer insertion request" } } } },
    "/insert": { post: { operationId: "queueInsert", description: "Queue an allowlisted asset insertion for an Adobe host session.", responses: { "201": { description: "Insert request" } } } },
    "/insert/next": { get: { operationId: "claimInsert", description: "Claim the next insertion for an Adobe host session.", responses: { "200": { description: "Insert request or empty" } } } },
    "/insert/result": { post: { operationId: "recordInsertResult", description: "Record the result of an Adobe host insertion.", responses: { "200": { description: "Insert result" } } } },
    "/signals": { post: { operationId: "publishSignal", description: "Publish a redacted XIO, VIZZ or PUPILA signal without host-side effects.", responses: { "200": { description: "Accepted signal and derived surface" } } } },
    "/signals/current": { get: { operationId: "currentSignals", description: "Read bounded signals for a local session.", responses: { "200": { description: "Signal history" } } } },
    "/surface/current": { get: { operationId: "currentSurface", description: "Read the proposal-only Adobe surface derived from context and external signals.", responses: { "200": { description: "Derived surface" } } } },
    "/jobs/{id}": { get: { operationId: "getJob", parameters: [{ name: "id", in: "path", required: true }], responses: { "200": { description: "Job status" } } } },
    "/jobs/{id}/adobe": { get: { operationId: "adobeStatus", parameters: [{ name: "id", in: "path", required: true }], responses: { "200": { description: "Adobe result envelopes" } } } },
    "/adobe/enqueue": { post: { operationId: "adobeEnqueue", responses: { "201": { description: "Queued Adobe command" } } } },
  },
}

function authorized(request) {
  if (!token) return true
  return request.headers.authorization === `Bearer ${token}`
}

function responseHeaders(request) {
  const origin = request.headers.origin
  if (!origin || !corsOrigins.has(origin)) return { "content-type": "application/json; charset=utf-8" }
  return {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-origin": origin,
    "access-control-allow-headers": "Authorization, Content-Type",
    "access-control-allow-methods": "GET, POST, OPTIONS",
    "access-control-max-age": "600",
    vary: "Origin",
  }
}

function send(response, status, body, request) {
  const payload = status === 204 ? "" : JSON.stringify(body, null, 2)
  response.writeHead(status, responseHeaders(request))
  response.end(payload)
}

function sendHtml(response, status, body) {
  response.writeHead(status, { "content-type": "text/html; charset=utf-8" })
  response.end(body)
}

async function body(request) {
  let value = ""
  let bytes = 0
  for await (const chunk of request) {
    bytes += Buffer.byteLength(chunk)
    if (bytes > MAX_BODY_BYTES) {
      const error = new Error(`Request body exceeds ${MAX_BODY_BYTES} bytes`)
      error.statusCode = 413
      throw error
    }
    value += chunk
  }
  return value ? JSON.parse(value) : {}
}

const server = http.createServer(async (request, response) => {
  try {
    if (request.method === "OPTIONS") return send(response, 204, {}, request)
    if (!authorized(request)) return send(response, 401, { error: "Unauthorized" }, request)
    const url = new URL(request.url, `http://${host}:${port}`)
    if (request.method === "GET" && url.pathname === "/health") return send(response, 200, { ok: true, service: "lucida-adobe", apiVersion: 1, branch: "ADOBE", focus: "adobe", host, port, capabilities: ["catalog/projects", "signal-surface"] }, request)
    if (request.method === "GET" && url.pathname === "/capabilities") return send(response, 200, registry, request)
    if (request.method === "GET" && url.pathname === "/agent-card") return send(response, 200, agentCard, request)
    if (request.method === "GET" && url.pathname === "/integration/sources") return send(response, 200, await integrationSources(), request)
    if (request.method === "GET" && url.pathname === "/integration/scripting-map") return send(response, 200, await integrationScriptingMap(), request)
    if (request.method === "GET" && url.pathname === "/integration/validate") return send(response, 200, await validateIntegration(), request)
    if (request.method === "GET" && url.pathname === "/openapi.json") return send(response, 200, openApi, request)
    if (request.method === "POST" && url.pathname === "/catalog/index") {
      const payload = await body(request)
      const catalog = await indexLocalCatalog(payload)
      const groups = await indexLocalGroups(payload)
      return send(response, 200, { ...catalog, groups }, request)
    }
    if (request.method === "GET" && url.pathname === "/semantic/status") return send(response, 200, await mobileClipStatus({ modelName: url.searchParams.get("model") || "mobileclip_s2" }), request)
    if (request.method === "POST" && url.pathname === "/semantic/index") {
      const payload = await body(request)
      return send(response, 200, await indexMobileClip(payload), request)
    }
    if (request.method === "POST" && url.pathname === "/semantic/install") {
      const payload = await body(request)
      return send(response, 200, await installMobileClipModel({ modelName: payload.modelName || "mobileclip_s2", force: payload.force === true }), request)
    }
    if (request.method === "GET" && url.pathname === "/catalog/stats") return send(response, 200, await catalogStats(), request)
    if (request.method === "GET" && url.pathname === "/catalog/groups") return send(response, 200, await catalogGroupSummary({ refresh: url.searchParams.get("refresh") === "true" }), request)
    if (request.method === "GET" && url.pathname === "/catalog/assets") return send(response, 200, await listCatalogAssets({
      type: url.searchParams.get("type"), key: url.searchParams.get("key"), query: url.searchParams.get("query") || "",
      assetIds: url.searchParams.get("ids") || "",
      page: url.searchParams.get("page"), pageSize: url.searchParams.get("pageSize"),
      semantic: url.searchParams.get("semantic") === "true",
    }), request)
    if (request.method === "GET" && url.pathname === "/catalog/projects") return send(response, 200, await listProjectInventory({
      projectId: url.searchParams.get("projectId"),
      refresh: url.searchParams.get("refresh") === "true",
    }), request)
    if (request.method === "POST" && url.pathname === "/context") {
      const payload = await body(request)
      return send(response, 200, publishContext(payload), request)
    }
    if (request.method === "GET" && url.pathname === "/context/current") {
      const value = currentContext({ sessionId: url.searchParams.get("sessionId"), host: url.searchParams.get("host") })
      return send(response, 200, { context: value, diagnostics: contextDiagnostics() }, request)
    }
    if (request.method === "GET" && url.pathname === "/analysis/current") {
      const value = currentContext({ sessionId: url.searchParams.get("sessionId"), host: url.searchParams.get("host") })
      return send(response, 200, { contextHash: value?.contextHash || null, analysis: value?.analysis || null }, request)
    }
    if (request.method === "POST" && url.pathname === "/recommendations") {
      const payload = await body(request)
      return send(response, 200, await recommendContext(payload), request)
    }
    if (request.method === "POST" && url.pathname === "/analysis/layer") {
      const payload = await body(request)
      return send(response, 201, await queueAnalysisLayer(payload), request)
    }
    if (request.method === "POST" && url.pathname === "/insert") {
      const payload = await body(request)
      return send(response, 201, queueInsert(payload), request)
    }
    if (request.method === "GET" && url.pathname === "/insert/next") {
      const requestValue = claimInsert(url.searchParams.get("sessionId"))
      return send(response, 200, { request: requestValue }, request)
    }
    if (request.method === "POST" && url.pathname === "/insert/result") {
      const payload = await body(request)
      return send(response, 200, recordInsertResult(payload), request)
    }
    if (request.method === "POST" && url.pathname === "/signals") {
      const payload = await body(request)
      return send(response, 200, publishSignal(payload), request)
    }
    if (request.method === "GET" && url.pathname === "/signals/current") {
      return send(response, 200, currentSignals({ sessionId: url.searchParams.get("sessionId"), limit: url.searchParams.get("limit") }), request)
    }
    if (request.method === "GET" && url.pathname === "/surface/current") {
      const context = currentContext({ sessionId: url.searchParams.get("sessionId"), host: url.searchParams.get("host") })
      return send(response, 200, { surface: currentSurface({ sessionId: url.searchParams.get("sessionId"), context }) }, request)
    }
    if (request.method === "GET" && url.pathname === "/planner") {
      const document = url.searchParams.get("document") || ""
      if (!document) return sendHtml(response, 200, renderPlanner())
      const extracted = await extractDocument(document)
      return sendHtml(response, 200, renderPlanner({ document, title: path.basename(extracted.source, path.extname(extracted.source)), pages: extracted.pages }))
    }
    if (request.method === "POST" && url.pathname === "/adobe/enqueue") {
      const payload = await body(request)
      return send(response, 201, await enqueueAdobe(payload), request)
    }
    if (request.method === "POST" && url.pathname === "/jobs") {
      const payload = await body(request)
      return send(response, 201, await createJob(payload.name || "agent-job", payload.request || {}), request)
    }
    if (request.method === "POST" && ["/assets/search", "/assets/fetch", "/assets/select"].includes(url.pathname)) {
      const payload = await body(request)
      const tool = { "/assets/search": "asset.search", "/assets/fetch": "asset.fetch", "/assets/select": "asset.select" }[url.pathname]
      if (payload.selectionPath) assertAllowedInput(payload.selectionPath, [...(config.allowedInputRoots || []), "C:\\IA\\flujo", "C:\\Users\\issvk\\claude_sesiones_recuperadas"])
      return send(response, 200, await runTool(tool, payload), request)
    }
    if (request.method === "POST" && url.pathname === "/run") {
      const payload = await body(request)
      if (!WEB_RUN_TOOLS.has(payload.tool)) return send(response, 400, { error: `Tool is not enabled for web execution: ${payload.tool}` }, request)
      if (payload.params?.image) assertAllowedInput(payload.params.image, config.allowedInputRoots)
      if (payload.params?.document) assertAllowedInput(payload.params.document, [...(config.allowedInputRoots || []), "C:\\IA\\flujo", "C:\\Users\\issvk\\claude_sesiones_recuperadas"])
      if (payload.params?.designPath) assertAllowedInput(payload.params.designPath, [...(config.allowedInputRoots || []), "C:\\IA\\flujo", "C:\\Users\\issvk\\claude_sesiones_recuperadas"])
      if (payload.params?.selectionPath) assertAllowedInput(payload.params.selectionPath, [...(config.allowedInputRoots || []), "C:\\IA\\flujo", "C:\\Users\\issvk\\claude_sesiones_recuperadas"])
      if (payload.tool?.startsWith("gdkb.") && payload.params?.input) assertAllowedInput(payload.params.input, config.allowedInputRoots)
      return send(response, 200, await runTool(payload.tool, payload.params || {}), request)
    }
    const match = url.pathname.match(/^\/jobs\/([^/]+)$/)
    const adobeMatch = url.pathname.match(/^\/jobs\/([^/]+)\/adobe$/)
    if (request.method === "GET" && adobeMatch) return send(response, 200, await adobeStatus(adobeMatch[1]), request)
    if (request.method === "GET" && match) {
      let job = await getJob(match[1])
      if (job.state === "waiting-for-adobe") {
        await adobeStatus(match[1])
        job = await getJob(match[1])
      }
      return send(response, 200, job, request)
    }
    send(response, 404, { error: "Not found" }, request)
  } catch (error) {
    send(response, error.statusCode || 500, { error: error.message }, request)
  }
})

server.listen(port, host, () => console.log(`Agent Toolkit listening on http://${host}:${port}`))

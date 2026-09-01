import assert from "node:assert/strict"
import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import test from "node:test"
import { normalizeContext, contextCompleteness } from "../core/context/normalize.mjs"
import { analyzeContext } from "../core/analysis/analyze.mjs"
import { rankProposals } from "../core/proposals/rank.mjs"
import { authorizeAction, cancelAction, createAction, rollbackAction, startAction } from "../core/actions/lifecycle.mjs"
import { appendAuditEvent, verifyAuditChain } from "../core/audit/chain.mjs"
import { replaySession } from "../core/replay/session.mjs"
import { assertAllowedPath, assertNoShellPayload, assertPermission, createSecurityPolicy } from "../core/security/policy.mjs"
import { createJob, getJob, cancelJob } from "../core/jobs/job-store.mjs"
import { searchText } from "../providers/text-search/search.mjs"
import { createSemanticSearchProvider } from "../providers/semantic-search/provider.mjs"
import { createCompanionState, reduceCompanionState } from "../clients/companion/view-model.mjs"
import { acceptPluginMessage } from "../transports/plugin-bridge/bridge.mjs"
import { createLocalHttpServer } from "../transports/local-http/server.mjs"
import fixtureContext from "../fixtures/context-incomplete.json" with { type: "json" }
import fixtureSession from "../fixtures/session.json" with { type: "json" }
import fixtureAssets from "../fixtures/assets.json" with { type: "json" }

test("contexto incompleto conserva null y la razón de cada dato ausente", () => {
  const context = normalizeContext(fixtureContext)
  assert.equal(context.host, null)
  assert.equal(context.document.path, null)
  assert.equal(context.unknown.host.reason, "not-provided-by-source")
  assert.equal(context.unknown["document.path"].value, null)
  assert.match(context.contextHash, /^sha256:/)
  assert.equal(normalizeContext(fixtureContext).contextHash, context.contextHash)
  assert.equal(contextCompleteness(context).complete, false)
})

test("análisis local detecta términos, ocupación y espacios libres", () => {
  const context = normalizeContext(fixtureContext)
  const analysis = analyzeContext(context, { vocabulary: ["composition"] })
  assert.equal(analysis.source, "deterministic-local")
  assert.ok(analysis.content.visualTerms.includes("composition"))
  assert.ok(analysis.layout.blankAreas.length > 0)
  assert.ok(analysis.layout.placementCandidates.length > 0)
})

test("propuestas se ordenan de forma determinista sin ejecutar acciones", () => {
  const context = normalizeContext(fixtureContext)
  const analysis = analyzeContext(context)
  const first = rankProposals({ candidates: fixtureAssets, context, analysis, query: "signal orange", limit: 2 })
  const second = rankProposals({ candidates: fixtureAssets, context, analysis, query: "signal orange", limit: 2 })
  assert.deepEqual(first, second)
  assert.equal(first[0].state, "proposed")
})

test("acción exige autorización explícita, permite cancelación y rollback sólo si está declarado", () => {
  const proposed = createAction({ type: "asset.insert", idempotencyKey: "demo-1", permissions: ["asset.read", "document.write"], destination: { kind: "host", id: "demo" }, rollback: { supported: true, token: "undo-demo" } })
  assert.throws(() => authorizeAction(proposed, { confirmed: false, actor: "user" }), /Explicit confirmation/)
  const authorized = authorizeAction(proposed, { confirmed: true, actor: "user", at: "2026-01-01T00:00:00.000Z" })
  const running = startAction(authorized, { at: "2026-01-01T00:00:01.000Z" })
  const cancelled = cancelAction(running, { actor: "user", at: "2026-01-01T00:00:02.000Z" })
  assert.equal(cancelled.state, "cancelled")
  assert.throws(() => rollbackAction(cancelled), /Only completed/)
})

test("permiso denegado y payload shell se rechazan", () => {
  const action = createAction({ type: "asset.insert", permissions: ["asset.read"], payload: {} })
  assert.throws(() => assertPermission(action, "document.write"), /Permission denied/)
  assert.throws(() => assertNoShellPayload({ command: "dir" }), /Arbitrary shell/)
  assert.throws(() => assertNoShellPayload({ nested: { executable: "cmd.exe" } }), /Arbitrary shell/)
})

test("política de rutas excluye fuentes sensibles y escapes", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gil-policy-"))
  const policy = createSecurityPolicy({ inputRoots: [root], outputRoots: [root], deniedPatterns: ["secret"] })
  assert.equal(assertAllowedPath(path.join(root, "safe.svg"), policy.inputRoots, policy), path.join(root, "safe.svg"))
  assert.throws(() => assertAllowedPath(path.join(root, "secret", "data.json"), policy.inputRoots, policy), /denied/)
  assert.throws(() => assertAllowedPath(path.join(root, "..", "outside.svg"), policy.inputRoots, policy), /outside/)
})

test("audit chain y replay son verificables y reproducibles", () => {
  let events = []
  for (const raw of fixtureSession) events = appendAuditEvent(events, raw)
  assert.equal(verifyAuditChain(events).valid, true)
  const first = replaySession(events)
  const second = replaySession(events)
  assert.equal(first.sessionHash, second.sessionHash)
  assert.equal(first.actions["action-demo"].state, "cancelled")
})

test("jobs quedan aislados y la cancelación no borra el trabajo", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gil-jobs-"))
  const created = await createJob({ root, name: "offline", request: { safe: true }, idempotencyKey: "job-demo" })
  const cancelled = await cancelJob(root, created.id)
  const loaded = await getJob(root, created.id)
  assert.equal(cancelled.state, "cancelled")
  assert.equal(loaded.state, "cancelled")
  await assert.doesNotReject(fs.access(path.join(created.directory, "request.json")))
})

test("proveedores pesados son opcionales y companion sólo reduce estado", async () => {
  const results = searchText(fixtureAssets, "orange signal")
  assert.equal(results[0].assetId, "asset-orange-wave")
  const semantic = createSemanticSearchProvider()
  assert.equal(semantic.available, false)
  const state = reduceCompanionState(createCompanionState(), { type: "selection.changed", assetIds: ["asset-orange-wave"] })
  assert.deepEqual(state.selection, ["asset-orange-wave"])
})

test("plugin bridge sólo acepta mensajes definidos y normaliza contexto", () => {
  const accepted = acceptPluginMessage({ type: "context.update", context: fixtureContext })
  assert.equal(accepted.context.source, "fixture")
  assert.throws(() => acceptPluginMessage({ type: "shell.execute", command: "dir" }), /allowlisted/)
})

test("HTTP local expone sólo contexto, acciones y cancelación allowlisted", async () => {
  const transport = createLocalHttpServer()
  const address = await transport.listen()
  const base = `http://${address.address}:${address.port}`
  try {
    const health = await fetch(`${base}/health`)
    assert.equal(health.status, 200)
    assert.deepEqual(await health.json(), { ok: true, arbitraryShell: false })

    const contextResponse = await fetch(`${base}/context`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(fixtureContext) })
    assert.equal(contextResponse.status, 200)
    const contextBody = await contextResponse.json()
    assert.equal(contextBody.context.contextId, normalizeContext(fixtureContext, { source: "local-http" }).contextId)

    const actionResponse = await fetch(`${base}/actions`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ type: "asset.insert", payload: { assetId: "asset-orange-wave" } }) })
    assert.equal(actionResponse.status, 201)
    const actionBody = await actionResponse.json()
    const cancelResponse = await fetch(`${base}/actions/${actionBody.action.actionId}/cancel`, { method: "POST" })
    assert.equal((await cancelResponse.json()).action.state, "cancelled")

    const shellResponse = await fetch(`${base}/actions`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ type: "unsafe", payload: { nested: { command: "dir" } } }) })
    assert.equal(shellResponse.status, 400)
    const unknownRoute = await fetch(`${base}/run`, { method: "POST" })
    assert.equal(unknownRoute.status, 404)
  } finally {
    await transport.close()
  }
})

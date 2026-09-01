import assert from "node:assert/strict"
import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import fixtureContext from "../fixtures/context-incomplete.json" with { type: "json" }
import fixtureAssets from "../fixtures/assets.json" with { type: "json" }
import { normalizeContext } from "../core/context/normalize.mjs"
import { analyzeContext } from "../core/analysis/analyze.mjs"
import { rankProposals } from "../core/proposals/rank.mjs"
import { createAction, authorizeAction, startAction, cancelAction } from "../core/actions/lifecycle.mjs"
import { appendAuditEvent, verifyAuditChain } from "../core/audit/chain.mjs"
import { assertNoShellPayload } from "../core/security/policy.mjs"

const context = normalizeContext(fixtureContext)
const analysis = analyzeContext(context)
const proposals = rankProposals({ candidates: fixtureAssets, context, analysis, query: "orange signal" })
assert.ok(context.contextHash && analysis.analysisHash && proposals.length)
let action = createAction({ type: "asset.insert", idempotencyKey: "smoke-1", permissions: ["asset.read"], payload: { assetId: proposals[0].assetId } })
action = authorizeAction(action, { confirmed: true, actor: "smoke", at: "2026-01-01T00:00:00.000Z" })
action = startAction(action, { at: "2026-01-01T00:00:01.000Z" })
action = cancelAction(action, { actor: "smoke", at: "2026-01-01T00:00:02.000Z" })
let events = []
events = appendAuditEvent(events, { type: "context.received", payload: { context, analysis }, timestamp: "2026-01-01T00:00:00.000Z" })
events = appendAuditEvent(events, { type: "action.updated", payload: { action }, timestamp: "2026-01-01T00:00:02.000Z" })
assert.equal(verifyAuditChain(events).valid, true)
assert.throws(() => assertNoShellPayload({ executable: "cmd.exe" }), /Arbitrary shell/)
const temp = await fs.mkdtemp(path.join(os.tmpdir(), "gil-smoke-"))
assert.ok(temp)
console.log(JSON.stringify({ ok: true, contextHash: context.contextHash, proposals: proposals.length, actionState: action.state, auditEvents: events.length, shell: "blocked" }))

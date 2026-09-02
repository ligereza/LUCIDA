import test from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { loadHostCapabilities, validateHostCapabilities } from "../src/tools/host-capabilities.mjs"
import { extractAdapterOperations, validateAdapterParity } from "../src/tools/adapter-parity.mjs"

const root = fileURLToPath(new URL("..", import.meta.url))

test("host capability contract keeps Adobe scope explicit", async () => {
  const contract = JSON.parse(await fs.readFile(path.join(root, "contracts", "host-capabilities.json"), "utf8"))
  assert.equal(contract.product, "LUCIDA")
  assert.equal(contract.branch, "ADOBE")
  assert.equal(contract.focus, "adobe")
  assert.deepEqual(contract.primaryHosts, ["photoshop", "illustrator", "after-effects", "premiere"])
  assert.equal(contract.companion.actionPolicy, "explicit-host-authorization")
  assert.equal(contract.connectors.xio.mode, "signal-only")
  assert.equal(contract.connectors.vizz.mode, "proposal-signal-only")
  assert.equal(contract.connectors.pupila.mode, "proposal-signal-only")
  assert.equal(contract.hosts.photoshop.contextProvider, "photoshop-uxp")
  assert.equal(contract.hosts.photoshop.contextStatus, "prepared-unverified")
  assert.equal(contract.hosts.illustrator.contextProvider, "none")
  assert.equal(contract.hosts["after-effects"].contextProvider, "none")
  assert.equal(contract.hosts.premiere.contextProvider, "none")
  assert.ok(contract.excludedResponsibilities.includes("resolume-control"))
  assert.ok(contract.excludedResponsibilities.includes("multi-device-transport"))
  assert.ok(contract.excludedResponsibilities.includes("source-project-migration"))
  assert.deepEqual(validateHostCapabilities(contract), { ok: true, issues: [] })
  assert.deepEqual((await loadHostCapabilities()).primaryHosts, contract.primaryHosts)
})

test("host capability validator rejects a cross-branch contract", () => {
  const result = validateHostCapabilities({ schemaVersion: 1, product: "LUCIDA", branch: "RESOLUME", focus: "resolume" })
  assert.equal(result.ok, false)
  assert.ok(result.issues.some((issue) => issue.startsWith("branch:")))
  assert.ok(result.issues.some((issue) => issue.startsWith("hosts:")))
})

test("host capability validator ignores harmless JSON ordering", async () => {
  const contract = await loadHostCapabilities()
  const reordered = {
    ...contract,
    primaryHosts: [...contract.primaryHosts].reverse(),
    hosts: Object.fromEntries(Object.entries(contract.hosts).reverse()),
  }
  assert.deepEqual(validateHostCapabilities(reordered), { ok: true, issues: [] })
})

test("Adobe adapter dispatches stay in parity with the host capability contract", async () => {
  const contract = await loadHostCapabilities()
  const result = await validateAdapterParity(contract)
  assert.equal(result.ok, true, result.issues.join("; "))
  assert.deepEqual(result.hosts.photoshop.declaredOperations, ["import-svg", "separate-objects"])
  assert.deepEqual(result.hosts.photoshop.adapters.map((adapter) => adapter.implementedOperations), [
    ["import-svg", "separate-objects"],
    ["import-svg", "separate-objects"],
  ])
})

test("adapter parity rejects a declared operation missing from a host consumer", async () => {
  const contract = await loadHostCapabilities()
  const broken = {
    ...contract,
    hosts: {
      ...contract.hosts,
      illustrator: { ...contract.hosts.illustrator, operations: ["import-svg", "missing-operation"] },
    },
  }
  const result = await validateAdapterParity(broken)
  assert.equal(result.ok, false)
  assert.ok(result.issues.some((issue) => issue.includes("illustrator\\agent.jsx") && issue.includes("missing-operation")))
})

test("adapter operation extraction returns unique sorted dispatch names", () => {
  assert.deepEqual(extractAdapterOperations("command.operation === 'z'; command.operation === 'a'; command.operation === 'z';"), ["a", "z"])
})

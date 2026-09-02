import test from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

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
})

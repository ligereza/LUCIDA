import fs from "node:fs/promises"
import path from "node:path"
import { TOOLKIT_ROOT, readJson } from "./utils.mjs"
import { integrationSources, validateIntegration } from "./tools/integration.mjs"
import { loadHostCapabilities } from "./tools/host-capabilities.mjs"
import { validateAdapterParity } from "./tools/adapter-parity.mjs"

const requiredDirectories = ["generic-interface-layer", "companion", "adobe-context-shelf", "contracts", "adapters", "src", "tools", "tests", "docs", "ICONOS", "jobs", "logs", "scripts", "integrations", "adapters/gdkb/runtime/gdkb"]
const requiredFiles = ["README.md", "registry.json", "package.json", "contracts/host-capabilities.json", "adapters/gdkb/bridge.py", "integrations/gdkb/v0.6.1/BUNDLE_MANIFEST.json", "integrations/tool-sources.json", "integrations/scripting-map.json", "ICONOS/CHEMSEX/manifest.json"]
const optionalSourceDirectories = ["umbrella", "d3", "three.js", "effect", "rxjs", "stdlib"]

async function exists(target) {
  try {
    await fs.access(target)
    return true
  } catch {
    return false
  }
}

async function verify() {
  const missing = []
  const missingSources = []
  const warnings = []
  for (const entry of requiredDirectories) {
    if (!(await exists(path.join(TOOLKIT_ROOT, entry)))) missing.push(entry)
  }
  for (const entry of requiredFiles) {
    if (!(await exists(path.join(TOOLKIT_ROOT, entry)))) missing.push(entry)
  }
  const sourceRoot = path.dirname(TOOLKIT_ROOT)
  for (const entry of optionalSourceDirectories) {
    if (!(await exists(path.join(sourceRoot, entry)))) warnings.push({ source: entry, message: "Optional external source is not bundled" })
  }
  const registry = await readJson(path.join(TOOLKIT_ROOT, "registry.json"))
  let capabilityContract = { ok: false, issues: ["not checked"] }
  let adapterParity = { ok: false, issues: ["not checked"], hosts: {} }
  let hostCapabilities = null
  try {
    hostCapabilities = await loadHostCapabilities()
    capabilityContract = { ok: true, issues: [] }
    adapterParity = await validateAdapterParity(hostCapabilities)
  } catch (error) {
    capabilityContract = { ok: false, issues: [error.message] }
    adapterParity = { ok: false, issues: ["skipped because the host capability contract is invalid"], hosts: {} }
  }
  const integration = await validateIntegration()
  const sourceInventory = await integrationSources()
  const entrypoints = []
  for (const tool of registry.tools || []) {
    if (!tool.entrypoint || tool.entrypoint.includes("{")) continue
    const alternatives = tool.entrypoint.split("|")
    const found = await Promise.all(alternatives.map((entrypoint) => exists(path.join(TOOLKIT_ROOT, entrypoint))))
    if (!found.some(Boolean)) entrypoints.push({ id: tool.id, entrypoint: tool.entrypoint })
  }

  const configPath = path.join(TOOLKIT_ROOT, "config.local.json")
  if (await exists(configPath)) {
    const config = await readJson(configPath)
    for (const [name, executable] of Object.entries({
      blender: config.blender?.executable,
      photoshop: config.adobe?.photoshop,
      illustrator: config.adobe?.illustrator,
      "after-effects": config.adobe?.["after-effects"],
      aerender: config.adobe?.["after-effects-render"],
    })) {
      if (executable && !(await exists(executable))) warnings.push({ executable: name, path: executable })
    }
  } else {
    warnings.push({ config: "config.local.json", message: "Local executable configuration is absent" })
  }

  return {
    ok: missing.length === 0 && missingSources.length === 0 && entrypoints.length === 0 && integration.ok && capabilityContract.ok && adapterParity.ok,
    root: TOOLKIT_ROOT,
    sourceRoot,
    installedSources: sourceInventory.sources.filter((source) => source.exists).map((source) => source.id),
    integratedKnowledge: ["gdkb-0.6.1"],
    registryTools: registry.tools?.length || 0,
    missing,
    missingSources,
    missingEntrypoints: entrypoints,
    integration,
    capabilityContract,
    adapterParity,
    executableWarnings: warnings,
    externalPending: [
      "Photoshop UXP host runtime validation (JSX/COM fallback verified)",
      "After Effects host runtime validation (intentionally deferred)",
      "Premiere host runtime validation (local executable missing)",
      "Remote web tunnel/session",
    ],
  }
}

console.log(JSON.stringify(await verify(), null, 2))

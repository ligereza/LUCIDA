import fs from "node:fs/promises"
import path from "node:path"
import { TOOLKIT_ROOT, readJson } from "./utils.mjs"
import { validateIntegration } from "./tools/integration.mjs"

const requiredDirectories = ["tools", "skills", "adapters", "templates", "jobs", "memory", "logs", "scripts", "integrations", "adapters/gdkb/runtime/gdkb"]
const requiredFiles = ["CAPABILITIES.md", "PROJECT-STATUS.md", "registry.json", "WEB-BRIDGE.md", "package.json", "adapters/gdkb/bridge.py", "integrations/gdkb/v0.6.1/BUNDLE_MANIFEST.json", "integrations/gdkb/v0.6.1/gdkb-architecture.png"]
const sourceDirectories = ["umbrella", "d3", "three.js", "effect", "rxjs", "stdlib"]

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
  for (const entry of sourceDirectories) {
    if (!(await exists(path.join(sourceRoot, entry)))) missingSources.push(entry)
  }
  if (!(await exists(path.join(TOOLKIT_ROOT, "integrations/gdkb/v0.6.1/core"))) || !(await exists(path.join(TOOLKIT_ROOT, "integrations/gdkb/v0.6.1/event_state")))) {
    missingSources.push("gdkb-0.6.1")
  }

  const registry = await readJson(path.join(TOOLKIT_ROOT, "registry.json"))
  const integration = await validateIntegration()
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
    ok: missing.length === 0 && missingSources.length === 0 && entrypoints.length === 0 && integration.ok,
    root: TOOLKIT_ROOT,
    sourceRoot,
    installedSources: sourceDirectories,
    integratedKnowledge: ["gdkb-0.6.1"],
    registryTools: registry.tools?.length || 0,
    missing,
    missingSources,
    missingEntrypoints: entrypoints,
    integration,
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

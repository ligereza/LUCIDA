import path from "node:path"
import { TOOLKIT_ROOT, readJson } from "../utils.mjs"

export const HOST_CAPABILITIES_PATH = path.join(TOOLKIT_ROOT, "contracts", "host-capabilities.json")

const REQUIRED_HOSTS = ["photoshop", "illustrator", "after-effects", "premiere"]
const REQUIRED_CONNECTORS = ["xio", "vizz", "pupila"]
const REQUIRED_EXCLUSIONS = ["resolume-control", "multi-device-transport", "source-project-migration"]
const SUPPORTED_ADAPTER_KINDS = ["jsx", "uxp"]

function addIssue(issues, field, message) {
  issues.push(`${field}: ${message}`)
}

function hasExactlyMembers(value, expected) {
  return Array.isArray(value)
    && value.length === expected.length
    && new Set(value).size === expected.length
    && [...value].sort().join("\u0000") === [...expected].sort().join("\u0000")
}

export function validateHostCapabilities(contract) {
  const issues = []
  if (!contract || typeof contract !== "object" || Array.isArray(contract)) {
    return { ok: false, issues: ["contract: expected an object"] }
  }
  if (contract.schemaVersion !== 1) addIssue(issues, "schemaVersion", "must be 1")
  if (contract.product !== "LUCIDA") addIssue(issues, "product", "must be LUCIDA")
  if (contract.branch !== "ADOBE") addIssue(issues, "branch", "must be ADOBE")
  if (contract.focus !== "adobe") addIssue(issues, "focus", "must be adobe")

  if (!hasExactlyMembers(contract.primaryHosts, REQUIRED_HOSTS)) {
    addIssue(issues, "primaryHosts", `must equal ${REQUIRED_HOSTS.join(",")}`)
  }
  const hosts = contract.hosts && typeof contract.hosts === "object" && !Array.isArray(contract.hosts) ? contract.hosts : {}
  if (!hasExactlyMembers(Object.keys(hosts), REQUIRED_HOSTS)) {
    addIssue(issues, "hosts", `must define ${REQUIRED_HOSTS.join(",")}`)
  }
  for (const hostName of REQUIRED_HOSTS) {
    const host = hosts[hostName]
    if (!host || typeof host !== "object" || Array.isArray(host)) {
      addIssue(issues, `hosts.${hostName}`, "must be an object")
      continue
    }
    if (!Array.isArray(host.operations) || host.operations.length === 0 || host.operations.some((operation) => typeof operation !== "string" || operation.length === 0)) {
      addIssue(issues, `hosts.${hostName}.operations`, "must contain non-empty strings")
    }
    if (new Set(host.operations || []).size !== (host.operations || []).length) {
      addIssue(issues, `hosts.${hostName}.operations`, "must not contain duplicates")
    }
    if (!Array.isArray(host.adapterKinds) || host.adapterKinds.length === 0 || host.adapterKinds.some((kind) => !SUPPORTED_ADAPTER_KINDS.includes(kind))) {
      addIssue(issues, `hosts.${hostName}.adapterKinds`, `must contain supported kinds: ${SUPPORTED_ADAPTER_KINDS.join(",")}`)
    }
    if (new Set(host.adapterKinds || []).size !== (host.adapterKinds || []).length) {
      addIssue(issues, `hosts.${hostName}.adapterKinds`, "must not contain duplicates")
    }
    if (typeof host.contextProvider !== "string" || typeof host.contextStatus !== "string" || typeof host.runtimeStatus !== "string") {
      addIssue(issues, `hosts.${hostName}`, "must declare contextProvider, contextStatus and runtimeStatus")
    }
  }

  const connectors = contract.connectors && typeof contract.connectors === "object" && !Array.isArray(contract.connectors) ? contract.connectors : {}
  if (Object.keys(connectors).sort().join("\u0000") !== [...REQUIRED_CONNECTORS].sort().join("\u0000")) {
    addIssue(issues, "connectors", `must define ${REQUIRED_CONNECTORS.join(",")}`)
  }
  for (const connectorName of REQUIRED_CONNECTORS) {
    const connector = connectors[connectorName]
    if (!connector || connector.direction !== "input" || typeof connector.mode !== "string" || !Array.isArray(connector.signalFamilies)) {
      addIssue(issues, `connectors.${connectorName}`, "must be an input with a mode and signalFamilies")
    }
  }
  if (connectors.vizz?.mode !== "proposal-signal-only" || connectors.pupila?.mode !== "proposal-signal-only") {
    addIssue(issues, "connectors", "vizz and pupila must remain proposal-signal-only")
  }

  if (contract.companion?.actionPolicy !== "explicit-host-authorization") {
    addIssue(issues, "companion.actionPolicy", "must require explicit host authorization")
  }
  const exclusions = Array.isArray(contract.excludedResponsibilities) ? contract.excludedResponsibilities : []
  for (const exclusion of REQUIRED_EXCLUSIONS) {
    if (!exclusions.includes(exclusion)) addIssue(issues, "excludedResponsibilities", `missing ${exclusion}`)
  }
  return { ok: issues.length === 0, issues }
}

export async function loadHostCapabilities() {
  const contract = await readJson(HOST_CAPABILITIES_PATH)
  const validation = validateHostCapabilities(contract)
  if (!validation.ok) throw new Error(`Invalid Adobe host capability contract: ${validation.issues.join("; ")}`)
  return contract
}

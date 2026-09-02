import fs from "node:fs/promises"
import path from "node:path"
import { TOOLKIT_ROOT } from "../utils.mjs"

export const ADAPTER_FILES = Object.freeze({ jsx: "agent.jsx", uxp: "agent.psjs" })

// This is a static dispatch audit. It verifies that the operation names exposed
// by the contract are present in the host consumer; it does not claim that an
// Adobe installation executed the operation successfully.
const OPERATION_DISPATCH_PATTERN = /(?:selectedCommand|next\.command|command)\.operation\s*===\s*["']([^"']+)["']/g

export function extractAdapterOperations(source) {
  const operations = new Set()
  for (const match of String(source).matchAll(OPERATION_DISPATCH_PATTERN)) operations.add(match[1])
  return [...operations].sort()
}

export function adapterRelativePath(hostName, adapterKind) {
  const filename = ADAPTER_FILES[adapterKind]
  if (!filename) return null
  return path.join("adapters", "adobe", hostName, filename)
}

function difference(left, right) {
  const rightSet = new Set(right)
  return left.filter((value) => !rightSet.has(value))
}

export async function validateAdapterParity(contract, toolkitRoot = TOOLKIT_ROOT) {
  const issues = []
  const hosts = {}
  for (const [hostName, host] of Object.entries(contract?.hosts || {})) {
    const declaredOperations = [...new Set(Array.isArray(host?.operations) ? host.operations : [])].sort()
    const adapterKinds = Array.isArray(host?.adapterKinds) ? host.adapterKinds : []
    const adapters = []
    for (const adapterKind of adapterKinds) {
      const relativePath = adapterRelativePath(hostName, adapterKind)
      if (!relativePath) {
        issues.push(`hosts.${hostName}.adapterKinds: unsupported adapter kind ${adapterKind}`)
        continue
      }
      const absolutePath = path.join(toolkitRoot, relativePath)
      try {
        const source = await fs.readFile(absolutePath, "utf8")
        const implementedOperations = extractAdapterOperations(source)
        const missingOperations = difference(declaredOperations, implementedOperations)
        const undeclaredOperations = difference(implementedOperations, declaredOperations)
        if (missingOperations.length) issues.push(`${relativePath}: missing declared operations ${missingOperations.join(",")}`)
        if (undeclaredOperations.length) issues.push(`${relativePath}: dispatches undeclared operations ${undeclaredOperations.join(",")}`)
        adapters.push({ adapterKind, path: relativePath, exists: true, implementedOperations, missingOperations, undeclaredOperations })
      } catch (error) {
        issues.push(`${relativePath}: ${error.code === "ENOENT" ? "file is missing" : error.message}`)
        adapters.push({ adapterKind, path: relativePath, exists: false, implementedOperations: [], missingOperations: declaredOperations, undeclaredOperations: [] })
      }
    }
    hosts[hostName] = {
      declaredOperations,
      adapters,
      ok: adapters.length > 0 && adapters.every((adapter) => adapter.exists && adapter.missingOperations.length === 0 && adapter.undeclaredOperations.length === 0),
    }
  }
  return { ok: issues.length === 0, issues, hosts }
}

import path from "node:path"

const DEFAULT_DENIED = [".env", "credentials", "secrets", "private", "chemsex", "mak", "rd_database_complete"]

function normalized(value) { return path.resolve(String(value || "")) }
function within(target, root) { const relative = path.relative(normalized(root), target); return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative)) }

export function createSecurityPolicy({ inputRoots = [], outputRoots = [], deniedPatterns = DEFAULT_DENIED } = {}) {
  return { inputRoots: inputRoots.map(normalized), outputRoots: outputRoots.map(normalized), deniedPatterns: deniedPatterns.map((item) => String(item).toLowerCase()) }
}

export function assertAllowedPath(value, roots = [], { deniedPatterns = DEFAULT_DENIED } = {}) {
  const target = normalized(value)
  if (!roots.some((root) => within(target, root))) throw new Error(`Path is outside the allowlist: ${target}`)
  const lower = target.toLowerCase()
  if (deniedPatterns.some((pattern) => lower.split(/[\\/]/).includes(pattern) || lower.includes(`${path.sep}${pattern}${path.sep}`))) throw new Error(`Path is denied by privacy policy: ${target}`)
  return target
}

export function assertNoShellPayload(value, seen = new WeakSet()) {
  if (!value || typeof value !== "object") return true
  if (seen.has(value)) throw new Error("Cyclic shell payloads are not supported")
  seen.add(value)
  const forbidden = new Set(["shell", "command", "executable", "argv", "powershell", "process", "spawn", "exec"])
  for (const [key, nested] of Object.entries(value)) {
    if (forbidden.has(key.toLowerCase())) throw new Error("Arbitrary shell execution is not supported")
    assertNoShellPayload(nested, seen)
  }
  return true
}

export function assertPermission(action, permission) {
  if (!action?.permissions?.includes(permission)) throw new Error(`Permission denied: ${permission}`)
  return true
}

export function checkActionSafety(action, policy, { permission = null, inputPath = null, outputPath = null } = {}) {
  assertNoShellPayload(action?.payload)
  if (permission) assertPermission(action, permission)
  if (inputPath) assertAllowedPath(inputPath, policy.inputRoots, policy)
  if (outputPath) assertAllowedPath(outputPath, policy.outputRoots, policy)
  return { allowed: true, risk: action?.risk?.level || "unknown" }
}

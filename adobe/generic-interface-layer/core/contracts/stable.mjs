import crypto from "node:crypto"

export function stable(value) {
  if (Array.isArray(value)) return value.map(stable)
  if (value && typeof value === "object") {
    return Object.keys(value).sort().reduce((result, key) => {
      result[key] = stable(value[key])
      return result
    }, {})
  }
  return value
}

export function stableStringify(value) {
  return JSON.stringify(stable(value))
}

export function sha256(value) {
  return `sha256:${crypto.createHash("sha256").update(typeof value === "string" ? value : stableStringify(value)).digest("hex")}`
}

export function deterministicId(prefix, value) {
  return `${prefix}-${sha256(value).slice("sha256:".length, 24)}`
}

export function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value))
}

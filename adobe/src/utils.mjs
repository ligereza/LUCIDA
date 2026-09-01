import fs from "node:fs/promises"
import { existsSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

export const TOOLKIT_ROOT = path.resolve(fileURLToPath(new URL("..", import.meta.url)))
export const JOBS_ROOT = path.join(TOOLKIT_ROOT, "jobs")
export const DEFAULT_INPUT_ROOTS = [TOOLKIT_ROOT, "C:\\IA\\svg", "C:\\Users\\issvk\\Downloads"]

function normalizeInput(value) {
  if (!value) throw new Error("Missing input path")
  return path.resolve(value)
}

function isWithinRoots(target, roots) {
  const allowed = roots.some((root) => {
    const relative = path.relative(path.resolve(root), target)
    return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative))
  })
  return allowed
}

export function resolveInput(value, options = {}) {
  const target = normalizeInput(value)
  const roots = options.roots || DEFAULT_INPUT_ROOTS
  if (options.allowOutside !== true && !isWithinRoots(target, roots)) {
    throw new Error(`Input is outside configured roots: ${target}`)
  }
  return target
}

export function assertAllowedInput(value, roots = DEFAULT_INPUT_ROOTS) {
  const target = normalizeInput(value)
  if (!isWithinRoots(target, roots)) throw new Error(`Input is outside configured roots: ${target}`)
  return target
}

export function assertJobId(value) {
  if (!value || !/^[a-z0-9][a-z0-9-]*$/i.test(value)) throw new Error(`Invalid job id: ${value}`)
  return value
}

export function resolveOutput(value, options = {}) {
  if (!value) throw new Error("Missing output path")
  const target = path.isAbsolute(value) ? path.resolve(value) : path.resolve(TOOLKIT_ROOT, value)
  const relative = path.relative(TOOLKIT_ROOT, target)
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`Output must stay inside ${TOOLKIT_ROOT}: ${target}`)
  }
  if (!options.overwrite && existsSync(target)) {
    throw new Error(`Output already exists: ${target}. Set overwrite=true or pass --force to replace it.`)
  }
  return target
}

export async function ensureDir(directory) {
  await fs.mkdir(directory, { recursive: true })
  return directory
}

export async function writeJson(file, value) {
  await ensureDir(path.dirname(file))
  await fs.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8")
}

export async function readJson(file) {
  return JSON.parse(await fs.readFile(file, "utf8"))
}

export function slugify(value) {
  return String(value || "job")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48) || "job"
}

export function nowId(prefix = "job") {
  const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)
  const random = Math.random().toString(36).slice(2, 7)
  return `${slugify(prefix)}-${stamp}-${random}`
}

export function mimeType(file) {
  const ext = path.extname(file).toLowerCase()
  return {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml"
  }[ext] || "application/octet-stream"
}

export function asNumber(value, fallback) {
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

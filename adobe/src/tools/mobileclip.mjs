import fs from "node:fs/promises"
import { existsSync } from "node:fs"
import { createWriteStream } from "node:fs"
import path from "node:path"
import crypto from "node:crypto"
import https from "node:https"
import { spawn } from "node:child_process"
import { fileURLToPath } from "node:url"
import { ensureDir, TOOLKIT_ROOT } from "../utils.mjs"

const MOBILECLIP_ROOT = path.join(TOOLKIT_ROOT, "cache", "context-shelf", "mobileclip")
const DEFAULT_INDEX_PATH = path.join(MOBILECLIP_ROOT, "index.json")
const WORKER_SCRIPT = fileURLToPath(new URL("../../scripts/mobileclip-worker.py", import.meta.url))
const APPLE_MODEL_HOST = "docs-assets.developer.apple.com"

// MobileCLIP v1 is the Apple release that has an official non-Hugging Face
// checkpoint URL. The digest is pinned before a checkpoint is ever loaded.
export const MOBILECLIP_MODELS = Object.freeze({
  mobileclip_s2: Object.freeze({
    name: "mobileclip_s2",
    fileName: "mobileclip_s2.pt",
    url: "https://docs-assets.developer.apple.com/ml-research/datasets/mobileclip/mobileclip_s2.pt",
    bytes: 398067246,
    sha256: "063a87b2a846791bcffafa9f7670ec3968d572a3e7f99e5e4b14348006631d6f",
    repository: "https://github.com/apple/ml-mobileclip",
    license: "Apple ML Research Model Terms of Use",
  }),
})

const DEFAULT_RUNTIME_PYTHON = process.platform === "win32"
  ? path.join(MOBILECLIP_ROOT, ".venv", "Scripts", "python.exe")
  : path.join(MOBILECLIP_ROOT, ".venv", "bin", "python")
const PYTHON = process.env.MOBILECLIP_PYTHON || process.env.PYTHON_EXE || (existsSync(DEFAULT_RUNTIME_PYTHON) ? DEFAULT_RUNTIME_PYTHON : "python")
let workerState = null
let workerSequence = 0
const modelVerificationCache = new Map()
const semanticIndexCache = new Map()

export function closeMobileClipWorker() {
  if (!workerState) return
  const child = workerState.child
  workerState = null
  if (!child.killed) child.kill()
}

function modelSpec(modelName = "mobileclip_s2") {
  const spec = MOBILECLIP_MODELS[modelName]
  if (!spec) throw new Error(`Unsupported MobileCLIP model: ${modelName}`)
  return spec
}

function modelPathFor(modelName = "mobileclip_s2") {
  return path.join(MOBILECLIP_ROOT, modelSpec(modelName).fileName)
}

function repositoryPath() {
  return path.resolve(process.env.MOBILECLIP_REPO || path.join(MOBILECLIP_ROOT, "ml-mobileclip"))
}

function vectorsPathFor(indexPath = DEFAULT_INDEX_PATH) {
  return path.join(path.dirname(path.resolve(indexPath)), "vectors.f32")
}

async function fileSha256(file) {
  const hash = crypto.createHash("sha256")
  const handle = await fs.open(file, "r")
  try {
    for await (const chunk of handle.createReadStream()) hash.update(chunk)
  } finally {
    await handle.close()
  }
  return hash.digest("hex")
}

async function inspectModel(modelName = "mobileclip_s2") {
  const spec = modelSpec(modelName)
  const file = modelPathFor(modelName)
  let stat
  try { stat = await fs.stat(file) } catch { return { present: false, verified: false, file, expectedBytes: spec.bytes, expectedSha256: spec.sha256 } }
  if (!stat.isFile()) return { present: false, verified: false, file, expectedBytes: spec.bytes, expectedSha256: spec.sha256 }
  const cacheKey = `${file}:${stat.size}:${stat.mtimeMs}`
  if (modelVerificationCache.has(cacheKey)) return modelVerificationCache.get(cacheKey)
  if (stat.size !== spec.bytes) {
    const result = { present: true, verified: false, file, bytes: stat.size, expectedBytes: spec.bytes, expectedSha256: spec.sha256, reason: "size-mismatch" }
    modelVerificationCache.set(cacheKey, result)
    return result
  }
  const sha256 = await fileSha256(file)
  const result = { present: true, verified: sha256 === spec.sha256, file, bytes: stat.size, sha256, expectedBytes: spec.bytes, expectedSha256: spec.sha256, reason: sha256 === spec.sha256 ? null : "sha256-mismatch" }
  modelVerificationCache.set(cacheKey, result)
  return result
}

function spawnWorker() {
  const child = spawn(PYTHON, [WORKER_SCRIPT, "--stdio"], {
    cwd: TOOLKIT_ROOT,
    windowsHide: true,
    env: {
      ...process.env,
      MOBILECLIP_REPO: repositoryPath(),
      OMP_NUM_THREADS: "1",
      OPENBLAS_NUM_THREADS: "1",
      MKL_NUM_THREADS: "1",
      NUMEXPR_NUM_THREADS: "1",
    },
  })
  const state = { child, buffer: "", pending: new Map(), stderr: "" }
  child.stdout.setEncoding("utf8")
  child.stderr.setEncoding("utf8")
  child.stdout.on("data", (chunk) => {
    state.buffer += chunk
    let newline
    while ((newline = state.buffer.indexOf("\n")) >= 0) {
      const line = state.buffer.slice(0, newline).trim()
      state.buffer = state.buffer.slice(newline + 1)
      if (!line) continue
      let message
      try { message = JSON.parse(line) } catch { continue }
      const pending = state.pending.get(message.id)
      if (!pending) continue
      state.pending.delete(message.id)
      clearTimeout(pending.timer)
      if (message.ok === false) pending.reject(new Error(message.error || "MobileCLIP worker error"))
      else pending.resolve(message)
    }
  })
  child.stderr.on("data", (chunk) => {
    state.stderr = `${state.stderr}${chunk}`.slice(-4000)
  })
  const failPending = (error) => {
    for (const pending of state.pending.values()) {
      clearTimeout(pending.timer)
      pending.reject(error)
    }
    state.pending.clear()
  }
  child.on("error", (error) => {
    if (workerState === state) workerState = null
    failPending(new Error(`Could not start MobileCLIP worker with ${PYTHON}: ${error.message}`))
  })
  child.on("exit", (code, signal) => {
    if (workerState === state) workerState = null
    const suffix = state.stderr ? `\n${state.stderr.trim()}` : ""
    failPending(new Error(`MobileCLIP worker stopped (${code ?? "signal"}${signal ? `/${signal}` : ""})${suffix}`))
  })
  return state
}

async function workerRequest(payload, timeoutMs = 120_000) {
  if (!workerState || workerState.child.exitCode !== null) workerState = spawnWorker()
  const state = workerState
  const id = ++workerSequence
  return await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      state.pending.delete(id)
      reject(new Error(`MobileCLIP worker timeout after ${timeoutMs}ms`))
    }, timeoutMs)
    state.pending.set(id, { resolve, reject, timer })
    try {
      state.child.stdin.write(`${JSON.stringify({ ...payload, id })}\n`)
    } catch (error) {
      clearTimeout(timer)
      state.pending.delete(id)
      reject(error)
    }
  })
}

async function downloadHttps(url, target, expectedBytes, expectedSha256, redirects = 0) {
  if (redirects > 2) throw new Error("Too many redirects while downloading MobileCLIP")
  const parsed = new URL(url)
  if (parsed.protocol !== "https:" || parsed.hostname !== APPLE_MODEL_HOST) {
    throw new Error(`Refusing MobileCLIP download outside ${APPLE_MODEL_HOST}`)
  }
  await ensureDir(path.dirname(target))
  const temporary = `${target}.part-${process.pid}-${Date.now()}`
  await new Promise((resolve, reject) => {
    const request = https.get(parsed, { headers: { "user-agent": "context-shelf-mobileclip/0.1" } }, (response) => {
      if ([301, 302, 303, 307, 308].includes(response.statusCode) && response.headers.location) {
        response.resume()
        return downloadHttps(new URL(response.headers.location, parsed).toString(), target, expectedBytes, expectedSha256, redirects + 1).then(resolve, reject)
      }
      if (response.statusCode !== 200) {
        response.resume()
        return reject(new Error(`Apple MobileCLIP download failed with HTTP ${response.statusCode}`))
      }
      const hash = crypto.createHash("sha256")
      let bytes = 0
      const output = createWriteStream(temporary, { flags: "wx" })
      response.on("data", (chunk) => { bytes += chunk.length; hash.update(chunk) })
      response.on("error", reject)
      output.on("error", reject)
      output.on("finish", async () => {
        try {
          const sha256 = hash.digest("hex")
          if (bytes !== expectedBytes) throw new Error(`MobileCLIP size mismatch: received ${bytes}, expected ${expectedBytes}`)
          if (sha256 !== expectedSha256) throw new Error(`MobileCLIP SHA-256 mismatch: received ${sha256}`)
          await fs.rename(temporary, target)
          resolve()
        } catch (error) { reject(error) }
      })
      response.pipe(output)
    })
    request.on("error", reject)
  }).catch(async (error) => {
    await fs.rm(temporary, { force: true }).catch(() => {})
    throw error
  })
}

export async function installMobileClipModel({ modelName = "mobileclip_s2", force = false } = {}) {
  const spec = modelSpec(modelName)
  const existing = await inspectModel(modelName)
  if (existing.verified && !force) return { ...existing, downloaded: false, model: spec.name, source: spec.url }
  if (existing.present && (!existing.verified || force)) await fs.rm(existing.file, { force: true })
  const file = modelPathFor(modelName)
  await downloadHttps(spec.url, file, spec.bytes, spec.sha256)
  return { ...(await inspectModel(modelName)), downloaded: true, model: spec.name, source: spec.url }
}

export async function mobileClipStatus({ modelName = "mobileclip_s2" } = {}) {
  const spec = modelSpec(modelName)
  const model = await inspectModel(modelName)
  const repository = repositoryPath()
  let runtime
  try {
    runtime = await workerRequest({ op: "status", modelName: spec.name, modelPath: model.file, repoPath: repository }, 15_000)
  } catch (error) {
    runtime = { ok: false, error: error.message }
  }
  return {
    ready: Boolean(model.verified && runtime?.onnxruntime && runtime?.onnxImage && runtime?.onnxText && runtime?.tokenizer && (runtime?.resvg || runtime?.cairosvg) && runtime?.cuda && runtime?.cupy && runtime?.cupyCuda),
    model: spec.name,
    source: spec.url,
    repository: spec.repository,
    modelFile: model,
    code: { path: repository, present: await fs.stat(repository).then((value) => value.isDirectory()).catch(() => false) },
    runtime,
    setup: {
      repository: "Clone the official Apple repository into the path reported above, or set MOBILECLIP_REPO.",
      dependencies: "The runtime uses ONNX Runtime GPU, CuPy CUDA preprocessing, Pillow, CairoSVG/resvg and the exported Apple MobileCLIP graphs. PyTorch is only needed for the one-time export step.",
    },
  }
}

async function readJson(file) {
  try { return JSON.parse(await fs.readFile(file, "utf8")) } catch { return null }
}

function vectorFileFromIndex(index, indexPath) {
  return path.isAbsolute(index.vectorsFile) ? index.vectorsFile : path.resolve(path.dirname(indexPath), index.vectorsFile || "vectors.f32")
}

function validVectorRange(buffer, offset, dimension) {
  const rowBytes = dimension * 4
  return Number.isInteger(offset) && offset >= 0 && offset + rowBytes <= buffer.length
}

function semanticItem(entry) {
  return {
    assetId: entry.assetId,
    file: entry.file,
    relativePath: entry.relativePath,
    name: entry.name,
    label: entry.label,
    kind: entry.kind,
    format: entry.format,
    width: entry.width,
    height: entry.height,
    aspectRatio: entry.aspectRatio,
    bytes: entry.bytes,
    license: entry.license || null,
    signature: entry.signature,
  }
}

async function validExistingIndex(index, indexPath, modelName) {
  const spec = modelSpec(modelName)
  if (!index || index.schemaVersion !== 1 || index.model?.name !== spec.name || index.model?.sha256 !== spec.sha256 || !Number.isInteger(index.dimension) || index.dimension < 1) return null
  const file = vectorFileFromIndex(index, indexPath)
  const vectors = await fs.readFile(file).catch(() => null)
  if (!vectors || vectors.length % (index.dimension * 4) !== 0) return null
  const items = Array.isArray(index.items) ? index.items.filter((item) => validVectorRange(vectors, item.vectorOffset * index.dimension * 4, index.dimension)) : []
  return { ...index, items, vectors, vectorsFile: file }
}

async function readExistingIndex(indexPath, modelName) {
  const resolved = path.resolve(indexPath)
  const stat = await fs.stat(resolved).catch(() => null)
  if (!stat?.isFile()) return null
  const cacheKey = `${resolved}:${stat.size}:${stat.mtimeMs}:${modelName}`
  if (semanticIndexCache.has(cacheKey)) return semanticIndexCache.get(cacheKey)
  const index = await validExistingIndex(await readJson(resolved), resolved, modelName)
  for (const key of semanticIndexCache.keys()) if (key.startsWith(`${resolved}:`) && key !== cacheKey) semanticIndexCache.delete(key)
  semanticIndexCache.set(cacheKey, index)
  return index
}

export async function indexMobileClip({ modelName = "mobileclip_s2", roots, cachePath, indexPath = DEFAULT_INDEX_PATH, refresh = false, batchSize = 96, preprocessWorkers = 1, device = "cuda", renderer = "auto", preprocessBackend = "cupy", profilePath, imageModelPath } = {}) {
  const spec = modelSpec(modelName)
  const { ensureLocalCatalog } = await import("./local-catalog.mjs")
  const catalog = await ensureLocalCatalog({ roots, cachePath })
  const entries = Object.values(catalog?.entries || {})
  const oldIndex = refresh ? null : await readExistingIndex(indexPath, modelName)
  const model = await inspectModel(modelName)
  if (!model.verified) throw new Error(`MobileCLIP model is not installed or failed verification. Run the explicit model install command first: ${model.file}`)
  const repository = repositoryPath()
  const modelStem = path.basename(model.file, path.extname(model.file))
  const defaultImageModelPath = path.join(path.dirname(model.file), `${modelStem}.image.onnx`)
  const normalizedBatchSize = Math.min(128, Math.max(1, Number(batchSize) || 96))
  const fixedImageCandidate = path.join(path.dirname(model.file), `${modelStem}.image.b${normalizedBatchSize}.onnx`)
  const autoImageModelPath = await fs.stat(fixedImageCandidate).then((value) => value.isFile()).catch(() => false)
    ? fixedImageCandidate
    : defaultImageModelPath
  const selectedImageModelPath = imageModelPath ? path.resolve(imageModelPath) : autoImageModelPath
  const runtimeFiles = [
    selectedImageModelPath,
    path.join(path.dirname(model.file), `${modelStem}.text.onnx`),
    path.join(path.dirname(model.file), `${modelStem}.tokenizer.json`),
  ]
  if (!await Promise.all(runtimeFiles.map((file) => fs.stat(file).then((value) => value.isFile()).catch(() => false))).then((values) => values.every(Boolean))) {
    throw new Error(`MobileCLIP ONNX runtime files are missing beside ${model.file}. Export the verified Apple checkpoint first.`)
  }
  const oldVectors = oldIndex?.vectors || Buffer.alloc(0)
  const oldById = new Map((oldIndex?.items || []).map((item) => [item.assetId, item]))
  const dimension = oldIndex?.dimension || null
  const reusable = new Map()
  const pending = []
  for (const entry of entries) {
    const previous = oldById.get(entry.assetId)
    if (previous && previous.signature === entry.signature && previous.file === entry.file && dimension && validVectorRange(oldVectors, previous.vectorOffset * dimension * 4, dimension)) {
      reusable.set(entry.assetId, { entry, previous })
    } else pending.push(entry)
  }

  const encodedPath = path.join(MOBILECLIP_ROOT, `pending-${process.pid}-${Date.now()}.f32`)
  let encoded = { items: [], dimension: dimension || 0, failed: [], device: null }
  try {
    if (pending.length) {
      encoded = await workerRequest({
        op: "encode_images",
        modelName: spec.name,
        modelPath: model.file,
        ...(selectedImageModelPath !== defaultImageModelPath ? { imageModelPath: selectedImageModelPath } : {}),
        repoPath: repository,
        outputPath: encodedPath,
        batchSize: Math.min(128, Math.max(1, Number(batchSize) || 48)),
        preprocessWorkers: Math.min(2, Math.max(1, Number(preprocessWorkers) || 1)),
        device,
        renderer,
        preprocessBackend,
        ...(profilePath ? { profilePath } : {}),
        files: pending.map(semanticItem),
      }, Math.max(180_000, pending.length * 2_000))
    }
    const encodedVectors = pending.length ? await fs.readFile(encodedPath).catch(() => Buffer.alloc(0)) : Buffer.alloc(0)
    const finalDimension = Number(encoded.dimension || dimension || 0)
    if (!finalDimension) throw new Error("MobileCLIP returned no embedding dimension")
    const rowBytes = finalDimension * 4
    const encodedById = new Map((encoded.items || []).map((item, index) => [item.assetId, encodedVectors.subarray(index * rowBytes, (index + 1) * rowBytes)]).filter(([, row]) => row.length === rowBytes))
    const parts = []
    const items = []
    let row = 0
    for (const entry of entries) {
      const previous = reusable.get(entry.assetId)?.previous
      const vector = encodedById.get(entry.assetId) || (previous && validVectorRange(oldVectors, previous.vectorOffset * rowBytes, finalDimension) ? oldVectors.subarray(previous.vectorOffset * rowBytes, (previous.vectorOffset + 1) * rowBytes) : null)
      if (!vector || vector.length !== rowBytes) continue
      parts.push(vector)
      items.push({ ...semanticItem(entry), vectorOffset: row })
      row += 1
    }
    await ensureDir(path.dirname(indexPath))
    const vectorFile = vectorsPathFor(indexPath)
    const temporaryVectors = `${vectorFile}.part-${process.pid}-${Date.now()}`
    await fs.writeFile(temporaryVectors, Buffer.concat(parts))
    await fs.rename(temporaryVectors, vectorFile)
    const resultIndex = {
      schemaVersion: 1,
      generatedAt: new Date().toISOString(),
      catalogGeneratedAt: catalog?.generatedAt || null,
      model: { name: spec.name, sha256: spec.sha256, source: spec.url, repository: spec.repository },
      dimension: finalDimension,
      vectorType: "float32-le",
      vectorsFile: path.basename(vectorFile),
      count: items.length,
      items,
    }
    await fs.writeFile(indexPath, `${JSON.stringify(resultIndex, null, 2)}\n`, "utf8")
    for (const key of semanticIndexCache.keys()) if (key.startsWith(`${path.resolve(indexPath)}:`)) semanticIndexCache.delete(key)
    return {
      indexPath,
      vectorsFile: vectorFile,
      model: spec.name,
      dimension: finalDimension,
      total: items.length,
      catalogFiles: entries.length,
      encoded: encoded.items?.length || 0,
      reused: reusable.size,
      failed: encoded.failed || [],
      device: encoded.device || null,
      renderer: encoded.renderer || renderer,
      preprocessBackend: encoded.preprocessBackend || preprocessBackend,
      preprocessWorkers: encoded.preprocessWorkers || null,
      requestedBatchSize: encoded.requestedBatchSize || Number(batchSize) || null,
      modelBatchSize: encoded.modelBatchSize || null,
      imageModelPath: selectedImageModelPath,
      batches: encoded.batches || 0,
      preprocessMs: encoded.preprocessMs || 0,
      inferenceMs: encoded.inferenceMs || 0,
      cpuTimeMs: encoded.cpuTimeMs || 0,
      cpuPercentOfOneCore: encoded.cpuPercentOfOneCore || 0,
      profileFiles: encoded.profileFiles || [],
      generatedAt: resultIndex.generatedAt,
    }
  } finally {
    await fs.rm(encodedPath, { force: true }).catch(() => {})
  }
}

const QUERY_TRANSLATIONS = Object.freeze({
  pulmon: ["lung", "lungs", "respiratory system"], pulmones: ["lung", "lungs", "respiratory system"],
  vih: ["hiv", "virus"], hiv: ["vih", "virus"], its: ["sti", "sexual infection"], sti: ["its", "sexual infection"],
  condon: ["condom", "protection"], condom: ["condon", "protection"], prevencion: ["prevention", "protection", "care"],
  prevention: ["prevencion", "protection", "care"], riesgo: ["risk", "warning", "danger"], risk: ["riesgo", "warning", "danger"],
  sustancias: ["substances", "drug", "drugs"], sustancia: ["substance", "drug"], droga: ["drug", "substance"], drogas: ["drugs", "substances"],
  pastilla: ["pill", "tablet", "capsule"], jeringa: ["syringe", "needle"], corazon: ["heart", "cardiac"], cerebro: ["brain", "mental"],
  boca: ["mouth", "oral", "lips"], labios: ["lips", "mouth", "oral"], persona: ["person", "people", "human"], personas: ["people", "person", "human"],
  comunidad: ["community", "people", "social"], cuidado: ["care", "health", "support"], consentimiento: ["consent", "communication", "limits"],
})

function queryVariants(query, terms = []) {
  const raw = [query, ...terms].map((value) => String(value || "").trim()).filter(Boolean)
  const translated = raw.flatMap((value) => value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").split(/[^a-z0-9]+/).filter(Boolean).flatMap((token) => QUERY_TRANSLATIONS[token] || []))
  const base = [...new Set([...raw, ...translated])]
  return [...new Set([
    ...base,
    ...base.map((value) => `an icon of ${value}`),
    ...base.map((value) => `a simple vector symbol representing ${value}`),
  ])].slice(0, 24)
}

export async function semanticScoresForQuery({ query = "", terms = [], modelName = "mobileclip_s2", indexPath = DEFAULT_INDEX_PATH, candidateAssetIds = null } = {}) {
  const index = await readExistingIndex(indexPath, modelName)
  if (!index) return { ready: false, scores: new Map(), items: new Map(), reason: "Semantic index is not available or uses another model." }
  const model = await inspectModel(modelName)
  if (!model.verified) return { ready: false, scores: new Map(), items: new Map(), reason: "MobileCLIP model is not installed or failed verification." }
  if (!query && !terms.length) return { ready: true, scores: new Map(), items: new Map(), variants: [] }
  const variants = queryVariants(query, terms)
  const response = await workerRequest({ op: "encode_text", modelName, modelPath: model.file, repoPath: repositoryPath(), texts: variants }, 30_000)
  const textBytes = Buffer.from(response.vectors || "", "base64")
  const dimension = Number(response.dimension || index.dimension)
  if (dimension !== index.dimension) throw new Error(`MobileCLIP text dimension ${dimension} does not match semantic index dimension ${index.dimension}`)
  const textCount = variants.length
  if (textBytes.length < dimension * 4 * textCount) throw new Error("MobileCLIP returned an invalid text embedding")
  const queryVector = new Float32Array(dimension)
  for (let item = 0; item < textCount; item += 1) for (let value = 0; value < dimension; value += 1) queryVector[value] += textBytes.readFloatLE((item * dimension + value) * 4)
  let norm = 0
  for (const value of queryVector) norm += value * value
  norm = Math.sqrt(norm) || 1
  for (let value = 0; value < queryVector.length; value += 1) queryVector[value] /= norm
  const vectors = index.vectors
  const allowed = candidateAssetIds ? new Set(candidateAssetIds) : null
  const scores = new Map()
  const items = new Map()
  for (const item of index.items) {
    if (allowed && !allowed.has(item.assetId)) continue
    const offset = item.vectorOffset * index.dimension * 4
    if (!validVectorRange(vectors, offset, dimension)) continue
    let score = 0
    for (let value = 0; value < dimension; value += 1) score += queryVector[value] * vectors.readFloatLE(offset + value * 4)
    scores.set(item.assetId, score)
    items.set(item.assetId, item)
  }
  return { ready: true, scores, items, variants, model: modelName, device: response.device || null }
}

export async function searchMobileClip({ query = "", terms = [], modelName = "mobileclip_s2", indexPath = DEFAULT_INDEX_PATH, candidateAssetIds = null, limit = 12 } = {}) {
  const value = await semanticScoresForQuery({ query, terms, modelName, indexPath, candidateAssetIds })
  if (!value.ready) return { ready: false, model: modelName, query, results: [], total: 0, reason: value.reason }
  const results = [...value.scores.entries()]
    .sort((left, right) => right[1] - left[1] || String(value.items.get(left[0])?.name || "").localeCompare(String(value.items.get(right[0])?.name || "")))
    .slice(0, Math.min(100, Math.max(1, Number(limit) || 12)))
    .map(([assetId, score], index) => ({ ...value.items.get(assetId), assetId, score: Number(score.toFixed(5)), semantic: true, provider: "local", local: true, id: value.items.get(assetId)?.relativePath, rank: index + 1 }))
  return { ready: true, model: modelName, query, queryVariants: value.variants, device: value.device, results, total: results.length }
}

export function mobileClipPaths({ modelName = "mobileclip_s2", indexPath = DEFAULT_INDEX_PATH } = {}) {
  const model = modelPathFor(modelName)
  const stem = path.basename(model, path.extname(model))
  const directory = path.dirname(model)
  return {
    model,
    repository: repositoryPath(),
    image: path.join(directory, `${stem}.image.onnx`),
    text: path.join(directory, `${stem}.text.onnx`),
    tokenizer: path.join(directory, `${stem}.tokenizer.json`),
    index: path.resolve(indexPath),
    vectors: vectorsPathFor(indexPath),
  }
}

import fs from "node:fs"
import path from "node:path"
import { spawn } from "node:child_process"

const root = process.cwd()
const args = process.argv.slice(2)

function flag(name, fallback) {
  const index = args.indexOf(`--${name}`)
  return index >= 0 ? args[index + 1] : fallback
}

const count = Math.max(1, Number(flag("count", 128)) || 128)
const renderer = flag("renderer", "cairosvg")
const preprocessBackend = flag("backend", "cupy")
const batchSize = Math.max(1, Math.min(128, Number(flag("batch-size", 96)) || 96))
const profilePath = flag("profile-path", "")
const imageModelPath = flag("image-model-path", "")
const cudaGraph = args.includes("--cuda-graph")
const outputPath = path.resolve(flag("output-path", path.join(root, "cache/context-shelf/mobileclip", `benchmark-${preprocessBackend}.f32`)))
const catalog = JSON.parse(fs.readFileSync(path.join(root, "cache/context-shelf/catalog.json"), "utf8"))
const entries = Object.values(catalog.entries || {})
const svgCount = Math.ceil(count / 2)
const rasterCount = Math.floor(count / 2)
const selected = [
  ...entries.filter((entry) => entry.format === "svg").slice(0, svgCount),
  ...entries.filter((entry) => ["png", "jpg", "jpeg"].includes(entry.format)).slice(0, rasterCount),
]
const files = selected.map((entry) => ({ assetId: entry.assetId, file: entry.file }))
const mobileClipRoot = path.join(root, "cache/context-shelf/mobileclip")
const python = path.join(mobileClipRoot, ".venv", "Scripts", "python.exe")
const request = {
  id: 1,
  op: "encode_images",
  modelName: "mobileclip_s2",
  modelPath: path.join(mobileClipRoot, "mobileclip_s2.pt"),
  ...(imageModelPath ? { imageModelPath: path.resolve(imageModelPath) } : {}),
  repoPath: path.join(mobileClipRoot, "ml-mobileclip"),
  outputPath,
  batchSize,
  preprocessWorkers: 1,
  device: "cuda",
  cudaGraph,
  renderer,
  preprocessBackend,
  ...(profilePath ? { profilePath: path.resolve(profilePath) } : {}),
  files,
}

const child = spawn(python, [path.join(root, "scripts/mobileclip-worker.py"), "--stdio"], {
  cwd: root,
  windowsHide: true,
})
let output = ""
let reported = false
child.stdout.setEncoding("utf8")
child.stdout.on("data", (chunk) => {
  output += chunk
  const newline = output.indexOf("\n")
  if (reported || newline < 0) return
  reported = true
  const response = JSON.parse(output.slice(0, newline).trim())
  console.log(JSON.stringify({
    ok: response.ok,
    count: response.items?.length || 0,
    failed: response.failed?.length || 0,
    dimension: response.dimension,
    device: response.device,
    renderer: response.renderer,
    preprocessBackend: response.preprocessBackend,
    preprocessWorkers: response.preprocessWorkers,
    requestedBatchSize: response.requestedBatchSize,
    modelBatchSize: response.modelBatchSize,
    cudaGraph,
    batches: response.batches,
    preprocessMs: response.preprocessMs,
    inferenceMs: response.inferenceMs,
    cpuTimeMs: response.cpuTimeMs,
    cpuPercentOfOneCore: response.cpuPercentOfOneCore,
    stagesMs: response.stagesMs,
    elapsedMs: response.elapsedMs,
  }, null, 2))
  child.kill()
})
child.stderr.on("data", () => {})
child.stdin.end(`${JSON.stringify(request)}\n`)

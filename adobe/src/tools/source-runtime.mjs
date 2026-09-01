import fs from "node:fs/promises"
import path from "node:path"
import { createRequire } from "node:module"
import { fileURLToPath, pathToFileURL } from "node:url"
import { ensureDir, resolveOutput, TOOLKIT_ROOT } from "../utils.mjs"

const SOURCE_ROOT = path.resolve(TOOLKIT_ROOT, "..")
const THREE_ROOT = path.join(SOURCE_ROOT, "three.js")
const STDLIB_ROOT = path.join(SOURCE_ROOT, "stdlib")
const RXJS_ROOT = path.join(SOURCE_ROOT, "rxjs", "packages", "rxjs")
const EFFECT_ROOT = path.join(SOURCE_ROOT, "effect", "packages", "effect")
const THING_ROOT = path.join(SOURCE_ROOT, "umbrella")
const THING_GEOM_ROOT = path.join(THING_ROOT, "packages", "geom")
const THREE_MODULE = path.join(THREE_ROOT, "build", "three.module.js")
const runtimeRequire = createRequire(import.meta.url)
const fsSync = runtimeRequire("node:fs")
let esbuild

function loadEsbuild() {
  if (esbuild) return esbuild
  const packageJson = path.join(RXJS_ROOT, "package.json")
  if (!fsSync.existsSync(packageJson)) {
    throw new Error("Optional source runtime unavailable: RxJS/esbuild is not bundled in LUCIDA Adobe")
  }
  try {
    esbuild = createRequire(packageJson)("esbuild")
    return esbuild
  } catch (error) {
    throw new Error(`Optional source runtime unavailable: ${error.message}`)
  }
}

let threePromise
let stdlibPromise
let rxjsPromise
let effectPromise
let thingGeomPromise

async function loadThree() {
  threePromise ||= import(pathToFileURL(THREE_MODULE).href)
  return threePromise
}

async function loadStdlib() {
  stdlibPromise ||= Promise.resolve().then(() => {
    const statsRoot = path.join(STDLIB_ROOT, "lib", "node_modules", "@stdlib", "stats", "base")
    return {
      mean: runtimeRequire(path.join(statsRoot, "sdsnanmean", "lib")),
      variance: runtimeRequire(path.join(statsRoot, "snanvariance", "lib")),
      stdev: runtimeRequire(path.join(statsRoot, "snanstdev", "lib")),
    }
  })
  return stdlibPromise
}

async function loadBundledTypeScript(cache, root, entry, aliases = {}) {
  if (cache) return cache
  const result = await loadEsbuild().build({
    stdin: {
      contents: entry,
      resolveDir: root,
      sourcefile: "lucida-adobe-runtime-entry.ts",
      loader: "ts",
    },
    bundle: true,
    platform: "node",
    format: "esm",
    write: false,
    logLevel: "silent",
    tsconfig: path.join(root, "tsconfig.json"),
    alias: aliases,
  })
  const source = Buffer.from(result.outputFiles[0].contents).toString("base64")
  return import(`data:text/javascript;base64,${source}`)
}

async function loadRxjs() {
  rxjsPromise ||= loadBundledTypeScript(
    null,
    RXJS_ROOT,
    'export { Subject } from "./src/Subject.ts";',
    { "@rxjs/observable-polyfill": path.join(RXJS_ROOT, "node_modules", "@rxjs", "observable-polyfill", "src", "index.ts") },
  )
  return rxjsPromise
}

async function loadEffect() {
  effectPromise ||= loadBundledTypeScript(
    null,
    EFFECT_ROOT,
    'export * as Effect from "./src/Effect.ts"; export * as Schedule from "./src/Schedule.ts";',
  )
  return effectPromise
}

function thiNgSourcePlugin() {
  return {
    name: "lucida-adobe-thi-ng-source",
    setup(build) {
      build.onResolve({ filter: /^@thi\.ng\// }, (args) => {
        const parts = args.path.split("/")
        const packageName = parts[1]
        const subpath = parts.slice(2).join("/").replace(/\.(js|ts)$/, "")
        const base = path.join(THING_ROOT, "packages", packageName, "src", subpath || "index")
        const candidates = [base + ".ts", base + ".tsx", base + ".js", path.join(base, "index.ts"), path.join(base, "index.js")]
        const target = candidates.find((candidate) => fsSync.existsSync(candidate))
        return target ? { path: target } : { errors: [{ text: `thi.ng source module not found: ${args.path}` }] }
      })
    },
  }
}

async function loadThiNgGeom() {
  if (thingGeomPromise) return thingGeomPromise
  const result = await loadEsbuild().build({
    stdin: {
      contents: 'export * as geom from "./src/index.ts";',
      resolveDir: THING_GEOM_ROOT,
      sourcefile: "lucida-adobe-thi-ng-entry.ts",
      loader: "ts",
    },
    bundle: true,
    platform: "node",
    format: "esm",
    write: false,
    logLevel: "silent",
    plugins: [thiNgSourcePlugin()],
  })
  const source = Buffer.from(result.outputFiles[0].contents).toString("base64")
  thingGeomPromise = import(`data:text/javascript;base64,${source}`)
  return thingGeomPromise
}

function number3(value, fallback = 0) {
  const values = Array.isArray(value) ? value : []
  return [0, 1, 2].map((index) => Number.isFinite(Number(values[index])) ? Number(values[index]) : fallback)
}

function colorValue(THREE, value) {
  try {
    return new THREE.Color(value || "#ffffff")
  } catch {
    return new THREE.Color("#ffffff")
  }
}

function createThreeObject(THREE, spec) {
  const type = String(spec.type || "plane").toLowerCase()
  if (type === "group") return new THREE.Group()
  const size = number3(spec.size || [1, 1, 1], 1)
  const geometry = type === "sphere"
    ? new THREE.SphereGeometry(Math.max(size[0], 0.001) / 2, 16, 12)
    : type === "box" || type === "cube"
      ? new THREE.BoxGeometry(Math.max(size[0], 0.001), Math.max(size[1], 0.001), Math.max(size[2], 0.001))
      : new THREE.PlaneGeometry(Math.max(size[0], 0.001), Math.max(size[1], 0.001))
  const material = new THREE.MeshBasicMaterial({
    color: colorValue(THREE, spec.color),
    transparent: Number(spec.opacity ?? 1) < 1,
    opacity: Math.max(0, Math.min(1, Number(spec.opacity ?? 1))),
    side: THREE.DoubleSide,
  })
  return new THREE.Mesh(geometry, material)
}

function browserSpec(spec) {
  return JSON.stringify(spec).replaceAll("<", "\\u003c")
}

export async function threeScenePreview(spec = {}, output, options = {}) {
  const THREE = await loadThree()
  const sceneSpec = {
    canvas: { width: Number(spec.canvas?.width || 1080), height: Number(spec.canvas?.height || 1440) },
    background: spec.background || "#101827",
    camera: spec.camera || { left: -1, right: 1, top: 1, bottom: -1, near: 0.1, far: 100 },
    objects: Array.isArray(spec.objects) ? spec.objects : [],
  }
  const scene = new THREE.Scene()
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100)
  camera.position.z = 5
  const root = new THREE.Group()
  scene.add(root)
  const names = new Set()
  const objects = []
  for (const [index, item] of sceneSpec.objects.entries()) {
    const objectSpec = { ...item, name: item.name || `object-${index + 1}` }
    if (names.has(objectSpec.name)) throw new Error(`Duplicate three.js object name: ${objectSpec.name}`)
    names.add(objectSpec.name)
    const object = createThreeObject(THREE, objectSpec)
    object.name = objectSpec.name
    object.position.set(...number3(objectSpec.position))
    object.rotation.set(...number3(objectSpec.rotation))
    object.scale.set(...number3(objectSpec.scale, 1))
    root.add(object)
    objects.push({ name: object.name, type: object.type, geometry: object.geometry?.type || null })
  }
  scene.updateMatrixWorld(true)
  const target = resolveOutput(output, options)
  const moduleTarget = path.join(path.dirname(target), "three.module.js")
  const resolvedModuleTarget = resolveOutput(moduleTarget, options)
  await ensureDir(path.dirname(target))
  await fs.copyFile(THREE_MODULE, resolvedModuleTarget)
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Agent Toolkit three.js preview</title><style>html,body{margin:0;background:${sceneSpec.background};height:100%;overflow:hidden}canvas{display:block;width:100%;height:100%}</style></head>
<body><canvas id="preview"></canvas><script type="module">
import * as THREE from "./three.module.js";
const spec = ${browserSpec(sceneSpec)};
const canvas = document.querySelector("#preview");
const renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(spec.background);
const camera = new THREE.OrthographicCamera(-1,1,1,-1,0.1,100); camera.position.z = 5;
for (const item of spec.objects) {
  const size = item.size || [1,1,1];
  const geometry = item.type === "sphere" ? new THREE.SphereGeometry(Math.max(size[0],.001)/2,16,12) : item.type === "box" || item.type === "cube" ? new THREE.BoxGeometry(Math.max(size[0],.001),Math.max(size[1],.001),Math.max(size[2],.001)) : new THREE.PlaneGeometry(Math.max(size[0],.001),Math.max(size[1],.001));
  const material = new THREE.MeshBasicMaterial({color:item.color || "#fff", transparent:(item.opacity ?? 1)<1, opacity:item.opacity ?? 1, side:THREE.DoubleSide});
  const mesh = new THREE.Mesh(geometry, material); mesh.name=item.name || "object"; mesh.position.set(...(item.position || [0,0,0])); mesh.rotation.set(...(item.rotation || [0,0,0])); mesh.scale.set(...(item.scale || [1,1,1])); scene.add(mesh);
}
function resize(){const r=canvas.getBoundingClientRect(); renderer.setSize(r.width,r.height,false);}
window.addEventListener("resize",resize); resize(); renderer.render(scene,camera);
</script></body></html>
`
  await fs.writeFile(target, html, "utf8")
  return { html: target, threeModule: resolvedModuleTarget, engine: "three-local", objectCount: objects.length, objects }
}

export async function stdlibStatistics(values, options = {}) {
  const stdlib = await loadStdlib()
  if (!Array.isArray(values) || values.length === 0) throw new Error("stdlib statistics requires a non-empty values array")
  const typed = new Float32Array(values.map((value) => {
    const number = Number(value)
    return Number.isFinite(number) ? number : Number.NaN
  }))
  const correction = Number.isInteger(Number(options.correction)) ? Number(options.correction) : 0
  return {
    engine: "stdlib-local",
    count: typed.length,
    finiteCount: [...typed].filter(Number.isFinite).length,
    correction,
    mean: stdlib.mean(typed.length, typed, 1),
    variance: stdlib.variance(typed.length, correction, typed, 1),
    standardDeviation: stdlib.stdev(typed.length, correction, typed, 1),
  }
}

export async function thiNgSvg(spec = {}, output, options = {}) {
  const { geom } = await loadThiNgGeom()
  const width = Number(spec.width || spec.canvas?.width || 1080)
  const height = Number(spec.height || spec.canvas?.height || 1440)
  const shapes = []
  for (const item of Array.isArray(spec.shapes) ? spec.shapes : []) {
    const attribs = {
      fill: item.fill || "none",
      stroke: item.stroke || "none",
      weight: Number(item.strokeWidth ?? 1),
    }
    const type = String(item.type || "rect").toLowerCase()
    if (type === "circle") {
      shapes.push(geom.circle([Number(item.x || 0), Number(item.y || 0)], Math.max(0, Number(item.radius || item.r || 0)), attribs))
    } else if (type === "rect") {
      shapes.push(geom.rect([Number(item.x || 0), Number(item.y || 0)], [Math.max(0, Number(item.width || 0)), Math.max(0, Number(item.height || 0))], attribs))
    } else {
      throw new Error(`Unsupported thi.ng geom shape: ${type}`)
    }
  }
  const document = geom.svgDoc({ width, height, viewBox: `0 0 ${width} ${height}` }, ...shapes)
  const svg = geom.asSvg(document)
  const target = resolveOutput(output, options)
  await ensureDir(path.dirname(target))
  await fs.writeFile(target, svg, "utf8")
  return { svg: target, engine: "thi-ng-geom-local", shapes: shapes.length, width, height }
}

export async function rxjsEventTimeline(events = []) {
  const { Subject } = await loadRxjs()
  if (!Array.isArray(events)) throw new Error("RxJS event timeline requires an events array")
  const subject = new Subject()
  const received = []
  let completed = false
  const subscription = subject.subscribe({
    next: (event) => received.push(event),
    complete: () => { completed = true },
  })
  for (const event of events) subject.next(event)
  subject.complete()
  if (subscription && typeof subscription.unsubscribe === "function") subscription.unsubscribe()
  const byType = {}
  for (const event of received) {
    const type = String(event?.type || "untyped")
    byType[type] = (byType[type] || 0) + 1
  }
  return { engine: "rxjs-local", received, count: received.length, byType, completed }
}

export async function effectRetrySimulation(options = {}) {
  const { Effect, Schedule } = await loadEffect()
  const failuresBeforeSuccess = Math.max(0, Number(options.failuresBeforeSuccess || 0))
  const maxRetries = Math.max(0, Number(options.maxRetries ?? failuresBeforeSuccess))
  let attempts = 0
  const task = Effect.suspend(() => {
    attempts += 1
    return attempts <= failuresBeforeSuccess
      ? Effect.fail({ attempt: attempts, reason: "simulated-failure" })
      : Effect.succeed({ attempt: attempts, value: options.value ?? "ok" })
  })
  try {
    const value = await Effect.runPromise(Effect.retry(task, Schedule.recurs(maxRetries)))
    return { engine: "effect-local", status: "succeeded", attempts, maxRetries, value }
  } catch (error) {
    return { engine: "effect-local", status: "failed", attempts, maxRetries, error: String(error) }
  }
}

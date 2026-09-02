const { app, BrowserWindow, ipcMain, nativeImage } = require("electron")
const { spawn } = require("node:child_process")
const http = require("node:http")
const { realpathSync, statSync } = require("node:fs")
const fs = require("node:fs/promises")
const path = require("node:path")
const { pathToFileURL } = require("node:url")

const BRIDGE_HOST = "127.0.0.1"
const BRIDGE_PORT = 47921
const TOOLKIT_ROOT = path.resolve(__dirname, "..")
const SERVER_ENTRY = path.join(TOOLKIT_ROOT, "src", "server.mjs")
const ALLOWED_ROUTES = new Set(["/context/current", "/recommendations", "/catalog/groups", "/catalog/assets", "/catalog/projects", "/semantic/status", "/semantic/index", "/insert", "/surface/current"])
const ASSET_ROOT = path.resolve(__dirname, "..")
const DRAG_EXTENSIONS = new Set([".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"])
const DRAG_ICON_DATA_URL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
let bridgeProcess = null
let ownsBridgeProcess = false
let bridgeReadyPromise = null
let dragIcon = null

function bridgeHeaders() {
  const token = process.env.AGENT_TOOLKIT_TOKEN
  return token ? { authorization: `Bearer ${token}` } : {}
}

function bridgeStatus() {
  return new Promise((resolve) => {
    const request = http.get({
      hostname: BRIDGE_HOST,
      port: BRIDGE_PORT,
      path: "/health",
      headers: bridgeHeaders(),
    }, (response) => {
      let value = ""
      response.setEncoding("utf8")
      response.on("data", (chunk) => { value += chunk })
      response.on("end", () => {
        let payload = null
        try { payload = JSON.parse(value) } catch (_) {}
        const reachable = response.statusCode >= 200 && response.statusCode < 300
        const compatible = reachable && payload?.service === "lucida-adobe" && payload?.apiVersion === 1 && payload?.branch === "ADOBE" && payload?.focus === "adobe" && payload?.capabilities?.includes("catalog/projects")
        resolve({ reachable, compatible })
      })
    })
    request.setTimeout(500, () => request.destroy())
    request.on("error", () => resolve({ reachable: false, compatible: false }))
  })
}

function startBridgeProcess() {
  const nodeExecutable = process.env.npm_node_execpath || process.env.NODE || process.execPath
  const environment = { ...process.env, AGENT_TOOLKIT_HOST: BRIDGE_HOST, AGENT_TOOLKIT_PORT: String(BRIDGE_PORT) }
  if (process.versions.electron && path.resolve(nodeExecutable) === path.resolve(process.execPath)) environment.ELECTRON_RUN_AS_NODE = "1"
  bridgeProcess = spawn(nodeExecutable, [SERVER_ENTRY], {
    cwd: TOOLKIT_ROOT,
    env: environment,
    stdio: ["ignore", "ignore", "pipe"],
    windowsHide: true,
  })
  ownsBridgeProcess = true
  bridgeProcess.stderr.on("data", (chunk) => console.error(`[context-shelf bridge] ${String(chunk).trim()}`))
  bridgeProcess.once("error", (error) => console.error(`[context-shelf bridge] ${error.message}`))
  bridgeProcess.once("exit", () => {
    bridgeProcess = null
    ownsBridgeProcess = false
    bridgeReadyPromise = null
  })
}

async function waitForBridge(timeoutMs = 8_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if ((await bridgeStatus()).compatible) return true
    await new Promise((resolve) => setTimeout(resolve, 150))
  }
  throw new Error(`Bridge unavailable at http://${BRIDGE_HOST}:${BRIDGE_PORT}`)
}

function ensureBridge() {
  if (bridgeReadyPromise) return bridgeReadyPromise
  bridgeReadyPromise = (async () => {
    const status = await bridgeStatus()
    if (status.compatible) return true
    if (status.reachable) throw new Error("An older bridge is already using port 47921. Close it and restart Context Shelf.")
    startBridgeProcess()
    await waitForBridge()
    return true
  })().catch((error) => {
    bridgeReadyPromise = null
    throw error
  })
  return bridgeReadyPromise
}

function stopBridge() {
  if (!ownsBridgeProcess || !bridgeProcess) return
  bridgeProcess.kill()
  bridgeProcess = null
  ownsBridgeProcess = false
}

function resolveAllowedAsset(file) {
  if (typeof file !== "string") throw new Error("Asset path must be a string")
  const root = realpathSync(ASSET_ROOT)
  const resolved = realpathSync(path.resolve(file))
  const relative = path.relative(root, resolved)
  if (relative.startsWith("..") || path.isAbsolute(relative)) throw new Error("Asset path is outside the package")
  if (!statSync(resolved).isFile()) throw new Error("Asset path is not a file")
  return resolved
}

function bridgeRequest(route, options = {}) {
  const url = new URL(`http://${BRIDGE_HOST}:${BRIDGE_PORT}${route}`)
  if (!ALLOWED_ROUTES.has(url.pathname)) return Promise.reject(new Error("Bridge route is not allowlisted"))
  const method = String(options.method || "GET").toUpperCase()
  if (!["GET", "POST"].includes(method)) return Promise.reject(new Error("Bridge method is not allowlisted"))
  const body = options.body ? String(options.body) : ""
  if (Buffer.byteLength(body) > 1_000_000) return Promise.reject(new Error("Bridge request is too large"))
  return new Promise((resolve, reject) => {
    const request = http.request({
      hostname: BRIDGE_HOST, port: BRIDGE_PORT, path: `${url.pathname}${url.search}`, method,
      headers: { "content-type": "application/json", "content-length": Buffer.byteLength(body), ...bridgeHeaders() },
    }, (response) => {
      let value = ""
      response.setEncoding("utf8")
      response.on("data", (chunk) => { value += chunk })
      response.on("end", () => {
        let payload
        try { payload = value ? JSON.parse(value) : {} } catch (_) { payload = { error: "Bridge returned invalid JSON" } }
        if (response.statusCode < 200 || response.statusCode >= 300) reject(new Error(payload.error || `Bridge HTTP ${response.statusCode}`))
        else resolve(payload)
      })
    })
    const timeoutMs = url.pathname === "/catalog/projects" ? 30_000 : 2_500
    request.setTimeout(timeoutMs, () => request.destroy(new Error(`Bridge timeout after ${timeoutMs}ms`)))
    request.on("error", reject)
    if (body) request.write(body)
    request.end()
  })
}

function createWindow() {
  const window = new BrowserWindow({
    width: 380, height: 520, minWidth: 320, minHeight: 360, alwaysOnTop: true,
    title: "LUCIDA · Context Shelf", frame: false, transparent: true, backgroundColor: "#00000000",
    hasShadow: true, roundedCorners: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, preload: path.join(__dirname, "preload.cjs") },
  })
  window.removeMenu()
  window.setAlwaysOnTop(true, "floating")
  window.loadFile(path.join(__dirname, "index.html"))
}

ipcMain.handle("bridge:request", async (_event, route, options) => {
  await ensureBridge()
  try {
    return await bridgeRequest(route, options)
  } catch (error) {
    if (error?.code !== "ECONNREFUSED") throw error
    bridgeReadyPromise = null
    await ensureBridge()
    return bridgeRequest(route, options)
  }
})
ipcMain.handle("window:minimize", (event) => BrowserWindow.fromWebContents(event.sender)?.minimize())
ipcMain.handle("window:toggle-maximize", (event) => {
  const window = BrowserWindow.fromWebContents(event.sender)
  if (!window) return false
  if (window.isMaximized()) window.unmaximize()
  else window.maximize()
  return window.isMaximized()
})
ipcMain.handle("window:close", (event) => BrowserWindow.fromWebContents(event.sender)?.close())
ipcMain.handle("asset:preview", async (_event, file) => {
  const resolved = resolveAllowedAsset(file)
  const extension = path.extname(resolved).toLowerCase()
  const mime = { ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif" }[extension]
  if (!mime) return null
  const stat = await fs.stat(resolved)
  // Large local assets stay as file URLs so the renderer does not have to
  // duplicate several megabytes as a base64 string just to show a thumbnail.
  if (stat.size > 2_000_000) return pathToFileURL(resolved).href
  const data = await fs.readFile(resolved)
  return `data:${mime};base64,${data.toString("base64")}`
})

// Starts a native OS file drag. This path is deliberately independent of the
// bridge so Photoshop and Illustrator can receive the real local file.
ipcMain.on("asset:drag", (event, file) => {
  try {
    const resolved = resolveAllowedAsset(file)
    if (!DRAG_EXTENSIONS.has(path.extname(resolved).toLowerCase())) return
    if (!dragIcon) dragIcon = nativeImage.createFromDataURL(DRAG_ICON_DATA_URL)
    event.sender.startDrag({ file: resolved, icon: dragIcon })
  } catch (error) {
    console.error(`[context-shelf drag] ${error.message}`)
  }
})

app.whenReady().then(() => {
  createWindow()
  ensureBridge().catch((error) => console.error(`[context-shelf] ${error.message}`))
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
})

app.on("before-quit", stopBridge)
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit() })

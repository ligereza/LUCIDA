import fs from "node:fs/promises"
import { createReadStream, createWriteStream } from "node:fs"
import path from "node:path"
import { createRequire } from "node:module"
import { pipeline } from "node:stream/promises"
import { ensureDir, TOOLKIT_ROOT } from "../utils.mjs"

const require = createRequire(import.meta.url)

const FLOW_ENV_FILE = "C:\\IA\\flujo\\.env"

function envFileCandidates() {
  return [
    process.env.PDF_SERVICES_ENV_FILE,
    path.join(TOOLKIT_ROOT, ".env"),
    FLOW_ENV_FILE,
  ].filter(Boolean).filter((file, index, files) => files.indexOf(file) === index)
}

export function parseEnvText(text) {
  const values = {}
  for (const rawLine of String(text || "").split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith("#")) continue
    const match = line.match(/^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/)
    if (!match || !/^(?:PDF_SERVICES_|ADOBE_PDF_SERVICES_)/.test(match[1])) continue
    let value = match[2].trim()
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1)
    }
    values[match[1]] = value
  }
  return values
}

async function readEnvFileValues() {
  const values = {}
  for (const file of envFileCandidates()) {
    try {
      const text = await fs.readFile(file, "utf8")
      Object.assign(values, parseEnvText(text))
    } catch (error) {
      if (error?.code !== "ENOENT") throw error
    }
  }
  return values
}

function credentialFilePath(envValues = {}) {
  return process.env.PDF_SERVICES_CREDENTIALS
    || process.env.ADOBE_PDF_SERVICES_CREDENTIALS
    || envValues.PDF_SERVICES_CREDENTIALS
    || envValues.ADOBE_PDF_SERVICES_CREDENTIALS
    || null
}

async function readCredentials({ loadDotEnv = true } = {}) {
  const envValues = loadDotEnv ? await readEnvFileValues() : {}
  const file = credentialFilePath(envValues)
  let fileCredentials = {}
  if (file) fileCredentials = JSON.parse(await fs.readFile(path.resolve(file), "utf8"))
  const nested = fileCredentials.client_credentials || fileCredentials.clientCredentials || {}
  return {
    clientId: process.env.PDF_SERVICES_CLIENT_ID
      || process.env.ADOBE_PDF_SERVICES_CLIENT_ID
      || process.env.PDF_SERVICES_API_KEY
      || process.env.ADOBE_PDF_SERVICES_API_KEY
      || envValues.PDF_SERVICES_CLIENT_ID
      || envValues.ADOBE_PDF_SERVICES_CLIENT_ID
      || envValues.PDF_SERVICES_API_KEY
      || envValues.ADOBE_PDF_SERVICES_API_KEY
      || nested.client_id
      || nested.clientId
      || "",
    clientSecret: process.env.PDF_SERVICES_CLIENT_SECRET
      || process.env.ADOBE_PDF_SERVICES_CLIENT_SECRET
      || envValues.PDF_SERVICES_CLIENT_SECRET
      || envValues.ADOBE_PDF_SERVICES_CLIENT_SECRET
      || nested.client_secret
      || nested.clientSecret
      || "",
  }
}

export async function pdfServicesConfigured(options = {}) {
  const credentials = await readCredentials(options)
  return Boolean(credentials.clientId && credentials.clientSecret)
}

function sdk() {
  try {
    return require("@adobe/pdfservices-node-sdk")
  } catch (error) {
    throw new Error(`Adobe PDF Services SDK is not installed. Run npm install. ${error.message}`)
  }
}

function safeEntryPath(root, entryName) {
  const relative = entryName.replaceAll("\\", "/")
  const target = path.resolve(root, relative)
  const rootWithSeparator = `${path.resolve(root)}${path.sep}`
  if (target !== path.resolve(root) && !target.startsWith(rootWithSeparator)) {
    throw new Error(`Adobe PDF Services returned an unsafe archive entry: ${entryName}`)
  }
  return target
}

async function extractZip(zipFile, outputDirectory) {
  const AdmZip = require("adm-zip")
  const archive = new AdmZip(zipFile)
  const files = []
  for (const entry of archive.getEntries()) {
    if (entry.isDirectory) continue
    const target = safeEntryPath(outputDirectory, entry.entryName)
    await ensureDir(path.dirname(target))
    await fs.writeFile(target, entry.getData())
    files.push(target)
  }
  return files
}

function pageNumber(element) {
  const value = element?.Page ?? element?.page
  if (Number.isFinite(Number(value))) return Math.max(1, Number(value))
  const match = String(element?.Path || "").match(/page\[?(\d+)\]?/i)
  return match ? Number(match[1]) + 1 : 1
}

function elementType(element) {
  const pathValue = String(element?.Path || "")
  const match = pathValue.match(/\/(H\d|Title|P|L|Li|Lbody|Figure|Table|TD|TH|Aside|Footnote|Reference)(?:\[|\/|$)/i)
  return match ? match[1].toLowerCase() : "element"
}

function textFromStructuredData(data) {
  const elements = Array.isArray(data?.elements) ? data.elements : []
  const lines = []
  let currentPage = null
  for (const element of elements) {
    if (typeof element?.Text !== "string" || !element.Text.trim()) continue
    const page = pageNumber(element)
    if (page !== currentPage) {
      if (lines.length) lines.push("")
      lines.push(`[[PAGE ${page}]]`)
    currentPage = page
    }
    lines.push(element.Text)
  }
  const pageCount = Array.isArray(data?.pages) ? data.pages.length : 0
  for (let page = (currentPage || 0) + 1; page <= pageCount; page += 1) {
    if (lines.length) lines.push("")
    lines.push(`[[PAGE ${page}]]`)
  }
  return lines.join("\n")
}

function findArtifact(rawPath, artifacts) {
  const normalized = String(rawPath || "").replaceAll("\\", "/")
  const basename = path.basename(normalized)
  return artifacts.find((file) => String(file).replaceAll("\\", "/").endsWith(normalized))
    || artifacts.find((file) => path.basename(file) === basename)
    || null
}

function placementForElement(element, data) {
  const bounds = element?.Bounds
  const page = pageNumber(element)
  const pageInfo = Array.isArray(data?.pages) ? data.pages[page - 1] : null
  if (!Array.isArray(bounds) || bounds.length < 4 || !pageInfo?.width || !pageInfo?.height) return null
  const [left, bottom, right, top] = bounds.map(Number)
  const width = Number(pageInfo.width)
  const height = Number(pageInfo.height)
  if (![left, bottom, right, top, width, height].every(Number.isFinite) || right <= left || top <= bottom) return null
  return {
    x: Math.max(0, Math.min(1, left / width)),
    y: Math.max(0, Math.min(1, (height - top) / height)),
    width: Math.max(0, Math.min(1, (right - left) / width)),
    height: Math.max(0, Math.min(1, (top - bottom) / height)),
  }
}

function assetManifestFromStructuredData(data, artifacts, source) {
  const assets = []
  const elements = Array.isArray(data?.elements) ? data.elements : []
  for (const [index, element] of elements.entries()) {
    const filePaths = Array.isArray(element?.FilePaths) ? element.FilePaths : []
    for (const rawPath of filePaths) {
      const file = findArtifact(rawPath, artifacts)
      if (!file) continue
      const type = elementType(element)
      assets.push({
        id: `pdf-${type}-${String(index + 1).padStart(4, "0")}`,
        name: path.basename(file),
        file,
        kind: path.extname(file).slice(1).toLowerCase() || "asset",
        role: type === "table" ? "data" : "illustration",
        source,
        slideIndex: pageNumber(element),
        anchor: type === "table" ? "text" : "illustration",
        placement: placementForElement(element, data),
        bounds: element.Bounds || null,
        sourcePath: rawPath,
      })
    }
  }
  return { version: 1, provider: "adobe-pdf-services", source, assets }
}

export function normalizeStructuredData(data, { source = null, artifacts = [], provider = "adobe-pdf-services" } = {}) {
  const elements = Array.isArray(data?.elements) ? data.elements : []
  const pages = Array.isArray(data?.pages) ? data.pages : []
  const layout = elements.map((element, index) => ({
    index,
    type: elementType(element),
    page: pageNumber(element),
    path: element.Path || null,
    text: typeof element.Text === "string" ? element.Text : null,
    bounds: element.Bounds || null,
    font: element.Font || null,
    textSize: element.TextSize || null,
    attributes: element.Attributes || null,
    filePaths: element.FilePaths || [],
  }))
  return {
    source,
    provider,
    text: textFromStructuredData(data),
    format: "pdf",
    pages: pages.length || Math.max(1, ...layout.map((item) => item.page)),
    structuredData: data,
    layout,
    assets: artifacts.filter((file) => /(?:^|[\\/])figures[\\/]|(?:^|[\\/])tables[\\/]/i.test(file)),
    artifacts,
  }
}

export async function extractWithPdfServices(input, { artifactDirectory = null } = {}) {
  const source = path.resolve(input)
  const credentials = await readCredentials()
  if (!credentials.clientId || !credentials.clientSecret) {
    throw new Error("Adobe PDF Services credentials are missing. Set PDF_SERVICES_CLIENT_ID and PDF_SERVICES_CLIENT_SECRET in C:\\IA\\flujo\\.env, or set PDF_SERVICES_CREDENTIALS to the downloaded credential JSON.")
  }

  const outputDirectory = path.resolve(artifactDirectory || path.join(TOOLKIT_ROOT, "cache", "pdf-services", path.basename(source, path.extname(source))))
  await ensureDir(outputDirectory)
  const Adobe = sdk()
  const serviceCredentials = new Adobe.ServicePrincipalCredentials({
    clientId: credentials.clientId,
    clientSecret: credentials.clientSecret,
  })
  const pdfServices = new Adobe.PDFServices({ credentials: serviceCredentials })
  const readStream = createReadStream(source)
  try {
    const inputAsset = await pdfServices.upload({ readStream, mimeType: Adobe.MimeType.PDF })
    const params = new Adobe.ExtractPDFParams({
      elementsToExtract: [Adobe.ExtractElementType.TEXT, Adobe.ExtractElementType.TABLES],
      elementsToExtractRenditions: [Adobe.ExtractRenditionsElementType.FIGURES, Adobe.ExtractRenditionsElementType.TABLES],
      addCharInfo: true,
      getStylingInfo: true,
    })
    const job = new Adobe.ExtractPDFJob({ inputAsset, params })
    const pollingURL = await pdfServices.submit({ job })
    const response = await pdfServices.getJobResult({ pollingURL, resultType: Adobe.ExtractPDFResult })
    const resultAsset = response.result.resource
    const streamAsset = await pdfServices.getContent({ asset: resultAsset })
    const zipPath = path.join(outputDirectory, "pdf-services-extract.zip")
    await pipeline(streamAsset.readStream, createWriteStream(zipPath))
    const artifacts = await extractZip(zipPath, outputDirectory)
    const structuredPath = path.join(outputDirectory, "structuredData.json")
    const structuredData = JSON.parse(await fs.readFile(structuredPath, "utf8"))
    const allArtifacts = [zipPath, ...artifacts]
    const normalized = normalizeStructuredData(structuredData, { source, artifacts: allArtifacts })
    const assetManifest = assetManifestFromStructuredData(structuredData, artifacts, source)
    const assetManifestPath = path.join(outputDirectory, "asset-manifest.json")
    await fs.writeFile(assetManifestPath, `${JSON.stringify(assetManifest, null, 2)}\n`, "utf8")
    return { ...normalized, assetManifest, assetManifestPath, artifacts: [...allArtifacts, assetManifestPath] }
  } finally {
    readStream.destroy()
  }
}

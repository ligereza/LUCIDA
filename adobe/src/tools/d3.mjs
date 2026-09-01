import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { asNumber, ensureDir, resolveInput, resolveOutput } from "../utils.mjs"

const D3_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "d3")
let d3Promise

async function loadD3() {
  d3Promise ||= import(pathToFileURL(path.join(D3_ROOT, "src", "index.js")).href)
  return d3Promise
}

const escapeXml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean)
  const headers = lines.shift().split(",").map((item) => item.trim())
  return lines.map((line) => {
    const values = line.split(",").map((item) => item.trim())
    return Object.fromEntries(headers.map((key, index) => [key, values[index]]))
  })
}

export async function d3BarChart(input, output, options = {}) {
  const d3 = await loadD3()
  const source = resolveInput(input)
  const text = await fs.readFile(source, "utf8")
  const data = path.extname(source).toLowerCase() === ".csv" ? parseCsv(text) : JSON.parse(text)
  if (!Array.isArray(data) || !data.length) throw new Error("D3 chart input must be a non-empty JSON array or CSV")
  const xKey = options.x || Object.keys(data[0])[0]
  const yKey = options.y || Object.keys(data[0])[1]
  const width = asNumber(options.width, 900)
  const height = asNumber(options.height, 500)
  const margin = { top: 40, right: 24, bottom: 64, left: 64 }
  const chartHeight = height - margin.top - margin.bottom
  const max = Math.max(d3.max(data, (row) => asNumber(row[yKey], 0)) || 0, 1)
  const x = d3.scaleBand()
    .domain(data.map((row) => String(row[xKey])))
    .range([margin.left, width - margin.right])
    .padding(0.12)
  const y = d3.scaleLinear()
    .domain([0, max])
    .range([height - margin.bottom, margin.top])
  const bars = data.map((row) => {
    const value = asNumber(row[yKey], 0)
    const yPosition = y(value)
    return `<rect x="${x(String(row[xKey])).toFixed(2)}" y="${yPosition.toFixed(2)}" width="${x.bandwidth().toFixed(2)}" height="${(y(0) - yPosition).toFixed(2)}" rx="4" fill="${escapeXml(options.color || "#38bdf8")}" data-value="${value}"/>\n<text x="${(x(String(row[xKey])) + x.bandwidth() / 2).toFixed(2)}" y="${height - 28}" text-anchor="middle" font-size="12">${escapeXml(row[xKey])}</text>`
  }).join("\n")
  const title = options.title || `${yKey} by ${xKey}`
  const description = options.description || `D3 bar chart with ${data.length} data points.`
  const svg = `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="svg-title svg-desc"><title id="svg-title">${escapeXml(title)}</title><desc id="svg-desc">${escapeXml(description)}</desc><rect width="100%" height="100%" fill="${escapeXml(options.background || "#0f172a")}"/><g fill="#e5e7eb" font-family="system-ui"><text x="${margin.left}" y="24" font-size="18">${escapeXml(title)}</text><line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="#64748b"/>${bars}</g></svg>\n`
  const target = resolveOutput(output, options)
  await ensureDir(path.dirname(target))
  await fs.writeFile(target, svg, "utf8")
  return { svg: target, xKey, yKey, rows: data.length, engine: "d3-local", d3Root: D3_ROOT }
}

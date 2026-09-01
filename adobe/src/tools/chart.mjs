import fs from "node:fs/promises"
import path from "node:path"
import { asNumber, ensureDir, resolveInput, resolveOutput } from "../utils.mjs"

const escapeXml = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;")

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean)
  const headers = lines.shift().split(",").map((item) => item.trim())
  return lines.map((line) => {
    const values = line.split(",").map((item) => item.trim())
    return Object.fromEntries(headers.map((key, index) => [key, values[index]]))
  })
}

export async function barChart(input, output, options = {}) {
  const source = resolveInput(input)
  const text = await fs.readFile(source, "utf8")
  const data = path.extname(source).toLowerCase() === ".csv" ? parseCsv(text) : JSON.parse(text)
  if (!Array.isArray(data) || !data.length) throw new Error("Chart input must be a non-empty JSON array or CSV")
  const xKey = options.x || Object.keys(data[0])[0]
  const yKey = options.y || Object.keys(data[0])[1]
  const width = asNumber(options.width, 900)
  const height = asNumber(options.height, 500)
  const margin = { top: 40, right: 24, bottom: 64, left: 64 }
  const max = Math.max(...data.map((row) => asNumber(row[yKey], 0)), 1)
  const chartWidth = width - margin.left - margin.right
  const chartHeight = height - margin.top - margin.bottom
  const band = chartWidth / data.length
  const bars = data.map((row, index) => {
    const value = asNumber(row[yKey], 0)
    const barHeight = (value / max) * chartHeight
    const x = margin.left + index * band + band * 0.12
    const y = margin.top + chartHeight - barHeight
    return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${(band * 0.76).toFixed(2)}" height="${barHeight.toFixed(2)}" rx="4" fill="${escapeXml(options.color || "#38bdf8")}" data-value="${value}"/>\n<text x="${(x + band * 0.38).toFixed(2)}" y="${height - 28}" text-anchor="middle" font-size="12">${escapeXml(row[xKey])}</text>`
  }).join("\n")
  const title = options.title || `${yKey} by ${xKey}`
  const description = options.description || `Bar chart with ${data.length} data points.`
  const svg = `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="svg-title svg-desc"><title id="svg-title">${escapeXml(title)}</title><desc id="svg-desc">${escapeXml(description)}</desc><rect width="100%" height="100%" fill="${escapeXml(options.background || "#0f172a")}"/><g fill="#e5e7eb" font-family="system-ui"><text x="${margin.left}" y="24" font-size="18">${escapeXml(title)}</text><line x1="${margin.left}" y1="${margin.top + chartHeight}" x2="${width - margin.right}" y2="${margin.top + chartHeight}" stroke="#64748b"/>${bars}</g></svg>\n`
  const target = resolveOutput(output, options)
  await ensureDir(path.dirname(target))
  await fs.writeFile(target, svg, "utf8")
  return { svg: target, xKey, yKey, rows: data.length }
}

export async function animateChart(input, output, durationMs = 1200, options = {}) {
  const source = resolveInput(input)
  const svg = await fs.readFile(source, "utf8")
  const duration = Math.max(100, asNumber(durationMs, 1200))
  const style = `<style>@keyframes agent-chart-bars{from{transform:scaleY(0)}to{transform:scaleY(1)}}.chart-bar-animated{transform-box:fill-box;transform-origin:center bottom;animation:agent-chart-bars ${duration}ms ease-out both}@media (prefers-reduced-motion:reduce){.chart-bar-animated{animation:none}}</style>`
  const result = svg
    .replace(/<rect\b([^>]*\bdata-value=["'][^"']+["'][^>]*)>/gi, (_match, attributes) => {
      const updated = attributes.includes("class=")
        ? attributes.replace(/class=["']([^"']*)["']/i, 'class="$1 chart-bar-animated"')
        : `${attributes} class="chart-bar-animated"`
      return `<rect${updated}>`
    })
    .replace(/<\/svg>\s*$/i, `${style}</svg>\n`)
  const target = resolveOutput(output, options)
  await ensureDir(path.dirname(target))
  await fs.writeFile(target, result, "utf8")
  return { svg: target, durationMs: duration }
}

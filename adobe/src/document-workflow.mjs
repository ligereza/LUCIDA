import fs from "node:fs/promises"
import path from "node:path"
import { createJob, updateJob, writeSummary } from "./jobs.mjs"
import { enqueueAdobe } from "./adapters/adobe.mjs"
import { runBlender } from "./adapters/blender.mjs"
import { ensureDir, readJson, resolveInput, resolveOutput, writeJson } from "./utils.mjs"
import { extractDocument, segmentDocument } from "./tools/document.mjs"
import { validateSvg } from "./tools/svg.mjs"
import { normalizeDesign } from "./tools/design.mjs"
import { planLayouts, wrapText } from "./tools/layout.mjs"

const escape = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;")

function iconName(keyword) {
  const value = String(keyword || "").toLowerCase()
  if (/agua|hidrat|bebida|fluido/.test(value)) return "water"
  if (/coraz|cuidado|comunidad|consent|care|community|heart/.test(value)) return "heart"
  if (/riesgo|crít|peligro|accidente|sobredosis|warning|emergency/.test(value)) return "warning"
  if (/droga|sustancia|mdma|coca|ketamina|metanf|viagra|substance|pill/.test(value)) return "pill"
  if (/hablar|conversa|inform|confianza|communication|speech/.test(value)) return "speech"
  return "spark"
}

function iconSvg(name, x, y, size, color) {
  const stroke = Math.max(2, size * 0.07)
  const common = `fill="none" stroke="${color}" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round"`
  const body = {
    water: `<path d="M0 -${size * .42} C-${size * .25} -${size * .12} -${size * .24} ${size * .2} 0 ${size * .42} C${size * .24} ${size * .2} ${size * .25} -${size * .12} 0 -${size * .42}Z"/>`,
    heart: `<path d="M0 ${size * .38} L-${size * .38} -${size * .02} C-${size * .62} -${size * .3} -${size * .22} -${size * .56} 0 -${size * .28} C${size * .22} -${size * .56} ${size * .62} -${size * .3} ${size * .38} -${size * .02}Z"/>`,
    warning: `<path d="M0 -${size * .45} L${size * .45} ${size * .4} H-${size * .45} Z"/><path d="M0 -${size * .18} V${size * .1} M0 ${size * .25} V${size * .26}"/>`,
    pill: `<rect x="-${size * .16}" y="-${size * .45}" width="${size * .32}" height="${size * .9}" rx="${size * .16}" transform="rotate(45)"/><path d="M-${size * .14} -${size * .14} L${size * .14} ${size * .14}"/>`,
    speech: `<path d="M-${size * .42} -${size * .28} H${size * .42} V${size * .22} H${size * .08} L-${size * .18} ${size * .46} V${size * .22} H-${size * .42} Z"/>`,
    spark: `<path d="M0 -${size * .48} L${size * .12} -${size * .12} L${size * .48} 0 L${size * .12} ${size * .12} L0 ${size * .48} L-${size * .12} ${size * .12} L-${size * .48} 0 L-${size * .12} -${size * .12} Z"/>`,
  }[name] || `<circle cx="0" cy="0" r="${size * .35}"/>`
  return `<g transform="translate(${x} ${y})" class="generated-icon" aria-label="${escape(name)}">${body}</g>`
}

function sceneIcons(item, design, art) {
  if (design.iconMode === "none") return ""
  const configured = Array.isArray(design.icons) ? design.icons : []
  const names = configured.length ? configured.map((icon) => icon.name) : [...new Set([...(item.keywords || []), ...(item.semanticTags || [])].map(iconName))]
  return names.slice(0, 4).map((name, index) => {
    const icon = configured[index] || {}
    const x = icon.x != null ? icon.x * design.canvas.width : art.x + art.width * (0.2 + index * 0.2)
    const y = icon.y != null ? icon.y * design.canvas.height : art.y + art.height * (0.22 + (index % 2) * 0.5)
    const size = icon.size != null ? icon.size * Math.min(design.canvas.width, design.canvas.height) : Math.min(art.width, art.height) * 0.08
    return iconSvg(name, x, y, size, design.colors.highlight)
  }).join("")
}

function textLinesSvg(lines, x, y, lineHeight, className, anchor = "start") {
  return `<text class="${className}" x="${x}" y="${y}" text-anchor="${anchor}">${lines.map((line, index) => `<tspan x="${x}" dy="${index ? lineHeight : 0}">${escape(line)}</tspan>`).join("")}</text>`
}

function sceneSvg(item, index, design) {
  const { width, height } = design.canvas
  const { top, right, bottom, left } = design.margins
  const { background, accent, highlight, text, muted } = design.colors
  const { titleFont, titleSize, summaryFont, summarySize, footerSize } = design.typography
  const layout = item.layout || design.layout
  const metrics = item.textMetrics || {}
  const bodySize = Number(metrics.recommendedSummarySize) || summarySize
  const motion = design.animation === "none" ? ".orbit,.core,.spark{animation:none!important}" : design.animation === "float" ? ".orbit{animation:none}.core{animation:none}" : design.animation === "rotate" ? ".core{animation:none}.spark{animation:none}" : ""
  const textBox = { x: layout.text.x * width, y: layout.text.y * height, width: layout.text.width * width, height: layout.text.height * height }
  const art = { x: layout.illustration.x * width, y: layout.illustration.y * height, width: layout.illustration.width * width, height: layout.illustration.height * height }
  const artCenterX = art.x + art.width / 2
  const artCenterY = art.y + art.height / 2
  const radius = Math.min(art.width, art.height) * 0.36
  const delay = `${index * -0.17}s`
  const innerWidth = Math.max(80, textBox.width - 36)
  const charsPerLine = Math.max(10, innerWidth / (bodySize * 0.52))
  const titleLines = wrapText(item.title, Math.max(8, innerWidth / (titleSize * 0.54)))
  const bodyLines = wrapText(item.sourceText || item.summary || "", charsPerLine)
  const pad = 18
  const titleY = textBox.y + titleSize + pad
  const bodyY = titleY + titleLines.length * titleSize * 1.12 + bodySize * 0.72
  const anchor = layout.textAlignment === "center" ? "middle" : "start"
  const textX = layout.textAlignment === "center" ? textBox.x + textBox.width / 2 : textBox.x + pad
  return `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" data-preset="${escape(design.preset)}" data-animation="${escape(design.animation)}" data-layout="${escape(layout.variant || layout.mode)}" data-theme="${escape(item.theme || "general")}" data-text-density="${escape(metrics.density ?? "")}" data-margins="${top} ${right} ${bottom} ${left}" role="img" aria-labelledby="svg-title svg-desc"><title id="svg-title">${escape(item.title)}</title><desc id="svg-desc">${escape(item.visual)} · ${escape(layout.visualRole || "")}</desc><style>svg{background:${background}}.orbit{fill:none;stroke:${accent};stroke-width:${Math.max(2, width / 540)};opacity:.35;transform-origin:${artCenterX}px ${artCenterY}px;animation:spin 8s linear infinite;animation-delay:${delay}}.core{fill:${accent};opacity:.88;transform-origin:${artCenterX}px ${artCenterY}px;animation:breathe 2.8s ease-in-out infinite alternate;animation-delay:${delay}}.spark{fill:${highlight};animation:float 3.2s ease-in-out infinite alternate;animation-delay:${delay}}.label{font:700 ${titleSize}px ${titleFont};fill:${highlight}}.body{font:${bodySize}px ${summaryFont};fill:${text};opacity:.92}.footer{font:${footerSize}px ${summaryFont};fill:${muted};opacity:.85}.generated-icon{animation:float 3.2s ease-in-out infinite alternate;animation-delay:${delay}}@keyframes spin{to{transform:rotate(360deg)}}@keyframes breathe{to{transform:scale(1.16);opacity:1}}@keyframes float{to{transform:translateY(-${Math.max(12, height / 70)}px)}}${motion}@media(prefers-reduced-motion:reduce){.orbit,.core,.spark,.generated-icon{animation:none!important}}</style><rect width="${width}" height="${height}" fill="${background}"/><rect id="text-zone" data-zone="text" x="${textBox.x}" y="${textBox.y}" width="${textBox.width}" height="${textBox.height}" rx="${Math.max(12, width / 70)}" fill="${background}" opacity="${layout.overlap ? ".78" : ".28"}" stroke="${muted}" stroke-opacity=".22"/><rect id="illustration-zone" data-zone="illustration" x="${art.x}" y="${art.y}" width="${art.width}" height="${art.height}" rx="${Math.max(12, width / 70)}" fill="${accent}" opacity=".06" stroke="${accent}" stroke-opacity=".35"/><circle class="orbit" cx="${artCenterX}" cy="${artCenterY}" r="${radius}"/><circle class="orbit" cx="${artCenterX}" cy="${artCenterY}" r="${radius * .65}" style="animation-direction:reverse"/><circle class="core" cx="${artCenterX}" cy="${artCenterY}" r="${radius * .37}"/><circle class="spark" cx="${art.x + art.width * .18}" cy="${art.y + art.height * .18}" r="${Math.max(6, width / 100)}"/><circle class="spark" cx="${art.x + art.width * .82}" cy="${art.y + art.height * .82}" r="${Math.max(5, width / 120)}"/>${sceneIcons(item, design, art)}${textLinesSvg(titleLines, textX, titleY, titleSize * 1.12, "label", anchor)}${textLinesSvg(bodyLines, textX, bodyY, bodySize * 1.36, "body", anchor)}<text class="footer" x="${left}" y="${height - bottom}">ESCENA ${String(index + 1).padStart(2, "0")} · ${escape(item.theme || "general")}</text></svg>`
}

function postHtml(parts, title, design) {
  const cards = parts.map((part) => `<article><div class="art">${part.svg.replace(/^<\?xml[^>]*\?>/, "")}</div><h2>${escape(part.title)}</h2><p>${escape(part.summary)}</p></article>`).join("\n")
  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)}</title><style>body{margin:0;background:#08080b;color:#f4f4f5;font-family:system-ui,sans-serif}header{max-width:1100px;margin:auto;padding:48px 24px 24px}h1{font-size:clamp(30px,6vw,64px);margin:0 0 12px}header p{color:#9ca3af;max-width:70ch}main{max-width:1100px;margin:auto;padding:0 24px 80px;display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:22px}article{background:#111118;border:1px solid #272733;border-radius:18px;padding:14px}.art{background:#000;border-radius:12px;overflow:hidden}.art svg{display:block;width:100%;height:auto}h2{font-size:18px;margin:16px 4px 8px}article p{color:#a1a1aa;line-height:1.5;margin:0 4px 8px}.spec{font:12px ui-monospace,monospace;color:#71717a}</style></head><body><header><p>PUBLICACIÓN ILUSTRADA · ${parts.length} PARTES</p><h1>${escape(title)}</h1><p>Formato ${design.canvas.width}×${design.canvas.height}px · márgenes ${design.margins.top}/${design.margins.right}/${design.margins.bottom}/${design.margins.left}px · preset ${escape(design.preset)}</p></header><main>${cards}</main></body></html>`
}

export async function documentToAnimatedPost({ document, title = null, maxParts = 12, minChars = 180, blender = false, adobeApp = null, splitBy = "auto", splitPlan = null, design = null, designPath = null, pdfProvider = "local" } = {}) {
  const job = await createJob("document-to-animated-post", { document, title, maxParts, minChars, blender, adobeApp, splitBy, splitPlan, design, designPath, pdfProvider })
  try {
    const extracted = await extractDocument(document, { pdfProvider, artifactDirectory: path.join(job.directory, "work", "pdf-services") })
    const staged = path.join(job.directory, "input", path.basename(extracted.source))
    await fs.copyFile(extracted.source, staged)
    await updateJob(job.id, { state: "running", inputs: [staged], currentTool: "document.segment" })
    const plan = typeof splitPlan === "string" ? await readJson(resolveInput(splitPlan, { roots: ["C:\\IA\\svg", "C:\\IA\\flujo", "C:\\Users\\issvk\\claude_sesiones_recuperadas"] })) : splitPlan
    const designInput = designPath ? await readJson(resolveInput(designPath, { roots: ["C:\\IA\\svg", "C:\\IA\\flujo", "C:\\Users\\issvk\\claude_sesiones_recuperadas"] })) : (design || {})
    const designSpec = normalizeDesign(designInput)
    const parts = segmentDocument(extracted.text, { maxParts, minChars, splitBy, splitPlan: plan, pages: extracted.pages })
    const postTitle = title || path.basename(extracted.source, path.extname(extracted.source))
    const plannedParts = planLayouts(parts, designSpec)
    await writeJson(path.join(job.directory, "work", "sections.json"), plannedParts)
    const outputParts = path.join(job.directory, "output", "parts")
    await ensureDir(outputParts)
    const storyboardPath = path.join(job.directory, "work", "storyboard.json")
    const storyboard = {
      title: postTitle,
      format: extracted.format,
      splitBy,
      splitPlan: plan,
      design: designSpec,
      parts: plannedParts.map((item) => ({ ...item, assets: [{ id: `${item.id}-scene`, file: path.join(outputParts, `${item.id}.svg`), kind: "svg", role: "scene", slideIndex: plannedParts.indexOf(item) + 1, anchor: "full", importMode: "curves" }] })),
      ...(extracted.assetManifestPath ? { assetManifest: extracted.assetManifestPath } : {}),
    }
    await writeJson(storyboardPath, storyboard)
    const files = []
    if (Array.isArray(extracted.artifacts)) files.push(...extracted.artifacts)
    const renderedParts = []
    for (const [index, item] of plannedParts.entries()) {
      const svg = sceneSvg(item, index, designSpec)
      const output = path.join(outputParts, `${item.id}.svg`)
      await fs.writeFile(output, svg, "utf8")
      const validation = await validateSvg(output)
      if (!validation.valid) throw new Error(`Generated SVG is invalid for ${item.id}`)
      files.push(output)
      renderedParts.push({ ...item, svg })
    }
    const post = path.join(job.directory, "output", "post.html")
    const manifest = path.join(job.directory, "output", "manifest.json")
    await fs.writeFile(post, postHtml(renderedParts, postTitle, designSpec), "utf8")
    await writeJson(manifest, { title: postTitle, source: staged, storyboard: storyboardPath, extraction: { provider: extracted.provider || "local", pages: extracted.pages, layout: extracted.layout || null, assets: extracted.assets || [], assetManifest: extracted.assetManifestPath || null }, design: designSpec, parts: plannedParts.map((item) => ({ ...item, output: `parts/${item.id}.svg` })) })
    files.push(post, manifest)
    if (blender) {
      const scene = path.join(job.directory, "output", "selected-scene.blend")
      const render = path.join(job.directory, "output", "selected-scene.png")
      const result = await runBlender({ operation: "layout-scene", spec: storyboardPath, output: scene, renderOutput: render })
      files.push(...result.files)
    }
    if (adobeApp) {
      for (const svgFile of files.filter((file) => file.endsWith(".svg"))) {
        const adobe = await enqueueAdobe({ app: adobeApp, operation: "import-svg", input: svgFile, jobId: job.id, options: {} })
        files.push(adobe.command)
      }
    }
    const state = adobeApp ? "waiting-for-adobe" : "completed"
    await updateJob(job.id, { state, files, currentTool: null, partCount: plannedParts.length, format: extracted.format })
    await writeSummary(job.id, `# document-to-animated-post\n\n- Input: ${staged}\n- Format: ${extracted.format}\n- Parts: ${plannedParts.length}\n- Canvas: ${designSpec.canvas.width}x${designSpec.canvas.height}px\n- Margins: ${designSpec.margins.top}/${designSpec.margins.right}/${designSpec.margins.bottom}/${designSpec.margins.left}px\n- Auto layout: ${designSpec.autoLayout}\n- Blender: ${blender}\n- Adobe: ${adobeApp || "none"}\n- State: ${state}\n\n## Outputs\n\n${files.map((file) => `- ${file}`).join("\n")}`)
    return { jobId: job.id, directory: job.directory, files, parts: plannedParts.length, format: extracted.format, state }
  } catch (error) {
    await updateJob(job.id, { state: "failed", errors: [error.message], currentTool: null })
    await writeSummary(job.id, `# document-to-animated-post\n\n- State: failed\n- Error: ${error.message}`)
    throw error
  }
}

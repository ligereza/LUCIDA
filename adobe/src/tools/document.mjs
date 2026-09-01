import fs from "node:fs/promises"
import path from "node:path"
import { execFile } from "node:child_process"
import { promisify } from "node:util"
import { fileURLToPath } from "node:url"
import { DEFAULT_INPUT_ROOTS, resolveInput, slugify } from "../utils.mjs"
import { extractWithPdfServices, pdfServicesConfigured } from "../adapters/pdf-services.mjs"

const execFileAsync = promisify(execFile)
const extractScript = fileURLToPath(new URL("../../adapters/document/extract.py", import.meta.url))
const stopwords = new Set("para pero como desde este esta estos estas una uno unos unas que con por del las los sobre entre hacia cuando donde quien sido será sus son más muy también solo cada puede parte texto documento porque cómo qué ella ellos ello así sin al de la en y o e se su lo no ya ha han fue era hay".split(/\s+/))

function cleanText(value) {
  return String(value || "")
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<h[1-6][^>]*>/gi, "\n")
    .replace(/<\/h[1-6]>/gi, "\n")
    .replace(/<br\s*\/?\s*>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/\r/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}

const encodingFixes = new Map([
  ["m�s", "más"], ["M�s", "Más"], ["informaci�n", "información"], ["Informaci�n", "Información"],
  ["C�mo", "Cómo"], ["c�mo", "cómo"], ["�Qu�", "¿Qué"], ["Qu�", "Qué"], ["qu�", "qué"], ["Reducci�n", "Reducción"], ["reducci�n", "reducción"],
  ["p�blic", "públic"], ["org�as", "orgías"], ["�xtasis", "éxtasis"], ["a�os", "años"], ["sesi�n", "sesión"],
  ["m�ltiples", "múltiples"], ["transmisi�n", "transmisión"], ["f�sicos", "físicos"], ["despu�s", "después"], ["com�nmente", "comúnmente"], ["pr�cticas", "prácticas"], ["Mant�n", "Mantén"], ["mant�n", "mantén"], ["l�minas", "láminas"],
  ["consumir�s", "consumirás"], ["test�alas", "testéalas"], ["composici�n", "composición"], ["r�pidamente", "rápidamente"], ["hipotensi�n", "hipotensión"], ["f�rmacos", "fármacos"], ["dosificaci�n", "dosificación"], ["escr�benos", "escríbenos"], ["comp�rtelo", "compártelo"],
  ["depresi�n", "depresión"], ["combinaci�n", "combinación"], ["presi�n", "presión"], ["card�aco", "cardíaco"],
  ["vasodilataci�n", "vasodilatación"], ["autonom�a", "autonomía"], ["l�mites", "límites"], ["mant�n", "mantén"],
  ["comunicaci�n", "comunicación"], ["Coca�na", "Cocaína"], ["m�dico", "médico"], ["M�dico", "Médico"],
  ["a�sla", "aísla"], ["decisi�n", "decisión"], ["cr�tico", "crítico"], ["isot�nicas", "isotónicas"],
  ["alg�n", "algún"], ["p�rdida", "pérdida"], ["�comedown�", "“comedown”"], ["� Fiestas", "• Fiestas"], ["� Encuentros", "• Encuentros"], ["� Cruising", "• Cruising"],
])

function repairEncoding(value) {
  let text = String(value || "")
  for (const [broken, fixed] of encodingFixes) text = text.replaceAll(broken, fixed)
  return text
}

export async function extractDocument(input, { pdfProvider = "local", artifactDirectory = null } = {}) {
  const source = resolveInput(input, { roots: [...DEFAULT_INPUT_ROOTS, "C:\\IA\\flujo", "C:\\Users\\issvk\\claude_sesiones_recuperadas"] })
  const extension = path.extname(source).toLowerCase()
  if ([".txt", ".md", ".html", ".htm"].includes(extension)) return { source, text: cleanText(await fs.readFile(source, "utf8")), format: extension.slice(1), pages: 1 }
  if ([".docx", ".pdf"].includes(extension)) {
    if (extension === ".pdf" && ["adobe", "auto"].includes(pdfProvider)) {
      const configured = await pdfServicesConfigured()
      if (pdfProvider === "adobe" || configured) {
        const extracted = await extractWithPdfServices(source, { artifactDirectory })
        return { ...extracted, text: cleanText(repairEncoding(extracted.text)) }
      }
    }
    const { stdout } = await execFileAsync(process.env.DOCUMENT_PYTHON || "python", [extractScript, source], { maxBuffer: 20 * 1024 * 1024 })
    const extracted = JSON.parse(stdout)
    return { source, text: cleanText(repairEncoding(extracted.text)), format: extension.slice(1), pages: extracted.pages || 1 }
  }
  throw new Error(`Unsupported document format: ${extension || "unknown"}. Use PDF, DOCX, HTML or TXT.`)
}

function words(text) {
  return text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").match(/[a-záéíóúñü]{5,}/gi) || []
}

function keywords(text, limit = 5) {
  const counts = new Map()
  for (const word of words(text)) {
    if (stopwords.has(word)) continue
    counts.set(word, (counts.get(word) || 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, limit).map(([word]) => word)
}

function part(title, text, index) {
  const compact = text.replace(/\s+/g, " ").trim()
  const key = keywords(compact)
  const lower = compact.toLowerCase()
  const mood = /noche|sombra|duelo|crisis|miedo|ilegal|dolor/.test(lower) ? "nocturno" : /futuro|tecnolog|cambio|revol|movimiento/.test(lower) ? "eléctrico" : "luminoso"
  const palette = mood === "nocturno" ? ["#090712", "#7c3aed", "#f0abfc"] : mood === "eléctrico" ? ["#07131b", "#22d3ee", "#facc15"] : ["#11120b", "#d7ff2e", "#f5f5dc"]
  return {
    id: `${String(index + 1).padStart(2, "0")}-${slugify(title)}`,
    title: title || `Parte ${index + 1}`,
    sourceText: compact,
    summary: compact.length > 180 ? `${compact.slice(0, 177).replace(/\s+\S*$/, "")}…` : compact,
    keywords: key,
    mood,
    visual: `composición ${mood} con núcleo pulsante y órbitas para ${key.join(", ") || "la idea central"}`,
    palette,
    animation: mood === "eléctrico" ? "rotate" : mood === "nocturno" ? "pulse" : "float",
  }
}

function plannedParts(text, plan) {
  const source = String(text || "")
  const parts = []
  let cursor = 0
  for (const [index, item] of plan.entries()) {
    const marker = String(item.start || item.contains || "")
    if (!marker) throw new Error(`Split plan part ${index + 1} needs a start or contains marker`)
    const start = source.toLowerCase().indexOf(marker.toLowerCase(), cursor)
    if (start < 0) throw new Error(`Split marker not found: ${marker}`)
    if (start > cursor && index === 0 && source.slice(cursor, start).trim()) parts.push({ title: "Introducción", text: source.slice(cursor, start) })
    const nextMarker = plan[index + 1]?.start || plan[index + 1]?.contains
    const next = nextMarker ? source.toLowerCase().indexOf(String(nextMarker).toLowerCase(), start + marker.length) : -1
    parts.push({ title: item.title || marker, text: source.slice(start, next < 0 ? source.length : next) })
    cursor = next < 0 ? source.length : next
  }
  return parts
}

export function segmentDocument(text, { maxParts = 12, minChars = 180, splitBy = "auto", splitPlan = null, pages = 1 } = {}) {
  const pageChunks = String(text || "").split(/\[\[PAGE\s+\d+\]\]/i).map((value) => value.trim()).filter(Boolean)
  let raw = []
  if (splitPlan?.length) raw = plannedParts(text, splitPlan)
  else if (splitBy === "pages") raw = pageChunks.map((value, index) => ({ title: `Página ${index + 1}`, text: value }))
  else {
  const lines = String(text || "").split("\n")
  const hasHeadings = lines.some((line) => /^#{1,6}\s+\S/.test(line.trim()))
  if (hasHeadings) {
    let title = "Introducción"
    let body = []
    const flush = () => { const value = body.join(" ").replace(/\s+/g, " ").trim(); if (value) raw.push({ title, text: value }); body = [] }
    for (const line of lines) {
      const heading = line.trim().match(/^#{1,6}\s+(.+)$/)
      if (heading) { flush(); title = heading[1].replace(/[*_`]/g, "").trim() }
      else if (line.trim()) body.push(line.trim())
    }
    flush()
  } else {
    raw = String(text || "").split(/\n\s*\n+/).map((value, index) => {
      const lines = value.split("\n").map((line) => line.trim()).filter(Boolean)
      const candidate = lines[0] || ""
      const looksLikeTitle = candidate.length > 2 && candidate.length <= 90 && !/[.!?:]$/.test(candidate) && !/^[-•–]/.test(candidate)
      return {
        title: looksLikeTitle ? candidate.replace(/^[-–—]+\s*/, "") : `Parte ${index + 1}`,
        text: (looksLikeTitle ? lines.slice(1) : lines).join(" ").replace(/\s+/g, " ").trim(),
      }
    }).filter((item) => item.text)
  }
  }
  const merged = []
  for (const item of raw) {
    const previous = merged.at(-1)
    if (previous && previous.text.length < minChars && splitBy !== "pages" && !splitPlan) previous.text += ` ${item.text}`
    else merged.push({ ...item })
  }
  const limited = merged.length <= maxParts ? merged : [...merged.slice(0, maxParts - 1), { title: "Continuación", text: merged.slice(maxParts - 1).map((item) => item.text).join(" ") }]
  return limited.map((item, index) => part(item.title, item.text, index))
}

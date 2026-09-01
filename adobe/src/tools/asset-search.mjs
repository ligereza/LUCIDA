import crypto from "node:crypto"
import fs from "node:fs/promises"
import path from "node:path"
import { ensureDir, readJson, slugify, writeJson, TOOLKIT_ROOT } from "../utils.mjs"
import { gdkbNormalize, gdkbResolve } from "./gdkb.mjs"

const CACHE_ROOT = path.join(TOOLKIT_ROOT, "cache", "asset-search")
const ICONIFY_API = "https://api.iconify.design"
const PUBCHEM_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
const CHEBI_API = "https://www.ebi.ac.uk/chebi/backend/api/public/advanced_search/"
const OLS_API = "https://www.ebi.ac.uk/ols4/api/search"
const BIOICONS_TREE_API = "https://api.github.com/repos/duerrsimon/bioicons/git/trees/main?recursive=1"
const BIOICONS_RAW = "https://raw.githubusercontent.com/duerrsimon/bioicons/main/static/icons"
const DEFAULT_LIMIT = 12
const CACHE_TTL_MS = 24 * 60 * 60 * 1000

const PROVIDER_ALIASES = {
  all: ["iconify", "bioicons", "pubchem", "chebi", "ols"],
  visual: ["iconify", "bioicons"],
  semantic: ["pubchem", "chebi", "ols"],
}

const VISUAL_HINTS = new Map([
  ["mdma", ["pill", "molecule", "brain", "heart", "warning"]],
  ["ecstasy", ["pill", "molecule", "brain", "heart", "warning"]],
  ["ghb", ["drop", "bottle", "warning", "interaction"]],
  ["ghb/ghb", ["drop", "bottle", "warning", "interaction"]],
  ["ketamine", ["molecule", "brain", "bottle", "warning"]],
  ["cocaine", ["powder", "nose", "heart", "warning"]],
  ["alcohol", ["bottle", "glass", "warning", "interaction"]],
  ["chemsex", ["people", "connection", "pill", "heart", "warning"]],
  ["consent", ["people", "chat", "hand", "check"]],
  ["vih", ["virus", "cell", "blood", "warning"]],
  ["hiv", ["virus", "cell", "blood", "warning"]],
  ["its", ["virus", "bacteria", "cell", "warning"]],
  ["biologia", ["cell", "dna", "virus", "microscope"]],
  ["biology", ["cell", "dna", "virus", "microscope"]],
])

function normalizeText(value) {
  return String(value || "").trim().replace(/\s+/g, " ")
}

function unique(values) {
  return [...new Set(values.filter(Boolean))]
}

function tokenise(value) {
  return unique(normalizeText(value)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .split(/[^a-z0-9áéíóúñü/-]+/i)
    .filter((token) => token.length >= 3))
}

function cacheKey(url, suffix = "json") {
  return `${crypto.createHash("sha1").update(url).digest("hex")}.${suffix}`
}

async function cachedFetch(url, { method = "GET", body = null, ttlMs = CACHE_TTL_MS, headers = {} } = {}) {
  const key = cacheKey(`${method}:${url}:${body || ""}`)
  const file = path.join(CACHE_ROOT, key)
  try {
    const stat = await fs.stat(file)
    if (Date.now() - stat.mtimeMs < ttlMs) return JSON.parse(await fs.readFile(file, "utf8"))
  } catch {}

  const response = await fetch(url, {
    method,
    body,
    headers: {
      accept: "application/json",
      "user-agent": "lucida-adobe-asset-search/0.1",
      ...(body ? { "content-type": "application/json" } : {}),
      ...headers,
    },
    signal: AbortSignal.timeout(15_000),
  })
  if (!response.ok) throw new Error(`${response.status} ${response.statusText} from ${url}`)
  const value = await response.json()
  await ensureDir(CACHE_ROOT)
  await fs.writeFile(file, `${JSON.stringify(value)}\n`, "utf8")
  return value
}

async function fetchText(url) {
  const response = await fetch(url, {
    headers: { accept: "image/svg+xml,text/plain", "user-agent": "lucida-adobe-asset-search/0.1" },
    signal: AbortSignal.timeout(15_000),
  })
  if (!response.ok) throw new Error(`${response.status} ${response.statusText} from ${url}`)
  return response.text()
}

function expandProviders(providers) {
  const requested = Array.isArray(providers) && providers.length ? providers : ["visual", "semantic"]
  return unique(requested.flatMap((provider) => PROVIDER_ALIASES[provider] || [provider]))
}

function searchTerms(query, terms) {
  return unique([query, ...(Array.isArray(terms) ? terms : [])].map(normalizeText))
}

function visualQueries(queries, semanticResults) {
  const terms = []
  for (const query of queries) {
    terms.push(query, ...tokenise(query))
    for (const token of tokenise(query)) terms.push(...(VISUAL_HINTS.get(token) || []))
  }
  for (const result of semanticResults) {
    for (const token of tokenise(result.label || result.name || "")) {
      terms.push(...(VISUAL_HINTS.get(token) || []))
    }
  }
  return unique(terms).slice(0, 24)
}

function iconifyResult(query, response) {
  return (response.icons || []).map((id) => {
    const [prefix, ...nameParts] = id.split(":")
    const name = nameParts.join(":")
    const collection = response.collections?.[prefix] || {}
    return {
      provider: "iconify",
      id,
      query,
      label: name.replace(/[-_]/g, " "),
      previewUrl: `${ICONIFY_API}/${encodeURIComponent(prefix)}/${encodeURIComponent(name)}.svg`,
      downloadUrl: `${ICONIFY_API}/${encodeURIComponent(prefix)}/${encodeURIComponent(name)}.svg`,
      sourceUrl: `https://icon-sets.iconify.design/${prefix}/`,
      license: collection.license || null,
      collection: collection.name || prefix,
      tags: collection.tags || [],
    }
  })
}

async function searchIconify(queries, limit) {
  const results = []
  for (const query of queries) {
    const url = new URL("/search", ICONIFY_API)
    url.searchParams.set("query", query)
    url.searchParams.set("limit", String(Math.max(32, limit)))
    const response = await cachedFetch(url.toString())
    results.push(...iconifyResult(query, response))
    if (results.length >= limit * 2) break
  }
  return results.slice(0, limit)
}

function bioiconsLicense(license) {
  return {
    "cc-0": { title: "CC0", spdx: "CC0-1.0", url: "https://creativecommons.org/publicdomain/zero/1.0/" },
    "cc-by": { title: "CC BY", spdx: "CC-BY-4.0", url: "https://creativecommons.org/licenses/by/4.0/" },
    mit: { title: "MIT", spdx: "MIT", url: "https://opensource.org/license/mit/" },
    bsd: { title: "BSD", spdx: "BSD-3-Clause", url: "https://opensource.org/license/bsd-3-clause/" },
  }[license] || { title: license, spdx: license, url: "https://github.com/duerrsimon/bioicons" }
}

async function bioiconsIndex() {
  const tree = await cachedFetch(BIOICONS_TREE_API)
  return (tree.tree || [])
    .filter((entry) => entry.type === "blob" && /^static\/icons\/[^/]+\/.*\.svg$/i.test(entry.path))
    .map((entry) => {
      const relative = entry.path.replace(/^static\/icons\//, "")
      const parts = relative.split("/")
      const license = parts[0]
      const category = parts[1] || ""
      const author = parts.length > 2 ? parts[2] : ""
      const filename = path.basename(parts.at(-1), ".svg")
      return { relative, license, category, author, filename, path: entry.path }
    })
}

async function searchBioicons(queries, limit) {
  const index = await bioiconsIndex()
  const tokens = unique(queries.flatMap(tokenise))
  const scored = index.map((entry) => {
    const haystack = `${entry.relative} ${entry.category} ${entry.filename}`.toLowerCase()
    const score = tokens.reduce((sum, token) => sum + (haystack.includes(token) ? 1 : 0), 0)
    return { entry, score }
  }).filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score || a.entry.relative.localeCompare(b.entry.relative))
  return scored.slice(0, limit).map(({ entry, score }) => ({
    provider: "bioicons",
    id: entry.relative,
    label: entry.filename.replace(/[-_]/g, " "),
    category: entry.category.replace(/[-_]/g, " "),
    author: entry.author.replace(/[-_]/g, " "),
    score,
    previewUrl: `${BIOICONS_RAW}/${entry.relative.split("/").map(encodeURIComponent).join("/")}`,
    downloadUrl: `${BIOICONS_RAW}/${entry.relative.split("/").map(encodeURIComponent).join("/")}`,
    sourceUrl: "https://github.com/duerrsimon/bioicons",
    license: bioiconsLicense(entry.license),
  }))
}

async function searchPubchem(queries, limit) {
  const results = []
  for (const query of queries) {
    const url = `${PUBCHEM_API}/compound/name/${encodeURIComponent(query)}/property/MolecularFormula,CanonicalSMILES,IsomericSMILES,IUPACName/JSON`
    try {
      const data = await cachedFetch(url)
      for (const item of data.PropertyTable?.Properties || []) {
        results.push({
          provider: "pubchem",
          id: String(item.CID),
          label: item.IUPACName || query,
          query,
          cid: item.CID,
          formula: item.MolecularFormula || null,
          smiles: item.SMILES || item.IsomericSMILES || null,
          structureUrl: `https://pubchem.ncbi.nlm.nih.gov/compound/${item.CID}`,
          sourceUrl: "https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest",
        })
      }
    } catch (error) {
      if (!/404/.test(error.message)) throw error
    }
    if (results.length >= limit) break
  }
  return results.slice(0, limit)
}

async function searchChebi(queries, limit) {
  const body = JSON.stringify({
    text_search_specification: {
      or_specification: queries.slice(0, 6).map((text) => ({ text, category: "all" })),
    },
  })
  const url = new URL(CHEBI_API)
  url.searchParams.set("three_star_only", "false")
  url.searchParams.set("size", String(limit))
  const data = await cachedFetch(url.toString(), { method: "POST", body })
  return (data.results || []).slice(0, limit).map((item) => {
    const source = item._source || item
    return {
      provider: "chebi",
      id: source.chebi_accession || item._id,
      label: source.name || source.ascii_name,
      definition: source.definition || null,
      formula: source.formula || null,
      smiles: source.smiles || null,
      inchikey: source.inchikey || null,
      stars: source.stars || null,
      sourceUrl: "https://www.ebi.ac.uk/chebi/tools",
    }
  })
}

async function searchOls(queries, limit) {
  const results = []
  for (const query of queries) {
    const url = new URL(OLS_API)
    url.searchParams.set("q", query)
    url.searchParams.set("rows", String(limit))
    const data = await cachedFetch(url.toString())
    for (const item of data.response?.docs || []) {
      results.push({
        provider: "ols",
        id: item.obo_id || item.short_form || item.iri,
        label: item.label,
        ontology: item.ontology_name,
        iri: item.iri,
        synonyms: item.exact_synonyms || item.related_synonyms || [],
        description: item.description?.[0] || null,
        sourceUrl: "https://www.ebi.ac.uk/ols4/api-docs",
      })
    }
    if (results.length >= limit) break
  }
  return results.slice(0, limit)
}

async function runProvider(provider, queries, limit) {
  if (provider === "iconify") return searchIconify(queries.flatMap((query) => [query, ...tokenise(query)]), limit)
  if (provider === "bioicons") return searchBioicons(queries, limit)
  if (provider === "pubchem") return searchPubchem(queries, limit)
  if (provider === "chebi") return searchChebi(queries, limit)
  if (provider === "ols") return searchOls(queries, limit)
  throw new Error(`Unknown asset search provider: ${provider}`)
}

export async function searchAssets({ query, terms = [], providers, limit = DEFAULT_LIMIT, ancla = null, role = null, useGdkb = true } = {}) {
  const normalizedQuery = normalizeText(query)
  if (!normalizedQuery && !terms.length) throw new Error("asset.search requires query or terms")
  const queries = searchTerms(normalizedQuery, terms)
  const selectedProviders = expandProviders(providers)
  const semanticResults = []
  const visualResults = []
  const errors = []
  const semanticProviders = selectedProviders.filter((provider) => ["pubchem", "chebi", "ols"].includes(provider))
  const visualProviders = selectedProviders.filter((provider) => ["iconify", "bioicons"].includes(provider))
  for (const provider of semanticProviders) {
    try {
      const results = await runProvider(provider, queries, Math.max(1, Number(limit) || DEFAULT_LIMIT))
      semanticResults.push(...results)
    } catch (error) {
      errors.push({ provider, message: error.message })
    }
  }
  const knowledge = { enabled: useGdkb !== false, normalization: null, resolution: null }
  if (useGdkb !== false) {
    try {
      knowledge.normalization = await gdkbNormalize(normalizedQuery || queries[0])
      if (semanticResults.length) {
        knowledge.resolution = await gdkbResolve(normalizedQuery || queries[0], semanticResults.map((item) => ({
          id: `${item.provider}:${item.id}`,
          label: item.label,
          source: item.provider,
          exact: item.synonyms?.some((synonym) => normalizeText(synonym).toLowerCase() === (normalizedQuery || queries[0]).toLowerCase()) || false,
        })))
      }
    } catch (error) {
      errors.push({ provider: "gdkb", message: error.message })
    }
  }
  const visualSearches = visualQueries(queries, semanticResults)
  for (const provider of visualProviders) {
    try {
      visualResults.push(...await runProvider(provider, visualSearches, Math.max(1, Number(limit) || DEFAULT_LIMIT)))
    } catch (error) {
      errors.push({ provider, message: error.message })
    }
  }
  return {
    version: 1,
    query: normalizedQuery || queries[0],
    queries,
    providers: selectedProviders,
    createdAt: new Date().toISOString(),
    semantic: { results: semanticResults.slice(0, Number(limit) || DEFAULT_LIMIT) },
    knowledge,
    visual: {
      suggestedQueries: visualSearches,
      results: visualResults.slice(0, Number(limit) * 2 || DEFAULT_LIMIT * 2),
    },
    context: { ancla, role },
    errors,
    next: {
      select: "Elegir uno o varios visual.results; conservar provider, id, license y sourceUrl.",
      fetch: "Usar asset.fetch para descargar el SVG elegido.",
      manifest: "Usar asset.select para crear un manifiesto enlazado al texto/ancla.",
    },
  }
}

function safeAssetName(provider, id) {
  return `${slugify(provider)}-${slugify(id.replace(/[:/\\]+/g, "-"))}.svg`
}

export async function fetchAsset({ provider, id, output, overwrite = false } = {}) {
  if (!provider || !id) throw new Error("asset.fetch requires provider and id")
  const target = path.resolve(output || path.join(TOOLKIT_ROOT, "jobs", "manual", "output", safeAssetName(provider, id)))
  const relativeTarget = path.relative(TOOLKIT_ROOT, target)
  if (relativeTarget.startsWith("..") || path.isAbsolute(relativeTarget)) throw new Error(`Asset output must stay inside ${TOOLKIT_ROOT}`)
  if (!overwrite) {
    try { await fs.access(target); throw new Error(`Output already exists: ${target}`) } catch (error) {
      if (error.message.startsWith("Output already exists")) throw error
    }
  }
  let url
  if (provider === "iconify") {
    const [prefix, ...parts] = String(id).split(":")
    if (!prefix || !parts.length || !/^[a-z0-9-]+$/i.test(prefix)) throw new Error(`Invalid Iconify id: ${id}`)
    url = `${ICONIFY_API}/${encodeURIComponent(prefix)}/${parts.map((part) => encodeURIComponent(part)).join(":")}.svg`
  } else if (provider === "bioicons") {
    if (String(id).includes("..") || !/^(cc-0|cc-by|mit|bsd)\//i.test(String(id))) throw new Error(`Invalid Bioicons id: ${id}`)
    url = `${BIOICONS_RAW}/${String(id).split("/").map(encodeURIComponent).join("/")}`
  } else {
    throw new Error(`Provider ${provider} does not expose an editable SVG asset`)
  }
  const svg = await fetchText(url)
  if (!/^\s*<svg[\s>]/i.test(svg)) throw new Error(`Provider returned a non-SVG asset: ${url}`)
  await ensureDir(path.dirname(target))
  await fs.writeFile(target, svg, "utf8")
  return { provider, id, url, output: target, bytes: Buffer.byteLength(svg), editable: true }
}

export async function selectAssets({ selection, selectionPath, selected = null, output, overwrite = false, project = null, ancla = null, role = null, exactText = null } = {}) {
  let value = selection
  if (!value && selectionPath) value = await readJson(selectionPath)
  if (!value) throw new Error("asset.select requires selection or selectionPath")
  const selectedItems = selected || value.selected
  if (!Array.isArray(selectedItems)) throw new Error("asset.select requires selected[] or a selection file with selected[]")
  const target = path.resolve(output || path.join(TOOLKIT_ROOT, "jobs", "manual", "output", "asset-manifest.json"))
  const relativeTarget = path.relative(TOOLKIT_ROOT, target)
  if (relativeTarget.startsWith("..") || path.isAbsolute(relativeTarget)) throw new Error(`Manifest output must stay inside ${TOOLKIT_ROOT}`)
  if (!overwrite) {
    try { await fs.access(target); throw new Error(`Output already exists: ${target}`) } catch (error) {
      if (error.message.startsWith("Output already exists")) throw error
    }
  }
  const assetDirectory = path.join(path.dirname(target), "assets")
  const searchResults = [...(value.visual?.results || []), ...(value.semantic?.results || [])]
  const assets = []
  for (const rawItem of selectedItems) {
    const match = searchResults.find((candidate) => candidate.provider === rawItem.provider && candidate.id === rawItem.id)
    const item = { ...(match || {}), ...rawItem }
    if (!item.provider || !item.id) throw new Error("Every selected asset needs provider and id")
    if (!["iconify", "bioicons"].includes(item.provider)) {
      assets.push({ ...item, editable: false, note: "Semantic source; choose a visual asset separately." })
      continue
    }
    const assetPath = path.join(assetDirectory, safeAssetName(item.provider, item.id))
    const fetched = await fetchAsset({ provider: item.provider, id: item.id, output: assetPath, overwrite: true })
    assets.push({ ...item, file: fetched.output, editable: true, fetchedFrom: fetched.url })
  }
  const manifest = {
    version: 1,
    createdAt: new Date().toISOString(),
    project: project || value.project || null,
    ancla: ancla || value.ancla || value.context?.ancla || null,
    role: role || value.role || value.context?.role || null,
    exactText: exactText || value.exactText || null,
    search: value.search || (value.query ? { query: value.query, queries: value.queries, providers: value.providers } : null),
    assets,
    illustrator: { importable: assets.some((asset) => asset.editable), keepGroupsNamed: true },
  }
  await writeJson(target, manifest)
  return { manifest, output: target, files: [target, ...assets.filter((asset) => asset.file).map((asset) => asset.file)] }
}

export function assetSearchProviders() {
  return {
    iconify: { kind: "visual", editable: true, description: "General SVG icon search" },
    bioicons: { kind: "visual", editable: true, description: "Biology and chemistry SVG catalog" },
    pubchem: { kind: "semantic", editable: false, description: "Compound identity and properties" },
    chebi: { kind: "semantic", editable: false, description: "Chemical ontology and compounds" },
    ols: { kind: "semantic", editable: false, description: "Biomedical ontology search" },
  }
}

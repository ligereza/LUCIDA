import test from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { TOOLKIT_ROOT } from "../src/utils.mjs"
import { indexLocalCatalog, searchLocalAssets } from "../src/tools/local-catalog.mjs"
import { indexLocalGroups, listCatalogAssets } from "../src/tools/catalog-groups.mjs"

test("local catalog indexes editable SVGs and returns direct file paths", async () => {
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), "context-shelf-catalog-"))
  const cachePath = path.join(temporary, "catalog.json")
  const root = path.join(TOOLKIT_ROOT, "tests", "fixtures")
  const summary = await indexLocalCatalog({ roots: [root], cachePath })
  assert.equal(summary.files, 1)
  assert.equal(summary.byFormat.svg, 1)
  const result = await searchLocalAssets({ roots: [root], cachePath, query: "multi app", limit: 4 })
  assert.equal(result.total, 1)
  assert.equal(result.results[0].local, true)
  assert.equal(result.results[0].file, path.join(root, "multi-app-asset.svg"))
  assert.equal(result.results[0].width, 80)
  const indexPath = path.join(temporary, "groups.json")
  const groups = await indexLocalGroups({ roots: [root], cachePath, indexPath, refresh: true })
  assert.equal(groups.total, 1)
  assert.equal(groups.groups.format[0].key, "svg")
  assert.equal(groups.groups.color.some((group) => ["blue", "purple", "pink"].includes(group.key)), true)
  const grouped = await listCatalogAssets({ type: "format", key: "svg", indexPath, pageSize: 5 })
  assert.equal(grouped.total, 1)
  assert.equal(grouped.results[0].provider, "local")

  const semanticRoot = path.join(root, `.semantic-${Date.now()}`)
  await fs.mkdir(semanticRoot, { recursive: true })
  await fs.writeFile(path.join(semanticRoot, "lungs.svg"), '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><path d="M8 8h32v32H8z"/></svg>')
  const semanticCache = path.join(temporary, "semantic-catalog.json")
  const semanticGroups = path.join(temporary, "semantic-groups.json")
  await indexLocalCatalog({ roots: [semanticRoot], cachePath: semanticCache })
  const lungs = await searchLocalAssets({ roots: [semanticRoot], cachePath: semanticCache, query: "pulmones", limit: 4 })
  assert.equal(lungs.total, 1)
  assert.equal(lungs.results[0].name, "lungs")
  const noMatch = await searchLocalAssets({ roots: [semanticRoot], cachePath: semanticCache, query: "termometro", limit: 4 })
  assert.equal(noMatch.total, 0)
  await indexLocalGroups({ roots: [semanticRoot], cachePath: semanticCache, indexPath: semanticGroups, refresh: true })
  const groupedLungs = await listCatalogAssets({ query: "pulmones", indexPath: semanticGroups, pageSize: 4 })
  assert.equal(groupedLungs.total, 1)
  assert.equal(groupedLungs.results[0].name, "lungs")
  await fs.rm(semanticRoot, { recursive: true, force: true })
  await fs.rm(temporary, { recursive: true, force: true })
})

test("Spanish protection queries resolve local English icon metadata without external libraries", async () => {
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), "context-shelf-semantic-alias-"))
  const root = path.join(TOOLKIT_ROOT, "ICONOS")
  const cachePath = path.join(temporary, "catalog.json")
  await indexLocalCatalog({ roots: [root], cachePath, refresh: true })
  const result = await searchLocalAssets({ roots: [root], cachePath, query: "proteccion", limit: 30 })
  assert.ok(result.total > 0)
  assert.ok(result.results.every((item) => item.local === true))
  assert.ok(result.results.every((item) => item.searchMode === "lexical"))
  assert.ok(result.results.some((item) => /protection|proteccion/i.test(item.relativePath)))
  await fs.rm(temporary, { recursive: true, force: true })
})

test("multiword semantic queries rank assets that cover the whole concept first", async () => {
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), "context-shelf-concept-ranking-"))
  const root = path.join(TOOLKIT_ROOT, "ICONOS", "CHEMSEX")
  const cachePath = path.join(temporary, "catalog.json")
  await indexLocalCatalog({ roots: [root], cachePath, refresh: true })
  const result = await searchLocalAssets({ roots: [root], cachePath, query: "salud sexual", limit: 8 })
  assert.ok(result.total > 0)
  assert.ok(result.results.slice(0, 8).every((item) => /sexual_health/i.test(item.relativePath)))
  assert.ok(result.results[0].matchReasons.includes("salud -> health"))
  assert.ok(result.results[0].matchReasons.includes("sexual"))
  assert.equal(result.results[0].matchedTokenCount, 2)
  assert.equal(result.results[0].queryTokenCount, 2)
  assert.equal(result.results[0].matchCoverage, 1)
  await fs.rm(temporary, { recursive: true, force: true })
})

test("local recommendations expose partial textual match coverage", async () => {
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), "context-shelf-match-coverage-"))
  const root = path.join(TOOLKIT_ROOT, "tests", "fixtures", `.match-coverage-${Date.now()}`)
  const cachePath = path.join(temporary, "catalog.json")
  await fs.mkdir(root, { recursive: true })
  await fs.writeFile(path.join(root, "chemsex-ribbon.svg"), '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><path d="M0 0h48v48H0z"/></svg>')
  try {
    await indexLocalCatalog({ roots: [root], cachePath })
    const result = await searchLocalAssets({ roots: [root], cachePath, query: "chemsex supplements magnesium", limit: 4 })
    assert.equal(result.total, 1)
    assert.deepEqual(result.results[0].matchReasons, ["chemsex"])
    assert.equal(result.results[0].matchedTokenCount, 1)
    assert.equal(result.results[0].queryTokenCount, 3)
    assert.equal(result.results[0].matchCoverage, 0.3333)
  } finally {
    await fs.rm(root, { recursive: true, force: true })
    await fs.rm(temporary, { recursive: true, force: true })
  }
})

test("related icon concepts are not reported as exact translation matches", async () => {
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), "context-shelf-related-match-"))
  const root = path.join(TOOLKIT_ROOT, "tests", "fixtures", `.related-match-${Date.now()}`)
  const cachePath = path.join(temporary, "catalog.json")
  await fs.mkdir(root, { recursive: true })
  await fs.writeFile(path.join(root, "protection-symbol.svg"), '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><path d="M0 0h48v48H0z"/></svg>')
  try {
    await indexLocalCatalog({ roots: [root], cachePath })
    const related = await searchLocalAssets({ roots: [root], cachePath, query: "condon", limit: 4 })
    assert.equal(related.total, 1)
    assert.deepEqual(related.results[0].matchReasons, ["condon ~ protection (relacionado)"])
    assert.equal(related.results[0].matchedTokenCount, 0)
    assert.equal(related.results[0].relatedTokenCount, 1)
    assert.equal(related.results[0].matchCoverage, 0)

    const translated = await searchLocalAssets({ roots: [root], cachePath, query: "proteccion", limit: 4 })
    assert.equal(translated.total, 1)
    assert.deepEqual(translated.results[0].matchReasons, ["proteccion -> protection"])
    assert.equal(translated.results[0].matchedTokenCount, 1)
    assert.equal(translated.results[0].relatedTokenCount, 0)
    assert.equal(translated.results[0].matchCoverage, 1)
  } finally {
    await fs.rm(root, { recursive: true, force: true })
    await fs.rm(temporary, { recursive: true, force: true })
  }
})

test("protection queries prioritize explicit protection symbols over generic care artwork", async () => {
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), "context-shelf-protection-ranking-"))
  const root = path.join(TOOLKIT_ROOT, "ICONOS", "CHEMSEX")
  const cachePath = path.join(temporary, "catalog.json")
  await indexLocalCatalog({ roots: [root], cachePath, refresh: true })
  const result = await searchLocalAssets({ roots: [root], cachePath, query: "proteccion", limit: 8 })
  assert.ok(result.results.some((item) => /protection-symbol/i.test(item.relativePath)))
  assert.ok(result.results.slice(0, 8).every((item) => /protection|prevention/i.test(item.relativePath)))
  assert.ok(result.results.some((item) => item.matchReasons.some((reason) => reason === "proteccion -> protection")))
  await fs.rm(temporary, { recursive: true, force: true })
})

test("concurrent catalog refreshes leave a complete JSON cache", async () => {
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), "context-shelf-catalog-concurrent-"))
  const cachePath = path.join(temporary, "catalog.json")
  const root = path.join(TOOLKIT_ROOT, "tests", "fixtures")
  const summaries = await Promise.all(Array.from({ length: 4 }, () => indexLocalCatalog({ roots: [root], cachePath, refresh: true })))
  const cached = JSON.parse(await fs.readFile(cachePath, "utf8"))
  assert.equal(summaries.every((summary) => summary.files === 1), true)
  assert.equal(Object.keys(cached.entries || {}).length, 1)
  await fs.rm(temporary, { recursive: true, force: true })
})

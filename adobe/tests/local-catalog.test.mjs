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

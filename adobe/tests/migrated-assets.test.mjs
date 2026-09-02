import test from "node:test"
import assert from "node:assert/strict"
import { indexLocalCatalog, searchLocalAssets } from "../src/tools/local-catalog.mjs"
import { listProjectInventory } from "../src/tools/project-inventory.mjs"

test("branch-local migrated assets are searchable and grouped by slide", async () => {
  const catalog = await indexLocalCatalog({ refresh: true })
  assert.ok(catalog.files >= 300)
  assert.ok(catalog.byFormat.png > 0)
  assert.ok(catalog.byFormat.svg > 0)

  const search = await searchLocalAssets({ query: "slide 03", limit: 8 })
  assert.ok(search.total > 0)
  assert.ok(search.results.every((item) => item.relativePath.includes("adobe/ICONOS/CHEMSEX/3/")))

  const inventory = await listProjectInventory({ projectId: "chemsex", refresh: true })
  assert.equal(inventory.project.id, "chemsex")
  assert.equal(inventory.stats.unassignedFiles, 0)
  assert.equal(inventory.stats.indexErrors, 0)
  assert.deepEqual(inventory.indexErrors, [])
  assert.equal(inventory.stats.collectionFiles, 96)
  assert.equal(inventory.collections.find((collection) => collection.id === "mini-icons")?.variants.length, 96)
  assert.ok(inventory.slides.find((slide) => slide.index === 3)?.groups.length > 0)
  assert.equal(inventory.slides.length, 8)
  assert.equal(inventory.slides[0].text, "Orgullo es cuidarnos en comunidad")
  assert.ok(inventory.slides.every((slide) => slide.text.length > 0))
})

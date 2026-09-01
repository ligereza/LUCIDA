import test from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { assetSearchProviders, selectAssets } from "../src/tools/asset-search.mjs"

test("asset search exposes semantic and visual providers", () => {
  const providers = assetSearchProviders()
  assert.deepEqual(Object.keys(providers), ["iconify", "bioicons", "pubchem", "chebi", "ols"])
  assert.equal(providers.iconify.editable, true)
  assert.equal(providers.pubchem.editable, false)
})

test("asset select writes a provenance manifest for semantic selections without downloading them", async () => {
  const directory = path.join(process.cwd(), "jobs", `asset-search-test-${Date.now()}`)
  const output = path.join(directory, "output", "manifest.json")
  try {
    const result = await selectAssets({
      selection: {
        query: "MDMA",
        semantic: { results: [{ provider: "pubchem", id: "1615", label: "MDMA", sourceUrl: "https://pubchem.ncbi.nlm.nih.gov/compound/1615" }] },
        selected: [{ provider: "pubchem", id: "1615" }],
      },
      output,
      project: "test",
      ancla: "exact anchor",
      role: "context",
      exactText: "exact source text",
      overwrite: true,
    })
    assert.equal(result.manifest.project, "test")
    assert.equal(result.manifest.ancla, "exact anchor")
    assert.equal(result.manifest.assets[0].editable, false)
    assert.equal(result.files.length, 1)
    assert.equal((await fs.stat(output)).isFile(), true)
  } finally {
    await fs.rm(directory, { recursive: true, force: true })
  }
})

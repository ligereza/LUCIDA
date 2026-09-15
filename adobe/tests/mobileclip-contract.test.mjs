import test from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { MOBILECLIP_MODELS, inspectSemanticIndexStatus, queryVariants } from "../src/tools/mobileclip.mjs"

test("visual query translations keep related concepts out of the canonical prompt", () => {
  const condom = queryVariants("condon")
  assert.ok(condom.includes("condom"))
  assert.equal(condom.includes("protection"), false)

  const consent = queryVariants("consentimiento")
  assert.ok(consent.includes("consent"))
  assert.equal(consent.includes("communication"), false)

  const harmReduction = queryVariants("reduccion de danos")
  assert.ok(harmReduction.includes("reduction"))
  assert.ok(harmReduction.includes("harm"))
  assert.equal(harmReduction.includes("risk"), false)
})

test("visual search readiness requires a matching index and valid vector file", async () => {
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), "lucida-mobileclip-index-"))
  const indexPath = path.join(temporary, "index.json")
  const vectorsPath = path.join(temporary, "vectors.f32")
  try {
    const missing = await inspectSemanticIndexStatus(indexPath)
    assert.equal(missing.ready, false)
    assert.equal(missing.present, false)

    const model = MOBILECLIP_MODELS.mobileclip_s2
    const index = {
      schemaVersion: 1,
      model: { name: model.name, sha256: model.sha256 },
      dimension: 2,
      count: 1,
      vectorsFile: "vectors.f32",
      items: [{ assetId: "fixture", vectorOffset: 0 }],
    }
    await fs.writeFile(vectorsPath, Buffer.alloc(8))
    await fs.writeFile(indexPath, JSON.stringify(index))
    const valid = await inspectSemanticIndexStatus(indexPath)
    assert.equal(valid.ready, true)
    assert.equal(valid.itemCount, 1)

    index.items[0].vectorOffset = 1
    await fs.writeFile(indexPath, JSON.stringify(index))
    const invalid = await inspectSemanticIndexStatus(indexPath)
    assert.equal(invalid.ready, false)
    assert.equal(invalid.reason, "El archivo de vectores no coincide con el índice.")
  } finally {
    await fs.rm(temporary, { recursive: true, force: true })
  }
})

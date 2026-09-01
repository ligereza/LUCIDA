import path from "node:path"
import { TOOLKIT_ROOT } from "./utils.mjs"

const REPO_ROOT = path.resolve(TOOLKIT_ROOT, "..")
const HISTORY_ASSETS_ROOT = path.join(REPO_ROOT, "rd_database_complete", "assets")

// These folders hold imagery generated or assembled in the local Codex
// workflow. Imported icons, chemical reference images and real photographs
// intentionally have no entry here.
const AUTHORED_HISTORY_FOLDERS = [
  "generated_icons",
  "salud_sexual_its_techno_iteraciones",
  "salud_sexual_its_techno_paleta_sobria",
  "slide3_contexto_reduccion_candidata_minimal_6of6",
  "slide3_contexto_reduccion_candidata_techno_v2_incompleta_5of6",
  "slide3_contexto_reduccion_candidata_techno_v3_6of6",
  "slide3_contexto_reduccion_variantes_illustrated",
  "slide3_contexto_reduccion_variantes_techno_v1_6of6",
  "slide4_sustancias_candidata_techno_v1_completa_8of8",
  "slide4_sustancias_candidata_techno_v2_incompleta_3of8",
  "slide4_sustancias_candidata_techno_v3_incompleta_3of8",
  "slide5_risks_icons_sober_v1",
  "slide6_care_icons_sober_v1",
  "slide7_interactions_icons_sober_v1",
]

export const AUTHORED_CATALOG_POLICY = Object.freeze({
  id: "authored-generated-only",
  description: "Only Codex-generated or locally authored visual assets are shown by default. Downloaded icon libraries and external reference media are excluded.",
})

export const AUTHORED_HISTORY_ROOTS = Object.freeze(
  AUTHORED_HISTORY_FOLDERS.map((folder) => path.join(HISTORY_ASSETS_ROOT, folder)),
)

export const AUTHORED_CATALOG_ROOTS = Object.freeze([
  ...AUTHORED_HISTORY_ROOTS,
  path.join(TOOLKIT_ROOT, "projects", "chemsex", "generated"),
])

export const AUTHORED_PROJECT_VARIATION_ROOTS = Object.freeze(
  AUTHORED_HISTORY_ROOTS.map((root) => ({ root, area: "project-variations" })),
)

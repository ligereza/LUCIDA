import path from "node:path"
import { TOOLKIT_ROOT } from "./utils.mjs"

const MIGRATED_ICONS_ROOT = path.join(TOOLKIT_ROOT, "ICONOS")

export const AUTHORED_CATALOG_POLICY = Object.freeze({
  id: "authored-generated-only",
  description: "Only Codex-generated or locally authored visual assets are shown by default. Downloaded icon libraries and external reference media are excluded.",
})

// Kept as an empty compatibility export. Historical source paths are not
// active catalog roots in the standalone LUCIDA package.
export const AUTHORED_HISTORY_ROOTS = Object.freeze([])

export const AUTHORED_CATALOG_ROOTS = Object.freeze([
  MIGRATED_ICONS_ROOT,
  path.join(TOOLKIT_ROOT, "projects", "chemsex", "generated"),
])

export const AUTHORED_PROJECT_VARIATION_ROOTS = Object.freeze(
  [
    { root: path.join(MIGRATED_ICONS_ROOT, "CHEMSEX"), area: "migrated-icons" },
  ],
)

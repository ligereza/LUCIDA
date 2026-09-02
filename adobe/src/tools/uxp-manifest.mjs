export const UXP_PLUGIN_FILES = [
  "adobe-context-shelf/photoshop-uxp/manifest.json",
  "adobe-context-shelf/photoshop-uxp/index.html",
  "adobe-context-shelf/photoshop-uxp/index.js",
  "adobe-context-shelf/photoshop-uxp/styles.css",
]

const BRIDGE_URL = "http://127.0.0.1:47921"

export function validateUxpManifest(manifest = {}) {
  const issues = []
  if (manifest.manifestVersion !== 5) issues.push("manifestVersion must be 5")
  if (manifest.main !== "index.html") issues.push("main must be index.html")
  if (manifest.host?.app !== "PS") issues.push("host.app must be PS")
  if (typeof manifest.host?.minVersion !== "string") issues.push("host.minVersion is required")
  if (!manifest.requiredPermissions?.localFileSystem) issues.push("localFileSystem permission is required")
  const domains = manifest.requiredPermissions?.network?.domains
  if (!Array.isArray(domains) || !domains.includes(BRIDGE_URL)) issues.push("bridge network permission is missing")
  const panel = Array.isArray(manifest.entrypoints)
    ? manifest.entrypoints.find((entrypoint) => entrypoint?.type === "panel" && entrypoint?.id === "contextShelf")
    : null
  if (!panel) issues.push("contextShelf panel entrypoint is missing")
  return { ok: issues.length === 0, issues }
}

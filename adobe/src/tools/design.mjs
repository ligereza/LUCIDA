const presets = {
  "instagram-portrait": {
    canvas: { width: 1080, height: 1350 },
    margins: { top: 96, right: 96, bottom: 96, left: 96 },
    colors: { background: "#090712", accent: "#7c3aed", highlight: "#f0abfc", text: "#ffffff", muted: "#c4b5fd" },
    typography: { titleFont: "Arial, sans-serif", titleSize: 52, summaryFont: "Arial, sans-serif", summarySize: 24, footerSize: 18 }, animation: "pulse",
    autoLayout: true, layoutStrategy: "semantic",
    layout: { mode: "auto", text: { x: 0.08, y: 0.08, width: 0.84, height: 0.22 }, illustration: { x: 0.08, y: 0.34, width: 0.84, height: 0.54 } },
    iconMode: "auto",
  },
  "chemsex-portrait": {
    canvas: { width: 1080, height: 1440 },
    margins: { top: 104, right: 96, bottom: 104, left: 96 },
    colors: { background: "#090712", accent: "#7c3aed", highlight: "#f0abfc", text: "#ffffff", muted: "#c4b5fd" },
    typography: { titleFont: "Arial, sans-serif", titleSize: 52, summaryFont: "Arial, sans-serif", summarySize: 24, footerSize: 18 }, animation: "pulse",
    autoLayout: true, layoutStrategy: "semantic",
    layout: { mode: "auto", text: { x: 0.08, y: 0.08, width: 0.84, height: 0.22 }, illustration: { x: 0.08, y: 0.34, width: 0.84, height: 0.54 } },
    iconMode: "auto",
  },
  "instagram-square": {
    canvas: { width: 1080, height: 1080 },
    margins: { top: 88, right: 88, bottom: 88, left: 88 },
    colors: { background: "#090712", accent: "#7c3aed", highlight: "#f0abfc", text: "#ffffff", muted: "#c4b5fd" },
    typography: { titleFont: "Arial, sans-serif", titleSize: 48, summaryFont: "Arial, sans-serif", summarySize: 22, footerSize: 18 }, animation: "pulse",
    autoLayout: true, layoutStrategy: "semantic",
    layout: { mode: "auto", text: { x: 0.08, y: 0.08, width: 0.84, height: 0.22 }, illustration: { x: 0.08, y: 0.34, width: 0.84, height: 0.54 } },
    iconMode: "auto",
  },
  story: {
    canvas: { width: 1080, height: 1920 },
    margins: { top: 120, right: 96, bottom: 120, left: 96 },
    colors: { background: "#090712", accent: "#7c3aed", highlight: "#f0abfc", text: "#ffffff", muted: "#c4b5fd" },
    typography: { titleFont: "Arial, sans-serif", titleSize: 64, summaryFont: "Arial, sans-serif", summarySize: 28, footerSize: 20 }, animation: "float",
    autoLayout: true, layoutStrategy: "semantic",
    layout: { mode: "auto", text: { x: 0.08, y: 0.07, width: 0.84, height: 0.2 }, illustration: { x: 0.08, y: 0.31, width: 0.84, height: 0.6 } },
    iconMode: "auto",
  },
  landscape: {
    canvas: { width: 1920, height: 1080 },
    margins: { top: 80, right: 120, bottom: 80, left: 120 },
    colors: { background: "#090712", accent: "#7c3aed", highlight: "#f0abfc", text: "#ffffff", muted: "#c4b5fd" },
    typography: { titleFont: "Arial, sans-serif", titleSize: 56, summaryFont: "Arial, sans-serif", summarySize: 26, footerSize: 20 }, animation: "rotate",
    autoLayout: true, layoutStrategy: "semantic",
    layout: { mode: "auto", text: { x: 0.06, y: 0.12, width: 0.38, height: 0.72 }, illustration: { x: 0.52, y: 0.12, width: 0.42, height: 0.72 } },
    iconMode: "auto",
  },
}

const merge = (base, override = {}) => ({ ...base, ...override })

export function normalizeDesign(raw = {}) {
  const requestedPreset = raw.preset || "instagram-portrait"
  const basePreset = requestedPreset === "custom" ? "instagram-portrait" : requestedPreset
  if (!presets[basePreset]) throw new Error(`Unknown design preset: ${requestedPreset}`)
  const base = presets[basePreset]
  const design = {
    preset: requestedPreset,
    canvas: merge(base.canvas, raw.canvas),
    margins: merge(base.margins, raw.margins),
    colors: merge(base.colors, raw.colors),
    typography: merge(base.typography, raw.typography),
    animation: raw.animation || base.animation,
    autoLayout: raw.autoLayout ?? base.autoLayout ?? true,
    layoutStrategy: raw.layoutStrategy || base.layoutStrategy || "semantic",
    theme: raw.theme || base.theme || "auto",
    themeVectors: raw.themeVectors && typeof raw.themeVectors === "object" ? raw.themeVectors : {},
    layout: {
      mode: raw.layout?.mode || base.layout.mode,
      text: merge(base.layout.text, raw.layout?.text),
      illustration: merge(base.layout.illustration, raw.layout?.illustration),
    },
    iconMode: raw.iconMode || base.iconMode,
    icons: Array.isArray(raw.icons) ? raw.icons : [],
  }
  if (!["pulse", "float", "rotate", "none"].includes(design.animation)) throw new Error(`Invalid animation: ${design.animation}`)
  if (!["auto", "manual", "none"].includes(design.iconMode)) throw new Error(`Invalid iconMode: ${design.iconMode}`)
  for (const block of ["text", "illustration"]) {
    const box = design.layout[block]
    for (const key of ["x", "y", "width", "height"]) if (!Number.isFinite(Number(box[key])) || Number(box[key]) < 0 || Number(box[key]) > 1) throw new Error(`Invalid layout.${block}.${key}`)
    if (box.x + box.width > 1 || box.y + box.height > 1) throw new Error(`Layout ${block} exceeds canvas`)
  }
  for (const [key, value] of Object.entries(design.canvas)) if (!Number.isFinite(Number(value)) || Number(value) <= 0) throw new Error(`Invalid canvas.${key}`)
  for (const [key, value] of Object.entries(design.margins)) if (!Number.isFinite(Number(value)) || Number(value) < 0) throw new Error(`Invalid margins.${key}`)
  if (design.margins.left + design.margins.right >= design.canvas.width) throw new Error("Horizontal margins leave no content area")
  if (design.margins.top + design.margins.bottom >= design.canvas.height) throw new Error("Vertical margins leave no content area")
  return design
}

export function designPresets() {
  return Object.keys(presets)
}

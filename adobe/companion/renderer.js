let current = null
let recommendationHash = null
let diagnosticHash = null
let surfaceHash = null
let mode = "suggested"
let exploreHash = null
let activeGroup = null
let groupSummary = null
let exploreFilterType = "theme"
let exploreQueryTimer = null
let exploreRequestId = 0
let selectionScopeHash = null
let projectInventory = null
let projectSelectedId = null
let projectSlideFilter = null
let projectStatusFilter = "all"
let projectQuery = ""
let projectRequestId = 0
let pollInFlight = false
let visibleResults = []
let peekIndex = -1
let previewObserver = null
let semanticStatusInFlight = false
let semanticStatusCheckedAt = 0
const FAVORITES_STORAGE_KEY = "context-shelf.favorite-assets"
const FAVORITE_RECORDS_STORAGE_KEY = "context-shelf.favorite-records"
const SELECTION_STORAGE_KEY = "context-shelf.checked-selections.v1"
const assetsById = new Map()

const $ = (selector) => document.querySelector(selector)

function readFavoriteIds() {
  try {
    const value = JSON.parse(localStorage.getItem(FAVORITES_STORAGE_KEY) || "[]")
    return new Set(Array.isArray(value) ? value.map((item) => String(item)) : [])
  } catch (_) { return new Set() }
}

let favoriteIds = readFavoriteIds()

function readFavoriteRecords() {
  try {
    const value = JSON.parse(localStorage.getItem(FAVORITE_RECORDS_STORAGE_KEY) || "[]")
    return new Map((Array.isArray(value) ? value : []).filter((item) => item?.assetId).map((item) => [String(item.assetId), item]))
  } catch (_) { return new Map() }
}

let favoriteRecords = readFavoriteRecords()

function emptySelectionStore() {
  return { schemaVersion: 1, updatedAt: null, documents: {} }
}

function readSelectionStore() {
  try {
    const value = JSON.parse(localStorage.getItem(SELECTION_STORAGE_KEY) || "null")
    if (!value || typeof value !== "object") return emptySelectionStore()
    return {
      schemaVersion: 1,
      updatedAt: value.updatedAt || null,
      documents: value.documents && typeof value.documents === "object" ? value.documents : {},
    }
  } catch (_) { return emptySelectionStore() }
}

let selectionStore = readSelectionStore()

for (const button of document.querySelectorAll(".window-control")) button.addEventListener("click", async () => {
  const action = button.dataset.windowAction
  if (action === "minimize") return window.contextShelf.windowControls.minimize()
  if (action === "maximize") return window.contextShelf.windowControls.toggleMaximize()
  if (action === "close") return window.contextShelf.windowControls.close()
})

function setConnection(online, message = null) {
  const target = $("#connection")
  target.className = `pill ${online ? "online" : "offline"}`
  target.textContent = message || (online ? "bridge online" : "bridge offline")
}

async function refreshSemanticStatus(force = false) {
  if (semanticStatusInFlight || (!force && Date.now() - semanticStatusCheckedAt < 30_000)) return
  const target = $("#semantic-status")
  if (!target) return
  semanticStatusInFlight = true
  try {
    const value = await window.contextShelf.request("/semantic/status")
    semanticStatusCheckedAt = Date.now()
    target.className = `semantic-status ${value.ready ? "ready" : "pending"}`
    target.textContent = value.ready ? "●" : "◌"
    target.title = value.ready
      ? `MobileCLIP activo · ${value.runtime?.cudaName || "GPU"}`
      : "MobileCLIP pendiente: prepara el modelo y genera el índice desde la terminal"
    target.setAttribute("aria-label", target.title)
  } catch (error) {
    semanticStatusCheckedAt = Date.now()
    target.className = "semantic-status error"
    target.textContent = "!"
    target.title = `MobileCLIP no disponible: ${error.message || "error"}`
    target.setAttribute("aria-label", target.title)
  } finally {
    semanticStatusInFlight = false
  }
}

function showContext(context) {
  current = context
  renderSelectionScope()
  $("#document").textContent = context?.document?.name || "Sin documento"
  $("#selection").textContent = context?.selection?.name || "Sin capa seleccionada"
  $("#copy").textContent = context?.selection?.text || "Sin texto; se usará el nombre de la capa o documento."
  const topic = context?.analysis?.content?.primaryTopic?.label || "sin tema dominante"
  const area = context?.analysis?.layout?.placementCandidates?.[0]
  const compositionScore = context?.analysis?.layers?.score
  const composition = Number.isFinite(Number(compositionScore)) ? ` · composición ${compositionScore}/100` : ""
  $("#analysis").textContent = area
    ? `Detectado: ${topic} · zona libre: ${area.position} (${Math.round((area.areaRatio || 0) * 100)}%)${composition}`
    : `Detectado: ${topic} · no se encontró una zona libre clara${composition}`
}

function renderSignalSurface(surface, unavailable = false) {
  const stateTarget = $("#signal-state")
  const sourcesTarget = $("#signal-sources")
  if (!stateTarget || !sourcesTarget) return
  if (unavailable) {
    stateTarget.textContent = "bridge no disponible"
    sourcesTarget.textContent = "XIO · VIZZ · PUPILA"
    return
  }
  const labels = { xio: "XIO", vizz: "VIZZ", pupila: "PUPILA" }
  const states = { active: "activo", stale: "stale", missing: "sin señal" }
  const values = Object.entries(surface?.sources || {})
  const active = values.filter(([, value]) => value.state === "active").length
  stateTarget.textContent = active ? `${active}/3 activos` : "sin señales"
  sourcesTarget.innerHTML = values.map(([source, value]) => {
    const event = value.eventType ? ` · ${escapeHtml(value.eventType)}` : ""
    return `<span class="signal-source ${escapeHtml(value.state || "missing")}"><b>${labels[source] || escapeHtml(source)}</b> ${states[value.state] || "sin estado"}${event}</span>`
  }).join("") || "XIO · VIZZ · PUPILA"
  const proposal = surface?.proposals?.[0]
  if (proposal) sourcesTarget.insertAdjacentHTML("beforeend", `<span class="signal-proposal">Propuesta ${escapeHtml(proposal.kind || "visual")} · confirmación requerida</span>`)
}

async function refreshSignalSurface(sessionId = null) {
  try {
    const query = sessionId ? `?sessionId=${encodeURIComponent(sessionId)}` : ""
    const value = await window.contextShelf.request(`/surface/current${query}`)
    const surface = value.surface || null
    if (surface?.surfaceHash !== surfaceHash) {
      surfaceHash = surface?.surfaceHash || null
      renderSignalSurface(surface)
    }
  } catch (_) {
    surfaceHash = null
    renderSignalSurface(null, true)
  }
}

function showEmpty(message) {
  previewObserver?.disconnect()
  previewObserver = null
  visibleResults = []
  assetsById.clear()
  $("#results").innerHTML = `<div class="empty">${escapeHtml(message)}</div>`
}

function selectionKey(value, fallback = "workspace") {
  const normalized = String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
  return normalized || fallback
}

function selectionContext(context = current) {
  if (mode === "project" && projectInventory?.project && projectSlideFilter && projectSlideFilter !== "all") {
    const project = projectInventory.project
    const slide = projectInventory.slides?.find((item) => String(item.index) === String(projectSlideFilter))
    return {
      ...(context || {}),
      project: { id: project.id, name: project.name },
      document: {
        ...(context?.document || {}),
        id: `project:${project.id}`,
        name: project.name,
        path: project.root,
        width: 1080,
        height: 1440,
      },
      location: { kind: "slide", index: Number(projectSlideFilter), label: slide?.title || `Lámina ${projectSlideFilter}` },
    }
  }
  return context
}

function activeDocumentSelectionKey(context = current) {
  const activeContext = selectionContext(context)
  const documentValue = activeContext?.document || {}
  const project = activeContext?.project?.id || activeContext?.project?.name || "local"
  const documentId = documentValue.path || documentValue.id || `${documentValue.name || "documento"}-${documentValue.width || ""}x${documentValue.height || ""}`
  return `${selectionKey(project, "local")}::${selectionKey(documentId, "document")}`
}

function activeSlideSelectionKey(context = current) {
  const location = selectionContext(context)?.location || {}
  if (location.index !== null && location.index !== undefined && Number.isFinite(Number(location.index))) return `slide-${Number(location.index)}`
  return `location-${selectionKey(location.label, "document")}`
}

function activeSelectionScopeHash(context = current) {
  return `${activeDocumentSelectionKey(context)}::${activeSlideSelectionKey(context)}`
}

function activeSelectionLabel(context = current) {
  const activeContext = selectionContext(context)
  const documentName = activeContext?.document?.name || "Documento"
  const location = activeContext?.location || {}
  const slide = location.index !== null && location.index !== undefined && Number.isFinite(Number(location.index))
    ? `Lámina ${Number(location.index)}`
    : location.label || "Documento"
  return `${documentName} · ${slide}`
}

function getSelectionBucket(create = false) {
  const documentKey = activeDocumentSelectionKey()
  const slideKey = activeSlideSelectionKey()
  if (!selectionStore.documents[documentKey]) {
    if (!create) return null
    selectionStore.documents[documentKey] = {
      documentId: selectionContext()?.document?.id || null,
      documentName: selectionContext()?.document?.name || null,
      documentPath: selectionContext()?.document?.path || null,
      slides: {},
    }
  }
  const documentEntry = selectionStore.documents[documentKey]
  documentEntry.slides ||= {}
  if (!documentEntry.slides[slideKey]) {
    if (!create) return null
    documentEntry.slides[slideKey] = {
      label: activeSelectionLabel(),
      checkedAssets: [],
      contextHash: selectionContext()?.contextHash || null,
      updatedAt: null,
    }
  }
  return documentEntry.slides[slideKey]
}

function persistSelectionStore() {
  selectionStore.updatedAt = new Date().toISOString()
  try { localStorage.setItem(SELECTION_STORAGE_KEY, JSON.stringify(selectionStore)) } catch (_) {}
}

function selectionRecord(item) {
  return {
    assetId: String(item.assetId),
    provider: item.provider || "local",
    id: item.id || item.relativePath || null,
    file: item.file || null,
    label: item.label || item.name || item.id || item.assetId,
    format: String(item.format || item.formats?.[0] || (item.local ? "asset" : "SVG")).toUpperCase(),
    width: item.width || null,
    height: item.height || null,
    local: item.local !== false,
    previewUrl: item.previewUrl || null,
    license: item.license || null,
    checkedAt: new Date().toISOString(),
  }
}

function isAssetSelected(assetId) {
  return Boolean(getSelectionBucket()?.checkedAssets?.some((item) => item.assetId === assetId))
}

function toggleAssetSelection(item) {
  if (!item?.assetId || (mode === "project" && projectSlideFilter === "all")) return false
  const bucket = getSelectionBucket(true)
  const index = bucket.checkedAssets.findIndex((candidate) => candidate.assetId === item.assetId)
  if (index >= 0) bucket.checkedAssets.splice(index, 1)
  else bucket.checkedAssets.push(selectionRecord(item))
  bucket.label = activeSelectionLabel()
  bucket.contextHash = current?.contextHash || bucket.contextHash || null
  bucket.updatedAt = new Date().toISOString()
  persistSelectionStore()
  return index < 0
}

function renderSelectionScope() {
  const target = mode === "project" ? $("#project-selection-scope") : $("#selection-scope")
  if (!target) return
  if (mode !== "explore" && mode !== "project") {
    target.hidden = true
    return
  }
  const count = getSelectionBucket()?.checkedAssets?.length || 0
  target.hidden = false
  const suffix = mode === "project" && projectSlideFilter === "all" ? " · selecciona una lámina para guardar checks" : ""
  target.textContent = `${activeSelectionLabel()} · ${count} elegido${count === 1 ? "" : "s"}${suffix}`
}

function updateSelectionButtons(assetId) {
  const active = isAssetSelected(assetId)
  const selectionDisabled = mode === "project" && projectSlideFilter === "all"
  for (const button of document.querySelectorAll(`.select-asset[data-asset-id="${CSS.escape(assetId)}"]`)) {
    button.classList.toggle("active", active)
    button.textContent = active ? "✓" : "□"
    button.disabled = selectionDisabled
    button.title = selectionDisabled ? "Elige una lámina para guardar checks" : active ? "Quitar de esta lámina" : "Seleccionar para esta lámina"
    button.setAttribute("aria-label", selectionDisabled ? "Elige una lámina para guardar checks" : active ? "Quitar de esta lámina" : "Seleccionar para esta lámina")
  }
  renderSelectionScope()
  const peekButton = $("#peek-select")
  if (peekButton?.dataset.assetId !== assetId) return
  peekButton.classList.toggle("active", active)
  peekButton.textContent = active ? "✓" : "□"
  peekButton.disabled = selectionDisabled
  peekButton.title = selectionDisabled ? "Elige una lámina para guardar checks" : active ? "Quitar de esta lámina" : "Seleccionar para esta lámina"
  peekButton.setAttribute("aria-label", selectionDisabled ? "Elige una lámina para guardar checks" : active ? "Quitar de esta lámina" : "Seleccionar para esta lámina")
}

function diagnosticScoreClass(score) {
  if (score >= 85) return "good"
  if (score >= 65) return "review"
  return "attention"
}

function renderLayerDiagnostics(analysis) {
  if (!analysis) return showEmpty("El host todavía no envía información suficiente para analizar las capas.")
  const summary = analysis.summary || {}
  const issues = analysis.issues || []
  const proposal = analysis.orderProposal || []
  const score = Number(analysis.score) || 0
  const issueMarkup = issues.length
    ? issues.map((issue) => {
      const severity = issue.severity === "warning" ? "warning" : "info"
      const names = (issue.layerNames || []).slice(0, 3).join(" · ")
      return `<article class="diagnostic-issue ${severity}"><span class="diagnostic-mark" aria-hidden="true">${severity === "warning" ? "!" : "i"}</span><div><strong>${escapeHtml(issue.title)}</strong><p>${escapeHtml(issue.reason)}</p>${names ? `<small>${escapeHtml(names)}</small>` : ""}</div></article>`
    }).join("")
    : `<div class="diagnostic-clear"><span aria-hidden="true">✓</span> No se detectaron problemas estructurales importantes.</div>`
  const proposalMarkup = proposal.length
    ? proposal.map((group) => `<div class="order-row"><strong>${escapeHtml(group.label)}</strong><span>${group.layerIds.length} capa${group.layerIds.length === 1 ? "" : "s"}</span><small>${escapeHtml(group.layerNames.slice(0, 3).join(" · "))}</small></div>`).join("")
    : `<div class="diagnostic-muted">Todavía no hay capas suficientes para proponer una estructura.</div>`
  $("#results").innerHTML = `<section class="diagnostic-summary"><div class="diagnostic-score ${diagnosticScoreClass(score)}"><strong>${score}</strong><span>/100</span><small>orden visual</small></div><div class="diagnostic-stats"><span><strong>${summary.total || 0}</strong> capas</span><span><strong>${summary.groups || 0}</strong> grupos</span><span><strong>${summary.hidden || 0}</strong> ocultas</span><span><strong>${summary.genericNames || 0}</strong> nombres a revisar</span><span><strong>${summary.possibleEmpty || 0}</strong> sin contenido detectable</span><span><strong>${summary.outsideCanvas || 0}</strong> fuera del lienzo</span><span><strong>${summary.overlapPairs || 0}</strong> solapamientos</span></div><p class="diagnostic-note">Diagnosticar no modifica el PSD. Si generas la capa guía, se añadirá un overlay bloqueado sin tocar las capas originales.</p><button id="create-analysis-layer" class="diagnostic-action" type="button">Generar capa guía</button></section><section class="diagnostic-section"><div class="diagnostic-heading"><h3>Hallazgos</h3><span>${issues.length}</span></div><div class="diagnostic-issues">${issueMarkup}</div></section><section class="diagnostic-section"><div class="diagnostic-heading"><h3>Plan de orden sugerido</h3><span>preview</span></div><div class="diagnostic-order">${proposalMarkup}</div></section>`
  $("#create-analysis-layer").addEventListener("click", requestAnalysisLayer)
}

async function requestAnalysisLayer() {
  const button = $("#create-analysis-layer")
  if (!button || !current?.sessionId) return
  const originalLabel = button.textContent
  button.disabled = true
  button.textContent = "Preparando…"
  try {
    await window.contextShelf.request("/analysis/layer", {
      method: "POST",
      body: JSON.stringify({ sessionId: current.sessionId }),
    })
    button.textContent = "En cola ✓"
    button.title = "La capa guía se insertará en Photoshop"
  } catch (error) {
    button.textContent = "Error"
    button.title = error.message || "No se pudo generar la capa guía"
  } finally {
    setTimeout(() => {
      button.textContent = originalLabel
      button.title = "Generar una capa guía bloqueada en Photoshop"
      button.disabled = false
    }, 1400)
  }
}

const EXPLORE_FILTERS = [
  ["theme", "Tema", "◉"], ["color", "Color", "◌"], ["style", "Estilo", "◒"], ["aspect", "Forma", "▱"], ["kind", "Tipo", "◇"], ["format", "Formato", "□"], ["size", "Peso", "≡"], ["favorites", "Guardados", "★"], ["selected", "Elegidos", "✓"],
]

function renderExploreControls() {
  const controls = $("#explore-controls")
  if (!controls) return
  controls.hidden = mode !== "explore"
  renderSelectionScope()
  const filterTypes = $("#explore-filter-types")
  if (!filterTypes) return
  filterTypes.innerHTML = EXPLORE_FILTERS.map(([type, label, icon]) => `<button class="filter-chip ${type === exploreFilterType ? "active" : ""}" type="button" data-filter-type="${type}" title="Filtrar por ${label}"><span aria-hidden="true">${icon}</span><span>${label}</span></button>`).join("")
  for (const button of filterTypes.querySelectorAll(".filter-chip")) button.addEventListener("click", () => {
    exploreFilterType = button.dataset.filterType
    const input = $("#explore-query")
    if (input) input.value = ""
    activeGroup = null
    const requestId = ++exploreRequestId
    renderExploreControls()
    if (exploreFilterType === "favorites") loadFavorites("", requestId)
    else if (exploreFilterType === "selected") loadSelection("", requestId)
    else renderGroupType()
  })
}

function renderGroupType() {
  const groups = groupSummary?.groups || {}
  const [type, title] = EXPLORE_FILTERS.find(([key]) => key === exploreFilterType) || EXPLORE_FILTERS[0]
  const items = (groups[type] || []).slice(0, 24)
  const html = items.length
    ? `<section class="group-section"><h3>${title}</h3><div class="group-buttons">${items.map((item) => `<button class="group-button" type="button" data-group-type="${escapeHtml(type)}" data-group-key="${escapeHtml(item.key)}"><span>${escapeHtml(item.label)}</span><small>${item.count}</small></button>`).join("")}</div></section>`
    : `<div class="empty">El índice de grupos todavía no está disponible.</div>`
  $("#results").innerHTML = html
  for (const button of document.querySelectorAll(".group-button")) button.addEventListener("click", () => loadGroup(button))
}

function renderGroups(value) {
  groupSummary = value
  renderExploreControls()
  if (exploreFilterType === "favorites") loadFavorites("", ++exploreRequestId)
  else if (exploreFilterType === "selected") loadSelection("", ++exploreRequestId)
  else renderGroupType()
}

const PROJECT_STATUS_FILTERS = [
  ["all", "Todo"], ["canonical", "Canónicos"], ["variant", "Variaciones"], ["rejected", "Rechazados"], ["legacy", "Históricos"],
]

function projectSlideLabel(slide) {
  return `L${String(slide.index).padStart(2, "0")} · ${slide.title || slide.theme || "Lámina"}`
}

function projectVariantMatches(item) {
  const queryTerms = projectQuery.toLowerCase().trim().split(/\s+/).filter(Boolean)
  const searchable = [item.label, item.name, item.relativePath, item.groupLabel, item.layerName, item.format].filter(Boolean).join(" ").toLowerCase()
  const statusMatch = projectStatusFilter === "all" || item.status === projectStatusFilter || (projectStatusFilter === "canonical" && item.canonical)
  return statusMatch && (!queryTerms.length || queryTerms.every((term) => searchable.includes(term)))
}

function projectTextMarkup(text) {
  const value = String(text || "").trim()
  if (!value) return ""
  return `<details class="project-slide-copy"><summary>Ver texto de la lámina</summary><p>${escapeHtml(value).replace(/\r?\n/g, "<br>")}</p></details>`
}

function renderProjectControls() {
  const controls = $("#project-controls")
  if (!controls) return
  controls.hidden = mode !== "project"
  if (mode !== "project") return
  const select = $("#project-select")
  const projects = projectInventory?.projects || []
  if (select) {
    select.innerHTML = projects.map((project) => `<option value="${escapeHtml(project.id)}">${escapeHtml(project.name || project.id)}</option>`).join("")
    if (projectSelectedId) select.value = projectSelectedId
  }
  const stats = projectInventory?.stats || {}
  const project = projectInventory?.project
  if ($("#project-summary")) {
    $("#project-summary").innerHTML = project
      ? `<strong>${escapeHtml(project.name || project.id)}</strong><span>${projectInventory.slides?.length || 0} láminas · ${stats.groups || 0} grupos · ${stats.visualFiles || 0} archivos · ${stats.variants || 0} vinculaciones · ${stats.rejected || 0} rechazados</span>`
      : `<span>No hay proyectos indexables.</span>`
  }
  const slides = projectInventory?.slides || []
  if (!projectSlideFilter && slides.length) {
    const contextualSlide = Number(current?.location?.index)
    projectSlideFilter = slides.some((slide) => slide.index === contextualSlide) ? String(contextualSlide) : String(slides[0].index)
  }
  const slideButtons = [
    `<button class="project-slide-chip ${projectSlideFilter === "all" ? "active" : ""}" type="button" data-project-slide="all">Todas</button>`,
    ...slides.map((slide) => `<button class="project-slide-chip ${String(projectSlideFilter) === String(slide.index) ? "active" : ""}" type="button" data-project-slide="${slide.index}" title="${escapeHtml(slide.title)}">${escapeHtml(projectSlideLabel(slide))}</button>`),
  ]
  const slideTarget = $("#project-slides")
  if (slideTarget) slideTarget.innerHTML = slideButtons.join("")
  for (const button of document.querySelectorAll(".project-slide-chip")) button.addEventListener("click", () => {
    projectSlideFilter = button.dataset.projectSlide
    renderProjectControls()
    renderProjectView()
  })
  const statusTarget = $("#project-status-filter")
  if (statusTarget) {
    statusTarget.innerHTML = PROJECT_STATUS_FILTERS.map(([key, label]) => `<button class="project-status-chip ${key === projectStatusFilter ? "active" : ""}" type="button" data-project-status="${key}">${label}</button>`).join("")
    for (const button of statusTarget.querySelectorAll(".project-status-chip")) button.addEventListener("click", () => {
      projectStatusFilter = button.dataset.projectStatus
      renderProjectControls()
      renderProjectView()
    })
  }
  renderSelectionScope()
}

function renderProjectView() {
  if (mode !== "project" || !projectInventory) return
  const selectedSlides = projectSlideFilter === "all"
    ? projectInventory.slides || []
    : (projectInventory.slides || []).filter((slide) => String(slide.index) === String(projectSlideFilter))
  const visible = []
  let markup = selectedSlides.map((slide) => {
    const groupMarkup = (slide.groups || []).map((group) => {
      const variants = (group.variants || []).filter(projectVariantMatches)
      if (!variants.length) return ""
      visible.push(...variants)
      const layers = (group.layers || []).map((layer) => `<span class="project-layer-chip" title="${escapeHtml(layer.role || "")}">${escapeHtml(layer.label)}</span>`).join("")
      return `<section class="project-group"><div class="project-group-heading"><strong>${escapeHtml(group.label)}</strong><span>${variants.length} variante${variants.length === 1 ? "" : "s"}</span></div><div class="project-layer-list">${layers || `<span class="project-layer-chip">archivo visual</span>`}</div><div class="project-variant-grid">${variants.map((item) => assetCard(item)).join("")}</div></section>`
    }).filter(Boolean).join("")
    return groupMarkup ? `<section class="project-slide"><div class="project-slide-heading"><strong>${escapeHtml(projectSlideLabel(slide))}</strong><span>${escapeHtml(slide.theme || "")}</span></div>${projectTextMarkup(slide.text)}${groupMarkup}</section>` : ""
  }).filter(Boolean).join("")
  if (projectSlideFilter === "all") {
    const unassigned = (projectInventory.unassigned || []).filter(projectVariantMatches)
    if (unassigned.length) {
      visible.push(...unassigned)
      markup += `<section class="project-slide"><div class="project-slide-heading"><strong>Sin lámina asignada</strong><span>${unassigned.length} archivo${unassigned.length === 1 ? "" : "s"}</span></div><section class="project-group"><div class="project-variant-grid">${unassigned.map((item) => assetCard(item)).join("")}</div></section></section>`
    }
  }
  if (!markup) return showEmpty(projectQuery ? "No hay capas o variaciones que coincidan." : projectSlideFilter === "all" ? "Este proyecto todavía no tiene archivos visuales indexados." : "Esta lámina todavía no tiene archivos visuales indexados.")
  prepareVisibleResults(visible)
  $("#results").innerHTML = markup
  bindAssetCards()
}

async function loadProjectInventory({ refresh = false } = {}) {
  const requestId = ++projectRequestId
  const params = new URLSearchParams()
  if (projectSelectedId) params.set("projectId", projectSelectedId)
  if (refresh) params.set("refresh", "true")
  const select = $("#project-select")
  if (select) select.disabled = true
  if (!projectInventory && $("#project-summary")) $("#project-summary").innerHTML = "<span>Indexando el proyecto y sus variaciones…</span>"
  try {
    const value = await window.contextShelf.request(`/catalog/projects?${params.toString()}`)
    if (requestId !== projectRequestId || mode !== "project") return
    projectInventory = value
    projectSelectedId = value.project?.id || projectSelectedId
    if (!projectSlideFilter || (projectSlideFilter !== "all" && !value.slides?.some((slide) => String(slide.index) === String(projectSlideFilter)))) {
      const contextualSlide = Number(current?.location?.index)
      projectSlideFilter = value.slides?.some((slide) => slide.index === contextualSlide) ? String(contextualSlide) : String(value.slides?.[0]?.index || "all")
    }
    renderProjectControls()
    renderProjectView()
  } catch (error) {
    if (requestId === projectRequestId && mode === "project") showEmpty(error.message || "No se pudo cargar el inventario del proyecto.")
  } finally {
    if (requestId === projectRequestId && select) select.disabled = false
  }
}

async function loadGroups() {
  const requestId = ++exploreRequestId
  const groups = await window.contextShelf.request("/catalog/groups")
  if (requestId !== exploreRequestId || mode !== "explore") return
  renderGroups(groups)
}

async function loadExploreQuery(query, page = 1) {
  const requestId = ++exploreRequestId
  const normalized = String(query || "").trim()
  if (!normalized) {
    if (exploreFilterType === "favorites") return loadFavorites("", requestId)
    if (exploreFilterType === "selected") return loadSelection("", requestId)
    return renderGroupType()
  }
  try {
    if (exploreFilterType === "favorites") return await loadFavorites(normalized, requestId)
    if (exploreFilterType === "selected") return loadSelection(normalized, requestId)
    const params = new URLSearchParams({ query: normalized, page: String(page), pageSize: "18", semantic: "true" })
    if (activeGroup?.type && activeGroup?.key) { params.set("type", activeGroup.type); params.set("key", activeGroup.key) }
    const value = await window.contextShelf.request(`/catalog/assets?${params.toString()}`)
    if (requestId !== exploreRequestId || mode !== "explore") return
    renderResults(value)
    appendPagination(value, (page) => loadExploreQuery(normalized, page))
  } catch (error) {
    if (requestId === exploreRequestId) showEmpty(error.message || "No se pudo buscar en la biblioteca.")
  }
}

async function loadGroup(button) {
  return loadGroupPage(button.dataset.groupType, button.dataset.groupKey, 1)
}

function appendPagination(value, onPage) {
  if (!value || value.total <= value.pageSize) return
  const pagination = document.createElement("div")
  pagination.className = "group-pagination"
  pagination.innerHTML = `<button class="group-page" data-page="${Math.max(1, value.page - 1)}" ${value.page <= 1 ? "disabled" : ""}>← Anterior</button><span>Página ${value.page} · ${value.total} recursos</span><button class="group-page" data-page="${value.page + 1}" ${value.page * value.pageSize >= value.total ? "disabled" : ""}>Siguiente →</button>`
  $("#results").appendChild(pagination)
  for (const pageButton of pagination.querySelectorAll(".group-page")) pageButton.addEventListener("click", () => onPage(Number(pageButton.dataset.page)))
}

async function loadGroupPage(type, key, page) {
  const requestId = ++exploreRequestId
  activeGroup = { type, key, page }
  const target = document.querySelector(`[data-group-type="${CSS.escape(type)}"][data-group-key="${CSS.escape(key)}"]`)
  if (target) target.disabled = true
  try {
    const query = new URLSearchParams({ type, key, page: String(page), pageSize: "18" })
    const value = await window.contextShelf.request(`/catalog/assets?${query.toString()}`)
    if (requestId !== exploreRequestId || mode !== "explore") return
    renderResults(value)
    appendPagination(value, (nextPage) => loadGroupPage(type, key, nextPage))
  } catch (error) {
    if (requestId === exploreRequestId && mode === "explore") showEmpty(error.message || "No se pudo abrir el grupo.")
  } finally {
    if (target) target.disabled = false
  }
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>\"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[character]))
}

function familyKey(item) {
  const source = String(item.relativePath || item.file || item.name || item.label || item.assetId || "")
  const leaf = source.split(/[\\/]/).pop() || source
  const key = leaf.replace(/\.[a-z0-9]+$/i, "")
    .toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/^(?:iconify[-_])/, "")
    .replace(/^(?:material-symbols|healthicons|bioicons|tabler|mdi|icon-park)[-_]/, "")
    .replace(/\b(?:outline|filled|regular|light|thin|bold|duotone|two-tone|multicolor|mono|icon|svg|png|jpeg|jpg)\b/g, " ")
    .replace(/[-_]\d+$/i, "")
    .replace(/(?:[-_](?:24|32|48|96|128|256|512))?(?:px)?$/i, "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
  return key.length >= 2 ? key : String(item.assetId || source)
}

function persistFavorites() {
  try {
    localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify([...favoriteIds]))
    localStorage.setItem(FAVORITE_RECORDS_STORAGE_KEY, JSON.stringify([...favoriteRecords.values()]))
  } catch (_) {}
}

function toggleFavorite(assetId, item = null) {
  if (favoriteIds.has(assetId)) {
    favoriteIds.delete(assetId)
    favoriteRecords.delete(assetId)
  } else {
    favoriteIds.add(assetId)
    const record = item || assetsById.get(assetId)
    if (record && !record.local) favoriteRecords.set(assetId, { ...record })
  }
  persistFavorites()
}

function updateFavoriteButtons(assetId) {
  const active = favoriteIds.has(assetId)
  for (const button of document.querySelectorAll(`.favorite[data-asset-id="${CSS.escape(assetId)}"]`)) {
    button.classList.toggle("active", active)
    button.textContent = active ? "★" : "☆"
    button.title = active ? "Quitar de guardados" : "Guardar recurso"
    button.setAttribute("aria-label", active ? "Quitar de guardados" : "Guardar recurso")
  }

  const peekButton = $("#peek-favorite")
  if (peekButton?.dataset.assetId !== assetId) return
  peekButton.classList.toggle("active", active)
  peekButton.textContent = active ? "★" : "☆"
  peekButton.title = active ? "Quitar de guardados" : "Guardar recurso"
  peekButton.setAttribute("aria-label", active ? "Quitar de guardados" : "Guardar recurso")
}

async function loadFavorites(query = "", requestId = null) {
  const ids = [...favoriteIds]
  if (!ids.length) return showEmpty("Todavía no tienes recursos guardados.")
  try {
    const localIds = ids.filter((assetId) => !favoriteRecords.has(assetId))
    const localValue = localIds.length
      ? await window.contextShelf.request(`/catalog/assets?${new URLSearchParams({ ids: localIds.join(","), query, page: "1", pageSize: "100" }).toString()}`)
      : { results: [] }
    const queryTerms = String(query || "").toLowerCase().trim().split(/\s+/).filter(Boolean)
    const remoteResults = ids.map((assetId) => favoriteRecords.get(assetId)).filter(Boolean).filter((item) => {
      const searchable = [item.label, item.name, item.provider, item.id, ...(item.reasons || [])].filter(Boolean).join(" ").toLowerCase()
      return !queryTerms.length || queryTerms.every((term) => searchable.includes(term))
    })
    if (requestId !== null && (requestId !== exploreRequestId || mode !== "explore")) return
    const results = [...(localValue.results || []), ...remoteResults].map((item, index) => ({ ...item, rank: index + 1 }))
    renderResults({ ...localValue, query, total: results.length, results })
  } catch (error) {
    if (requestId === null || requestId === exploreRequestId) showEmpty(error.message || "No se pudieron cargar los recursos guardados.")
  }
}

function loadSelection(query = "", requestId = null) {
  const selectedItems = getSelectionBucket()?.checkedAssets || []
  const queryTerms = String(query || "").toLowerCase().trim().split(/\s+/).filter(Boolean)
  const results = selectedItems.filter((item) => {
    const searchable = [item.label, item.name, item.provider, item.id, item.format].filter(Boolean).join(" ").toLowerCase()
    return !queryTerms.length || queryTerms.every((term) => searchable.includes(term))
  }).map((item, index) => ({ ...item, rank: index + 1 }))
  if (requestId !== null && (requestId !== exploreRequestId || mode !== "explore")) return
  if (!results.length) return showEmpty(query ? "No hay elegidos que coincidan con esa búsqueda." : "Todavía no has elegido recursos para esta lámina.")
  renderResults({ page: 1, pageSize: results.length, query, total: results.length, results })
}

function groupVisualFamilies(results) {
  const families = new Map()
  for (const item of results) {
    const key = familyKey(item)
    if (!families.has(key)) families.set(key, [])
    families.get(key).push(item)
  }
  return [...families.values()]
}

function assetCard(item) {
  const label = escapeHtml(item.label || item.name || item.id || item.assetId)
  const format = escapeHtml(String(item.format || item.formats?.[0] || (item.local ? "asset" : "SVG")).toUpperCase())
  const dimensions = item.width && item.height ? ` · ${item.width}×${item.height}` : ""
  const inventoryStatus = item.inventoryStatus ? ` · ${escapeHtml(item.inventoryStatus)}` : ""
  const layerName = item.layerName ? ` · ${escapeHtml(item.layerName)}` : ""
  const favorite = favoriteIds.has(item.assetId)
  const selected = isAssetSelected(item.assetId)
  const selectionDisabled = mode === "project" && projectSlideFilter === "all"
  const draggable = item.local && item.file ? "true" : "false"
  const dragHint = item.local && item.file ? " · Arrastra a Photoshop o Illustrator" : ""
  return `<article class="asset" data-asset-id="${escapeHtml(item.assetId)}" draggable="${draggable}" title="${label}${dragHint}"><div class="thumb" data-thumb-id="${escapeHtml(item.assetId)}" role="button" tabindex="0" aria-label="Previsualizar ${label}">${item.local ? "…" : "SVG"}</div><div class="asset-meta">${format}${dimensions}${inventoryStatus}${layerName}</div><button class="select-asset ${selected ? "active" : ""}" type="button" title="${selectionDisabled ? "Elige una lámina para guardar checks" : selected ? "Quitar de esta lámina" : "Seleccionar para esta lámina"}" aria-label="${selectionDisabled ? "Elige una lámina para guardar checks" : selected ? "Quitar de esta lámina" : "Seleccionar para esta lámina"}" data-asset-id="${escapeHtml(item.assetId)}"${selectionDisabled ? " disabled" : ""}>${selected ? "✓" : "□"}</button><button class="favorite ${favorite ? "active" : ""}" type="button" title="${favorite ? "Quitar de guardados" : "Guardar recurso"}" aria-label="${favorite ? "Quitar de guardados" : "Guardar recurso"}" data-asset-id="${escapeHtml(item.assetId)}">${favorite ? "★" : "☆"}</button><button class="insert" title="Insertar recurso" aria-label="Insertar ${label}" data-provider="${escapeHtml(item.provider)}" data-id="${escapeHtml(item.id)}" data-asset-id="${escapeHtml(item.assetId)}">+</button></article>`
}

function enableAssetDrag() {
  for (const card of document.querySelectorAll('.asset[draggable="true"]')) {
    const item = assetsById.get(card.dataset.assetId)
    if (!item?.file) continue
    card.addEventListener("dragstart", (event) => {
      event.preventDefault()
      window.contextShelf.drag(item.file)
      card.classList.add("dragging")
    })
    card.addEventListener("dragend", () => card.classList.remove("dragging"))
  }
}

function prepareVisibleResults(results) {
  visibleResults = results
  assetsById.clear()
  for (const item of results) assetsById.set(item.assetId, item)
}

function observeAssetPreviews() {
  previewObserver?.disconnect()
  previewObserver = null

  const thumbs = [...document.querySelectorAll(".thumb[data-thumb-id]")]
  const loadFor = (target) => {
    const item = assetsById.get(target.dataset.thumbId)
    if (!item || target.dataset.previewState) return
    target.dataset.previewState = "loading"
    loadPreview(item, target)
  }

  if (!("IntersectionObserver" in window)) {
    thumbs.slice(0, 40).forEach(loadFor)
    return
  }

  previewObserver = new IntersectionObserver((entries, observer) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue
      observer.unobserve(entry.target)
      loadFor(entry.target)
    }
  }, { rootMargin: "360px 0px", threshold: 0.01 })

  for (const thumb of thumbs) previewObserver.observe(thumb)
}

function bindAssetCards() {
  for (const button of document.querySelectorAll(".insert")) button.addEventListener("click", () => insert(button))
  for (const button of document.querySelectorAll(".select-asset")) button.addEventListener("click", () => {
    const item = assetsById.get(button.dataset.assetId)
    const active = toggleAssetSelection(item)
    updateSelectionButtons(button.dataset.assetId)
    if (exploreFilterType === "selected" && !active) {
      const card = button.closest(".asset")
      const family = card?.closest(".asset-family")
      visibleResults = visibleResults.filter((candidate) => candidate.assetId !== button.dataset.assetId)
      assetsById.delete(button.dataset.assetId)
      card?.remove()
      if (family && !family.querySelector(".asset")) family.remove()
      if (!document.querySelector(".asset")) showEmpty("Todavía no has elegido recursos para esta lámina.")
    }
  })
  for (const button of document.querySelectorAll(".favorite")) button.addEventListener("click", () => {
    toggleFavorite(button.dataset.assetId, assetsById.get(button.dataset.assetId))
    const active = favoriteIds.has(button.dataset.assetId)
    updateFavoriteButtons(button.dataset.assetId)
    if (exploreFilterType === "favorites" && !active) {
      const card = button.closest(".asset")
      const family = card?.closest(".asset-family")
      card?.remove()
      if (family && !family.querySelector(".asset")) family.remove()
    }
  })
  enableAssetDrag()
  for (const thumb of document.querySelectorAll(".thumb")) {
    thumb.addEventListener("click", () => openPeek(thumb.dataset.thumbId))
    thumb.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openPeek(thumb.dataset.thumbId) } })
  }
  observeAssetPreviews()
}

function renderResults(value) {
  const results = value?.results || []
  if (!results.length) return showEmpty(value?.errors?.join(" · ") || "Todavía no hay sugerencias para este contexto.")
  prepareVisibleResults(results)
  const families = groupVisualFamilies(results)
  $("#results").innerHTML = families.map((items) => {
    if (items.length === 1) return assetCard(items[0])
    const label = escapeHtml(items[0].label || items[0].name || "Familia visual")
    return `<section class="asset-family" title="${label}"><div class="family-badge"><span aria-hidden="true">✦</span>${items.length} variantes</div><div class="family-grid">${items.map((item) => assetCard(item)).join("")}</div></section>`
  }).join("")
  bindAssetCards()
}

async function loadPreview(item, target) {
  try {
    const source = item.local ? await window.contextShelf.preview(item.previewFile || item.file) : item.previewUrl
    if (!source || !target?.isConnected) {
      if (target) target.dataset.previewState = "unavailable"
      return
    }
    const image = document.createElement("img")
    image.alt = item.label || ""
    image.draggable = false
    image.addEventListener("load", () => {
      if (!target.isConnected) return
      target.replaceChildren(image)
      target.dataset.previewState = "loaded"
    }, { once: true })
    image.addEventListener("error", () => {
      if (target.isConnected) {
        target.textContent = "…"
        target.dataset.previewState = "error"
      }
    }, { once: true })
    image.src = source
  } catch (_) {
    if (target?.isConnected) {
      target.textContent = "…"
      target.dataset.previewState = "error"
    }
  }
}

function licenseLabel(license) {
  if (!license) return "licencia por revisar"
  if (typeof license === "string") return license
  return license.title || license.spdx || "licencia por revisar"
}

async function renderPeekItem() {
  const item = visibleResults[peekIndex]
  if (!item) return
  const label = item.label || item.name || item.id || "Recurso"
  const format = String(item.format || item.formats?.[0] || "SVG").toUpperCase()
  const source = item.local ? "biblioteca local" : item.provider || "fuente remota"
  const dimensions = item.width && item.height ? `${item.width}×${item.height}` : null
  const meta = [source, format, dimensions, licenseLabel(item.license)].filter(Boolean).join(" · ")
  $("#peek-title").textContent = label
  $("#peek-meta").textContent = meta
  const selectButton = $("#peek-select")
  selectButton.dataset.assetId = item.assetId
  updateSelectionButtons(item.assetId)
  const favoriteButton = $("#peek-favorite")
  favoriteButton.dataset.assetId = item.assetId
  updateFavoriteButtons(item.assetId)
  $("#peek-previous").disabled = peekIndex <= 0
  $("#peek-next").disabled = peekIndex >= visibleResults.length - 1
  const insertButton = $("#peek-insert")
  insertButton.dataset.assetId = item.assetId
  insertButton.dataset.provider = item.provider || "local"
  insertButton.dataset.id = item.id || item.relativePath || item.assetId
  const imageTarget = $("#peek-image")
  imageTarget.textContent = item.local ? "…" : "SVG"
  if ((item.local && (item.previewFile || item.file)) || item.previewUrl) {
    try {
      const sourceUrl = item.local ? await window.contextShelf.preview(item.previewFile || item.file) : item.previewUrl
      if (visibleResults[peekIndex] !== item) return
      imageTarget.textContent = ""
      const image = document.createElement("img")
      image.alt = label
      image.src = sourceUrl
      imageTarget.appendChild(image)
    } catch (_) {}
  }
}

function openPeek(assetId) {
  peekIndex = visibleResults.findIndex((item) => item.assetId === assetId)
  if (peekIndex < 0) return
  const peek = $("#peek")
  peek.hidden = false
  peek.setAttribute("aria-hidden", "false")
  renderPeekItem()
}

function closePeek() {
  const peek = $("#peek")
  peek.hidden = true
  peek.setAttribute("aria-hidden", "true")
  peekIndex = -1
}

function movePeek(offset) {
  const nextIndex = peekIndex + offset
  if (nextIndex < 0 || nextIndex >= visibleResults.length) return
  peekIndex = nextIndex
  renderPeekItem()
}

$("#peek-close").addEventListener("click", closePeek)
$("#peek-backdrop").addEventListener("click", closePeek)
$("#peek-previous").addEventListener("click", () => movePeek(-1))
$("#peek-next").addEventListener("click", () => movePeek(1))
$("#peek-select").addEventListener("click", () => {
  const item = visibleResults[peekIndex]
  if (!item) return
  const active = toggleAssetSelection(item)
  updateSelectionButtons(item.assetId)
  if (exploreFilterType === "selected" && !active) closePeek()
})
$("#peek-favorite").addEventListener("click", () => {
  const item = visibleResults[peekIndex]
  if (!item) return
  toggleFavorite(item.assetId, item)
  updateFavoriteButtons(item.assetId)
  if (exploreFilterType === "favorites" && !favoriteIds.has(item.assetId)) closePeek()
})
$("#peek-insert").addEventListener("click", () => {
  const item = visibleResults[peekIndex]
  if (item) insertAsset(item, $("#peek-insert"))
})
document.addEventListener("keydown", (event) => {
  if ($("#peek").hidden) return
  if (event.key === "Escape") closePeek()
  if (event.key === "ArrowLeft") movePeek(-1)
  if (event.key === "ArrowRight") movePeek(1)
})

$("#explore-query").addEventListener("input", (event) => {
  clearTimeout(exploreQueryTimer)
  exploreQueryTimer = setTimeout(() => loadExploreQuery(event.target.value), 220)
})
$("#explore-reset").addEventListener("click", () => {
  $("#explore-query").value = ""
  exploreRequestId += 1
  activeGroup = null
  exploreFilterType = "theme"
  renderExploreControls()
  renderGroupType()
})

$("#project-select").addEventListener("change", (event) => {
  projectSelectedId = event.target.value || null
  projectInventory = null
  projectSlideFilter = null
  projectStatusFilter = "all"
  projectQuery = ""
  $("#project-query").value = ""
  loadProjectInventory()
})
$("#project-refresh").addEventListener("click", () => loadProjectInventory({ refresh: true }))
$("#project-query").addEventListener("input", (event) => {
  projectQuery = event.target.value || ""
  clearTimeout(exploreQueryTimer)
  exploreQueryTimer = setTimeout(() => renderProjectView(), 180)
})

async function insertAsset(item, button) {
  if (!item) return
  const originalLabel = button.textContent
  if (!current?.sessionId) {
    button.textContent = "Adobe"
    button.title = "Conecta Photoshop o Illustrator para insertar"
    return setTimeout(() => { button.textContent = originalLabel; button.title = "Insertar recurso" }, 1200)
  }
  button.disabled = true
  try {
    await window.contextShelf.request("/insert", {
      method: "POST",
      body: JSON.stringify({
        sessionId: current.sessionId,
        asset: { assetId: item.assetId, provider: item.provider, id: item.id, file: item.file || null },
        mode: "unitary", placement: "safe-region", colorPolicy: "original",
      }),
    })
    button.textContent = "✓"
  } catch (error) {
    button.textContent = "!"
    button.title = error.message
  } finally {
    setTimeout(() => { button.textContent = originalLabel; button.title = "Insertar recurso"; button.disabled = false }, 900)
  }
}

async function insert(button) {
  return insertAsset(assetsById.get(button.dataset.assetId), button)
}

async function poll() {
  if (pollInFlight) return
  pollInFlight = true
  try {
    const response = await window.contextShelf.request("/context/current")
    setConnection(true)
    refreshSemanticStatus()
    await refreshSignalSurface(response.context?.sessionId || null)

    // Explorar usa únicamente el índice local; no necesita un documento de Adobe.
    if (mode === "explore") {
      showContext(response.context || null)
      const nextSelectionScopeHash = activeSelectionScopeHash(response.context || null)
      const selectionScopeChanged = selectionScopeHash !== nextSelectionScopeHash
      selectionScopeHash = nextSelectionScopeHash
      if (selectionScopeChanged && exploreFilterType === "selected" && exploreHash === "catalog") {
        const requestId = ++exploreRequestId
        return await loadSelection("", requestId)
      }
      if (exploreHash === "catalog") return
      exploreHash = "catalog"
      return await loadGroups()
    }

    if (mode === "project") {
      showContext(response.context || null)
      renderSelectionScope()
      if (!projectInventory) return await loadProjectInventory()
      return
    }

    if (!response.context) {
      showContext(null)
      return showEmpty("Abre el panel Context Shelf dentro de Photoshop.")
    }
    showContext(response.context)
    if (mode === "layers") {
      if (diagnosticHash === response.context.contextHash) return
      diagnosticHash = response.context.contextHash
      return renderLayerDiagnostics(response.context.analysis?.layers)
    }
    if (mode !== "suggested") return showEmpty(`El modo ${mode} se habilitará después del vertical slice.`)
    if (recommendationHash === response.context.contextHash) return
    recommendationHash = response.context.contextHash
    const recommendations = await window.contextShelf.request("/recommendations", {
      method: "POST",
      body: JSON.stringify({ sessionId: response.context.sessionId, limit: 8 }),
    })
    renderResults(recommendations)
  } catch (error) {
    setConnection(false)
    showEmpty(error.message || "Bridge no disponible")
  } finally {
    pollInFlight = false
  }
}

for (const tab of document.querySelectorAll(".tab")) tab.addEventListener("click", () => {
  for (const item of document.querySelectorAll(".tab")) item.classList.remove("active")
  tab.classList.add("active")
  mode = tab.dataset.mode
  recommendationHash = null
  diagnosticHash = null
  exploreHash = null
  selectionScopeHash = null
  exploreRequestId += 1
  closePeek()
  renderExploreControls()
  renderProjectControls()
  if (mode === "project") return loadProjectInventory()
  poll()
})

poll()
setInterval(poll, 1200)

// Photoshop ExtendScript fallback queue consumer.
// UXP (agent.psjs) is the primary adapter; this script supports legacy
// ExtendScript/COM hosts where UXP tooling is not available.
#include "../json-compat.jsxinc"
var TOOLKIT_ROOT = "C:/IA/LUCIDA/adobe";

function pad(value) { return value < 10 ? "0" + value : String(value); }
function timestamp() {
  var d = new Date();
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " +
    pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
}

function allowedPath(value) {
  var candidate = String(value || "").replace(/\\/g, "/").toLowerCase();
  var root = TOOLKIT_ROOT.replace(/\\/g, "/").toLowerCase();
  return candidate === root || candidate.indexOf(root + "/") === 0;
}

function readJson(file) {
  file.open("r");
  var value = AgentJson.parse(file.read());
  file.close();
  return value;
}

function writeJson(file, value) {
  file.parent.create();
  file.open("w");
  file.write(AgentJson.stringify(value));
  file.close();
}

function resultFor(commandFile, command, state, data, error) {
  var results = new Folder(commandFile.parent.parent.fsName + "/results");
  var result = {
    id: command.id,
    app: "photoshop",
    state: state,
    data: data || {},
    error: error || null,
    finishedAt: timestamp()
  };
  writeJson(new File(results.fsName + "/" + command.id + ".json"), result);
  return result;
}

function finish(commandFile, command, state, data, error) {
  command.state = state;
  command.finishedAt = timestamp();
  command.error = error || null;
  writeJson(commandFile, command);
  return resultFor(commandFile, command, state, data, error);
}

function saveDocument(document, output) {
  if (!output) return null;
  if (!allowedPath(output)) throw new Error("Output must be inside the toolkit root");
  var target = new File(output);
  var extension = output.toLowerCase().split(".").pop();
  if (extension === "psd") {
    document.saveAs(target, new PhotoshopSaveOptions(), true, Extension.LOWERCASE);
  } else if (extension === "png") {
    document.saveAs(target, new PNGSaveOptions(), true, Extension.LOWERCASE);
  } else if (extension === "jpg" || extension === "jpeg") {
    var options = new JPEGSaveOptions();
    options.quality = 12;
    document.saveAs(target, options, true, Extension.LOWERCASE);
  } else {
    throw new Error("Unsupported Photoshop output format: " + extension);
  }
  return output;
}

function importSvg(command) {
  if (!command.input || !allowedPath(command.input)) throw new Error("Input must be inside the toolkit root");
  var source = new File(command.input);
  if (!source.exists) throw new Error("Input file does not exist: " + source.fsName);
  var previousDialogs = app.displayDialogs;
  app.displayDialogs = DialogModes.NO;
  try {
    var document = app.open(source);
    var output = saveDocument(document, (command.options || {}).output || null);
    return { document: document.name, output: output };
  } finally {
    app.displayDialogs = previousDialogs;
  }
}

function safeName(value, fallback) {
  var normalized = String(value || fallback || "object").replace(/[^a-z0-9áéíóúñü _-]/gi, "").replace(/\s+/g, "-").slice(0, 64);
  return normalized || fallback || "object";
}

function numberValue(value) {
  try { return Number(value.as("px")); } catch (_) { return Number(value); }
}

function normalizeBounds(raw, width, height, padding) {
  var source = raw && raw.bounds ? raw.bounds : raw;
  if (!source) throw new Error("Each object region needs bounds");
  var left = Number(source.left !== undefined ? source.left : (source.x || 0));
  var top = Number(source.top !== undefined ? source.top : (source.y || 0));
  var right = Number(source.right !== undefined ? source.right : left + Number(source.width || 0));
  var bottom = Number(source.bottom !== undefined ? source.bottom : top + Number(source.height || 0));
  var pad = Math.max(0, Number(padding || 0));
  return [
    Math.max(0, Math.floor(left - pad)),
    Math.max(0, Math.floor(top - pad)),
    Math.min(width, Math.ceil(right + pad)),
    Math.min(height, Math.ceil(bottom + pad))
  ];
}

function selectSubject() {
  var descriptor = new ActionDescriptor();
  descriptor.putBoolean(stringIDToTypeID("sampleAllLayers"), false);
  executeAction(stringIDToTypeID("autoCutout"), descriptor, DialogModes.NO);
}

function revealSelectionMask() {
  var descriptor = new ActionDescriptor();
  var reference = new ActionReference();
  descriptor.putClass(stringIDToTypeID("new"), stringIDToTypeID("channel"));
  reference.putEnumerated(stringIDToTypeID("channel"), stringIDToTypeID("channel"), stringIDToTypeID("mask"));
  descriptor.putReference(stringIDToTypeID("at"), reference);
  descriptor.putEnumerated(stringIDToTypeID("using"), stringIDToTypeID("userMaskEnabled"), stringIDToTypeID("revealSelection"));
  executeAction(stringIDToTypeID("make"), descriptor, DialogModes.NO);
}

function selectRectangle(document, bounds) {
  document.selection.select([
    [bounds[0], bounds[1]],
    [bounds[2], bounds[1]],
    [bounds[2], bounds[3]],
    [bounds[0], bounds[3]]
  ]);
}

function findLayer(document, name) {
  for (var i = 0; i < document.layers.length; i++) {
    if (document.layers[i].name === name) return document.layers[i];
  }
  return null;
}

function exportMaskedLayer(document, layerName, cropBounds, outputDir, sourceWidth, sourceHeight, index, placementBounds, selectionMethod) {
  placementBounds = placementBounds || {
    left: cropBounds[0], top: cropBounds[1], right: cropBounds[2], bottom: cropBounds[3]
  };
  var exportDocument = document.duplicate(safeName(layerName, "object") + " export", false);
  try {
    var exportLayer = findLayer(exportDocument, layerName);
    if (!exportLayer) throw new Error("Duplicated layer not found: " + layerName);
    for (var i = 0; i < exportDocument.layers.length; i++) exportDocument.layers[i].visible = exportDocument.layers[i] === exportLayer;
    exportDocument.crop([cropBounds[0], cropBounds[1], cropBounds[2], cropBounds[3]]);
    var outputFile = new File(outputDir + "/" + ("0" + (index + 1)).slice(-2) + "-" + safeName(layerName, "object") + ".png");
    var pngOptions = new PNGSaveOptions();
    exportDocument.saveAs(outputFile, pngOptions, true, Extension.LOWERCASE);
    return {
      id: safeName(layerName, "object"),
      name: layerName,
      file: outputFile.fsName,
      bounds: placementBounds,
      sourceCanvas: { width: sourceWidth, height: sourceHeight },
      placement: {
        x: placementBounds.left / sourceWidth,
        y: placementBounds.top / sourceHeight,
        width: (placementBounds.right - placementBounds.left) / sourceWidth,
        height: (placementBounds.bottom - placementBounds.top) / sourceHeight
      },
      anchor: "full",
      fit: "contain",
      importMode: "raster",
      role: "illustration",
      singleSlide: true,
      selectionMethod: selectionMethod || "mask"
    };
  } finally {
    exportDocument.close(SaveOptions.DONOTSAVECHANGES);
  }
}

function separateRegionAsObject(document, sourceBounds, layerName, outputDir, sourceWidth, sourceHeight, index, padding) {
  var regionDocument = document.duplicate(safeName(layerName, "object") + " detect", false);
  try {
    regionDocument.crop([sourceBounds[0], sourceBounds[1], sourceBounds[2], sourceBounds[3]]);
    var regionLayer = regionDocument.layers[0];
    if (!regionLayer) throw new Error("Region copy has no source layer");
    regionDocument.activeLayer = regionLayer;
    selectSubject();
    var selectionBounds = regionDocument.selection.bounds;
    if (!selectionBounds) throw new Error("Select Subject returned no region selection");
    var regionWidth = numberValue(regionDocument.width);
    var regionHeight = numberValue(regionDocument.height);
    if (numberValue(selectionBounds[0]) <= 0 && numberValue(selectionBounds[1]) <= 0 && numberValue(selectionBounds[2]) >= regionWidth - 1 && numberValue(selectionBounds[3]) >= regionHeight - 1) {
      throw new Error("Select Subject returned the whole region; rectangle fallback used");
    }
    var localBounds = normalizeBounds({
      left: numberValue(selectionBounds[0]),
      top: numberValue(selectionBounds[1]),
      right: numberValue(selectionBounds[2]),
      bottom: numberValue(selectionBounds[3])
    }, regionWidth, regionHeight, padding);
    var layer = regionLayer.duplicate();
    layer.name = layerName;
    regionDocument.activeLayer = layer;
    revealSelectionMask();
    for (var i = 0; i < regionDocument.layers.length; i++) regionDocument.layers[i].visible = regionDocument.layers[i] === layer;
    layer.copy(true);
    app.activeDocument = document;
    var outputLayer = document.paste();
    outputLayer.name = layerName;
    var currentBounds = outputLayer.bounds;
    var placementBounds = {
      left: sourceBounds[0] + localBounds[0],
      top: sourceBounds[1] + localBounds[1],
      right: sourceBounds[0] + localBounds[2],
      bottom: sourceBounds[1] + localBounds[3]
    };
    if (currentBounds) outputLayer.translate(placementBounds.left - numberValue(currentBounds[0]), placementBounds.top - numberValue(currentBounds[1]));
    return exportMaskedLayer(regionDocument, layerName, localBounds, outputDir, sourceWidth, sourceHeight, index, placementBounds, "select-subject-in-region-transparent-copy");
  } finally {
    regionDocument.close(SaveOptions.DONOTSAVECHANGES);
  }
}

function separateObjects(command) {
  if (!command.input || !allowedPath(command.input)) throw new Error("Input must be inside the toolkit root");
  var options = command.options || {};
  var source = new File(command.input);
  if (!source.exists) throw new Error("Input file does not exist: " + source.fsName);
  var outputDir = new Folder(options.outputDir || new File(options.output).parent.fsName);
  outputDir.create();
  var previousDialogs = app.displayDialogs;
  var previousRulerUnits = app.preferences.rulerUnits;
  app.displayDialogs = DialogModes.NO;
  app.preferences.rulerUnits = Units.PIXELS;
  var document = app.open(source);
  var sourceWidth = numberValue(document.width);
  var sourceHeight = numberValue(document.height);
  var mode = String(options.mode || (options.objects ? "regions" : "subject")).toLowerCase();
  var objects = options.objects instanceof Array ? options.objects : [];
  var assets = [];
  try {
    var baseLayer = document.layers[0];
    if (!baseLayer) throw new Error("Photoshop document has no source layer");
    if (mode === "subject") {
      document.activeLayer = baseLayer;
      selectSubject();
      var subjectBounds = document.selection.bounds;
      if (!subjectBounds) throw new Error("Photoshop Select Subject returned no selection");
      var subjectRect = normalizeBounds({ left: numberValue(subjectBounds[0]), top: numberValue(subjectBounds[1]), right: numberValue(subjectBounds[2]), bottom: numberValue(subjectBounds[3]) }, sourceWidth, sourceHeight, options.padding);
      var subjectName = safeName(options.subjectName, "subject-01");
      var subjectLayer = baseLayer.duplicate();
      subjectLayer.name = subjectName;
      document.activeLayer = subjectLayer;
      revealSelectionMask();
      assets.push(exportMaskedLayer(document, subjectName, subjectRect, outputDir.fsName, sourceWidth, sourceHeight, 0));
    } else if (mode === "regions") {
      if (!objects.length) throw new Error("regions mode requires options.objects with named bounds");
      for (var index = 0; index < objects.length; index++) {
        var item = objects[index] || {};
        var bounds = normalizeBounds(item, sourceWidth, sourceHeight, options.padding);
        var name = safeName(item.name, "object-" + ("0" + (index + 1)).slice(-2));
        var selectionMode = String(item.selectionMode || options.selectionMode || "object").toLowerCase();
        var selectionError = null;
        if (selectionMode === "object") {
          try {
            assets.push(separateRegionAsObject(document, bounds, name, outputDir.fsName, sourceWidth, sourceHeight, index, Number(options.objectPadding !== undefined ? options.objectPadding : 2)));
            continue;
          } catch (error) {
            selectionError = String(error);
            // Keep the deterministic rectangle fallback when Photoshop's AI
            // cannot isolate a usable subject in this region.
          }
        }
        selectRectangle(document, bounds);
        var layer = baseLayer.duplicate();
        layer.name = name;
        document.activeLayer = layer;
        revealSelectionMask();
        var fallback = exportMaskedLayer(document, name, bounds, outputDir.fsName, sourceWidth, sourceHeight, index, {
          left: bounds[0], top: bounds[1], right: bounds[2], bottom: bounds[3]
        }, "rectangle-fallback");
        if (selectionError) fallback.selectionError = selectionError;
        assets.push(fallback);
      }
    } else {
      throw new Error("Unsupported Photoshop separation mode: " + mode);
    }
    if (options.psdOutput) {
      var psdOptions = new PhotoshopSaveOptions();
      document.saveAs(new File(options.psdOutput), psdOptions, true, Extension.LOWERCASE);
    }
    var manifest = {
      version: 1,
      app: "photoshop",
      operation: "separate-objects",
      mode: mode,
      source: command.input,
      canvas: { width: sourceWidth, height: sourceHeight },
      singleSlide: true,
      psd: options.psdOutput || null,
      assets: assets
    };
    writeJson(new File(options.output), manifest);
    return manifest;
  } finally {
    document.close(SaveOptions.DONOTSAVECHANGES);
    app.displayDialogs = previousDialogs;
    app.preferences.rulerUnits = previousRulerUnits;
  }
}

function consumeNext() {
  var jobs = new Folder(TOOLKIT_ROOT + "/jobs");
  if (!jobs.exists) return { state: "empty" };
  var folders = jobs.getFiles();
  var selectedFile = null;
  var selectedCommand = null;
  for (var i = 0; i < folders.length; i++) {
    if (!(folders[i] instanceof Folder)) continue;
    var commands = new Folder(folders[i].fsName + "/adobe/commands");
    if (!commands.exists) continue;
    var files = commands.getFiles("*.json");
    for (var j = 0; j < files.length; j++) {
      var candidate = readJson(files[j]);
      if (candidate.app !== "photoshop" || candidate.state !== "queued") continue;
      if (!selectedCommand || String(candidate.createdAt) > String(selectedCommand.createdAt)) {
        selectedFile = files[j];
        selectedCommand = candidate;
      }
    }
  }
  if (!selectedFile || !selectedCommand) return { state: "empty" };
  try {
    var data = selectedCommand.operation === "import-svg" ? importSvg(selectedCommand) :
      selectedCommand.operation === "separate-objects" ? separateObjects(selectedCommand) : null;
    if (!data) throw new Error("Unsupported Photoshop operation: " + selectedCommand.operation);
    return finish(selectedFile, selectedCommand, "completed", data, null);
  } catch (error) {
    return finish(selectedFile, selectedCommand, "failed", {}, String(error));
  }
}

try {
  consumeNext();
} catch (error) {
  var diagnostic = new File(TOOLKIT_ROOT + "/adapters/adobe/photoshop/last-error.txt");
  diagnostic.parent.create();
  diagnostic.open("w");
  diagnostic.write(timestamp() + "\n" + String(error));
  diagnostic.close();
  throw error;
}

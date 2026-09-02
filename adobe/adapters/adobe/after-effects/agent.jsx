// After Effects queue consumer. Run from After Effects' scripting menu first;
// it consumes one queued command and writes a result envelope back to the job.
#include "../json-compat.jsxinc"
// Resolve the package from this script so the adapter survives a clone or
// worktree move. Technical paths stay local to the current checkout.
var TOOLKIT_ROOT = new File($.fileName).parent.parent.parent.fsName;

function pad(value) {
  return value < 10 ? "0" + value : String(value);
}

// ExtendScript does not consistently expose Date.prototype.toISOString().
function timestamp() {
  var d = new Date();
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " +
    pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
}

function writeText(file, value) {
  file.parent.create();
  file.open("w");
  file.write(String(value));
  file.close();
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

function allowedPath(value) {
  var candidate = String(value || "").replace(/\\/g, "/").toLowerCase();
  var root = TOOLKIT_ROOT.replace(/\\/g, "/").toLowerCase();
  return candidate === root || candidate.indexOf(root + "/") === 0;
}

function resultFor(commandFile, command, state, data, error) {
  var results = new Folder(commandFile.parent.parent.fsName + "/results");
  var result = { id: command.id, app: "after-effects", state: state, data: data || {}, error: error || null, finishedAt: timestamp() };
  writeJson(new File(results.fsName + "/" + command.id + ".json"), result);
  return result;
}

function importSvg(command) {
  if (!command.input || !allowedPath(command.input)) throw new Error("Input must be inside the toolkit root");
  var source = new File(command.input);
  if (!source.exists) throw new Error("Input file does not exist: " + source.fsName);
  if (!app.project) app.newProject();
  var imported = app.project.importFile(new ImportOptions(source));
  var options = command.options || {};
  var name = options.compName || source.displayName.replace(/\.[^\.]+$/, "");
  var width = Number(options.width || imported.width || 800);
  var height = Number(options.height || imported.height || 600);
  var duration = Number(options.duration || 5);
  var comp = app.project.items.addComp(name, width, height, 1, duration, 30);
  comp.layers.add(imported);
  if (options.output) {
    if (!allowedPath(options.output)) throw new Error("Output must be inside the toolkit root");
    var queueItem = app.project.renderQueue.items.add(comp);
    queueItem.outputModule(1).file = new File(options.output);
    app.project.renderQueue.render();
  }
  return { composition: name, width: width, height: height, output: options.output || null };
}

function consumeNext() {
  var jobs = new Folder(TOOLKIT_ROOT + "/jobs");
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
      if (candidate.app !== "after-effects" || candidate.state !== "queued") continue;
      if (!selectedCommand || String(candidate.createdAt) > String(selectedCommand.createdAt)) {
        selectedFile = files[j];
        selectedCommand = candidate;
      }
    }
  }
  if (selectedFile && selectedCommand) {
    try {
      app.beginUndoGroup("Agent Toolkit");
      var data = selectedCommand.operation === "import-svg" ? importSvg(selectedCommand) : null;
      if (!data) throw new Error("Unsupported After Effects operation: " + selectedCommand.operation);
      app.endUndoGroup();
      return resultFor(selectedFile, selectedCommand, "completed", data, null);
    } catch (error) {
      try { app.endUndoGroup(); } catch (_) {}
      return resultFor(selectedFile, selectedCommand, "failed", {}, String(error));
    }
  }
  return { state: "empty" };
}

try {
  writeText(new File(TOOLKIT_ROOT + "/adapters/adobe/after-effects/last-run.txt"), timestamp() + "\nscript-started");
  consumeNext();
} catch (error) {
  writeText(new File(TOOLKIT_ROOT + "/adapters/adobe/after-effects/last-error.txt"), timestamp() + "\n" + String(error));
  throw error;
}

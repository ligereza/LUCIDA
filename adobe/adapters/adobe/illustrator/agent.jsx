// Illustrator queue consumer. Run from Illustrator's scripting menu.
#include "../json-compat.jsxinc"
// Resolve the package from this script so the adapter survives a clone or
// worktree move. Technical paths stay local to the current checkout.
var TOOLKIT_ROOT = new File($.fileName).parent.parent.parent.fsName;

function pad(value) {
  return value < 10 ? "0" + value : String(value);
}

function timestamp() {
  var d = new Date();
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " +
    pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
}

function readJson(file) {
  file.open("r");
  var text = file.read();
  file.close();
  return AgentJson.parse(text);
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
  var result = {
    id: command.id,
    app: "illustrator",
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

function importSvg(command) {
  if (!command.input || !allowedPath(command.input)) throw new Error("Input must be inside the toolkit root");
  var source = new File(command.input);
  if (!source.exists) throw new Error("Input file does not exist: " + source.fsName);
  var document = app.open(source, DocumentColorSpace.RGB);
  var options = command.options || {};
  if (options.output) {
    if (!allowedPath(options.output)) throw new Error("Output must be inside the toolkit root");
    var target = new File(options.output);
    var exportOptions = new ExportOptionsSVG();
    document.exportFile(target, ExportType.SVG, exportOptions);
  }
  return { document: document.name, output: options.output || null };
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
      if (candidate.app !== "illustrator" || candidate.state !== "queued") continue;
      if (!selectedCommand || String(candidate.createdAt) > String(selectedCommand.createdAt)) {
        selectedFile = files[j];
        selectedCommand = candidate;
      }
    }
  }
  if (!selectedFile || !selectedCommand) return { state: "empty" };
  var selectedJob = selectedFile.parent.parent.parent;
  var selectedCommands = new Folder(selectedJob.fsName + "/adobe/commands");
  var selectedFiles = selectedCommands.getFiles("*.json");
  var processed = 0;
  for (var k = 0; k < selectedFiles.length; k++) {
    var commandFile = selectedFiles[k];
    var command = readJson(commandFile);
    if (command.app !== "illustrator" || command.state !== "queued") continue;
    try {
      var data = command.operation === "import-svg" ? importSvg(command) : null;
      if (!data) throw new Error("Unsupported Illustrator operation: " + command.operation);
      finish(commandFile, command, "completed", data, null);
    } catch (error) {
      finish(commandFile, command, "failed", {}, String(error));
    }
    processed += 1;
  }
  return { state: "processed", count: processed, job: selectedJob.name };
}

try {
  consumeNext();
} catch (error) {
  var diagnostic = new File(TOOLKIT_ROOT + "/adapters/adobe/illustrator/last-error.txt");
  diagnostic.parent.create();
  diagnostic.open("w");
  diagnostic.write(timestamp() + "\n" + String(error));
  diagnostic.close();
  throw error;
}

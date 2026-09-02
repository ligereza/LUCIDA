// Premiere Pro queue consumer. Run from a CEP/ExtendScript host inside Premiere.
#include "../json-compat.jsxinc"
// Resolve the package from this script so the adapter survives a clone or
// worktree move. Technical paths stay local to the current checkout.
var TOOLKIT_ROOT = new File($.fileName).parent.parent.parent.fsName;

function pad(value) { return value < 10 ? "0" + value : String(value); }
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
  var path = String(value || "").replace(/\\/g, "/").toLowerCase();
  var root = TOOLKIT_ROOT.toLowerCase();
  return path === root || path.indexOf(root + "/") === 0;
}

function resultFor(commandFile, command, state, data, error) {
  var results = new Folder(commandFile.parent.parent.fsName + "/results");
  var result = { id: command.id, app: "premiere", state: state, data: data || {}, error: error || null, finishedAt: timestamp() };
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

function importMedia(command) {
  if (!command.input || !allowedPath(command.input)) throw new Error("Input must be inside the toolkit root");
  var imported = app.project.importFiles([command.input], true, app.project.rootItem, false);
  if (!imported) throw new Error("Premiere could not import the media");
  return { imported: true, input: command.input };
}

function findProjectItem(name) {
  var children = app.project.rootItem.children;
  for (var i = 0; i < children.numItems; i++) {
    if (children[i].name === name) return children[i];
  }
  return null;
}

function createSequence(command) {
  var options = command.options || {};
  var item = findProjectItem(options.clipName);
  if (!item) throw new Error("Project item not found: " + (options.clipName || ""));
  var name = options.sequenceName || "Agent Toolkit Sequence";
  var sequence = app.project.createNewSequenceFromClips(name, [item]);
  if (!sequence) throw new Error("Premiere could not create the sequence");
  return { sequence: sequence.name, sequenceID: sequence.sequenceID };
}

function exportSequence(command) {
  var options = command.options || {};
  if (!options.output || !allowedPath(options.output)) throw new Error("Output must be inside the toolkit root");
  var sequence = app.project.activeSequence;
  if (!sequence) throw new Error("No active Premiere sequence");
  if (!options.preset) throw new Error("An Adobe Media Encoder .epr preset is required");
  var ok = sequence.exportAsMediaDirect(options.output, options.preset, Number(options.workAreaType || 0));
  if (!ok) throw new Error("Premiere failed to export the active sequence");
  return { sequence: sequence.name, output: options.output };
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
      if (candidate.app !== "premiere" || candidate.state !== "queued") continue;
      if (!selectedCommand || String(candidate.createdAt) > String(selectedCommand.createdAt)) {
        selectedFile = files[j];
        selectedCommand = candidate;
      }
    }
  }
  if (!selectedFile || !selectedCommand) return { state: "empty" };
  try {
    var data = selectedCommand.operation === "import-media" ? importMedia(selectedCommand) :
      selectedCommand.operation === "create-sequence" ? createSequence(selectedCommand) :
      selectedCommand.operation === "export-sequence" ? exportSequence(selectedCommand) : null;
    if (!data) throw new Error("Unsupported Premiere operation: " + selectedCommand.operation);
    return finish(selectedFile, selectedCommand, "completed", data, null);
  } catch (error) {
    return finish(selectedFile, selectedCommand, "failed", {}, String(error));
  }
}

try {
  consumeNext();
} catch (error) {
  var diagnostic = new File(TOOLKIT_ROOT + "/adapters/adobe/premiere/last-error.txt");
  diagnostic.parent.create();
  diagnostic.open("w");
  diagnostic.write(timestamp() + "\n" + String(error));
  diagnostic.close();
  throw error;
}

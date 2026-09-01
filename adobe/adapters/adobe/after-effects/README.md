# After Effects adapter

The initial adapter is a JSX contract. The production adapter should import
the generated SVG or PNG sequence, create a composition, apply the requested
timeline, render through the configured After Effects installation, and write a
result envelope into the originating job.

Use `aerender.exe` for repeatable render jobs when the project can be rendered
without interactive UI.

## Consuming the local queue

The JSX consumer must be run inside an interactive After Effects session. The
command-line `-r` option forwards a script to an already-running instance; it
does not reliably bootstrap the desktop session on its own.

1. Open Adobe After Effects 2026 normally.
2. Enable `Edit > Preferences > Scripting & Expressions > Allow Scripts to
   Write Files And Access Network`.
3. Choose `File > Scripts > Run Script File...` and select
   `adapters/adobe/after-effects/agent.jsx`.
4. Verify the originating job has a JSON result under
   `jobs/<job-id>/adobe/results/`.

The consumer records `last-run.txt` when After Effects actually receives the
script, and `last-error.txt` if execution fails before a result can be written.

The Node adapter exposes this as:

```powershell
npm run tool -- adobe render --project C:\path\project.aep --output jobs\render\output\movie
```

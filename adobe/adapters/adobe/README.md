# Adobe adapter contract

The local orchestrator does not attempt to control Adobe windows with mouse
automation. It writes signed-by-workspace command envelopes to:

```text
jobs/<job-id>/adobe/commands/*.json
```

A host-specific UXP plugin or script consumes a command, performs the operation
inside the Adobe document, exports the result to the job output folder, and
writes a matching result file to `jobs/<job-id>/adobe/results/`.

For an Illustrator document workflow, one run with `--adobe illustrator` queues
one command per generated SVG. The Illustrator JSX consumer selects the newest
job and imports all queued SVGs from that job in a single execution.

Generated SVGs expose stable zone identifiers (`text-zone`,
`illustration-zone`, and `generated-icon`) so the imported artwork can be
located and edited in Illustrator after generation.

Supported host identifiers in the MVP:

- `photoshop`
- `illustrator`
- `after-effects`
- `premiere`

The host consumers are now present for all four identifiers. They still need
to be run from their respective Adobe hosts before a command is considered
verified in a real document. Illustrator, After Effects, and Premiere use
JSX/ExtendScript-compatible consumers; Photoshop uses a `.psjs` UXP script
with a legacy `agent.jsx` fallback for COM/ExtendScript hosts.

Current host status on this machine:

- Illustrator: adapter, syntax and a real COM-driven import test verified.
- Photoshop: UXP and JSX adapters/syntax verified; JSX/COM fallback import
  import/export completed, while direct UXP execution remains pending.
- After Effects: intentionally left pending; the non-interactive launch test
  did not provide a trustworthy completion signal.
- Premiere: adapter present, but the detected local installation has no
  executable, so in-host execution is pending.

The command format is intentionally small:

```json
{
  "app": "photoshop",
  "operation": "import-svg",
  "input": "C:\\IA\\svg\\agent-toolkit\\jobs\\...\\animated.svg",
  "options": { "output": "result.psd" },
  "state": "queued"
}
```

The Adobe bridge should only accept commands from the configured toolkit jobs
directory and should never execute arbitrary JavaScript supplied by a remote
request.

Photoshop's consumer uses the documented UXP `file:` entries and
`Document.saveAs.*` APIs. See the [Photoshop UXP `app.open` reference](https://developer.adobe.com/photoshop/uxp/2022/ps-reference/classes/photoshop) and the [Document save reference](https://developer.adobe.com/photoshop/uxp/2022/ps-reference/classes/document).

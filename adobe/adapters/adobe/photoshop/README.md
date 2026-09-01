# Photoshop adapter

`agent.psjs` is the primary UXP consumer and is loaded from Photoshop through
the host's script workflow. `agent.jsx` is a legacy ExtendScript/COM fallback
for machines where UXP Developer Tooling is unavailable.

Both consumers read the same queued envelopes and write results to:

```text
jobs/<job-id>/adobe/results/<command-id>.json
```

The JSX fallback has been tested against Photoshop 2026 with a real SVG
import/export and a completed result envelope. Direct UXP execution remains a
separate host validation step.

## Object separation

The `photoshop.separate-objects` operation is the raster-to-editable-assets
bridge used before Blender. It produces three coordinated outputs:

1. a PSD with one editable layer per extracted object (mask-backed for
   rectangle fallback, transparent copied layer after a successful region
   detection);
2. a transparent PNG for each object, cropped to its bounds; and
3. a manifest containing the source canvas and normalized placement for each
   PNG, so `blender.layout-scene` can put the objects back in their original
   positions. The manifest is marked as a single-slide asset set and maps to
   the first part of a one-slide storyboard automatically.

There are two modes:

- `subject`: Photoshop runs Select Subject and exports the detected main
  subject as a masked layer. This is useful for a quick single-object cutout.
- `regions`: the caller supplies named rectangles. Each rectangle becomes an
  independent object attempt and asset. Photoshop first runs Select Subject
  inside the rectangle; if it cannot produce a usable selection, the adapter
  falls back to a non-destructive rectangle mask and records the reason in the
  manifest. Set `"selectionMode": "rectangle"` for an intentional manual
  division.

The host command is queued with:

```powershell
npm run tool -- photoshop separate-objects `
  --input C:\path\to\source.png `
  --mode subject `
  --output separated\manifest.json `
  --psd-output separated\objects.psd
```

For deterministic regions, pass a JSON file such as:

```json
{
  "objects": [
    { "name": "person-left", "bounds": { "left": 120, "top": 180, "right": 620, "bottom": 1280 } },
    { "name": "network", "bounds": { "left": 760, "top": 420, "right": 1320, "bottom": 1080 } }
  ]
}
```

```powershell
npm run tool -- photoshop separate-objects `
  --input C:\path\to\source.png `
  --mode regions `
  --objects C:\path\to\regions.json `
  --output separated\manifest.json `
  --psd-output separated\objects.psd
```

The Photoshop script must be run from Photoshop. The Node side stages the
source and queues the command; it does not report success until the host
writes the result envelope.

# Illustrator adapter

The adapter is a JSX queue consumer. It currently supports importing an SVG
and optionally exporting the active document as SVG. Additional Illustrator
operations can be added as explicit allowlisted command types, such as
converting artwork to paths or applying a template.

The script must consume only command envelopes created by
`npm run tool -- adobe enqueue`.

The image workflow automatically creates a vectorized import variant when the
destination is Illustrator and the source would otherwise be an embedded
raster SVG; this avoids Illustrator's interactive raster import dialog.

Run it from Illustrator through `File > Scripts > Other Scripts` and select
`agent.jsx`. Adobe's scripting guide documents this host-side execution path;
the local project verifies the script syntax and has a successful COM-driven
import test recorded as a completed result envelope in a job directory.

# Premiere Pro adapter

This adapter consumes queued commands from `jobs/<id>/adobe/commands/` inside a
Premiere Pro ExtendScript/CEP host. It supports:

- `import-media`;
- `create-sequence` from an imported project item;
- `export-sequence` through `Sequence.exportAsMediaDirect` and an `.epr` preset.

The local Premiere Pro 2020 directory is incomplete and has no executable, so
the host runtime is not verified on this machine yet.

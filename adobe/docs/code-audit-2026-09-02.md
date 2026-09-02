# Code audit 2026-09-02

## Result

The ADOBE branch remains a local-first companion. The audit found no syntax failure in the bridge, renderer or host adapters. The main functional defect was that the inventory produced `collections` but the Project view ignored them.

## Fixed in this pass

- Project view renders indexed collections such as `mini-icons` independently from numbered slides.
- Project summary exposes collection and indexing-error counts.
- Indexing failures are returned as relative-path diagnostics instead of being silently discarded.
- A requested unknown `sessionId` no longer falls back to another session's latest context.
- Context sessions, recommendation entries and stored insert results have bounded retention.
- External signal sessions now have bounded retention as well; their history remains proposal-only.
- Insertion boundary was audited: external proposals do not enqueue host work; insertion still requires an explicit companion action and matching host session.
- Catalog and group indexes use serialized refreshes and atomic JSON replacement.
- SVG and raster metadata reads use bounded file prefixes where full content is unnecessary.
- Companion asset paths are resolved through real paths and restricted to the package root.
- The Electron document has a local-only content security policy.
- Adobe context normalization now drops document paths before storage or recommendation analysis; the UXP source also sends a null path.
- Generated Photoshop output names are restricted to ASCII in both UXP and JSX adapters.
- The Photoshop UXP queue consumer now wraps open, save, close and import mutations in `core.executeAsModal`; an offline source-contract regression covers the boundary.
- The package now has explicit npm ignore rules for development caches, jobs, logs, credentials and dependency trees.
- Insert result payloads are now depth/key/string bounded and remove file/path/content-like keys; the UXP consumer reports only the asset id.
- `npm run verify` now validates the Photoshop UXP manifest, required panel entrypoint and local bridge permission instead of checking only file presence.

## Packaging audit

`npm pack --dry-run --json` reports 702 runtime/documentation files after the explicit ignore rules, with no dependency trees, credentials, caches, root jobs or root logs included. The archive is approximately 687 MB because it intentionally contains the high-resolution `ICONOS/CHEMSEX/` preview library. The root `package-lock.json` is tracked for repository installs but npm omits it from tarballs by design; this branch is documented and tested as a private repository application, not as a publishable npm package.

## Remaining external validation

- Photoshop UXP execution still requires a user-operated Photoshop session.
- After Effects and Premiere host execution remain unverified on this machine.
- `npm audit` still reports the transitive `uuid` advisory from the Adobe PDF SDK; no automatic fix is available.

## Evidence

- `npm run legacy:test`: 52 passed.
- `npm run test`: 11 passed.
- `npm run smoke`: passed.
- `npm run verify`: passed.
- `npm run companion:check`: passed.
- `npm run signal:test`: 3 passed.

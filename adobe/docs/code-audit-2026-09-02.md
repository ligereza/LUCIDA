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

## Remaining external validation

- Photoshop UXP execution still requires a user-operated Photoshop session.
- After Effects and Premiere host execution remain unverified on this machine.
- `npm audit` still reports the transitive `uuid` advisory from the Adobe PDF SDK; no automatic fix is available.

## Evidence

- `npm run legacy:test`: 44 passed.
- `npm run test`: 11 passed.
- `npm run smoke`: passed.
- `npm run verify`: passed.
- `npm run companion:check`: passed.
- `npm run signal:test`: 3 passed.

# LUCIDA signal bridge

## Purpose

The Adobe companion is a visual surface, not a second host application. The bridge lets nearby LUCIDA components contribute small, auditable context signals without forwarding the user's raw work.

## Sources

- `xio`: network, peer, app, workflow and transport state.
- `vizz`: attention, gaze-derived region or display context, only as metadata.
- `pupila`: learning, collaboration, handoff or portfolio context, only as metadata.

## Flow

1. A local component sends one event to `POST /signals`. XIO envelopes may use its existing `event` and `timestamp_utc` fields; the bridge maps them to the common contract.
2. The bridge normalizes ASCII identifiers, bounds numeric values, removes forbidden fields and keeps a bounded in-memory history.
3. `GET /surface/current` derives one compact surface with source state, latest metadata and pending proposals.
4. The companion renders the state and the recommendation engine may use the allowed terms as query context.
5. Any host operation still goes through an existing explicit Adobe queue and host adapter.

The recommendation cache includes the derived `surfaceHash`. A new bounded
signal, a source becoming stale, or a proposal expiring therefore invalidates
old recommendations without disabling caching for an unchanged surface.

## Boundary

The bridge never forwards raw text, source files, image data, paths, keyboard values, scripts, shell commands, URLs or arbitrary payloads. Signals do not execute host actions. `vizz` and `pupila` proposals are confirmation-only and proposal-only.

Signals are retained in a bounded 96-event session history. Source state is
marked `stale` after 45 seconds, and proposals are clamped to that same
window; expired proposals are omitted from the derived surface. The historical
signal record remains available until it leaves the bounded history, so the
surface cannot turn an old VIZZ or PUPILA proposal into a current host action.

Signals are retained in a bounded 96-event session history. Source state is
marked `stale` after 45 seconds, and proposals are clamped to that same
window; expired proposals are omitted from the derived surface. The historical
signal record remains available until it leaves the bounded history, so the
surface cannot turn an old VIZZ or PUPILA proposal into a current host action.

The default catalog is local to this branch and includes `ICONOS/CHEMSEX`; the source SVG repository is not required at runtime. The catalog and project inventory use the migrated files and their manifest, with no external corpus or downloaded model required for the base flow.

## API

```text
POST /signals
GET  /signals/current?sessionId=...
GET  /surface/current?sessionId=...
```

The JSON schemas are `contracts/external-signal.schema.json` and `contracts/surface.schema.json`.

For XIO radio-monitor envelopes, the bridge accepts `event` and `timestamp_utc` directly and maps only bounded summary fields: `wifi_signal_percent` to `signalPercent`, `gateway_loss_percent` to `lossPercent`, `wifi_receive_mbps` to `receiveMbps`, `wifi_transmit_mbps` to `transmitMbps`, `cell_rat` to `radioType` and `cell_channel` to `cellChannel`.

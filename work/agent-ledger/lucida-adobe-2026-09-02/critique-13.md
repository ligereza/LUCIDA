# Self-critique 13

## Decision

Repair remote preview behavior at the Electron boundary instead of weakening the renderer content policy.

## Why

The renderer received remote preview URLs, but the companion CSP allowed only local image sources. Adding a broad `https:` image permission would have made the policy less explicit. A main-process proxy keeps the renderer local-only while constraining remote hosts, response type, size and time.

## Trade-off

The proxy supports the two current SVG preview sources and rejects redirects, unexpected content types and oversized responses. It is intentionally not a general URL fetcher. New providers must be added explicitly and tested.

## Next decision gate

Before adding more providers, validate the UXP panel in the installed Photoshop host and decide whether the duplicate generic/runtime boundary should be consolidated.

# Self-critique 15

## Decision

Implement a documented UXP cancellation path instead of leaving the bridge request lifecycle unbounded.

## Why

The previous risk was material: a hung fetch could keep the in-flight guard set forever, so polling would stop recovering. Adobe's current UXP documentation explicitly shows AbortController and AbortSignal for bounded fetches.

## Trade-off

The default timeout is short for local context and queue calls, while remote asset retrieval receives a longer but finite budget. The implementation remains isolated and can be reverted if the installed Photoshop build fails the host validation.

## Next decision gate

Run the UXP panel in the installed Photoshop host. Do not treat the source-contract test as proof of host cancellation behavior.

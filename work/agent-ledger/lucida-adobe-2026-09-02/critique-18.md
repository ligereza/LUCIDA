# Self-critique 18

## Decision

Test the UXP timeout path as executable behavior, not only as source structure.

## Why

The previous harness proved that an AbortSignal was passed to fetch, but that did not prove a hung request would transition the panel offline and release the polling lifecycle. The failure mode was precisely the one that could make the plugin appear frozen.

## Trade-off

The test uses a deterministic mock timer and a hung fetch promise, so it adds no three-second wait and does not claim Adobe host behavior. It does prove the local request helper's timeout handling and observable panel state.

## Next decision gate

Validate the same sequence in Photoshop after the plugin is loaded; retain the hostless test as the regression floor.

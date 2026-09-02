# Self-critique 17

## Decision

Add a hostless execution harness for the UXP producer while keeping real Photoshop validation separate.

## Why

The installed Photoshop process exists, but the LUCIDA UXP plugin and UXP Developer Tool are not present in the detected local environment. Static regex checks alone were too weak to exercise the producer's collection traversal and fetch options.

## Trade-off

The VM harness uses controlled mocks, so it can prove serialization limits, privacy fields, abort signal propagation and polling lifecycle, but it cannot prove Adobe DOM behavior or plugin loading. That boundary is explicit.

## Next decision gate

Use the harness as the regression floor, then perform the short manual test after the plugin is loaded into Photoshop.

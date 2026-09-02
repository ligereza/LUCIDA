# Self-critique 12

## Decision

Fix runtime reliability and bounded input production before adding another Adobe feature.

## Why

The server already bounded normalized context, but the Photoshop UXP producer could still traverse a large layer tree and build a large payload before that server-side boundary. Its two polling loops also retried rapidly and could overwrite the panel log with repeated bridge failures. Those are structural runtime risks, not missing capability requests.

## Trade-off

The producer now reports a bounded snapshot rather than attempting to describe an arbitrarily large document. The five-second retry interval reduces pressure and noise while keeping recovery automatic. Actual Photoshop host execution remains an external validation step; passing source tests does not replace it.

## Next decision gate

Do not add a new Adobe adapter until the local suites remain green and the UXP panel has been exercised in the installed Photoshop host.

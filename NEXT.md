# NEXT — open work, observations, suggestions

Written from memory at the end of the 2026-09-07 session, without re-reading
the tree. Re-measure any number here before acting on it. Not a contract.

Nothing in this repository was modified in that session. What follows is
measurement and the questions it raises.

## The shape of the problem

`main` is a one-line README. From memory, 179 tests pass across three
surfaces and none of them is on `main`:

- `codex/lucida-python-engine` contains every file of `RESOLUME`
  byte-identically, plus a `lucida/engine/` package -- reducer, pipeline,
  contracts, replay, overlay frame -- and its own test suite. Around 111 tests.
- `MULTI`, around 65 tests plus subtests.
- `codex/adobe-adaptive-composition` is 735 of 736 files identical to `ADOBE`
  plus four more. Three tests.

So there are three surfaces, two of which have a working branch slightly ahead
of the named one. `RESOLUME` and `ADOBE` are not alternatives to their codex
branches; they are earlier states of them.

The engine's code is not over-promised, which is worth saying because it is
rare: every claim in its README has a module and a test behind it. The problem
is topology, not quality. Good code is stranded off the branch anyone lands on.

## `MULTI` has no code of its own

This is the finding that reframes the rest. From memory the branch tracks fifty
files: a `.gitignore`, two READMEs, and forty-seven under `XIO_LAYER/`.
`multi/` holds one README and no code, and nothing imports it. All of its tests
live in `XIO_LAYER/tests/`, testing XIO's package.

That `XIO_LAYER/` is a stale copy of the one in XIO's `codex/xio-transport`.
Every path is present there, most byte-identical, and where they differ XIO's
side is the hardened one -- type checks and JSON-safety validation where this
copy has the bare original. Its own README says the layer was extracted from
XIO.

FARMAKSIA's responsibility map forbids copying implementations between
surfaces, gives transport, handoff and replay to XIO, and says LUCIDA/MULTI is
specifically not network capture or transport. So the frontier assigned to this
branch was never written, and what occupies it is the thing the map says it is
not. The measurement is recorded in FARMAKSIA `research/handoffs/002`.

## Decisions waiting

1. **What goes on `main`.** The map calls LUCIDA the floating, host-neutral,
   reversible layer, and the engine is that. Making it `main` and keeping
   ADOBE, RESOLUME and MULTI as adaptation branches is the reading the
   documents support, but it is a decision, not a deduction.
2. **How LUCIDA consumes XIO's layer without copying it.** Submodule,
   installable package, or a vendored contract with its recorded hash. The rule
   forbids the copy and names no mechanism.
3. **What the multi-user consumption frontier actually is**, if it is not the
   transport. No measurement answers this one.

## Suggestions

Anchor pytest before measuring anything here. Without a `pytest.ini` of its
own, running these tests from inside MAK adopts a parent configuration whose
marker filter deselects everything and exits 5 -- so a suite of 111 passing
tests reports nothing, and reads like a repository without tests.

The Adobe surface is a UXP plugin: on the order of 85 `.mjs`, a few `.jsx` and
over five hundred PNG and SVG assets, with three tests for 736 files. That is
where the coverage gap is, and it is a different kind of work than the Python
engine.

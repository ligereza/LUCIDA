# Source adapter registry

`SourceAdapterRegistry` is the portable boundary for future Adobe, Resolume
and other application sources in LUCIDA/MULTI. It routes only event types
declared by an already registered adapter; it does not discover applications,
open sockets or execute actions.

## Consumer snapshot

`SourceAdapterRegistry.snapshot()` returns a new JSON-safe list on every call.
Entries are sorted by `source_app`; `supported_event_types` and `capabilities`
are sorted lists. Each entry contains only:

```text
source_app
supported_event_types
capabilities
```

The snapshot contains no adapter instances, callables, records, paths,
credentials or network state. LUCIDA/MULTI may cache or serialize it to select
an already registered source route. Mutating a returned snapshot cannot change
the registry.

## Candidate discovery

`SourceAdapterRegistry.candidates(event_type, required_capabilities=())`
filters the frozen declarations without inspecting or executing adapters. It
returns a new JSON-safe list containing only `source_app`,
`supported_event_types` and `capabilities`, sorted deterministically. An empty
list is the explicit no-match result. Query identifiers use the same ASCII
rules as registration; invalid queries are rejected before routing.

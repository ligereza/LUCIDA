objective: Make external LUCIDA inputs change Adobe recommendations when their bounded surface changes, without allowing them to execute host actions.
current_state: recommendContext reads the current signal surface and uses its terms, but its cache key contains only contextHash and result limit.
verified_evidence: A new XIO, VIZZ or PUPILA signal changes surfaceHash; the existing recommendation cache remains valid for ten minutes under the old key.
strongest_failure_mode: The transparent companion visibly receives a new external input while continuing to show recommendations produced from an older surface.
alternatives:
  - action: include_surface_hash_in_cache_key
    benefit: invalidates recommendations deterministically on any derived surface change while retaining caching for stable state.
    risk: frequent external signals can increase recommendation work; the bounded surface and source TTL limit this cost.
  - action: disable_recommendation_cache
    benefit: always fresh results.
    risk: unnecessary local and remote provider work, worse latency and no need for a stable context cache.
  - action: invalidate_by_source_manually
    benefit: smaller key.
    risk: duplicates surface semantics and can miss proposal expiry or stale transitions.
selected_action: include_surface_hash_in_cache_key
decision_delta: Use the deterministic derived surface hash as a cache dependency and expose surface status in recommendation output.
confidence: high

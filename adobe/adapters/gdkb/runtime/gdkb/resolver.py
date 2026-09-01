from dataclasses import dataclass
from difflib import SequenceMatcher
from .normalize import normalize_name

@dataclass(frozen=True)
class Candidate:
    entity_id: str
    matched_value: str
    source: str
    exact: bool
    similarity: float
    identifier_match: bool = False

@dataclass(frozen=True)
class Resolution:
    entity_id: str | None
    decision: str
    score: float
    candidates: list[Candidate]
    reason: str

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()

def resolve(query: str, candidates: list[Candidate]) -> Resolution:
    if not candidates:
        return Resolution(None, "candidate", 0.0, [], "no_candidates")

    # Strong identifiers are the only single-signal automatic confirmation.
    ids = [c for c in candidates if c.identifier_match]
    if len(ids) == 1:
        return Resolution(ids[0].entity_id, "confirmed", 1.0, candidates,
                          "unique_identifier_match")
    if len(ids) > 1:
        return Resolution(None, "needs_review", 1.0, candidates,
                          "conflicting_identifier_matches")

    exact = [c for c in candidates if c.exact]
    distinct = {c.entity_id for c in exact}
    if len(distinct) == 1 and exact:
        return Resolution(next(iter(distinct)), "needs_review", 0.90,
                          candidates, "exact_name_requires_context")
    if len(distinct) > 1:
        return Resolution(None, "needs_review", 0.90, candidates,
                          "ambiguous_exact_name")

    ranked = sorted(candidates, key=lambda c: c.similarity, reverse=True)
    best = ranked[0]
    gap = best.similarity - (ranked[1].similarity if len(ranked) > 1 else 0.0)

    # Fuzzy matching creates candidates; it does not auto-merge.
    return Resolution(best.entity_id, "candidate", best.similarity, ranked,
                      f"fuzzy_candidate_gap={gap:.4f}")

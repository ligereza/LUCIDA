from dataclasses import dataclass

@dataclass(frozen=True)
class MergePlan:
    source_entity_id: str
    target_entity_id: str
    reason: str
    evidence_ids: tuple[str, ...]

def validate_merge(plan: MergePlan):
    if plan.source_entity_id == plan.target_entity_id:
        raise ValueError("cannot merge an entity into itself")
    if not plan.reason.strip():
        raise ValueError("merge requires a reason")
    if not plan.evidence_ids:
        raise ValueError("merge requires evidence")
    return True

def merge_event(plan: MergePlan):
    validate_merge(plan)
    return {
        "event_type": "merge",
        "entity_id": plan.source_entity_id,
        "target_entity_id": plan.target_entity_id,
        "payload": {
            "reason": plan.reason,
            "evidence_ids": list(plan.evidence_ids)
        }
    }

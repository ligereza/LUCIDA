from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class Entity:
    id: str
    kind: str
    canonical_name: str
    status: str = "active"

@dataclass(frozen=True)
class Observation:
    id: str
    source_id: str
    external_record_id: str
    raw_value: dict[str, Any]
    payload_hash: str
    source_version: str | None = None

@dataclass(frozen=True)
class Evidence:
    id: str
    observation_id: str | None
    evidence_type: str
    target_entity_id: str | None
    strength: float | None
    method: str | None = None

@dataclass(frozen=True)
class Assertion:
    id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str | None = None
    object_value: Any = None
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    status: str = "asserted"

@dataclass(frozen=True)
class EntityEvent:
    id: str
    event_type: str
    entity_id: str
    target_entity_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

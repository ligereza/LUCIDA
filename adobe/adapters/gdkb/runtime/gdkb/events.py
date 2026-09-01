from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class Event:
    id: str
    event_type: str
    entity_id: str | None
    target_entity_id: str | None = None
    payload: dict[str, Any] | None = None
    sequence: int = 0

    def body(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "entity_id": self.entity_id,
            "target_entity_id": self.target_entity_id,
            "payload": self.payload or {},
            "sequence": self.sequence,
        }

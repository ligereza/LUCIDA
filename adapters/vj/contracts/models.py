"""Small, dependency-free contracts shared by the VJ adapter and replay."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


PHASES = ("preflight", "preparation", "show", "incident", "recovery", "closure")
RESULT_STATUSES = ("observed", "accepted", "rejected", "executed", "skipped", "failed")


class ContractError(ValueError):
    """Raised when an event, state, proposal, or result is malformed."""


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field_name} must be non-empty text.")
    return value.strip()


def _timestamp(value: Any) -> str:
    text = _required_text(value, "timestamp")
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"timestamp is not valid ISO-8601: {text}") from exc
    return text


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ContractError(f"{field_name} debe ser un objeto.")
    return dict(value)


def _tuple_text(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        raise ContractError(f"{field_name} debe ser una lista de textos.")
    return tuple(item for item in value if item.strip())


@dataclass(frozen=True)
class VJEvent:
    event_id: str
    timestamp: str
    phase: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "operator"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "VJEvent":
        if not isinstance(value, Mapping):
            raise ContractError("event debe ser un objeto.")
        phase = _required_text(value.get("phase"), "phase")
        if phase not in PHASES:
            raise ContractError(f"phase desconocida: {phase}")
        return cls(
            event_id=_required_text(value.get("event_id"), "event_id"),
            timestamp=_timestamp(value.get("timestamp")),
            phase=phase,
            event_type=_required_text(value.get("event_type"), "event_type"),
            payload=_mapping(value.get("payload"), "payload"),
            source=_required_text(value.get("source", "operator"), "source"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "phase": self.phase,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "source": self.source,
        }


@dataclass(frozen=True)
class VJProposal:
    proposal_id: str
    event_id: str
    phase: str
    operation: str
    reason: str
    risk: str = "low"
    requires_explicit_approval: bool = True
    reversible: bool = True
    execution_mode: str = "proposal_only"
    evidence: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "VJProposal":
        if not isinstance(value, Mapping):
            raise ContractError("proposal debe ser un objeto.")
        phase = _required_text(value.get("phase"), "phase")
        if phase not in PHASES:
            raise ContractError(f"phase desconocida: {phase}")
        if value.get("requires_explicit_approval", True) is not True:
            raise ContractError("Every VJ proposal must require explicit approval.")
        if value.get("reversible", True) is not True:
            raise ContractError("Toda propuesta VJ debe ser recuperable/reversible.")
        if value.get("execution_mode", "proposal_only") != "proposal_only":
            raise ContractError("El adaptador VJ no ejecuta acciones directamente.")
        return cls(
            proposal_id=_required_text(value.get("proposal_id"), "proposal_id"),
            event_id=_required_text(value.get("event_id"), "event_id"),
            phase=phase,
            operation=_required_text(value.get("operation"), "operation"),
            reason=_required_text(value.get("reason"), "reason"),
            risk=_required_text(value.get("risk", "low"), "risk"),
            evidence=_tuple_text(value.get("evidence"), "evidence"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "event_id": self.event_id,
            "phase": self.phase,
            "operation": self.operation,
            "reason": self.reason,
            "risk": self.risk,
            "requires_explicit_approval": self.requires_explicit_approval,
            "reversible": self.reversible,
            "execution_mode": self.execution_mode,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class VJResult:
    result_id: str
    proposal_id: str
    recorded_at: str
    status: str
    notes: str = ""
    evidence: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "VJResult":
        if not isinstance(value, Mapping):
            raise ContractError("result debe ser un objeto.")
        status = _required_text(value.get("status"), "status")
        if status not in RESULT_STATUSES:
            raise ContractError(f"status de resultado desconocido: {status}")
        return cls(
            result_id=_required_text(value.get("result_id"), "result_id"),
            proposal_id=_required_text(value.get("proposal_id"), "proposal_id"),
            recorded_at=_timestamp(value.get("recorded_at")),
            status=status,
            notes=str(value.get("notes", "")),
            evidence=_tuple_text(value.get("evidence"), "evidence"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "proposal_id": self.proposal_id,
            "recorded_at": self.recorded_at,
            "status": self.status,
            "notes": self.notes,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class VJState:
    session_id: str
    phase: str = "preflight"
    status: str = "created"
    sequence: int = 0
    last_event_id: str | None = None
    last_timestamp: str | None = None
    checkpoint_id: str | None = None
    completed_phases: tuple[str, ...] = ()
    open_incidents: tuple[str, ...] = ()
    pending_proposal_ids: tuple[str, ...] = ()
    results: tuple[VJResult, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "VJState":
        if not isinstance(value, Mapping):
            raise ContractError("state debe ser un objeto.")
        phase = _required_text(value.get("phase", "preflight"), "phase")
        if phase not in PHASES:
            raise ContractError(f"phase desconocida: {phase}")
        results = tuple(VJResult.from_dict(item) for item in value.get("results", ()))
        return cls(
            session_id=_required_text(value.get("session_id"), "session_id"),
            phase=phase,
            status=_required_text(value.get("status", "created"), "status"),
            sequence=int(value.get("sequence", 0)),
            last_event_id=value.get("last_event_id"),
            last_timestamp=value.get("last_timestamp"),
            checkpoint_id=value.get("checkpoint_id"),
            completed_phases=_tuple_text(value.get("completed_phases"), "completed_phases"),
            open_incidents=_tuple_text(value.get("open_incidents"), "open_incidents"),
            pending_proposal_ids=_tuple_text(value.get("pending_proposal_ids"), "pending_proposal_ids"),
            results=results,
            metadata=_mapping(value.get("metadata"), "metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "phase": self.phase,
            "status": self.status,
            "sequence": self.sequence,
            "last_event_id": self.last_event_id,
            "last_timestamp": self.last_timestamp,
            "checkpoint_id": self.checkpoint_id,
            "completed_phases": list(self.completed_phases),
            "open_incidents": list(self.open_incidents),
            "pending_proposal_ids": list(self.pending_proposal_ids),
            "results": [result.to_dict() for result in self.results],
            "metadata": dict(self.metadata),
        }

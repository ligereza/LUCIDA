"""Small dependency-free contracts for the LUCIDA Python engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


ENGINE_SCHEMA_VERSION = "0.1"
MAX_SUMMARY_KEYS = 16
MAX_TEXT_LENGTH = 280


class EngineContractError(ValueError):
    """Raised when an engine input or output is malformed."""


def _ascii_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EngineContractError(f"{field_name} must be non-empty text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise EngineContractError(f"{field_name} must contain ASCII only.") from exc
    return text


def _bounded_text(value: Any, field_name: str) -> str:
    text = _ascii_text(value, field_name)
    if len(text) > MAX_TEXT_LENGTH:
        raise EngineContractError(f"{field_name} exceeds the text bound.")
    return text


def _timestamp(value: Any, field_name: str) -> str:
    text = _ascii_text(value, field_name)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EngineContractError(f"{field_name} must be ISO-8601.") from exc
    return text


def _positive_int(value: Any, field_name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise EngineContractError(f"{field_name} must be an integer from 0 to {maximum}.")
    return value


def _summary(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise EngineContractError("summary must be an object.")
    if len(value) > MAX_SUMMARY_KEYS:
        raise EngineContractError("summary exceeds the key bound.")
    result: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = _ascii_text(raw_key, "summary key")
        if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            if isinstance(raw_value, str):
                result[key] = _bounded_text(raw_value, f"summary.{key}")
            else:
                result[key] = raw_value
            continue
        raise EngineContractError(f"summary.{key} must be a scalar value.")
    return result


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class EngineProposal:
    """A visible proposal that never represents an executed host action."""

    proposal_id: str
    event_id: str
    source: str
    created_at: str
    kind: str
    title: str
    body: str
    priority: int = 50
    ttl_ms: int = 3000
    requires_confirmation: bool = True
    reversible: bool = True

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        *,
        event_id: str,
        source: str,
        created_at: str,
    ) -> "EngineProposal":
        if not isinstance(value, Mapping):
            raise EngineContractError("proposal must be an object.")
        if value.get("requires_confirmation", True) is not True:
            raise EngineContractError("proposals must require confirmation.")
        if value.get("reversible", True) is not True:
            raise EngineContractError("proposals must be reversible.")
        priority = value.get("priority", 50)
        ttl_ms = value.get("ttl_ms", 3000)
        if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 100:
            raise EngineContractError("proposal priority must be from 0 to 100.")
        if isinstance(ttl_ms, bool) or not isinstance(ttl_ms, int) or not 250 <= ttl_ms <= 120000:
            raise EngineContractError("proposal ttl_ms must be from 250 to 120000.")
        return cls(
            proposal_id=_ascii_text(value.get("proposal_id"), "proposal_id"),
            event_id=_ascii_text(event_id, "event_id"),
            source=_ascii_text(source, "source"),
            created_at=_timestamp(created_at, "proposal.created_at"),
            kind=_ascii_text(value.get("kind"), "proposal.kind"),
            title=_bounded_text(value.get("title"), "proposal.title"),
            body=_bounded_text(value.get("body"), "proposal.body"),
            priority=priority,
            ttl_ms=ttl_ms,
        )

    def expires_at(self) -> str:
        expiry = _utc(self.created_at) + timedelta(milliseconds=self.ttl_ms)
        return expiry.isoformat().replace("+00:00", "Z")

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "event_id": self.event_id,
            "source": self.source,
            "created_at": self.created_at,
            "kind": self.kind,
            "title": self.title,
            "body": self.body,
            "priority": self.priority,
            "ttl_ms": self.ttl_ms,
            "requires_confirmation": self.requires_confirmation,
            "reversible": self.reversible,
        }


@dataclass(frozen=True)
class EngineEvent:
    """Bounded event input consumed by the reducer."""

    session_id: str
    event_id: str
    timestamp: str
    sequence: int
    source: str
    event_type: str
    source_version: str = "0.1"
    capabilities: tuple[str, ...] = ()
    summary: dict[str, Any] = field(default_factory=dict)
    proposal: EngineProposal | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EngineEvent":
        if not isinstance(value, Mapping):
            raise EngineContractError("event must be an object.")
        session_id = _ascii_text(value.get("session_id"), "session_id")
        event_id = _ascii_text(value.get("event_id"), "event_id")
        timestamp = _timestamp(value.get("timestamp"), "timestamp")
        sequence = _positive_int(value.get("sequence"), "sequence", 1_000_000_000)
        source = _ascii_text(value.get("source"), "source")
        event_type = _ascii_text(value.get("event_type"), "event_type")
        source_version = _ascii_text(value.get("source_version", "0.1"), "source_version")
        raw_capabilities = value.get("capabilities", ())
        if not isinstance(raw_capabilities, (list, tuple)):
            raise EngineContractError("capabilities must be a list.")
        capabilities = tuple(_ascii_text(item, "capability") for item in raw_capabilities)
        raw_proposal = value.get("proposal")
        proposal = None
        if raw_proposal is not None:
            proposal = EngineProposal.from_dict(
                raw_proposal,
                event_id=event_id,
                source=source,
                created_at=timestamp,
            )
        return cls(
            session_id=session_id,
            event_id=event_id,
            timestamp=timestamp,
            sequence=sequence,
            source=source,
            event_type=event_type,
            source_version=source_version,
            capabilities=capabilities,
            summary=_summary(value.get("summary")),
            proposal=proposal,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "EngineEvent",
            "schema_version": ENGINE_SCHEMA_VERSION,
            "session_id": self.session_id,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "source": self.source,
            "event_type": self.event_type,
            "source_version": self.source_version,
            "capabilities": list(self.capabilities),
            "summary": dict(self.summary),
            "proposal": self.proposal.to_dict() if self.proposal else None,
        }


@dataclass(frozen=True)
class EngineState:
    """Immutable reducer state with per-source ordering."""

    session_id: str
    revision: int = 0
    last_sequence_by_source: dict[str, int] = field(default_factory=dict)
    last_timestamp_by_source: dict[str, str] = field(default_factory=dict)
    seen_event_ids: tuple[str, ...] = ()
    active_proposals: tuple[EngineProposal, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "EngineState",
            "schema_version": ENGINE_SCHEMA_VERSION,
            "session_id": self.session_id,
            "revision": self.revision,
            "last_sequence_by_source": dict(self.last_sequence_by_source),
            "last_timestamp_by_source": dict(self.last_timestamp_by_source),
            "seen_event_ids": list(self.seen_event_ids),
            "active_proposals": [item.to_dict() for item in self.active_proposals],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class RenderPlan:
    """Safe visual output for any host surface."""

    session_id: str
    revision: int
    items: tuple[dict[str, Any], ...] = ()
    mode: str = "read_only"
    automatic_actions: bool = False
    raw_payload_forwarded: bool = False
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "RenderPlan",
            "schema_version": ENGINE_SCHEMA_VERSION,
            "session_id": self.session_id,
            "revision": self.revision,
            "items": [dict(item) for item in self.items],
            "mode": self.mode,
            "automatic_actions": self.automatic_actions,
            "raw_payload_forwarded": self.raw_payload_forwarded,
            "warnings": list(self.warnings),
        }

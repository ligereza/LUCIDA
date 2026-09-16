"""Explicit host decisions for proposal-only LUCIDA integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any, Callable, Mapping


DECISION_STATUSES = ("accepted", "rejected", "unknown")
_TECHNICAL_ID = re.compile(r"^[A-Za-z0-9_.:-]+$")


class DecisionContractError(ValueError):
    """Raised when a host decision receipt is invalid."""


def _ascii_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionContractError(f"{field_name} must be non-empty ASCII text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise DecisionContractError(f"{field_name} must contain ASCII characters only.") from exc
    return text


def _technical_id(value: Any, field_name: str) -> str:
    text = _ascii_text(value, field_name)
    if not _TECHNICAL_ID.fullmatch(text):
        raise DecisionContractError(f"{field_name} contains unsupported technical characters.")
    return text


def _timestamp(value: Any) -> str:
    text = _ascii_text(value, "timestamp")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionContractError(f"timestamp is not valid ISO-8601: {text}") from exc
    if parsed.tzinfo is None:
        raise DecisionContractError("timestamp must include a timezone.")
    return text


def _provenance(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise DecisionContractError("provenance must be an object.")
    result = dict(value)
    for key in result:
        _ascii_text(key, "provenance key")
    return result


@dataclass(frozen=True)
class ProposalDecision:
    """A host decision receipt that never asserts execution."""

    decision_id: str
    proposal_id: str
    status: str
    reason: str
    sequence: int
    timestamp: str
    source: str
    explicit_confirmation: bool
    provenance: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProposalDecision":
        if not isinstance(value, Mapping):
            raise DecisionContractError("proposal decision must be an object.")
        required = {
            "decision_id",
            "proposal_id",
            "status",
            "reason",
            "sequence",
            "timestamp",
            "source",
            "explicit_confirmation",
        }
        missing = sorted(required - set(value))
        if missing:
            raise DecisionContractError(f"proposal decision missing fields: {missing}.")
        status = _ascii_text(value.get("status"), "status")
        if status not in DECISION_STATUSES:
            raise DecisionContractError(f"status is not allowed: {status}.")
        explicit_confirmation = value.get("explicit_confirmation")
        if not isinstance(explicit_confirmation, bool):
            raise DecisionContractError("explicit_confirmation must be boolean.")
        if status in {"accepted", "rejected"} and explicit_confirmation is not True:
            raise DecisionContractError(
                "accepted and rejected decisions require explicit confirmation."
            )
        if status == "unknown" and explicit_confirmation is not False:
            raise DecisionContractError("unknown decisions cannot have explicit confirmation.")
        sequence = value.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
            raise DecisionContractError("sequence must be a positive integer.")
        return cls(
            decision_id=_technical_id(value.get("decision_id"), "decision_id"),
            proposal_id=_technical_id(value.get("proposal_id"), "proposal_id"),
            status=status,
            reason=_ascii_text(value.get("reason"), "reason"),
            sequence=sequence,
            timestamp=_timestamp(value.get("timestamp")),
            source=_technical_id(value.get("source"), "source"),
            explicit_confirmation=explicit_confirmation,
            provenance=_provenance(value.get("provenance")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "ProposalDecision",
            "schema_version": "0.1",
            "decision_id": self.decision_id,
            "proposal_id": self.proposal_id,
            "status": self.status,
            "reason": self.reason,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "source": self.source,
            "explicit_confirmation": self.explicit_confirmation,
            "provenance": dict(self.provenance),
        }


class ProposalDecisionRecorder:
    """Record decisions locally and optionally send immutable audit receipts."""

    def __init__(self, audit_sink: Callable[[Mapping[str, Any]], None] | None = None) -> None:
        self._audit_sink = audit_sink
        self._decisions: tuple[ProposalDecision, ...] = ()

    @property
    def decisions(self) -> tuple[ProposalDecision, ...]:
        return self._decisions

    def record(self, decision: ProposalDecision | Mapping[str, Any]) -> ProposalDecision:
        parsed = decision if isinstance(decision, ProposalDecision) else ProposalDecision.from_dict(decision)
        if any(item.decision_id == parsed.decision_id for item in self._decisions):
            raise DecisionContractError(f"duplicate decision_id: {parsed.decision_id}.")
        receipt = parsed.to_dict()
        receipt["mode"] = "proposal_only"
        receipt["execution_asserted"] = False
        if self._audit_sink is not None:
            self._audit_sink(receipt)
        self._decisions = (*self._decisions, parsed)
        return parsed

"""Shared proposal-only surface projection contract for LUCIDA consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SURFACE_PROJECTION_CONTRACT_TYPE = "SurfaceProjection"
SURFACE_PROJECTION_SCHEMA_VERSION = "1.0"
SURFACE_PROJECTION_STATUSES = frozenset(
    {"pending_approval", "approved", "rejected", "undone"}
)


class SurfaceProjectionError(ValueError):
    """Raised when a serialized surface projection is not safe to consume."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or not value.isascii():
        raise SurfaceProjectionError(f"surface projection {field} is invalid.")
    return value


def _bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise SurfaceProjectionError(f"surface projection {field} is invalid.")
    return value


@dataclass(frozen=True)
class SurfaceProjectionProposalV1:
    """The portable proposal and evidence portion of a surface projection."""

    proposal_id: str
    reason: str
    evidence: tuple[str, ...]
    execution_mode: str
    requires_explicit_approval: bool
    reversible: bool

    def __post_init__(self) -> None:
        _text(self.proposal_id, "proposal_id")
        _text(self.reason, "reason")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise SurfaceProjectionError("surface projection evidence is invalid.")
        for item in self.evidence:
            _text(item, "evidence")
        if self.execution_mode != "proposal_only":
            raise SurfaceProjectionError("surface projection execution_mode is invalid.")
        if _bool(self.requires_explicit_approval, "requires_explicit_approval") is not True:
            raise SurfaceProjectionError(
                "surface projection requires_explicit_approval is invalid."
            )
        if _bool(self.reversible, "reversible") is not True:
            raise SurfaceProjectionError("surface projection reversible is invalid.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "execution_mode": self.execution_mode,
            "requires_explicit_approval": self.requires_explicit_approval,
            "reversible": self.reversible,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SurfaceProjectionProposalV1":
        if not isinstance(value, Mapping):
            raise SurfaceProjectionError("surface projection proposal is invalid.")
        evidence = value.get("evidence")
        if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
            raise SurfaceProjectionError("surface projection evidence is invalid.")
        return cls(
            proposal_id=_text(value.get("proposal_id"), "proposal_id"),
            reason=_text(value.get("reason"), "reason"),
            evidence=tuple(evidence),
            execution_mode=value.get("execution_mode"),
            requires_explicit_approval=value.get("requires_explicit_approval"),
            reversible=value.get("reversible"),
        )


@dataclass(frozen=True)
class SurfaceProjectionSafetyV1:
    """Host-independent side-effect guarantees for a projection."""

    proposal_only: bool
    automatic_actions: bool
    external_side_effects: bool
    host_opened: bool

    def __post_init__(self) -> None:
        if _bool(self.proposal_only, "proposal_only") is not True:
            raise SurfaceProjectionError("surface projection proposal_only is invalid.")
        if _bool(self.automatic_actions, "automatic_actions") is not False:
            raise SurfaceProjectionError("surface projection automatic_actions is invalid.")
        if _bool(self.external_side_effects, "external_side_effects") is not False:
            raise SurfaceProjectionError(
                "surface projection external_side_effects is invalid."
            )
        if _bool(self.host_opened, "host_opened") is not False:
            raise SurfaceProjectionError("surface projection host_opened is invalid.")

    def to_dict(self) -> dict[str, bool]:
        return {
            "proposal_only": self.proposal_only,
            "automatic_actions": self.automatic_actions,
            "external_side_effects": self.external_side_effects,
            "host_opened": self.host_opened,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SurfaceProjectionSafetyV1":
        if not isinstance(value, Mapping):
            raise SurfaceProjectionError("surface projection safety is invalid.")
        return cls(
            proposal_only=value.get("proposal_only"),
            automatic_actions=value.get("automatic_actions"),
            external_side_effects=value.get("external_side_effects"),
            host_opened=value.get("host_opened"),
        )


@dataclass(frozen=True)
class SurfaceProjectionV1:
    """Minimal serialized projection shared by LUCIDA surface consumers."""

    host_id: str
    surface_id: str
    status: str
    proposal: SurfaceProjectionProposalV1
    safety: SurfaceProjectionSafetyV1
    contract_type: str = SURFACE_PROJECTION_CONTRACT_TYPE
    schema_version: str = SURFACE_PROJECTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.contract_type != SURFACE_PROJECTION_CONTRACT_TYPE:
            raise SurfaceProjectionError("surface projection contract_type is invalid.")
        if self.schema_version != SURFACE_PROJECTION_SCHEMA_VERSION:
            raise SurfaceProjectionError("surface projection schema_version is invalid.")
        _text(self.host_id, "host_id")
        _text(self.surface_id, "surface_id")
        if self.status not in SURFACE_PROJECTION_STATUSES:
            raise SurfaceProjectionError("surface projection status is invalid.")
        if not isinstance(self.proposal, SurfaceProjectionProposalV1):
            raise SurfaceProjectionError("surface projection proposal is invalid.")
        if not isinstance(self.safety, SurfaceProjectionSafetyV1):
            raise SurfaceProjectionError("surface projection safety is invalid.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "host_id": self.host_id,
            "surface_id": self.surface_id,
            "status": self.status,
            "proposal": self.proposal.to_dict(),
            "safety": self.safety.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SurfaceProjectionV1":
        if not isinstance(value, Mapping):
            raise SurfaceProjectionError("surface projection is invalid.")
        return cls(
            contract_type=value.get("contract_type"),
            schema_version=value.get("schema_version"),
            host_id=_text(value.get("host_id"), "host_id"),
            surface_id=_text(value.get("surface_id"), "surface_id"),
            status=_text(value.get("status"), "status"),
            proposal=SurfaceProjectionProposalV1.from_dict(value.get("proposal")),
            safety=SurfaceProjectionSafetyV1.from_dict(value.get("safety")),
        )


__all__ = [
    "SURFACE_PROJECTION_CONTRACT_TYPE",
    "SURFACE_PROJECTION_SCHEMA_VERSION",
    "SURFACE_PROJECTION_STATUSES",
    "SurfaceProjectionError",
    "SurfaceProjectionProposalV1",
    "SurfaceProjectionSafetyV1",
    "SurfaceProjectionV1",
]

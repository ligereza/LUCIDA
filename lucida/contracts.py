"""Contracts for the LUCIDA integration surface.

The lifecycle contracts remain owned by ``adapters.vj``.  This module only
adds the integration envelope that puts the three VJ capabilities on one
read-only surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from adapters.vj.contracts import VJProposal, VJState


LUCIDA_SCHEMA_VERSION = "0.1"
CAPABILITY_NAMES = ("INSTAR", "NAYADE", "IMAGO")


class LucidaContractError(ValueError):
    """Raised when a LUCIDA integration contract is malformed."""


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LucidaContractError(f"{field_name} must be non-empty text.")
    return value.strip()


def _timestamp(value: Any, field_name: str) -> str:
    text = _required_text(value, field_name)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LucidaContractError(f"{field_name} is not valid ISO-8601: {text}") from exc
    return text


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise LucidaContractError(f"{field_name} debe ser un objeto.")
    return dict(value)


def _texts(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        raise LucidaContractError(f"{field_name} debe ser una lista de textos.")
    return tuple(item.strip() for item in value if item.strip())


@dataclass(frozen=True)
class CapabilityReport:
    """One capability's observation on the shared LUCIDA surface."""

    capability: str
    observed: tuple[str, ...] = ()
    state: dict[str, Any] = field(default_factory=dict)
    proposals: tuple[VJProposal, ...] = ()
    expected_results: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CapabilityReport":
        if not isinstance(value, Mapping):
            raise LucidaContractError("capability report debe ser un objeto.")
        capability = _required_text(value.get("capability"), "capability")
        if capability not in CAPABILITY_NAMES:
            raise LucidaContractError(f"capacidad desconocida: {capability}")
        proposals = tuple(VJProposal.from_dict(item) for item in value.get("proposals", ()))
        return cls(
            capability=capability,
            observed=_texts(value.get("observed"), "observed"),
            state=_mapping(value.get("state"), "state"),
            proposals=proposals,
            expected_results=_texts(value.get("expected_results"), "expected_results"),
            unknowns=_texts(value.get("unknowns"), "unknowns"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "observed": list(self.observed),
            "state": dict(self.state),
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "expected_results": list(self.expected_results),
            "unknowns": list(self.unknowns),
        }


@dataclass(frozen=True)
class LucidaState:
    """The single state surface exposed to a future overlay or host."""

    session_id: str
    vj_state: VJState
    capabilities: tuple[CapabilityReport, ...] = ()
    proposals: tuple[VJProposal, ...] = ()
    overlay_status: str = "ready"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LucidaState":
        if not isinstance(value, Mapping):
            raise LucidaContractError("lucida_state debe ser un objeto.")
        session_id = _required_text(value.get("session_id"), "session_id")
        raw_vj_state = value.get("vj_state")
        if not isinstance(raw_vj_state, Mapping):
            raise LucidaContractError("lucida_state necesita vj_state.")
        vj_state = VJState.from_dict(raw_vj_state)
        if vj_state.session_id != session_id:
            raise LucidaContractError("session_id no coincide con vj_state.session_id.")
        capabilities = tuple(
            CapabilityReport.from_dict(item) for item in value.get("capabilities", ())
        )
        proposals = tuple(VJProposal.from_dict(item) for item in value.get("proposals", ()))
        return cls(
            session_id=session_id,
            vj_state=vj_state,
            capabilities=capabilities,
            proposals=proposals,
            overlay_status=_required_text(value.get("overlay_status", "ready"), "overlay_status"),
            metadata=_mapping(value.get("metadata"), "metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "LucidaState",
            "schema_version": LUCIDA_SCHEMA_VERSION,
            "session_id": self.session_id,
            "overlay_status": self.overlay_status,
            "vj_state": self.vj_state.to_dict(),
            "pending_proposal_ids": list(self.vj_state.pending_proposal_ids),
            "capabilities": [capability.to_dict() for capability in self.capabilities],
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "metadata": dict(self.metadata),
        }

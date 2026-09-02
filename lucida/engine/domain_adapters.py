"""Strict VIZZ and PUPILA adapters for the host-neutral engine."""

from __future__ import annotations

import math
from typing import Any, Mapping

from .adapters import AdapterRegistry
from .input_contracts import ContractRegistry, InputContract
from .models import EngineEvent


VIZZ_ADAPTER_ID = "vizz.metadata"
VIZZ_CONTRACT_ID = "vizz.perception.v1"
VIZZ_SOURCE = "vizz"
VIZZ_SOURCE_VERSION = "0.1"
VIZZ_CAPABILITY = "observe.perception"

PUPILA_ADAPTER_ID = "pupila.coordination"
PUPILA_CONTRACT_ID = "pupila.coordination.v1"
PUPILA_SOURCE = "pupila"
PUPILA_SOURCE_VERSION = "0.1"
PUPILA_CAPABILITY = "observe.coordination"


class DomainAdapterError(ValueError):
    """Raised when a domain value crosses the boundary incorrectly."""


_EVENT_KEYS = {
    "session_id",
    "event_id",
    "timestamp",
    "sequence",
    "event_type",
    "source",
    "source_version",
    "summary",
}
_PUPILA_EVENT_KEYS = _EVENT_KEYS | {"proposal"}

_VIZZ_SUMMARY_KEYS = {
    "focus.state": {"focused", "confidence", "signal_age_ms"},
    "geometry.state": {
        "interocular_px",
        "face_scale",
        "yaw_deg",
        "pitch_deg",
        "roll_deg",
        "geometry_valid",
    },
    "perception.quality": {"quality", "sample_count", "signal_age_ms", "policy"},
}
_PUPILA_SUMMARY_KEYS = {
    "coordination.state": {"participant_count", "proposal_count"},
    "coordination.proposal": {"participant_count", "proposal_kind", "proposal_state"},
}
_PROPOSAL_KEYS = {
    "proposal_id",
    "kind",
    "title",
    "body",
    "priority",
    "ttl_ms",
    "requires_confirmation",
    "reversible",
}


def _require_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DomainAdapterError("domain value must be a mapping")
    return value


def _reject_unknown_keys(value: Mapping[str, Any], allowed: set[str], field_name: str) -> None:
    unknown = set(value).difference(allowed)
    if unknown:
        names = ",".join(sorted(str(item) for item in unknown))
        raise DomainAdapterError(f"{field_name} has undeclared keys: {names}")


def _validate_scalar(key: str, value: Any) -> None:
    if not isinstance(value, (str, int, float, bool)) and value is not None:
        raise DomainAdapterError(f"summary.{key} must be a scalar")
    if isinstance(value, float) and not math.isfinite(value):
        raise DomainAdapterError(f"summary.{key} must be finite")
    if isinstance(value, str) and len(value) > 80:
        raise DomainAdapterError(f"summary.{key} exceeds the text bound")


def _validate_summary_value(key: str, value: Any) -> None:
    _validate_scalar(key, value)
    if key in {"focused", "geometry_valid"}:
        if not isinstance(value, bool):
            raise DomainAdapterError(f"summary.{key} must be boolean")
        return
    if key in {"confidence", "quality"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DomainAdapterError(f"summary.{key} must be numeric")
        if not 0.0 <= float(value) <= 1.0:
            raise DomainAdapterError(f"summary.{key} must be from 0 to 1")
        return
    if key in {"sample_count", "signal_age_ms", "participant_count", "proposal_count"}:
        if isinstance(value, bool) or not isinstance(value, int):
            raise DomainAdapterError(f"summary.{key} must be an integer")
        maximum = 1_000_000 if key == "sample_count" else 120_000
        if key in {"participant_count", "proposal_count"}:
            maximum = 64
        if not 0 <= value <= maximum:
            raise DomainAdapterError(f"summary.{key} is outside its bound")
        return
    if key in {"interocular_px", "face_scale", "yaw_deg", "pitch_deg", "roll_deg"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DomainAdapterError(f"summary.{key} must be numeric")
        number = float(value)
        if key == "interocular_px" and not 0.0 < number <= 2000.0:
            raise DomainAdapterError("summary.interocular_px is outside its bound")
        if key == "face_scale" and not 0.0 < number <= 2.0:
            raise DomainAdapterError("summary.face_scale is outside its bound")
        if key in {"yaw_deg", "pitch_deg", "roll_deg"} and not -180.0 <= number <= 180.0:
            raise DomainAdapterError(f"summary.{key} is outside its bound")


def _validate_summary(
    value: Any,
    *,
    event_type: str,
    declared: Mapping[str, set[str]],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DomainAdapterError("summary must be a mapping")
    allowed = declared[event_type]
    _reject_unknown_keys(value, allowed, "summary")
    if not value:
        raise DomainAdapterError("summary must not be empty")
    summary = {str(key): raw_value for key, raw_value in value.items()}
    for key, raw_value in summary.items():
        _validate_summary_value(key, raw_value)
    return summary


def _validate_source(value: Mapping[str, Any], source: str, version: str) -> None:
    if "source" in value and value["source"] != source:
        raise DomainAdapterError("source does not match adapter")
    if "source_version" in value and value["source_version"] != version:
        raise DomainAdapterError("source_version does not match adapter")


def _event(
    value: Mapping[str, Any],
    *,
    source: str,
    source_version: str,
    capability: str,
    event_types: set[str],
    summary: dict[str, Any],
    proposal: Mapping[str, Any] | None = None,
) -> EngineEvent:
    event_type = value.get("event_type")
    if not isinstance(event_type, str) or event_type not in event_types:
        raise DomainAdapterError("event_type is not declared by adapter")
    payload: dict[str, Any] = {
        "session_id": value.get("session_id"),
        "event_id": value.get("event_id"),
        "timestamp": value.get("timestamp"),
        "sequence": value.get("sequence"),
        "source": source,
        "source_version": source_version,
        "event_type": event_type,
        "capabilities": [capability],
        "summary": summary,
    }
    if proposal is not None:
        payload["proposal"] = dict(proposal)
    try:
        return EngineEvent.from_dict(payload)
    except ValueError as exc:
        raise DomainAdapterError(str(exc)) from exc


class VizzMetadataAdapter:
    """Translate one already-redacted VIZZ observation into an EngineEvent."""

    adapter_id = VIZZ_ADAPTER_ID

    def adapt(self, value: Mapping[str, Any]) -> EngineEvent:
        source = _require_mapping(value)
        _reject_unknown_keys(source, _EVENT_KEYS, "vizz event")
        _validate_source(source, VIZZ_SOURCE, VIZZ_SOURCE_VERSION)
        event_type = source.get("event_type")
        if not isinstance(event_type, str) or event_type not in _VIZZ_SUMMARY_KEYS:
            raise DomainAdapterError("event_type is not declared by VIZZ adapter")
        summary = _validate_summary(
            source.get("summary"),
            event_type=event_type,
            declared=_VIZZ_SUMMARY_KEYS,
        )
        return _event(
            source,
            source=VIZZ_SOURCE,
            source_version=VIZZ_SOURCE_VERSION,
            capability=VIZZ_CAPABILITY,
            event_types=set(_VIZZ_SUMMARY_KEYS),
            summary=summary,
        )


class PupilaCoordinationAdapter:
    """Translate one redacted PUPILA coordination state or proposal."""

    adapter_id = PUPILA_ADAPTER_ID

    def adapt(self, value: Mapping[str, Any]) -> EngineEvent:
        source = _require_mapping(value)
        _reject_unknown_keys(source, _PUPILA_EVENT_KEYS, "pupila event")
        _validate_source(source, PUPILA_SOURCE, PUPILA_SOURCE_VERSION)
        event_type = source.get("event_type")
        if not isinstance(event_type, str) or event_type not in _PUPILA_SUMMARY_KEYS:
            raise DomainAdapterError("event_type is not declared by PUPILA adapter")
        summary = _validate_summary(
            source.get("summary"),
            event_type=event_type,
            declared=_PUPILA_SUMMARY_KEYS,
        )
        raw_proposal = source.get("proposal")
        if event_type == "coordination.state" and raw_proposal is not None:
            raise DomainAdapterError("coordination.state cannot carry a proposal")
        if event_type == "coordination.proposal" and not isinstance(raw_proposal, Mapping):
            raise DomainAdapterError("coordination.proposal requires a proposal")
        proposal = None
        if raw_proposal is not None:
            _reject_unknown_keys(raw_proposal, _PROPOSAL_KEYS, "proposal")
            proposal = raw_proposal
        return _event(
            source,
            source=PUPILA_SOURCE,
            source_version=PUPILA_SOURCE_VERSION,
            capability=PUPILA_CAPABILITY,
            event_types=set(_PUPILA_SUMMARY_KEYS),
            summary=summary,
            proposal=proposal,
        )


def register_vizz_pupila_routes(
    adapters: AdapterRegistry,
    contracts: ContractRegistry,
) -> None:
    """Register the two known routes; callers still choose ids explicitly."""

    adapters.register(VizzMetadataAdapter())
    adapters.register(PupilaCoordinationAdapter())
    contracts.register(
        InputContract(
            contract_id=VIZZ_CONTRACT_ID,
            source=VIZZ_SOURCE,
            source_version=VIZZ_SOURCE_VERSION,
            event_types=tuple(sorted(_VIZZ_SUMMARY_KEYS)),
            capabilities=(VIZZ_CAPABILITY,),
        )
    )
    contracts.register(
        InputContract(
            contract_id=PUPILA_CONTRACT_ID,
            source=PUPILA_SOURCE,
            source_version=PUPILA_SOURCE_VERSION,
            event_types=tuple(sorted(_PUPILA_SUMMARY_KEYS)),
            capabilities=(PUPILA_CAPABILITY,),
        )
    )


__all__ = [
    "DomainAdapterError",
    "PupilaCoordinationAdapter",
    "PUPILA_ADAPTER_ID",
    "PUPILA_CONTRACT_ID",
    "VizzMetadataAdapter",
    "VIZZ_ADAPTER_ID",
    "VIZZ_CONTRACT_ID",
    "register_vizz_pupila_routes",
]

"""Safe bridge from an IMAGO show session to the VJ event contract."""

from __future__ import annotations

from datetime import datetime
import math
import re
from typing import Any, Mapping

from .contracts import VJEvent
from .contracts.models import ContractError
from .show_input import ShowInputError, ShowInputProjection, ShowInputProjector


MAX_SHOW_ITEMS = 200
_ASCII_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]+$")
_STATUS_PHASE = {
    "prepared": "preparation",
    "showing": "show",
    "incident": "incident",
    "recovering": "recovery",
    "closed": "closure",
}
_PROFILE_FIELDS = ("profile_id", "venue_id", "signal_profile_id", "mapping_profile_id", "approved_at")
_EVENT_TYPES = {
    "show_started",
    "cue_fired",
    "guard_window_requested",
    "incident_detected",
    "recovery_started",
    "recovery_verified",
    "show_closed",
}
_PROPOSAL_RESULTS = {"accepted", "rejected", "review"}


class ImagoInputError(ShowInputError):
    """Raised when an IMAGO session cannot cross the VJ boundary safely."""


def _ascii_text(value: Any, field_name: str, *, max_length: int = 96) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ImagoInputError(f"{field_name} must be non-empty ASCII text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ImagoInputError(f"{field_name} must contain ASCII characters only.") from exc
    if len(text) > max_length or any(character in text for character in "\\/"):
        raise ImagoInputError(f"{field_name} contains unsupported text.")
    return text


def _identifier(value: Any, field_name: str) -> str:
    text = _ascii_text(value, field_name)
    if not _ASCII_IDENTIFIER.fullmatch(text):
        raise ImagoInputError(f"{field_name} must be a stable identifier.")
    return text


def _timestamp(value: Any) -> str:
    text = _ascii_text(value, "updated_at")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ImagoInputError("updated_at must be ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise ImagoInputError("updated_at must include a timezone.")
    return text


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ImagoInputError(f"{field_name} must be a non-negative integer.")
    return value


def _safe_scalar(value: Any, field_name: str) -> int | float | str | bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ImagoInputError(f"{field_name} must be finite.")
        return int(value) if float(value).is_integer() else round(float(value), 6)
    return _ascii_text(value, field_name, max_length=64)


def _counts(values: list[Mapping[str, Any]], field_name: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, value in enumerate(values):
        item = _ascii_text(value.get(field_name, "unknown"), f"{field_name}[{index}]")
        result[item] = result.get(item, 0) + 1
    return result


def _profile_summary(profile: Any) -> dict[str, int | float | str | bool | None]:
    if not isinstance(profile, Mapping):
        raise ImagoInputError("IMAGO profile must be an object.")
    result: dict[str, int | float | str | bool | None] = {}
    for key in _PROFILE_FIELDS:
        normalized = _safe_scalar(profile.get(key), f"profile.{key}")
        if normalized is not None:
            result[key] = normalized
    return result


def _proposal_summary(proposals: Any) -> dict[str, Any]:
    if not isinstance(proposals, list):
        raise ImagoInputError("IMAGO proposals must be a list.")
    if len(proposals) > MAX_SHOW_ITEMS:
        raise ImagoInputError(f"IMAGO session cannot contain more than {MAX_SHOW_ITEMS} proposals.")
    operations: dict[str, int] = {}
    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, Mapping):
            raise ImagoInputError(f"proposals[{index}] must be an object.")
        if proposal.get("requires_explicit_approval") is not True:
            raise ImagoInputError("IMAGO proposal must require explicit approval.")
        if proposal.get("reversible") is not True:
            raise ImagoInputError("IMAGO proposal must be reversible.")
        if proposal.get("execution_mode") != "proposal_only":
            raise ImagoInputError("IMAGO proposal must be proposal_only.")
        operation = _ascii_text(proposal.get("operation", "unknown"), f"proposals[{index}].operation")
        operations[operation] = operations.get(operation, 0) + 1
    return {"count": len(proposals), "operations": operations}


def _result_summary(results: Any) -> dict[str, Any]:
    if not isinstance(results, list):
        raise ImagoInputError("IMAGO results must be a list.")
    if len(results) > MAX_SHOW_ITEMS:
        raise ImagoInputError(f"IMAGO session cannot contain more than {MAX_SHOW_ITEMS} results.")
    for index, result in enumerate(results):
        if not isinstance(result, Mapping):
            raise ImagoInputError(f"results[{index}] must be an object.")
        value = _ascii_text(result.get("result", "unknown"), f"results[{index}].result")
        if value not in _PROPOSAL_RESULTS:
            raise ImagoInputError(f"results[{index}].result is unsupported.")
    return {"count": len(results), "statuses": _counts(results, "result")}


def _event_summary(events: Any) -> dict[str, Any]:
    if not isinstance(events, list):
        raise ImagoInputError("IMAGO events must be a list.")
    if len(events) > MAX_SHOW_ITEMS:
        raise ImagoInputError(f"IMAGO session cannot contain more than {MAX_SHOW_ITEMS} events.")
    summaries = []
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            raise ImagoInputError(f"events[{index}] must be an object.")
        event_type = _ascii_text(event.get("event_type", "unknown"), f"events[{index}].event_type")
        if event_type not in _EVENT_TYPES:
            raise ImagoInputError(f"events[{index}].event_type is unsupported.")
        status_after = _ascii_text(event.get("status_after", "unknown"), f"events[{index}].status_after")
        summaries.append(
            {
                "event_type": event_type,
                "status_after": status_after,
                "has_payload": isinstance(event.get("payload"), Mapping)
                and bool(event.get("payload")),
                "has_checkpoint": bool(event.get("checkpoint_id")),
            }
        )
    return {
        "count": len(events),
        "types": _counts(events, "event_type"),
        "items": summaries,
    }


def _session_payload(session: Mapping[str, Any]) -> dict[str, Any]:
    status = _ascii_text(session.get("status"), "status")
    if status not in _STATUS_PHASE:
        raise ImagoInputError("IMAGO status is unsupported.")
    sequence = _non_negative_int(session.get("sequence", 0), "session_sequence")
    open_incidents = session.get("open_incidents")
    pending = session.get("pending_proposal_ids")
    if not isinstance(open_incidents, list) or not isinstance(pending, list):
        raise ImagoInputError("IMAGO incident and proposal cursors must be lists.")
    if len(open_incidents) > MAX_SHOW_ITEMS or len(pending) > MAX_SHOW_ITEMS:
        raise ImagoInputError(f"IMAGO cursors cannot contain more than {MAX_SHOW_ITEMS} items.")
    checkpoint = _identifier(session.get("checkpoint_id"), "checkpoint_id")
    last_event = session.get("last_event_id")
    last_event_id = _identifier(last_event, "last_event_id") if last_event is not None else None
    return {
        "session_id": _identifier(session.get("session_id"), "session_id"),
        "session_schema_version": _ascii_text(
            session.get("schema_version", "unknown"), "session_schema_version"
        ),
        "status": status,
        "session_sequence": sequence,
        "checkpoint_id": checkpoint,
        "last_event_id": last_event_id,
        "open_incident_count": len(open_incidents),
        "pending_proposal_count": len(pending),
        "profile": _profile_summary(session.get("profile")),
        "proposals": _proposal_summary(session.get("proposals")),
        "results": _result_summary(session.get("results")),
        "events": _event_summary(session.get("events")),
        "unknown_count": len(session.get("unknowns", []))
        if isinstance(session.get("unknowns", []), list)
        else 0,
    }


def build_imago_event(
    session: Mapping[str, Any],
    *,
    event_id: str,
    sequence: int,
) -> VJEvent:
    """Build one canonical show snapshot without copying event payloads."""

    if not isinstance(session, Mapping):
        raise ImagoInputError("IMAGO session must be an object.")
    if session.get("read_only") is not True:
        raise ImagoInputError("IMAGO session must be read-only.")
    if session.get("commands_sent") is not False:
        raise ImagoInputError("IMAGO session cannot report sent commands.")
    event_id = _identifier(event_id, "event_id")
    sequence = _non_negative_int(sequence, "sequence")
    timestamp = _timestamp(session.get("updated_at"))
    payload = _session_payload(session)
    try:
        return VJEvent.from_dict(
            {
                "event_id": event_id,
                "timestamp": timestamp,
                "phase": _STATUS_PHASE[payload["status"]],
                "event_type": "imago.show.observed",
                "source": "IMAGO",
                "payload": {
                    "sequence": sequence,
                    "transport": "unknown",
                    "provenance": {
                        "source": "IMAGO",
                        "transport": "unknown",
                        "producer": "IMAGO",
                        "protocol": "session-snapshot",
                    },
                    "show": payload,
                },
            }
        )
    except ContractError as exc:
        raise ImagoInputError(str(exc)) from exc


class ImagoInputProjector:
    """Project an IMAGO session through the existing bounded show-input path."""

    def __init__(self) -> None:
        self._projector = ShowInputProjector()

    def event(self, session: Mapping[str, Any], *, event_id: str, sequence: int) -> VJEvent:
        return build_imago_event(session, event_id=event_id, sequence=sequence)

    def project(
        self,
        session: Mapping[str, Any],
        *,
        event_id: str,
        sequence: int,
        previous: ShowInputProjection | Mapping[str, Any] | None = None,
    ) -> ShowInputProjection:
        return self._projector.project(self.event(session, event_id=event_id, sequence=sequence), previous)


def project_imago_show_input(
    session: Mapping[str, Any],
    *,
    event_id: str,
    sequence: int,
    previous: ShowInputProjection | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a safe phase projection for an IMAGO show snapshot."""

    return ImagoInputProjector().project(
        session,
        event_id=event_id,
        sequence=sequence,
        previous=previous,
    ).to_dict()

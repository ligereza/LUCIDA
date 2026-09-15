"""Read-only live show observation and proposal recording for IMAGO."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .media import ResolumeAdapterError


SCHEMA_VERSION = "0.1"
EVENT_TYPES = (
    "show_started",
    "cue_fired",
    "guard_window_requested",
    "incident_detected",
    "recovery_started",
    "recovery_verified",
    "show_closed",
)
RESULTS = ("accepted", "rejected", "review")
_ALLOWED = {
    "prepared": {"show_started"},
    "showing": {"cue_fired", "guard_window_requested", "incident_detected", "show_closed"},
    "incident": {"recovery_started", "incident_detected"},
    "recovering": {"recovery_verified", "incident_detected"},
    "closed": set(),
}
_STATUS_FOR = {
    "show_started": "showing",
    "cue_fired": "showing",
    "guard_window_requested": "showing",
    "incident_detected": "incident",
    "recovery_started": "recovering",
    "recovery_verified": "showing",
    "show_closed": "closed",
}
_PROPOSAL_OPERATION = {
    "show_started": "observe_show",
    "guard_window_requested": "prepare_guard_window",
    "incident_detected": "capture_incident",
    "recovery_started": "compare_checkpoint",
    "recovery_verified": "verify_recovery",
    "show_closed": "preserve_summary",
}


class ImagoError(ResolumeAdapterError):
    """Raised when an IMAGO show contract is invalid."""


def build_show_session(
    profile: Mapping[str, Any] | None = None,
    *,
    session_id: str,
    name: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a proposal-only live session from a safe profile summary."""

    _text(session_id, "session_id")
    _text(name, "name")
    if profile is not None and not isinstance(profile, Mapping):
        raise ImagoError("profile must be an object.")
    timestamp = created_at or _now()
    _timestamp(timestamp, "created_at")
    session = {
        "schema_version": SCHEMA_VERSION,
        "session_type": "ImagoShowSession",
        "session_id": session_id.strip(),
        "name": name.strip(),
        "created_at": timestamp,
        "updated_at": timestamp,
        "read_only": True,
        "commands_sent": False,
        "profile": _profile_summary(profile or {}),
        "status": "prepared",
        "sequence": 0,
        "last_event_id": None,
        "last_timestamp": None,
        "checkpoint_id": "checkpoint-prepared",
        "open_incidents": [],
        "proposals": [],
        "pending_proposal_ids": [],
        "results": [],
        "events": [],
        "unknowns": [
            "Live output and physical screen state are not observed by this offline recorder.",
            "A proposal does not authorize a Resolume, DMX, or processor action.",
        ],
    }
    validate_session(session)
    return session


def record_event(
    session: Mapping[str, Any],
    *,
    event_type: str,
    recorded_at: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Record one observed live event and publish any explicit proposal."""

    validate_session(session)
    if event_type not in EVENT_TYPES:
        raise ImagoError(f"unknown event_type: {event_type}")
    current_status = session["status"]
    if event_type not in _ALLOWED[current_status]:
        raise ImagoError(f"transition not allowed: {current_status} -> {event_type}")
    timestamp = recorded_at or _now()
    _timestamp(timestamp, "recorded_at")
    if session.get("last_timestamp") and _time(timestamp) < _time(session["last_timestamp"]):
        raise ImagoError("recorded_at cannot precede the last recorded event.")
    safe_payload = _event_payload(payload)
    updated = copy.deepcopy(dict(session))
    event_id = f"event-{updated['sequence'] + 1:03d}"
    next_status = _STATUS_FOR[event_type]
    if event_type == "incident_detected":
        if event_id not in updated["open_incidents"]:
            updated["open_incidents"].append(event_id)
    elif event_type == "recovery_verified":
        updated["open_incidents"] = []
    updated["sequence"] += 1
    updated["status"] = next_status
    updated["last_event_id"] = event_id
    updated["last_timestamp"] = timestamp
    if event_type in {"show_started", "incident_detected", "recovery_verified", "show_closed"}:
        updated["checkpoint_id"] = f"checkpoint-{event_id}"
    updated["events"].append({
        "event_id": event_id,
        "created_at": timestamp,
        "event_type": event_type,
        "payload": safe_payload,
        "status_after": next_status,
        "checkpoint_id": updated["checkpoint_id"],
    })
    operation = _PROPOSAL_OPERATION.get(event_type)
    if operation:
        proposal = {
            "proposal_id": f"proposal-{event_id}-{operation}",
            "event_id": event_id,
            "operation": operation,
            "reason": _proposal_reason(event_type, safe_payload),
            "requires_explicit_approval": True,
            "reversible": True,
            "execution_mode": "proposal_only",
        }
        updated["proposals"].append(proposal)
        updated["pending_proposal_ids"].append(proposal["proposal_id"])
    updated["updated_at"] = timestamp
    validate_session(updated)
    return updated


def record_result(
    session: Mapping[str, Any],
    *,
    proposal_id: str,
    result: str,
    notes: str = "",
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Record an operator result for a pending proposal without executing it."""

    validate_session(session)
    if result not in RESULTS:
        raise ImagoError(f"result must be one of: {', '.join(RESULTS)}")
    if proposal_id not in session["pending_proposal_ids"]:
        raise ImagoError("proposal_id is not pending.")
    if not isinstance(notes, str):
        raise ImagoError("notes must be text.")
    timestamp = recorded_at or _now()
    _timestamp(timestamp, "recorded_at")
    if session.get("last_timestamp") and _time(timestamp) < _time(session["last_timestamp"]):
        raise ImagoError("recorded_at cannot precede the last recorded event.")
    updated = copy.deepcopy(dict(session))
    updated["pending_proposal_ids"].remove(proposal_id)
    updated["results"].append({
        "result_id": f"result-{len(updated['results']) + 1:03d}",
        "proposal_id": proposal_id,
        "created_at": timestamp,
        "result": result,
        "notes": notes,
    })
    updated["updated_at"] = timestamp
    validate_session(updated)
    return updated


def next_proposal(session: Mapping[str, Any]) -> dict[str, Any] | None:
    validate_session(session)
    pending = set(session["pending_proposal_ids"])
    for proposal in session["proposals"]:
        if proposal["proposal_id"] in pending:
            return copy.deepcopy(proposal)
    return None


def load_session(path: str | Path) -> dict[str, Any]:
    session_path = Path(path).expanduser().resolve()
    if not session_path.is_file():
        raise ImagoError(f"IMAGO session does not exist: {session_path}")
    try:
        value = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ImagoError(f"IMAGO session cannot be read: {session_path}") from exc
    validate_session(value)
    return value


def write_session(session: Mapping[str, Any], path: str | Path) -> Path:
    validate_session(session)
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(session, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def validate_session(value: Mapping[str, Any]) -> None:
    """Validate the strict fields IMAGO owns."""

    if not isinstance(value, Mapping):
        raise ImagoError("session must be an object.")
    required = {
        "schema_version", "session_type", "session_id", "name", "created_at", "updated_at",
        "read_only", "commands_sent", "profile", "status", "sequence", "last_event_id",
        "last_timestamp", "checkpoint_id", "open_incidents", "proposals", "pending_proposal_ids",
        "results", "events", "unknowns",
    }
    if set(value) != required:
        raise ImagoError("session fields do not match the IMAGO contract.")
    if value["schema_version"] != SCHEMA_VERSION or value["session_type"] != "ImagoShowSession":
        raise ImagoError("session contract identity is invalid.")
    _text(value["session_id"], "session_id")
    _text(value["name"], "name")
    _timestamp(value["created_at"], "created_at")
    _timestamp(value["updated_at"], "updated_at")
    if value["read_only"] is not True or value["commands_sent"] is not False:
        raise ImagoError("IMAGO session must remain read_only with commands_sent false.")
    if not isinstance(value["profile"], Mapping) or value["status"] not in _ALLOWED:
        raise ImagoError("profile or status is invalid.")
    if isinstance(value["sequence"], bool) or not isinstance(value["sequence"], int) or value["sequence"] < 0:
        raise ImagoError("sequence must be a non-negative integer.")
    for field_name in ("last_event_id", "last_timestamp"):
        field_value = value[field_name]
        if field_value is not None and not isinstance(field_value, str):
            raise ImagoError(f"{field_name} must be text or null.")
    _text(value["checkpoint_id"], "checkpoint_id")
    for field_name in ("open_incidents", "pending_proposal_ids", "proposals", "results", "events", "unknowns"):
        if not isinstance(value[field_name], list):
            raise ImagoError(f"{field_name} must be a list.")
    for proposal in value["proposals"]:
        if not isinstance(proposal, Mapping) or set(proposal) != {
            "proposal_id", "event_id", "operation", "reason", "requires_explicit_approval", "reversible", "execution_mode"
        }:
            raise ImagoError("proposal fields are invalid.")
        if proposal["requires_explicit_approval"] is not True or proposal["reversible"] is not True or proposal["execution_mode"] != "proposal_only":
            raise ImagoError("IMAGO proposals must be explicit, reversible, and proposal_only.")
    for event in value["events"]:
        if not isinstance(event, Mapping) or set(event) != {"event_id", "created_at", "event_type", "payload", "status_after", "checkpoint_id"}:
            raise ImagoError("event fields are invalid.")
        _text(event["event_id"], "event_id")
        _timestamp(event["created_at"], "event.created_at")
        if event["event_type"] not in EVENT_TYPES or event["status_after"] not in _ALLOWED:
            raise ImagoError("event type or status is invalid.")
        if not isinstance(event["payload"], Mapping):
            raise ImagoError("event payload must be an object.")
    for result in value["results"]:
        if not isinstance(result, Mapping) or set(result) != {"result_id", "proposal_id", "created_at", "result", "notes"}:
            raise ImagoError("result fields are invalid.")
        if result["result"] not in RESULTS or not isinstance(result["notes"], str):
            raise ImagoError("result value or notes are invalid.")


def _profile_summary(profile: Mapping[str, Any]) -> dict[str, Any]:
    allowed = ("profile_id", "venue_id", "signal_profile_id", "mapping_profile_id", "approved_at")
    summary = {key: profile[key] for key in allowed if key in profile}
    return {key: value for key, value in summary.items() if isinstance(value, (str, int, float, bool)) or value is None}


def _event_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ImagoError("payload must be an object.")
    allowed = ("cue_id", "clip_id", "layer", "category", "reason", "signal_status", "notes", "duration_ms", "base_clip_id", "test_scope")
    result = {key: payload[key] for key in allowed if key in payload}
    if any(not isinstance(value, (str, int, float, bool)) and value is not None for value in result.values()):
        raise ImagoError("event payload values must be scalar or null.")
    if "duration_ms" in result:
        duration = result["duration_ms"]
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0 or duration > 60000:
            raise ImagoError("duration_ms must be greater than 0 and no more than 60000.")
        result["duration_ms"] = round(float(duration), 3)
    return result


def _proposal_reason(event_type: str, payload: Mapping[str, Any]) -> str:
    if event_type == "incident_detected":
        return f"Capture evidence for incident category: {payload.get('category', 'unclassified')}."
    if event_type == "guard_window_requested":
        duration = payload.get("duration_ms", 5000)
        return f"Prepare a {duration:g} ms guard window for explicit operator approval; keep the base visual available during the test."
    reasons = {
        "show_started": "Record the live show start for later replay.",
        "recovery_started": "Compare the current observation with the last checkpoint.",
        "recovery_verified": "Record that recovery was verified by the operator.",
        "show_closed": "Preserve the show summary for later analysis.",
    }
    return reasons[event_type]


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ImagoError(f"{field_name} must be non-empty text.")
    return value.strip()


def _timestamp(value: Any, field_name: str) -> str:
    text = _text(value, field_name)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ImagoError(f"{field_name} must be ISO-8601.") from exc
    return text


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


__all__ = [
    "EVENT_TYPES",
    "ImagoError",
    "RESULTS",
    "build_show_session",
    "load_session",
    "next_proposal",
    "record_event",
    "record_result",
    "validate_session",
    "write_session",
]

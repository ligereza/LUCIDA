"""Safe bridge from a NAYADE soundcheck session to the VJ event contract."""

from __future__ import annotations

from datetime import datetime
import math
import re
from typing import Any, Mapping

from .contracts import VJEvent
from .contracts.models import ContractError
from .show_input import ShowInputError, ShowInputProjection, ShowInputProjector


MAX_SOUNDCHECK_ITEMS = 200
_ASCII_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]+$")
_PROCESSOR_TRANSPORTS = {"unknown", "usb", "serial", "ethernet", "hdmi", "manual"}
_CONFIDENCE = {"unknown", "low", "medium", "high"}
_SIGNAL_FIELDS = ("resolution", "fps", "range", "colorspace", "scan_type")
_MODULE_FIELDS = (
    "indoor_outdoor",
    "pixel_pitch_mm",
    "width",
    "height",
    "refresh_hz",
    "max_nits",
    "gamma",
    "color_range",
    "color_space",
    "confidence",
)


class NayadeInputError(ShowInputError):
    """Raised when a NAYADE session cannot cross the VJ boundary safely."""


def _ascii_text(value: Any, field_name: str, *, max_length: int = 96) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NayadeInputError(f"{field_name} must be non-empty ASCII text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise NayadeInputError(f"{field_name} must contain ASCII characters only.") from exc
    if len(text) > max_length or any(character in text for character in "\\/"):
        raise NayadeInputError(f"{field_name} contains unsupported text.")
    return text


def _identifier(value: Any, field_name: str) -> str:
    text = _ascii_text(value, field_name)
    if not _ASCII_IDENTIFIER.fullmatch(text):
        raise NayadeInputError(f"{field_name} must be a stable identifier.")
    return text


def _timestamp(value: Any) -> str:
    text = _ascii_text(value, "updated_at")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NayadeInputError("updated_at must be ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise NayadeInputError("updated_at must include a timezone.")
    return text


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise NayadeInputError(f"{field_name} must be a non-negative integer.")
    return value


def _safe_scalar(value: Any, field_name: str) -> int | float | str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise NayadeInputError(f"{field_name} must be finite.")
        return int(value) if float(value).is_integer() else round(float(value), 6)
    return _ascii_text(value, field_name, max_length=64)


def _safe_signal(value: Any, field_name: str) -> dict[str, int | float | str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise NayadeInputError(f"{field_name} must be an object.")
    result: dict[str, int | float | str] = {}
    for key in _SIGNAL_FIELDS:
        normalized = _safe_scalar(value.get(key), f"{field_name}.{key}")
        if normalized is not None:
            result[key] = normalized
    return result


def _processor_summary(observation: Any) -> dict[str, Any] | None:
    if observation is None:
        return None
    if not isinstance(observation, Mapping):
        raise NayadeInputError("processor_observation must be an object.")
    if observation.get("read_only") is not True:
        raise NayadeInputError("processor_observation must be read-only.")
    if observation.get("commands_sent") is not False:
        raise NayadeInputError("processor_observation cannot report sent commands.")
    transport = _ascii_text(observation.get("transport", "unknown"), "processor.transport")
    if transport not in _PROCESSOR_TRANSPORTS:
        raise NayadeInputError("processor.transport is unsupported.")
    confidence = _ascii_text(observation.get("confidence", "unknown"), "processor.confidence")
    if confidence not in _CONFIDENCE:
        raise NayadeInputError("processor.confidence is unsupported.")
    result: dict[str, Any] = {
        "transport": transport,
        "confidence": confidence,
        "read_only": True,
        "commands_sent": False,
        "evidence_count": len(observation.get("evidence", ()))
        if isinstance(observation.get("evidence", ()), (list, tuple))
        else 0,
        "input_signal": _safe_signal(observation.get("input_signal"), "processor.input_signal"),
        "output_signal": _safe_signal(observation.get("output_signal"), "processor.output_signal"),
    }
    for source_key, target_key in (("model", "model"), ("firmware", "firmware")):
        normalized = observation.get(source_key)
        if normalized is not None:
            result[target_key] = _ascii_text(normalized, f"processor.{source_key}")

    module_profile = observation.get("module_profile")
    if module_profile is not None and not isinstance(module_profile, Mapping):
        raise NayadeInputError("processor.module_profile must be an object.")
    module_summary: dict[str, int | float | str] = {}
    for key in _MODULE_FIELDS:
        normalized = _safe_scalar((module_profile or {}).get(key), f"processor.module_profile.{key}")
        if normalized is not None:
            module_summary[key] = normalized
    result["module_profile"] = module_summary
    return result


def _result_counts(values: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for index, value in enumerate(values):
        result = _ascii_text(value.get("result", "UNKNOWN"), f"items[{index}].result")
        counts[result] = counts.get(result, 0) + 1
    return counts


def _readiness_summary(planned_steps: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Project only the bounded readiness cursor needed by downstream stages."""

    actionable_results = {"planned", "running", "review", "rejected"}
    risks: list[dict[str, str]] = []
    pending = [step for step in planned_steps if step.get("result") == "planned"]
    pending_required = [
        step for step in pending
        if isinstance(step.get("parameters"), Mapping)
        and step["parameters"].get("priority") == "required"
    ]
    for index, step in enumerate(planned_steps):
        result = _ascii_text(step.get("result", "unknown"), f"planned_steps[{index}].result")
        if result in {"running", "review", "rejected"}:
            step_id = _identifier(step.get("step_id"), f"planned_steps[{index}].step_id")
            risks.append({"step_id": step_id, "status": result})

    if any(item["status"] == "rejected" for item in risks):
        status = "BLOCKED"
    elif risks or pending_required:
        status = "REVIEW"
    elif pending:
        status = "INCOMPLETE"
    else:
        status = "READY"

    next_step = None
    for index, step in enumerate(planned_steps):
        result = _ascii_text(step.get("result", "unknown"), f"planned_steps[{index}].result")
        if result not in actionable_results:
            continue
        step_id = _identifier(step.get("step_id"), f"planned_steps[{index}].step_id")
        operation = _ascii_text(step.get("operation", "unknown"), f"planned_steps[{index}].operation")
        scope = _ascii_text(step.get("scope", "unknown"), f"planned_steps[{index}].scope")
        parameters = step.get("parameters") or {}
        if not isinstance(parameters, Mapping):
            raise NayadeInputError(f"planned_steps[{index}].parameters must be an object.")
        pattern = parameters.get("pattern")
        if pattern is not None:
            pattern = _identifier(pattern, f"planned_steps[{index}].parameters.pattern")
        priority = _ascii_text(parameters.get("priority", "unclassified"), f"planned_steps[{index}].parameters.priority")
        checks = step.get("expected_checks", [])
        if not isinstance(checks, list):
            raise NayadeInputError(f"planned_steps[{index}].expected_checks must be a list.")
        next_step = {
            "step_id": step_id,
            "operation": operation,
            "scope": scope,
            "pattern": pattern,
            "priority": priority,
            "expected_checks": [
                _identifier(value, f"planned_steps[{index}].expected_checks") for value in checks[:12]
            ],
            "result": result,
        }
        break
    return {
        "status": status,
        "pending_count": len(pending),
        "pending_required_count": len(pending_required),
        "risk_count": len(risks),
        "risk_steps": risks,
        "next_step": next_step,
    }


def _session_payload(session: Mapping[str, Any], processor_observation: Any) -> dict[str, Any]:
    planned_steps = session.get("planned_steps")
    events = session.get("events")
    if not isinstance(planned_steps, list) or not isinstance(events, list):
        raise NayadeInputError("NAYADE planned_steps and events must be lists.")
    if len(planned_steps) > MAX_SOUNDCHECK_ITEMS or len(events) > MAX_SOUNDCHECK_ITEMS:
        raise NayadeInputError(f"NAYADE session cannot contain more than {MAX_SOUNDCHECK_ITEMS} steps or events.")
    if any(not isinstance(item, Mapping) for item in (*planned_steps, *events)):
        raise NayadeInputError("NAYADE steps and events must be objects.")

    source = session.get("source")
    targets = session.get("targets")
    if source is not None and not isinstance(source, Mapping):
        raise NayadeInputError("NAYADE source must be an object.")
    if not isinstance(targets, Mapping):
        raise NayadeInputError("NAYADE targets must be an object.")
    slices = targets.get("slices", [])
    groups = targets.get("input_groups", [])
    if not isinstance(slices, list) or not isinstance(groups, list):
        raise NayadeInputError("NAYADE targets must contain lists.")

    composition = session.get("composition") or {}
    if not isinstance(composition, Mapping):
        raise NayadeInputError("NAYADE composition must be an object.")
    composition_summary = {}
    for key in ("width", "height"):
        normalized = _safe_scalar(composition.get(key), f"composition.{key}")
        if normalized is not None:
            composition_summary[key] = normalized

    event_summary = []
    for index, event in enumerate(events):
        operation = _ascii_text(event.get("operation", "unknown"), f"events[{index}].operation")
        scope = _ascii_text(event.get("scope", "unknown"), f"events[{index}].scope")
        result = _ascii_text(event.get("result", "unknown"), f"events[{index}].result")
        targets_value = event.get("targets", [])
        if not isinstance(targets_value, list):
            raise NayadeInputError(f"events[{index}].targets must be a list.")
        event_summary.append(
            {
                "operation": operation,
                "scope": scope,
                "target_count": len(targets_value),
                "result": result,
            }
        )

    return {
        "session_id": _identifier(session.get("session_id"), "session_id"),
        "session_schema_version": _ascii_text(
            session.get("schema_version", "unknown"), "session_schema_version"
        ),
        "read_only_source": session.get("read_only_source") is True,
        "source_type": _ascii_text((source or {}).get("source_type", "unknown"), "source_type"),
        "composition": composition_summary,
        "seed": _safe_scalar(session.get("seed", 0), "seed"),
        "slice_count": len(slices),
        "input_group_count": len(groups),
        "planned_step_count": len(planned_steps),
        "planned_step_results": _result_counts([item for item in planned_steps]),
        "event_count": len(events),
        "event_results": _result_counts([item for item in events]),
        "events": event_summary,
        "readiness": _readiness_summary([item for item in planned_steps]),
        "processor": _processor_summary(processor_observation),
    }


def build_nayade_event(
    session: Mapping[str, Any],
    *,
    event_id: str,
    sequence: int,
    processor_observation: Mapping[str, Any] | None = None,
) -> VJEvent:
    """Build one canonical preparation event without copying session paths."""

    if not isinstance(session, Mapping):
        raise NayadeInputError("NAYADE session must be an object.")
    event_id = _identifier(event_id, "event_id")
    sequence = _non_negative_int(sequence, "sequence")
    timestamp = _timestamp(session.get("updated_at"))
    payload = _session_payload(session, processor_observation)
    if session.get("read_only_source") is not True:
        raise NayadeInputError("NAYADE session must declare a read-only source.")
    try:
        return VJEvent.from_dict(
            {
                "event_id": event_id,
                "timestamp": timestamp,
                "phase": "preparation",
                "event_type": "nayade.soundcheck.observed",
                "source": "NAYADE",
                "payload": {
                    "sequence": sequence,
                    "transport": "unknown",
                    "provenance": {
                        "source": "NAYADE",
                        "transport": "unknown",
                        "producer": "NAYADE",
                        "protocol": "session-report",
                    },
                    "soundcheck": payload,
                },
            }
        )
    except ContractError as exc:
        raise NayadeInputError(str(exc)) from exc


class NayadeInputProjector:
    """Project a NAYADE session through the existing bounded show-input path."""

    def __init__(self) -> None:
        self._projector = ShowInputProjector()

    def event(
        self,
        session: Mapping[str, Any],
        *,
        event_id: str,
        sequence: int,
        processor_observation: Mapping[str, Any] | None = None,
    ) -> VJEvent:
        return build_nayade_event(
            session,
            event_id=event_id,
            sequence=sequence,
            processor_observation=processor_observation,
        )

    def project(
        self,
        session: Mapping[str, Any],
        *,
        event_id: str,
        sequence: int,
        processor_observation: Mapping[str, Any] | None = None,
        previous: ShowInputProjection | Mapping[str, Any] | None = None,
    ) -> ShowInputProjection:
        return self._projector.project(
            self.event(
                session,
                event_id=event_id,
                sequence=sequence,
                processor_observation=processor_observation,
            ),
            previous,
        )


def project_nayade_show_input(
    session: Mapping[str, Any],
    *,
    event_id: str,
    sequence: int,
    processor_observation: Mapping[str, Any] | None = None,
    previous: ShowInputProjection | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a safe preparation projection for a NAYADE session."""

    return NayadeInputProjector().project(
        session,
        event_id=event_id,
        sequence=sequence,
        processor_observation=processor_observation,
        previous=previous,
    ).to_dict()

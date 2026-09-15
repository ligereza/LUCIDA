"""Host-neutral show input projection for the RESOLUME_ADAPTER VJ adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Mapping

from .contracts import ALLOWED_NEXT_PHASES, PHASES, VJEvent
from .contracts.models import ContractError


SHOW_INPUT_SCHEMA_VERSION = "0.1"
SHOW_STATES = ("idle", "ready", "showing", "incident", "recovering", "closed", "unknown")
SHOW_INPUT_TRANSPORTS = ("artnet", "osc", "sacn", "timecode", "unknown", "xio")
PROVENANCE_OPTIONAL_FIELDS = ("clock_id", "device", "producer", "protocol", "raw_hash")
_ASCII_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]+$")


class ShowInputError(ValueError):
    """Raised when a host-neutral show input cannot be projected safely."""


class StaleShowInputError(ShowInputError):
    """Raised when an input is older than the current projection cursor."""


def _ascii_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ShowInputError(f"{field_name} must be non-empty ASCII text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ShowInputError(f"{field_name} must contain ASCII characters only.") from exc
    return text


def _timestamp(value: Any) -> tuple[str, datetime]:
    text = _ascii_text(value, "source_timestamp")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ShowInputError("source_timestamp must be ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise ShowInputError("source_timestamp must include a timezone.")
    return text, parsed


def _payload(event: VJEvent) -> Mapping[str, Any]:
    if not isinstance(event.payload, Mapping):
        raise ShowInputError("event payload must be an object.")
    return event.payload


def _sequence(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ShowInputError("sequence must be a non-negative integer.")
    return value


def _transport(payload: Mapping[str, Any]) -> str:
    value = payload.get("transport", "unknown")
    transport = _ascii_text(value, "provenance.transport")
    if transport not in SHOW_INPUT_TRANSPORTS:
        raise ShowInputError(f"Unsupported show input transport: {transport}.")
    return transport


def _show_state(event: VJEvent, payload: Mapping[str, Any]) -> str:
    explicit = payload.get("show_state")
    if explicit is not None:
        state = _ascii_text(explicit, "show_state")
        if state not in SHOW_STATES:
            raise ShowInputError(f"Unsupported show_state: {state}.")
        return state
    if event.event_type == "show.closed" or event.phase == "closure":
        return "closed"
    if event.event_type == "incident.detected" or event.phase == "incident":
        return "incident"
    if event.event_type == "recovery.started" or event.phase == "recovery":
        return "recovering"
    if event.event_type == "show.started" or event.phase == "show":
        return "showing"
    if event.phase in {"preflight", "preparation"}:
        return "ready"
    return "unknown"


def _preview_candidate(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("preview_candidate")
    if value is None:
        return None
    candidate = _ascii_text(value, "preview_candidate")
    if not _ASCII_IDENTIFIER.fullmatch(candidate):
        raise ShowInputError("preview_candidate must be a stable identifier.")
    return candidate


def _provenance(event: VJEvent, payload: Mapping[str, Any], transport: str) -> dict[str, str]:
    raw = payload.get("provenance", {})
    if not isinstance(raw, Mapping):
        raise ShowInputError("provenance must be an object.")
    unknown_fields = set(raw) - {"source", "transport", *PROVENANCE_OPTIONAL_FIELDS}
    if unknown_fields:
        raise ShowInputError("provenance contains unsupported fields.")
    source = _ascii_text(event.source, "provenance.source")
    if "source" in raw and _ascii_text(raw["source"], "provenance.source") != source:
        raise ShowInputError("provenance.source must match event source.")
    if "transport" in raw and _ascii_text(raw["transport"], "provenance.transport") != transport:
        raise ShowInputError("provenance.transport must match event transport.")
    result = {"source": source, "transport": transport}
    for field_name in PROVENANCE_OPTIONAL_FIELDS:
        if field_name in raw:
            result[field_name] = _ascii_text(raw[field_name], f"provenance.{field_name}")
    return {key: result[key] for key in sorted(result)}


@dataclass(frozen=True)
class ShowInputProjection:
    """The bounded metadata surface consumed by a future LUCIDA reducer."""

    show_state: str
    show_phase: str
    preview_candidate: str | None
    source_timestamp: str
    sequence: int
    provenance: dict[str, str]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ShowInputProjection":
        """Validate a projection received by a reducer or replay consumer."""

        return ShowInputProjector._from_projection_dict(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "ResolumeAdapterShowInput",
            "schema_version": SHOW_INPUT_SCHEMA_VERSION,
            "show_state": self.show_state,
            "show_phase": self.show_phase,
            "preview_candidate": self.preview_candidate,
            "source_timestamp": self.source_timestamp,
            "sequence": self.sequence,
            "provenance": dict(self.provenance),
        }


class ShowInputProjector:
    """Project canonical VJ events without mutating state or performing actions."""

    def project(
        self,
        event: VJEvent | Mapping[str, Any],
        previous: ShowInputProjection | Mapping[str, Any] | None = None,
    ) -> ShowInputProjection:
        try:
            parsed_event = event if isinstance(event, VJEvent) else VJEvent.from_dict(event)
        except ContractError as exc:
            raise ShowInputError(str(exc)) from exc
        payload = _payload(parsed_event)
        sequence = _sequence(payload.get("sequence"))
        source_timestamp, parsed_timestamp = _timestamp(parsed_event.timestamp)
        transport = _transport(payload)
        projection = ShowInputProjection(
            show_state=_show_state(parsed_event, payload),
            show_phase=parsed_event.phase,
            preview_candidate=_preview_candidate(payload),
            source_timestamp=source_timestamp,
            sequence=sequence,
            provenance=_provenance(parsed_event, payload, transport),
        )
        if previous is not None:
            previous_projection = (
                previous
                if isinstance(previous, ShowInputProjection)
                else ShowInputProjection.from_dict(previous)
            )
            _, previous_timestamp = _timestamp(previous_projection.source_timestamp)
            if sequence <= previous_projection.sequence or parsed_timestamp < previous_timestamp:
                raise StaleShowInputError(
                    f"stale show input sequence {sequence} after {previous_projection.sequence}."
                )
            if parsed_event.phase not in ALLOWED_NEXT_PHASES[previous_projection.show_phase]:
                raise ShowInputError(
                    "show phase transition not allowed: "
                    f"{previous_projection.show_phase} -> {parsed_event.phase}."
                )
        return projection

    def project_osc(
        self,
        envelope: Any,
        previous: ShowInputProjection | Mapping[str, Any] | None = None,
    ) -> ShowInputProjection:
        """Normalize one existing OSC envelope and project it without opening a socket."""

        from lucida.signals import OscResolumeBoundary

        try:
            event = OscResolumeBoundary().normalize(envelope)
        except ValueError as exc:
            raise ShowInputError(f"OSC input invalid: {exc}") from exc
        return self.project(event, previous)

    @staticmethod
    def _from_projection_dict(value: Mapping[str, Any]) -> ShowInputProjection:
        if not isinstance(value, Mapping):
            raise ShowInputError("previous projection must be an object.")
        required = {
            "contract_type",
            "schema_version",
            "show_state",
            "show_phase",
            "preview_candidate",
            "source_timestamp",
            "sequence",
            "provenance",
        }
        if set(value) != required:
            raise ShowInputError("previous projection contains unsupported or missing fields.")
        if value["contract_type"] != "ResolumeAdapterShowInput":
            raise ShowInputError("previous projection contract_type is invalid.")
        if value["schema_version"] != SHOW_INPUT_SCHEMA_VERSION:
            raise ShowInputError("previous projection schema_version is invalid.")
        show_state = _ascii_text(value["show_state"], "show_state")
        if show_state not in SHOW_STATES:
            raise ShowInputError("previous projection show_state is invalid.")
        show_phase = _ascii_text(value["show_phase"], "show_phase")
        if show_phase not in PHASES:
            raise ShowInputError("previous projection show_phase is invalid.")
        preview_candidate = value["preview_candidate"]
        if preview_candidate is not None:
            preview_candidate = _preview_candidate({"preview_candidate": preview_candidate})
        sequence = _sequence(value["sequence"])
        source_timestamp, _ = _timestamp(value["source_timestamp"])
        provenance = value["provenance"]
        if not isinstance(provenance, Mapping):
            raise ShowInputError("previous projection provenance must be an object.")
        allowed_provenance = {"source", "transport", *PROVENANCE_OPTIONAL_FIELDS}
        if set(provenance) - allowed_provenance:
            raise ShowInputError("previous projection provenance has unsupported fields.")
        if "source" not in provenance or "transport" not in provenance:
            raise ShowInputError("previous projection provenance needs source and transport.")
        provenance_source = _ascii_text(provenance["source"], "provenance source")
        provenance_transport = _ascii_text(provenance["transport"], "provenance transport")
        if provenance_transport not in SHOW_INPUT_TRANSPORTS:
            raise ShowInputError("previous projection provenance transport is invalid.")
        normalized_provenance = {
            "source": provenance_source,
            "transport": provenance_transport,
        }
        for field_name in PROVENANCE_OPTIONAL_FIELDS:
            if field_name in provenance:
                normalized_provenance[field_name] = _ascii_text(
                    provenance[field_name], f"provenance {field_name}"
                )
        return ShowInputProjection(
            show_state=show_state,
            show_phase=show_phase,
            preview_candidate=preview_candidate,
            source_timestamp=source_timestamp,
            sequence=sequence,
            provenance={key: normalized_provenance[key] for key in sorted(normalized_provenance)},
        )


def project_show_input(
    event: VJEvent | Mapping[str, Any],
    previous: ShowInputProjection | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one safe show input projection for a reducer or replay."""

    return ShowInputProjector().project(event, previous).to_dict()


def project_osc_show_input(
    envelope: Any,
    previous: ShowInputProjection | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize and project one existing OSC envelope for a future reducer."""

    return ShowInputProjector().project_osc(envelope, previous).to_dict()


def validate_show_input(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a detached canonical dictionary for a validated projection."""

    return ShowInputProjection.from_dict(value).to_dict()

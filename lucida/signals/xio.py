"""Offline consumer for canonical XIO ApplicationEvent records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping
import json

from adapters.vj.contracts import VJEvent, VJResult

if TYPE_CHECKING:
    from ..replay.session import SessionReplay, SessionReplayRecord, SignalEnvelope


XIO_SCHEMA_VERSION = "0.1"
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
_PHASES = {"preflight", "preparation", "show", "incident", "recovery", "closure"}
_LIFECYCLE_TYPES = {
    "phase.completed",
    "show.started",
    "incident.detected",
    "recovery.started",
    "recovery.verified",
    "show.closed",
}
_CHANNEL_PHASES = {
    "instar": "preflight",
    "preflight": "preflight",
    "nayade": "preparation",
    "soundcheck": "preparation",
    "preparation": "preparation",
    "imago": "show",
    "show": "show",
    "live": "show",
    "incident": "incident",
    "recovery": "recovery",
    "closure": "closure",
}


class XioConsumerError(ValueError):
    """Base error for canonical XIO event consumption."""


class XioSchemaError(XioConsumerError):
    """Raised when an ApplicationEvent is incomplete or malformed."""


class XioClockError(XioConsumerError):
    """Raised when source and received clocks are invalid."""


class XioMappingError(XioConsumerError):
    """Raised when an XIO event cannot map to a VJ lifecycle event."""


def _ascii_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise XioSchemaError(f"{field_name} must be non-empty ASCII text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise XioSchemaError(f"{field_name} must contain ASCII characters only.") from exc
    return text


def _technical_id(value: Any, field_name: str) -> str:
    text = _ascii_text(value, field_name)
    if not _ID_PATTERN.fullmatch(text):
        raise XioSchemaError(f"{field_name} contains unsupported technical characters.")
    return text


def _technical_token(value: Any, field_name: str) -> str:
    text = _ascii_text(value, field_name)
    if not _TOKEN_PATTERN.fullmatch(text):
        raise XioSchemaError(f"{field_name} contains unsupported path characters.")
    return text


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise XioSchemaError(f"{field_name} must be an object.")
    result = dict(value)
    for key in result:
        _ascii_text(key, f"{field_name} key")
    return result


def _clock(value: Any, field_name: str) -> tuple[str, datetime]:
    text = _ascii_text(value, field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise XioClockError(f"{field_name} is not valid ISO-8601: {text}") from exc
    if parsed.tzinfo is None:
        raise XioClockError(f"{field_name} must include a timezone.")
    return text, parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ApplicationEvent:
    """Canonical XIO event accepted by the offline consumer."""

    event_id: str
    source_app: str
    event_type: str
    channel: str
    payload: dict[str, Any]
    source_timestamp: str
    received_timestamp: str
    session_id: str
    peer_id: str
    sequence: int
    raw_hash: str
    provenance: dict[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ApplicationEvent":
        if not isinstance(value, Mapping):
            raise XioSchemaError("ApplicationEvent must be an object.")
        required = {
            "event_id",
            "source_app",
            "event_type",
            "channel",
            "payload",
            "source_timestamp",
            "received_timestamp",
            "session_id",
            "peer_id",
            "sequence",
            "raw_hash",
            "provenance",
        }
        missing = sorted(required - set(value))
        if missing:
            raise XioSchemaError(f"ApplicationEvent missing fields: {missing}.")

        source_timestamp, source_time = _clock(value.get("source_timestamp"), "source_timestamp")
        received_timestamp, received_time = _clock(value.get("received_timestamp"), "received_timestamp")
        if received_time < source_time:
            raise XioClockError("received_timestamp cannot precede source_timestamp.")
        sequence = value.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
            raise XioSchemaError("sequence must be a positive integer.")
        return cls(
            event_id=_technical_id(value.get("event_id"), "event_id"),
            source_app=_technical_id(value.get("source_app"), "source_app"),
            event_type=_technical_token(value.get("event_type"), "event_type"),
            channel=_technical_token(value.get("channel"), "channel"),
            payload=_mapping(value.get("payload"), "payload"),
            source_timestamp=source_timestamp,
            received_timestamp=received_timestamp,
            session_id=_technical_id(value.get("session_id"), "session_id"),
            peer_id=_technical_id(value.get("peer_id"), "peer_id"),
            sequence=sequence,
            raw_hash=_technical_id(value.get("raw_hash"), "raw_hash"),
            provenance=_mapping(value.get("provenance"), "provenance"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "ApplicationEvent",
            "schema_version": XIO_SCHEMA_VERSION,
            "event_id": self.event_id,
            "source_app": self.source_app,
            "event_type": self.event_type,
            "channel": self.channel,
            "payload": dict(self.payload),
            "source_timestamp": self.source_timestamp,
            "received_timestamp": self.received_timestamp,
            "session_id": self.session_id,
            "peer_id": self.peer_id,
            "sequence": self.sequence,
            "raw_hash": self.raw_hash,
            "provenance": dict(self.provenance),
        }

    def trace_metadata(self) -> dict[str, Any]:
        return {
            "source_app": self.source_app,
            "source_event_id": self.event_id,
            "session_id": self.session_id,
            "peer_id": self.peer_id,
            "raw_hash": self.raw_hash,
            "source_timestamp": self.source_timestamp,
            "received_timestamp": self.received_timestamp,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class XioConsumeResult:
    """Conversion result returned after one event enters SessionReplay."""

    application_event: ApplicationEvent
    vj_event: VJEvent
    signal: SignalEnvelope
    record: SessionReplayRecord

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "XioConsumeResult",
            "schema_version": XIO_SCHEMA_VERSION,
            "application_event": self.application_event.to_dict(),
            "vj_event": self.vj_event.to_dict(),
            "signal": self.signal.to_dict(),
            "record": self.record.to_dict(),
        }


class XioEventConsumer:
    """Consume XIO dicts into one proposal-only LUCIDA session replay."""

    def __init__(self, session_id: str, *, first_sequence: int = 1) -> None:
        from ..replay.session import SessionReplay

        self._session_id = _technical_id(session_id, "session_id")
        self._replay = SessionReplay(
            self._session_id,
            first_sequence=first_sequence,
            metadata={"consumer": "xio", "source_app": "XIO"},
        )

    @property
    def state(self):
        return self._replay.state

    def consume(
        self,
        application_event: ApplicationEvent | Mapping[str, Any],
        results: tuple[VJResult | Mapping[str, Any], ...] | list[VJResult | Mapping[str, Any]] = (),
    ) -> XioConsumeResult:
        from ..replay.session import SignalEnvelope

        event = (
            application_event
            if isinstance(application_event, ApplicationEvent)
            else ApplicationEvent.from_dict(application_event)
        )
        if event.session_id != self._session_id:
            raise XioSchemaError(
                f"session_id mismatch: {event.session_id} != {self._session_id}."
        )
        vj_event = self.to_vj_event(event)
        signal = self.to_signal(event)
        record = self._replay.append(
            vj_event,
            signal,
            results,
            metadata=event.trace_metadata(),
        )
        return XioConsumeResult(
            application_event=event,
            vj_event=vj_event,
            signal=signal,
            record=record,
        )

    @staticmethod
    def to_vj_event(event: ApplicationEvent) -> VJEvent:
        phase = XioEventConsumer._phase_for(event)
        event_type = XioEventConsumer._event_type_for(event)
        payload = dict(event.payload)
        payload["xio_provenance"] = event.trace_metadata()
        payload["xio_event_type"] = event.event_type
        payload["xio_channel"] = event.channel
        payload["xio_sequence"] = event.sequence
        return VJEvent(
            event_id=event.event_id,
            timestamp=event.source_timestamp,
            phase=phase,
            event_type=event_type,
            payload=payload,
            source=f"xio:{event.source_app}",
        )

    @staticmethod
    def to_signal(event: ApplicationEvent) -> SignalEnvelope:
        from ..replay.session import SignalEnvelope

        return SignalEnvelope(
            envelope_id=f"xio-{event.event_id}",
            event_id=event.event_id,
            timestamp=event.source_timestamp,
            sequence=event.sequence,
            source=event.source_app,
            address=f"/xio/{event.channel}/{event.event_type}",
            arguments=(event.event_id, event.sequence, event.raw_hash),
            transport="xio",
        )

    def report(self) -> dict[str, Any]:
        report = dict(self._replay.report())
        report["replay_type"] = "XioApplicationReplay"
        report["source_app"] = "XIO"
        return report

    @staticmethod
    def _phase_for(event: ApplicationEvent) -> str:
        candidate = event.payload.get("phase")
        if candidate is not None:
            if not isinstance(candidate, str) or candidate not in _PHASES:
                raise XioMappingError("payload.phase must be a supported VJ phase.")
            return candidate
        phase = _CHANNEL_PHASES.get(event.channel.lower())
        if phase is None:
            raise XioMappingError(f"Cannot map channel to a VJ phase: {event.channel}.")
        return phase

    @staticmethod
    def _event_type_for(event: ApplicationEvent) -> str:
        candidate = event.payload.get("vj_event_type")
        if candidate is not None:
            return _technical_token(candidate, "payload.vj_event_type")
        if event.event_type in _LIFECYCLE_TYPES:
            return event.event_type
        return f"signal.{event.channel.lower()}"


def replay_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(fixture, Mapping):
        raise XioSchemaError("XIO replay fixture must be an object.")
    session_id = _technical_id(fixture.get("session_id"), "session_id")
    raw_events = fixture.get("events")
    raw_results = fixture.get("results", [])
    if not isinstance(raw_events, list) or not raw_events:
        raise XioSchemaError("XIO replay fixture needs non-empty events.")
    if not isinstance(raw_results, list):
        raise XioSchemaError("XIO replay fixture results must be a list.")

    results_by_event: dict[str, list[Mapping[str, Any]]] = {}
    for raw_result in raw_results:
        if not isinstance(raw_result, Mapping):
            raise XioSchemaError("Each XIO result must be an object.")
        event_id = _technical_id(raw_result.get("after_event_id"), "after_event_id")
        results_by_event.setdefault(event_id, []).append(raw_result)

    consumer = XioEventConsumer(session_id)
    seen_event_ids: set[str] = set()
    for raw_event in raw_events:
        event = ApplicationEvent.from_dict(raw_event)
        if event.event_id in seen_event_ids:
            raise DuplicateReplayIdError(f"Duplicate event_id in XIO fixture: {event.event_id}.")
        seen_event_ids.add(event.event_id)
        consumer.consume(event, tuple(results_by_event.get(event.event_id, [])))

    unknown_events = set(results_by_event) - seen_event_ids
    if unknown_events:
        raise XioSchemaError(f"Results reference unknown event ids: {sorted(unknown_events)}")
    return consumer.report()


def replay_path(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path).expanduser().resolve()
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise XioSchemaError(f"XIO replay fixture cannot be read: {fixture_path}") from exc
    return replay_fixture(fixture)

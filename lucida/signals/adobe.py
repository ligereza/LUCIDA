"""Offline Adobe summary-signal consumer for the LUCIDA replay surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from pathlib import Path
import re
from typing import Any, Mapping

from adapters.vj.contracts import VJEvent, VJResult

from ..replay.session import SessionReplay, SessionReplayRecord, SignalEnvelope


ADOBE_SIGNAL_SCHEMA_VERSION = 1
DEFAULT_ADOBE_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "adobe-signal-fictional.json"
)
ADOBE_SOURCES = frozenset({"xio", "vizz", "pupila"})
ADOBE_PHASES = frozenset(
    {"preflight", "preparation", "show", "incident", "recovery", "closure"}
)
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_EVENT_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)+$")
_METADATA_KEYS = frozenset(
    {
        "app",
        "host",
        "channel",
        "action",
        "state",
        "phase",
        "region",
        "mode",
        "status",
        "workflow",
        "eventClass",
        "intent",
        "kind",
        "target",
        "revision",
        "count",
        "participantCount",
        "confidence",
        "focusScore",
        "attentionScore",
        "latencyMs",
        "pointerMode",
        "sourceVersion",
        "transport",
        "protocol",
        "signalPercent",
        "lossPercent",
        "receiveMbps",
        "transmitMbps",
        "radioType",
        "cellChannel",
    }
)
_FORBIDDEN_KEYS = frozenset(
    {
        "command",
        "content",
        "data",
        "executable",
        "file",
        "frame",
        "html",
        "image",
        "key",
        "keys",
        "path",
        "payload",
        "process",
        "raw",
        "script",
        "shell",
        "text",
        "url",
    }
)


class AdobeSignalError(ValueError):
    """Raised when an Adobe bridge signal is unsafe or incomplete."""


def _ascii_text(value: Any, field_name: str, *, max_length: int = 160) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdobeSignalError(f"{field_name} must be non-empty ASCII text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise AdobeSignalError(f"{field_name} must contain ASCII characters only.") from exc
    if len(text) > max_length:
        raise AdobeSignalError(f"{field_name} exceeds the maximum length.")
    return text


def _id(value: Any, field_name: str) -> str:
    text = _ascii_text(value, field_name)
    if not _ID_PATTERN.fullmatch(text):
        raise AdobeSignalError(f"{field_name} contains unsupported characters.")
    return text


def _event_type(value: Any) -> str:
    text = _ascii_text(value, "eventType")
    if not _EVENT_PATTERN.fullmatch(text):
        raise AdobeSignalError("eventType contains unsupported characters.")
    return text


def _timestamp(value: Any, field_name: str) -> str:
    text = _ascii_text(value, field_name, max_length=80)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AdobeSignalError(f"{field_name} is not valid ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise AdobeSignalError(f"{field_name} must include a timezone.")
    return text


def _metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdobeSignalError("metadata must be an object.")
    result: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = _ascii_text(raw_key, "metadata key")
        if key.lower() in _FORBIDDEN_KEYS or key not in _METADATA_KEYS:
            raise AdobeSignalError(f"metadata key is not allowed: {key}.")
        if isinstance(raw_value, bool):
            normalized = raw_value
        elif isinstance(raw_value, int):
            normalized = raw_value
        elif isinstance(raw_value, float):
            if not isfinite(raw_value):
                raise AdobeSignalError(f"metadata.{key} must be finite.")
            normalized = raw_value
        elif isinstance(raw_value, str):
            normalized = _ascii_text(raw_value, f"metadata.{key}", max_length=400)
        else:
            raise AdobeSignalError(f"metadata.{key} must be a scalar.")
        result[key] = normalized
    return result


def _proposal(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise AdobeSignalError("proposal must be an object.")
    if value.get("proposalOnly") is not True:
        raise AdobeSignalError("Adobe proposals must remain proposalOnly.")
    if value.get("requiresConfirmation") is not True:
        raise AdobeSignalError("Adobe proposals must require confirmation.")
    if value.get("reversible") is not True:
        raise AdobeSignalError("Adobe proposals must be reversible.")
    result: dict[str, Any] = {
        "proposalOnly": True,
        "requiresConfirmation": True,
        "reversible": True,
    }
    for key in ("proposalId", "kind", "title", "reason", "target", "expiresAt"):
        if key not in value or value[key] in (None, ""):
            continue
        limit = 400 if key == "reason" else 180
        result[key] = _ascii_text(value[key], f"proposal.{key}", max_length=limit)
    if "expiresAt" in result:
        _timestamp(result["expiresAt"], "proposal.expiresAt")
    return result


@dataclass(frozen=True)
class AdobeSignal:
    """Normalized, summary-only signal emitted by the Adobe bridge."""

    signal_id: str
    source: str
    session_id: str
    sequence: int
    event_type: str
    timestamp: str
    metadata: dict[str, Any]
    proposal: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AdobeSignal":
        if not isinstance(value, Mapping):
            raise AdobeSignalError("Adobe signal must be an object.")
        if value.get("schemaVersion") != ADOBE_SIGNAL_SCHEMA_VERSION:
            raise AdobeSignalError("Unsupported Adobe signal schemaVersion.")
        source = _id(value.get("source"), "source").lower()
        if source not in ADOBE_SOURCES:
            raise AdobeSignalError(f"Unsupported Adobe signal source: {source}.")
        sequence = value.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise AdobeSignalError("sequence must be a non-negative integer.")
        redaction = value.get("redaction")
        if not isinstance(redaction, Mapping) or redaction.get("rawContentForwarded") is not False:
            raise AdobeSignalError("Adobe signal must confirm rawContentForwarded=false.")
        return cls(
            signal_id=_id(value.get("signalId"), "signalId"),
            source=source,
            session_id=_id(value.get("sessionId"), "sessionId"),
            sequence=sequence,
            event_type=_event_type(value.get("eventType")),
            timestamp=_timestamp(value.get("timestamp"), "timestamp"),
            metadata=_metadata(value.get("metadata")),
            proposal=_proposal(value.get("proposal")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": ADOBE_SIGNAL_SCHEMA_VERSION,
            "signalId": self.signal_id,
            "source": self.source,
            "sessionId": self.session_id,
            "sequence": self.sequence,
            "eventType": self.event_type,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
            "proposal": dict(self.proposal) if self.proposal else None,
            "redaction": {"rawContentForwarded": False},
        }

    def to_vj_event(self) -> VJEvent:
        phase = self.metadata.get("phase")
        if not isinstance(phase, str) or phase not in ADOBE_PHASES:
            raise AdobeSignalError(
                "Adobe signal metadata.phase must name an explicit LUCIDA phase."
            )
        payload = {
            "adobe_metadata": dict(self.metadata),
            "adobe_provenance": {
                "signal_id": self.signal_id,
                "source": self.source,
                "sequence": self.sequence,
                "session_id": self.session_id,
                "raw_content_forwarded": False,
            },
        }
        if self.proposal:
            payload["adobe_proposal"] = dict(self.proposal)
        return VJEvent(
            event_id=self.signal_id,
            timestamp=self.timestamp,
            phase=phase,
            event_type=f"signal.adobe.{self.source}.{self.event_type}",
            payload=payload,
            source=f"adobe:{self.source}",
        )

    def to_signal_envelope(self) -> SignalEnvelope:
        return SignalEnvelope(
            envelope_id=f"adobe-{self.signal_id}",
            event_id=self.signal_id,
            timestamp=self.timestamp,
            sequence=self.sequence,
            source=f"adobe:{self.source}",
            address=f"/adobe/{self.source}/{self.event_type}",
            arguments=(self.signal_id, self.sequence),
            transport="adobe",
        )


@dataclass(frozen=True)
class AdobeConsumeResult:
    """Result of one Adobe signal entering proposal-only replay."""

    signal: AdobeSignal
    event: VJEvent
    envelope: SignalEnvelope
    record: SessionReplayRecord

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "AdobeConsumeResult",
            "schema_version": str(ADOBE_SIGNAL_SCHEMA_VERSION),
            "signal": self.signal.to_dict(),
            "event": self.event.to_dict(),
            "envelope": self.envelope.to_dict(),
            "record": self.record.to_dict(),
        }


class AdobeSignalConsumer:
    """Consume Adobe summaries without opening Adobe or executing proposals."""

    def __init__(self, session_id: str, *, first_sequence: int = 0) -> None:
        self._session_id = _id(session_id, "session_id")
        if first_sequence < 0:
            raise AdobeSignalError("first_sequence must be non-negative.")
        self._replay = SessionReplay(
            self._session_id,
            first_sequence=first_sequence,
            metadata={"consumer": "adobe", "source_app": "ADOBE"},
        )

    @property
    def state(self):
        return self._replay.state

    def consume(
        self,
        signal: AdobeSignal | Mapping[str, Any],
        results: tuple[VJResult | Mapping[str, Any], ...]
        | list[VJResult | Mapping[str, Any]] = (),
    ) -> AdobeConsumeResult:
        parsed = signal if isinstance(signal, AdobeSignal) else AdobeSignal.from_dict(signal)
        if parsed.session_id != self._session_id:
            raise AdobeSignalError(
                f"session_id mismatch: {parsed.session_id} != {self._session_id}."
            )
        event = parsed.to_vj_event()
        envelope = parsed.to_signal_envelope()
        record = self._replay.append(event, envelope, results)
        return AdobeConsumeResult(
            signal=parsed,
            event=event,
            envelope=envelope,
            record=record,
        )

    def report(self) -> dict[str, Any]:
        report = dict(self._replay.report())
        report["replay_type"] = "AdobeSummaryReplay"
        report["source_app"] = "ADOBE"
        return report


def parse_adobe_signal(value: Mapping[str, Any]) -> AdobeSignal:
    """Validate one normalized Adobe bridge output."""

    return AdobeSignal.from_dict(value)


def convert_adobe_signal(value: Mapping[str, Any]) -> VJEvent:
    """Convert one validated Adobe summary into a proposal-only VJ event."""

    return AdobeSignal.from_dict(value).to_vj_event()


def consume_adobe_signal(
    consumer: AdobeSignalConsumer,
    value: AdobeSignal | Mapping[str, Any],
    results: tuple[VJResult | Mapping[str, Any], ...]
    | list[VJResult | Mapping[str, Any]] = (),
) -> AdobeConsumeResult:
    """Deliver one Adobe summary to deterministic LUCIDA replay."""

    return consumer.consume(value, results=results)


__all__ = [
    "DEFAULT_ADOBE_FIXTURE",
    "ADOBE_PHASES",
    "ADOBE_SIGNAL_SCHEMA_VERSION",
    "ADOBE_SOURCES",
    "AdobeConsumeResult",
    "AdobeSignal",
    "AdobeSignalConsumer",
    "AdobeSignalError",
    "consume_adobe_signal",
    "convert_adobe_signal",
    "parse_adobe_signal",
]

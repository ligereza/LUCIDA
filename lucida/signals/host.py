"""Host-neutral signal input and explicit outcome contract."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Callable, Mapping

from adapters.vj.contracts import VJEvent, VJResult

from ..replay.session import (
    OutOfOrderReplayError,
    SequenceGapError,
    SessionReplay,
    SessionReplayError,
    SignalEnvelope,
)
from .boundary import (
    OscBoundaryError,
    OscResolumeBoundary,
    UnknownAddressError,
)
from .xio import ApplicationEvent, XioConsumerError, XioEventConsumer


HOST_RESULT_STATUSES = ("accepted", "rejected", "unknown")


class HostContractError(ValueError):
    """Base error for host-neutral result contracts."""


def _ascii_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HostContractError(f"{field_name} must be non-empty ASCII text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise HostContractError(f"{field_name} must contain ASCII characters only.") from exc
    return text


def _timestamp(value: Any, field_name: str) -> str:
    text = _ascii_text(value, field_name)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HostContractError(f"{field_name} is not valid ISO-8601: {text}") from exc
    return text


def _technical_keys(value: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    result = dict(value)
    for key in result:
        _ascii_text(key, f"{field_name} key")
    return result


def _safe_signal_details(value: Any) -> tuple[int | None, str | None, str | None, str | None]:
    if isinstance(value, SignalEnvelope):
        return value.sequence, value.timestamp, value.source, value.event_id
    if isinstance(value, Mapping):
        sequence = value.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            sequence = None
        timestamp = value.get("timestamp") if isinstance(value.get("timestamp"), str) else None
        source = value.get("source") if isinstance(value.get("source"), str) else None
        event_id = value.get("event_id") if isinstance(value.get("event_id"), str) else None
        return sequence, timestamp, source, event_id
    return None, None, None, None


def _safe_xio_details(value: Any) -> tuple[int | None, str | None, str | None, str | None, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None, None, None, None, {}
    sequence = value.get("sequence") if isinstance(value.get("sequence"), int) else None
    timestamp = value.get("source_timestamp") if isinstance(value.get("source_timestamp"), str) else None
    source = value.get("source_app") if isinstance(value.get("source_app"), str) else None
    event_id = value.get("event_id") if isinstance(value.get("event_id"), str) else None
    raw_provenance = value.get("provenance")
    provenance = dict(raw_provenance) if isinstance(raw_provenance, Mapping) else {}
    return sequence, timestamp, source, event_id, provenance


@dataclass(frozen=True)
class HostResult:
    """Explicit host outcome for an accepted, rejected, or unknown signal."""

    status: str
    reason: str
    sequence: int | None
    timestamp: str | None
    source: str | None
    event_id: str | None
    provenance: dict[str, Any] = field(default_factory=dict)
    proposal_ids: tuple[str, ...] = ()
    result_ids: tuple[str, ...] = ()
    overlay: dict[str, Any] = field(default_factory=dict)
    mode: str = "proposal_only"

    def __post_init__(self) -> None:
        if self.status not in HOST_RESULT_STATUSES:
            raise HostContractError(f"Unknown host result status: {self.status}.")
        _ascii_text(self.reason, "reason")
        if self.sequence is not None and (
            isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0
        ):
            raise HostContractError("sequence must be a non-negative integer or null.")
        if self.timestamp is not None:
            _timestamp(self.timestamp, "timestamp")
        for value, field_name in (
            (self.source, "source"),
            (self.event_id, "event_id"),
            (self.mode, "mode"),
        ):
            if value is not None:
                _ascii_text(value, field_name)
        if not isinstance(self.provenance, Mapping):
            raise HostContractError("provenance must be an object.")
        _technical_keys(self.provenance, "provenance")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "HostResult",
            "schema_version": "0.1",
            "status": self.status,
            "reason": self.reason,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "source": self.source,
            "event_id": self.event_id,
            "provenance": dict(self.provenance),
            "proposal_ids": list(self.proposal_ids),
            "result_ids": list(self.result_ids),
            "overlay": dict(self.overlay),
            "mode": self.mode,
        }


class HostSignalBoundary:
    """Receive host-injected signals and publish explicit proposal outcomes."""

    def __init__(self, session_id: str, *, first_sequence: int = 1) -> None:
        self._replay = SessionReplay(session_id, first_sequence=first_sequence)
        self._osc_normalizer = OscResolumeBoundary()

    @property
    def state(self):
        return self._replay.state

    def receive(
        self,
        signal: SignalEnvelope | Mapping[str, Any],
        *,
        event: VJEvent | Mapping[str, Any] | None = None,
        provenance: Mapping[str, Any] | None = None,
        results: tuple[VJResult | Mapping[str, Any], ...] | list[VJResult | Mapping[str, Any]] = (),
    ) -> HostResult:
        sequence, timestamp, source, event_id = _safe_signal_details(signal)
        try:
            parsed_signal = (
                SignalEnvelope.from_dict(signal.to_dict())
                if isinstance(signal, SignalEnvelope)
                else SignalEnvelope.from_dict(signal)
            )
            parsed_provenance = _technical_keys(dict(provenance or {}), "provenance")
            parsed_event = None
            if event is not None:
                parsed_event = event if isinstance(event, VJEvent) else VJEvent.from_dict(event)
            if parsed_event is None:
                if parsed_signal.transport != "osc":
                    return self._unknown(
                        "A canonical VJEvent is required for non-OSC input.",
                        parsed_signal.sequence,
                        parsed_signal.timestamp,
                        parsed_signal.source,
                        parsed_signal.event_id,
                        parsed_provenance,
                    )
                normalized = self._osc_normalizer.normalize(parsed_signal.to_dict())
                parsed_event = replace(normalized, event_id=parsed_signal.event_id)
            record = self._replay.append(
                parsed_event,
                parsed_signal,
                results,
                metadata=parsed_provenance,
            )
            return self._accepted(parsed_signal, record, parsed_provenance)
        except UnknownAddressError as exc:
            return self._unknown(str(exc), sequence, timestamp, source, event_id, provenance)
        except (OscBoundaryError, SessionReplayError, ValueError) as exc:
            return self._rejected(str(exc), sequence, timestamp, source, event_id, provenance)

    def receive_xio(
        self,
        application_event: ApplicationEvent | Mapping[str, Any],
        results: tuple[VJResult | Mapping[str, Any], ...] | list[VJResult | Mapping[str, Any]] = (),
    ) -> HostResult:
        sequence, timestamp, source, event_id, provenance = _safe_xio_details(application_event)
        try:
            parsed = (
                application_event
                if isinstance(application_event, ApplicationEvent)
                else ApplicationEvent.from_dict(application_event)
            )
            if parsed.session_id != self._replay.state.session_id:
                raise HostContractError("session_id does not match host boundary session.")
            return self.receive(
                XioEventConsumer.to_signal(parsed),
                event=XioEventConsumer.to_vj_event(parsed),
                provenance=parsed.trace_metadata(),
                results=results,
            )
        except (XioConsumerError, HostContractError, ValueError) as exc:
            return self._rejected(str(exc), sequence, timestamp, source, event_id, provenance)

    def read_overlay(self) -> dict[str, Any]:
        current = self._replay.state
        pending = [
            proposal.to_dict()
            for record in current.records
            for proposal in record.proposals
            if proposal.proposal_id in current.lucida_state.vj_state.pending_proposal_ids
        ]
        return {
            "surface": "LUCIDA",
            "mode": "read_only",
            "state": current.lucida_state.to_dict(),
            "pending_proposals": pending,
            "safety": {
                "sockets_opened": False,
                "resolume_opened": False,
                "automatic_actions": False,
                "external_side_effects": False,
            },
        }

    def report(self) -> dict[str, Any]:
        return self._replay.report()

    def _accepted(
        self,
        signal: SignalEnvelope,
        record,
        provenance: Mapping[str, Any],
    ) -> HostResult:
        return HostResult(
            status="accepted",
            reason="Signal accepted into SessionReplay; no action executed.",
            sequence=signal.sequence,
            timestamp=signal.timestamp,
            source=signal.source,
            event_id=signal.event_id,
            provenance=dict(provenance),
            proposal_ids=tuple(proposal.proposal_id for proposal in record.proposals),
            result_ids=tuple(result.result_id for result in record.results),
            overlay=self.read_overlay(),
        )

    def _rejected(
        self,
        reason: str,
        sequence: int | None,
        timestamp: str | None,
        source: str | None,
        event_id: str | None,
        provenance: Mapping[str, Any] | None,
    ) -> HostResult:
        return HostResult(
            status="rejected",
            reason=_ascii_reason(reason),
            sequence=sequence,
            timestamp=_safe_timestamp(timestamp),
            source=_safe_ascii(source),
            event_id=_safe_ascii(event_id),
            provenance=_safe_provenance(provenance),
            overlay=self.read_overlay(),
        )

    def _unknown(
        self,
        reason: str,
        sequence: int | None,
        timestamp: str | None,
        source: str | None,
        event_id: str | None,
        provenance: Mapping[str, Any] | None,
    ) -> HostResult:
        return HostResult(
            status="unknown",
            reason=_ascii_reason(reason),
            sequence=sequence,
            timestamp=_safe_timestamp(timestamp),
            source=_safe_ascii(source),
            event_id=_safe_ascii(event_id),
            provenance=_safe_provenance(provenance),
            overlay=self.read_overlay(),
        )


def _ascii_reason(value: Any) -> str:
    text = str(value).strip() or "Host input could not be classified."
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return "Host input failed technical validation."
    return text


def _safe_ascii(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return _ascii_text(value, "value")
    except HostContractError:
        return None


def _safe_timestamp(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return _timestamp(value, "timestamp")
    except HostContractError:
        return None


def _safe_provenance(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    try:
        return _technical_keys(value, "provenance")
    except HostContractError:
        return {}

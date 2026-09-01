"""Auditable, deterministic session replay for VJ events and signal envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from adapters.vj.contracts import VJEvent, VJProposal, VJResult

from ..contracts import LUCIDA_SCHEMA_VERSION, LucidaState
from ..orchestrator import LucidaOrchestrator
from ..signals.boundary import OscEnvelope


class SessionReplayError(ValueError):
    """Base error for session replay contract violations."""


class SequenceGapError(SessionReplayError):
    """Raised when a sequence skips one or more expected values."""


class DuplicateReplayIdError(SessionReplayError):
    """Raised when an event, signal, or sequence is repeated."""


class OutOfOrderReplayError(SessionReplayError):
    """Raised when sequence or timestamps move backwards."""


class EventSignalMismatchError(SessionReplayError):
    """Raised when an event and signal envelope cannot be paired."""


def _ascii_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SessionReplayError(f"{field_name} must be non-empty ASCII text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise SessionReplayError(f"{field_name} must contain ASCII characters only.") from exc
    return text


def _time_value(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _assert_event_technical_fields(event: VJEvent) -> None:
    _ascii_text(event.event_id, "event_id")
    _ascii_text(event.timestamp, "timestamp")
    _ascii_text(event.phase, "phase")
    _ascii_text(event.event_type, "event_type")
    _ascii_text(event.source, "source")


@dataclass(frozen=True)
class SignalEnvelope:
    """Signal provenance paired with one normalized VJ event."""

    envelope_id: str
    event_id: str
    timestamp: str
    sequence: int
    source: str
    address: str
    arguments: tuple[Any, ...] = ()
    transport: str = "osc"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SignalEnvelope":
        if not isinstance(value, Mapping):
            raise SessionReplayError("signal envelope must be an object.")
        osc = OscEnvelope.from_dict(value)
        envelope_id = _ascii_text(value.get("envelope_id"), "envelope_id")
        event_id = _ascii_text(value.get("event_id"), "event_id")
        transport = value.get("transport", "osc")
        if transport not in {"osc", "xio"}:
            raise SessionReplayError("transport must be osc or xio.")
        return cls(
            envelope_id=envelope_id,
            event_id=event_id,
            timestamp=osc.timestamp,
            sequence=osc.sequence,
            source=osc.source,
            address=osc.address,
            arguments=osc.arguments,
            transport=transport,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "SignalEnvelope",
            "schema_version": LUCIDA_SCHEMA_VERSION,
            "envelope_id": self.envelope_id,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "source": self.source,
            "address": self.address,
            "arguments": list(self.arguments),
            "transport": self.transport,
        }


@dataclass(frozen=True)
class SessionReplayRecord:
    """One immutable replay unit with normalized proposals and outcomes."""

    event: VJEvent
    signal: SignalEnvelope
    proposals: tuple[VJProposal, ...]
    results: tuple[VJResult, ...]
    state_after: LucidaState
    audit: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "SessionReplayRecord",
            "schema_version": LUCIDA_SCHEMA_VERSION,
            "event": self.event.to_dict(),
            "signal": self.signal.to_dict(),
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "results": [result.to_dict() for result in self.results],
            "state_after": self.state_after.to_dict(),
            "audit": dict(self.audit),
        }


@dataclass(frozen=True)
class SessionReplayState:
    """Persistable state for a deterministic replay stream."""

    session_id: str
    lucida_state: LucidaState
    next_sequence: int = 1
    last_timestamp: str | None = None
    seen_event_ids: tuple[str, ...] = ()
    seen_envelope_ids: tuple[str, ...] = ()
    seen_sequences: tuple[int, ...] = ()
    records: tuple[SessionReplayRecord, ...] = ()
    audit_log: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "SessionReplayState",
            "schema_version": LUCIDA_SCHEMA_VERSION,
            "session_id": self.session_id,
            "next_sequence": self.next_sequence,
            "last_timestamp": self.last_timestamp,
            "seen_event_ids": list(self.seen_event_ids),
            "seen_envelope_ids": list(self.seen_envelope_ids),
            "seen_sequences": list(self.seen_sequences),
            "records": [record.to_dict() for record in self.records],
            "audit_log": [dict(item) for item in self.audit_log],
            "lucida_state": self.lucida_state.to_dict(),
            "metadata": dict(self.metadata),
        }


class SessionReplay:
    """Append-only replay that never opens a transport or executes actions."""

    def __init__(
        self,
        session_id: str,
        *,
        first_sequence: int = 1,
        metadata: Mapping[str, Any] | None = None,
        orchestrator: LucidaOrchestrator | None = None,
    ) -> None:
        if isinstance(first_sequence, bool) or not isinstance(first_sequence, int) or first_sequence < 0:
            raise SessionReplayError("first_sequence must be a non-negative integer.")
        self._orchestrator = orchestrator or LucidaOrchestrator()
        lucida_state = self._orchestrator.initial_state(session_id, metadata=metadata)
        self._state = SessionReplayState(
            session_id=lucida_state.session_id,
            lucida_state=lucida_state,
            next_sequence=first_sequence,
            metadata=dict(metadata or {}),
        )

    @property
    def state(self) -> SessionReplayState:
        return self._state

    def append(
        self,
        event: VJEvent | Mapping[str, Any],
        signal: SignalEnvelope | Mapping[str, Any],
        results: tuple[VJResult | Mapping[str, Any], ...] | list[VJResult | Mapping[str, Any]] = (),
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> SessionReplayRecord:
        parsed_event = event if isinstance(event, VJEvent) else VJEvent.from_dict(event)
        parsed_signal = signal if isinstance(signal, SignalEnvelope) else SignalEnvelope.from_dict(signal)
        _assert_event_technical_fields(parsed_event)
        self._validate_pair(parsed_event, parsed_signal)
        self._validate_order(parsed_event, parsed_signal)

        next_lucida_state = self._orchestrator.propose(parsed_event, self._state.lucida_state)
        proposals = tuple(
            proposal for proposal in next_lucida_state.proposals if proposal.event_id == parsed_event.event_id
        )
        if any(
            not proposal.requires_explicit_approval
            or not proposal.reversible
            or proposal.execution_mode != "proposal_only"
            for proposal in proposals
        ):
            raise SessionReplayError("Replay proposals must be explicit, reversible, and proposal_only.")

        parsed_results: list[VJResult] = []
        for raw_result in results:
            result = raw_result if isinstance(raw_result, VJResult) else VJResult.from_dict(raw_result)
            if _time_value(result.recorded_at) < _time_value(parsed_signal.timestamp):
                raise OutOfOrderReplayError(
                    f"Result timestamp precedes signal: {result.result_id}."
                )
            next_lucida_state = self._orchestrator.register_result(next_lucida_state, result)
            parsed_results.append(result)

        audit = {
            "audit_id": f"audit-{parsed_signal.envelope_id}",
            "event_id": parsed_event.event_id,
            "envelope_id": parsed_signal.envelope_id,
            "timestamp": parsed_signal.timestamp,
            "sequence": parsed_signal.sequence,
            "source": parsed_signal.source,
            "event_source": parsed_event.source,
            "metadata": dict(metadata or {}),
            "proposal_ids": [proposal.proposal_id for proposal in proposals],
            "result_ids": [result.result_id for result in parsed_results],
            "mode": "proposal_only",
            "external_side_effects": False,
        }
        record = SessionReplayRecord(
            event=parsed_event,
            signal=parsed_signal,
            proposals=proposals,
            results=tuple(parsed_results),
            state_after=next_lucida_state,
            audit=audit,
        )
        self._state = replace(
            self._state,
            lucida_state=next_lucida_state,
            next_sequence=parsed_signal.sequence + 1,
            last_timestamp=parsed_signal.timestamp,
            seen_event_ids=(*self._state.seen_event_ids, parsed_event.event_id),
            seen_envelope_ids=(*self._state.seen_envelope_ids, parsed_signal.envelope_id),
            seen_sequences=(*self._state.seen_sequences, parsed_signal.sequence),
            records=(*self._state.records, record),
            audit_log=(*self._state.audit_log, audit),
        )
        return record

    def report(self) -> dict[str, Any]:
        final_state = self._state.to_dict()
        active_capabilities = sorted(
            {
                report.capability
                for record in self._state.records
                for report in record.state_after.capabilities
                if report.proposals
            }
        )
        complete = (
            final_state["lucida_state"]["vj_state"]["phase"] == "closure"
            and final_state["lucida_state"]["vj_state"]["status"] == "closed"
            and not final_state["lucida_state"]["pending_proposal_ids"]
            and active_capabilities == ["IMAGO", "INSTAR", "NAYADE"]
        )
        return {
            "contract_type": "LucidaSessionReplayReport",
            "schema_version": LUCIDA_SCHEMA_VERSION,
            "session_id": self._state.session_id,
            "status": "PASS" if complete else "REVIEW",
            "event_count": len(self._state.records),
            "signal_count": len(self._state.records),
            "proposal_count": sum(len(record.proposals) for record in self._state.records),
            "result_count": sum(len(record.results) for record in self._state.records),
            "capabilities_observed": active_capabilities,
            "records": [record.to_dict() for record in self._state.records],
            "audit_log": [dict(item) for item in self._state.audit_log],
            "final_state": final_state,
            "safety": {
                "replay_only": True,
                "proposal_only": True,
                "sockets_opened": False,
                "resolume_opened": False,
                "external_side_effects": False,
            },
        }

    def _validate_pair(self, event: VJEvent, signal: SignalEnvelope) -> None:
        if event.event_id != signal.event_id:
            raise EventSignalMismatchError(
                f"Event and signal ids differ: {event.event_id} != {signal.event_id}."
            )
        if event.timestamp != signal.timestamp:
            raise EventSignalMismatchError(
                f"Event and signal timestamps differ: {event.event_id}."
            )
        if event.event_id in self._state.seen_event_ids:
            raise DuplicateReplayIdError(f"Duplicate event_id: {event.event_id}.")
        if signal.envelope_id in self._state.seen_envelope_ids:
            raise DuplicateReplayIdError(f"Duplicate envelope_id: {signal.envelope_id}.")
        if signal.sequence in self._state.seen_sequences:
            raise DuplicateReplayIdError(f"Duplicate sequence: {signal.sequence}.")

    def _validate_order(self, event: VJEvent, signal: SignalEnvelope) -> None:
        if signal.sequence > self._state.next_sequence:
            raise SequenceGapError(
                f"Sequence gap: expected {self._state.next_sequence}, got {signal.sequence}."
            )
        if signal.sequence < self._state.next_sequence:
            raise OutOfOrderReplayError(
                f"Sequence out of order: expected {self._state.next_sequence}, got {signal.sequence}."
            )
        if self._state.last_timestamp is not None and _time_value(event.timestamp) < _time_value(
            self._state.last_timestamp
        ):
            raise OutOfOrderReplayError(f"Timestamp out of order: {event.event_id}.")


def replay_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(fixture, Mapping):
        raise SessionReplayError("Session replay fixture must be an object.")
    session_id = fixture.get("session_id")
    entries = fixture.get("entries")
    if not isinstance(session_id, str) or not session_id.strip():
        raise SessionReplayError("Session replay fixture needs session_id.")
    if not isinstance(entries, list) or not entries:
        raise SessionReplayError("Session replay fixture needs non-empty entries.")

    replay = SessionReplay(session_id, metadata={"fixture": True})
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise SessionReplayError("Each replay entry must be an object.")
        raw_event = entry.get("event")
        raw_signal = entry.get("signal")
        raw_results = entry.get("results", [])
        if not isinstance(raw_event, Mapping) or not isinstance(raw_signal, Mapping):
            raise SessionReplayError("Each replay entry needs event and signal.")
        if not isinstance(raw_results, list):
            raise SessionReplayError("Replay entry results must be a list.")
        replay.append(raw_event, raw_signal, tuple(raw_results))
    return replay.report()

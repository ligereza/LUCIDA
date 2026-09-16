"""Pure OSC/Resolume boundary with injected transport and sender."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from math import isfinite
import re
from typing import Any, Callable, Mapping

from adapters.vj.contracts import VJEvent, VJProposal, VJResult

from ..contracts import LUCIDA_SCHEMA_VERSION, LucidaState
from ..orchestrator import LucidaOrchestrator


OSC_SCHEMA_VERSION = "0.1"
_ADDRESS_PART = re.compile(r"^[A-Za-z0-9._-]+$")
_SOURCE = re.compile(r"^[A-Za-z0-9_.-]+$")


class OscBoundaryError(ValueError):
    """Base error for the injected OSC/Resolume boundary."""


class EnvelopeValidationError(OscBoundaryError):
    """Raised when an injected envelope is malformed."""


class UnknownAddressError(OscBoundaryError):
    """Raised when an OSC address is outside the supported boundary."""


class SequenceOrderError(OscBoundaryError):
    """Raised when a signal sequence is not strictly increasing."""


class DuplicateEnvelopeError(OscBoundaryError):
    """Raised when an already received sequence is injected again."""


class OutgoingSenderError(OscBoundaryError):
    """Raised when an explicitly injected sender cannot publish a message."""


def _ascii_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EnvelopeValidationError(f"{field_name} must be non-empty ASCII text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise EnvelopeValidationError(f"{field_name} must contain ASCII characters only.") from exc
    return text


def _timestamp(value: Any) -> str:
    text = _ascii_text(value, "timestamp")
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EnvelopeValidationError(f"timestamp is not valid ISO-8601: {text}") from exc
    return text


def _arguments(value: Any) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise EnvelopeValidationError("arguments must be a list or tuple.")
    normalized: list[Any] = []
    for index, argument in enumerate(value):
        if argument is None or isinstance(argument, (bool, int)):
            normalized.append(argument)
            continue
        if isinstance(argument, float):
            if not isfinite(argument):
                raise EnvelopeValidationError(f"arguments[{index}] must be finite.")
            normalized.append(argument)
            continue
        if isinstance(argument, str):
            normalized.append(_ascii_text(argument, f"arguments[{index}]"))
            continue
        raise EnvelopeValidationError(
            f"arguments[{index}] has unsupported type: {type(argument).__name__}."
        )
    return tuple(normalized)


def _address(value: Any) -> str:
    text = _ascii_text(value, "address")
    if not text.startswith("/") or "//" in text:
        raise EnvelopeValidationError("address must be an OSC path without empty segments.")
    parts = text[1:].split("/")
    if not parts or any(not _ADDRESS_PART.fullmatch(part) for part in parts):
        raise EnvelopeValidationError("address contains an invalid OSC path segment.")
    return text


def _sequence(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EnvelopeValidationError("sequence must be a non-negative integer.")
    return value


@dataclass(frozen=True)
class OscEnvelope:
    """Validated OSC-like data injected by a host or test harness."""

    address: str
    arguments: tuple[Any, ...]
    timestamp: str
    sequence: int
    source: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OscEnvelope":
        if not isinstance(value, Mapping):
            raise EnvelopeValidationError("OSC envelope must be an object.")
        source = _ascii_text(value.get("source"), "source")
        if not _SOURCE.fullmatch(source):
            raise EnvelopeValidationError("source contains unsupported characters.")
        return cls(
            address=_address(value.get("address")),
            arguments=_arguments(value.get("arguments", [])),
            timestamp=_timestamp(value.get("timestamp")),
            sequence=_sequence(value.get("sequence")),
            source=source,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "OscEnvelope",
            "schema_version": OSC_SCHEMA_VERSION,
            "address": self.address,
            "arguments": list(self.arguments),
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "source": self.source,
        }


@dataclass(frozen=True)
class OscBridgeState:
    """Boundary state plus the single LUCIDA state surface."""

    lucida_state: LucidaState
    last_sequence: int | None = None
    seen_sequences: tuple[int, ...] = ()
    received_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OscBridgeState":
        if not isinstance(value, Mapping):
            raise EnvelopeValidationError("OSC bridge state must be an object.")
        raw_state = value.get("lucida_state")
        if not isinstance(raw_state, Mapping):
            raise EnvelopeValidationError("OSC bridge state needs lucida_state.")
        raw_seen = value.get("seen_sequences", ())
        if not isinstance(raw_seen, (list, tuple)) or not all(
            isinstance(item, int) and not isinstance(item, bool) and item >= 0 for item in raw_seen
        ):
            raise EnvelopeValidationError("seen_sequences must contain non-negative integers.")
        last_sequence = value.get("last_sequence")
        if last_sequence is not None:
            last_sequence = _sequence(last_sequence)
            if raw_seen and raw_seen[-1] != last_sequence:
                raise EnvelopeValidationError("last_sequence must match the last seen sequence.")
        raw_metadata = value.get("metadata")
        if raw_metadata is not None and not isinstance(raw_metadata, Mapping):
            raise EnvelopeValidationError("metadata must be an object.")
        return cls(
            lucida_state=LucidaState.from_dict(raw_state),
            last_sequence=last_sequence,
            seen_sequences=tuple(raw_seen),
            received_count=int(value.get("received_count", 0)),
            metadata=dict(raw_metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "OscBridgeState",
            "schema_version": OSC_SCHEMA_VERSION,
            "lucida_state": self.lucida_state.to_dict(),
            "last_sequence": self.last_sequence,
            "seen_sequences": list(self.seen_sequences),
            "received_count": self.received_count,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SignalReceive:
    """Result of one injected signal, including optional proposal notice."""

    envelope: OscEnvelope
    event: VJEvent
    state: OscBridgeState
    overlay: dict[str, Any]
    proposals: tuple[VJProposal, ...]
    outgoing_message: dict[str, Any] | None = None
    sender_called: bool = False
    recorded_result: VJResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "SignalReceive",
            "schema_version": OSC_SCHEMA_VERSION,
            "envelope": self.envelope.to_dict(),
            "event": self.event.to_dict(),
            "state": self.state.to_dict(),
            "overlay": self.overlay,
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "outgoing_message": self.outgoing_message,
            "sender_called": self.sender_called,
            "recorded_result": self.recorded_result.to_dict() if self.recorded_result else None,
        }


class OscResolumeBoundary:
    """Normalize injected OSC/Resolume messages without opening a socket."""

    def __init__(self, orchestrator: LucidaOrchestrator | None = None) -> None:
        self._orchestrator = orchestrator or LucidaOrchestrator()

    def initial_state(
        self,
        session_id: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> OscBridgeState:
        return OscBridgeState(
            lucida_state=self._orchestrator.initial_state(session_id, metadata=metadata),
            metadata=dict(metadata or {}),
        )

    def receive(
        self,
        envelope: OscEnvelope | Mapping[str, Any],
        state: OscBridgeState | Mapping[str, Any],
        sender: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> SignalReceive:
        parsed = envelope if isinstance(envelope, OscEnvelope) else OscEnvelope.from_dict(envelope)
        current = state if isinstance(state, OscBridgeState) else OscBridgeState.from_dict(state)
        self._validate_sequence(parsed, current)
        event = self.normalize(parsed)
        lucida_state = self._orchestrator.propose(event, current.lucida_state)
        next_state = replace(
            current,
            lucida_state=lucida_state,
            last_sequence=parsed.sequence,
            seen_sequences=(*current.seen_sequences, parsed.sequence),
            received_count=current.received_count + 1,
        )
        proposals = tuple(
            proposal for proposal in lucida_state.proposals if proposal.event_id == event.event_id
        )
        outgoing = self._proposal_message(parsed, event, proposals)
        sender_called = False
        if sender is not None:
            if not callable(sender):
                raise OutgoingSenderError("sender must be callable when provided.")
            try:
                sender(dict(outgoing))
            except Exception as exc:
                raise OutgoingSenderError("Injected sender failed to publish the message.") from exc
            sender_called = True
        return SignalReceive(
            envelope=parsed,
            event=event,
            state=next_state,
            overlay=self.read_overlay(next_state),
            proposals=proposals,
            outgoing_message=outgoing,
            sender_called=sender_called,
        )

    def normalize(self, envelope: OscEnvelope | Mapping[str, Any]) -> VJEvent:
        parsed = envelope if isinstance(envelope, OscEnvelope) else OscEnvelope.from_dict(envelope)
        capability, phase = self._route(parsed.address)
        event_type = self._event_type(parsed.address, capability, phase)
        return VJEvent(
            event_id=f"osc-{parsed.source}-{parsed.sequence:06d}",
            timestamp=parsed.timestamp,
            phase=phase,
            event_type=event_type,
            payload={
                "transport": "osc",
                "address": parsed.address,
                "arguments": list(parsed.arguments),
                "sequence": parsed.sequence,
                "route": capability.lower(),
            },
            source=f"osc:{parsed.source}",
        )

    def register_result(
        self,
        state: OscBridgeState | Mapping[str, Any],
        result: VJResult | Mapping[str, Any],
    ) -> OscBridgeState:
        current = state if isinstance(state, OscBridgeState) else OscBridgeState.from_dict(state)
        return replace(
            current,
            lucida_state=self._orchestrator.register_result(current.lucida_state, result),
        )

    def read_overlay(self, state: OscBridgeState | Mapping[str, Any]) -> dict[str, Any]:
        current = state if isinstance(state, OscBridgeState) else OscBridgeState.from_dict(state)
        overlay = dict(self._orchestrator.read_overlay(current.lucida_state))
        overlay["signal_boundary"] = {
            "contract_type": "OscBridgeState",
            "schema_version": OSC_SCHEMA_VERSION,
            "last_sequence": current.last_sequence,
            "received_count": current.received_count,
        }
        return overlay

    @staticmethod
    def _validate_sequence(envelope: OscEnvelope, state: OscBridgeState) -> None:
        if envelope.sequence in state.seen_sequences:
            raise DuplicateEnvelopeError(f"Duplicate sequence: {envelope.sequence}.")
        if state.last_sequence is not None and envelope.sequence <= state.last_sequence:
            raise SequenceOrderError(
                f"Sequence must increase: {envelope.sequence} after {state.last_sequence}."
            )

    @staticmethod
    def _route(address: str) -> tuple[str, str]:
        parts = address[1:].split("/")
        if parts[0] == "composition":
            return "IMAGO", "show"
        if parts[0] != "lucida" or len(parts) < 3:
            raise UnknownAddressError(f"Unknown OSC address: {address}.")
        capability = parts[1].lower()
        if capability == "instar":
            return "INSTAR", "preflight"
        if capability == "nayade":
            return "NAYADE", "preparation"
        if capability == "imago":
            phase = {
                "incident": "incident",
                "recovery": "recovery",
                "closed": "closure",
                "closure": "closure",
            }.get(parts[2].lower(), "show")
            return "IMAGO", phase
        raise UnknownAddressError(f"Unknown OSC address: {address}.")

    @staticmethod
    def _event_type(address: str, capability: str, phase: str) -> str:
        token = address.rstrip("/").split("/")[-1].lower()
        if token in {"closed", "close"}:
            return "show.closed"
        if token in {"completed", "complete", "done"}:
            return "phase.completed"
        if phase == "incident":
            return "incident.detected"
        if phase == "recovery":
            return "recovery.started"
        if phase == "show" and address.startswith("/composition/"):
            return "show.started"
        return f"signal.{capability.lower()}"

    @staticmethod
    def _proposal_message(
        envelope: OscEnvelope,
        event: VJEvent,
        proposals: tuple[VJProposal, ...],
    ) -> dict[str, Any]:
        return {
            "address": "/lucida/proposal",
            "arguments": [event.event_id, *[proposal.proposal_id for proposal in proposals]],
            "timestamp": envelope.timestamp,
            "sequence": envelope.sequence,
            "source": "lucida",
            "message_type": "proposal_notice",
            "schema_version": LUCIDA_SCHEMA_VERSION,
        }

"""Proposal-only bridge from RESOLUME_ADAPTER VJ project events into LUCIDA replay."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from adapters.vj.contracts import VJEvent, VJResult

from ..replay.session import SessionReplay, SessionReplayRecord, SignalEnvelope


RESOLUME_ADAPTER_SOURCES = frozenset({"INSTAR", "NAYADE", "IMAGO"})


class ResolumeAdapterBridgeError(ValueError):
    """Raised when a RESOLUME_ADAPTER event cannot cross the LUCIDA boundary."""


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or not value.isascii():
        raise ResolumeAdapterBridgeError(f"{field_name} must be non-empty ASCII text.")
    return value.strip()


def _sequence(event: VJEvent) -> int:
    value = event.payload.get("sequence")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResolumeAdapterBridgeError("RESOLUME_ADAPTER event payload.sequence must be a positive integer.")
    return value


def parse_resolume_adapter_event(value: Mapping[str, Any]) -> VJEvent:
    """Validate one canonical event emitted by RESOLUME_ADAPTER's ``vj-project`` bridge."""

    try:
        event = VJEvent.from_dict(value)
    except (TypeError, ValueError) as exc:
        raise ResolumeAdapterBridgeError(str(exc)) from exc
    if event.source not in RESOLUME_ADAPTER_SOURCES:
        raise ResolumeAdapterBridgeError(
            f"RESOLUME_ADAPTER event source must be one of {sorted(RESOLUME_ADAPTER_SOURCES)}."
        )
    _identifier(event.event_id, "event_id")
    _sequence(event)
    return event


def _signal(event: VJEvent) -> SignalEnvelope:
    sequence = _sequence(event)
    source = event.source.lower()
    return SignalEnvelope(
        envelope_id=f"resolume_adapter-{event.event_id}",
        event_id=event.event_id,
        timestamp=event.timestamp,
        sequence=sequence,
        source=f"resolume_adapter:{source}",
        address=f"/resolume_adapter/{source}/{event.event_type}",
        arguments=(event.event_id, event.phase, event.event_type),
        transport="resolume_adapter",
    )


@dataclass(frozen=True)
class ResolumeAdapterConsumeResult:
    """One RESOLUME_ADAPTER event and its auditable LUCIDA replay record."""

    event: VJEvent
    signal: SignalEnvelope
    record: SessionReplayRecord

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "ResolumeAdapterConsumeResult",
            "schema_version": "0.1",
            "event": self.event.to_dict(),
            "signal": self.signal.to_dict(),
            "record": self.record.to_dict(),
        }


class ResolumeAdapterEventConsumer:
    """Consume RESOLUME_ADAPTER project events without controlling the liveshow host."""

    def __init__(self, session_id: str, *, first_sequence: int = 1) -> None:
        self._replay = SessionReplay(
            _identifier(session_id, "session_id"),
            first_sequence=first_sequence,
            metadata={"consumer": "resolume_adapter", "source_app": "RESOLUME_ADAPTER"},
        )

    @property
    def state(self):
        return self._replay.state

    def consume(
        self,
        event: VJEvent | Mapping[str, Any],
        results: tuple[VJResult | Mapping[str, Any], ...] | list[VJResult | Mapping[str, Any]] = (),
    ) -> ResolumeAdapterConsumeResult:
        parsed = parse_resolume_adapter_event(event.to_dict() if isinstance(event, VJEvent) else event)
        signal = _signal(parsed)
        record = self._replay.append(parsed, signal, results, metadata={
            "source_app": "RESOLUME_ADAPTER",
            "source": parsed.source,
            "event_type": parsed.event_type,
            "phase": parsed.phase,
        })
        return ResolumeAdapterConsumeResult(event=parsed, signal=signal, record=record)

    def report(self) -> dict[str, Any]:
        report = dict(self._replay.report())
        report["replay_type"] = "ResolumeAdapterProjectReplay"
        report["source_app"] = "RESOLUME_ADAPTER"
        return report


def replay_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Replay a RESOLUME_ADAPTER export containing ``session_id`` and canonical events."""

    if not isinstance(fixture, Mapping):
        raise ResolumeAdapterBridgeError("RESOLUME_ADAPTER replay fixture must be an object.")
    session_id = _identifier(fixture.get("session_id"), "session_id")
    events = fixture.get("events")
    results = fixture.get("results", [])
    if not isinstance(events, list) or not events:
        raise ResolumeAdapterBridgeError("RESOLUME_ADAPTER replay fixture needs non-empty events.")
    if not isinstance(results, list):
        raise ResolumeAdapterBridgeError("RESOLUME_ADAPTER replay fixture results must be a list.")

    by_event: dict[str, list[Mapping[str, Any]]] = {}
    for result in results:
        if not isinstance(result, Mapping):
            raise ResolumeAdapterBridgeError("Each RESOLUME_ADAPTER result must be an object.")
        event_id = _identifier(result.get("after_event_id"), "after_event_id")
        by_event.setdefault(event_id, []).append(result)

    consumer = ResolumeAdapterEventConsumer(session_id)
    seen: set[str] = set()
    for raw_event in events:
        parsed = parse_resolume_adapter_event(raw_event)
        if parsed.event_id in seen:
            raise ResolumeAdapterBridgeError(f"Duplicate RESOLUME_ADAPTER event_id: {parsed.event_id}.")
        seen.add(parsed.event_id)
        consumer.consume(parsed, tuple(by_event.get(parsed.event_id, [])))

    unknown = set(by_event) - seen
    if unknown:
        raise ResolumeAdapterBridgeError(f"Results reference unknown event ids: {sorted(unknown)}")
    return consumer.report()


def replay_path(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path).expanduser().resolve()
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResolumeAdapterBridgeError(f"RESOLUME_ADAPTER replay fixture cannot be read: {fixture_path}") from exc
    return replay_fixture(fixture)


__all__ = [
    "RESOLUME_ADAPTER_SOURCES",
    "ResolumeAdapterBridgeError",
    "ResolumeAdapterConsumeResult",
    "ResolumeAdapterEventConsumer",
    "parse_resolume_adapter_event",
    "replay_fixture",
    "replay_path",
]

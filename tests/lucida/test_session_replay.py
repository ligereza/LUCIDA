import json
from pathlib import Path

import pytest

from adapters.vj.contracts import VJEvent
from lucida.replay.session import (
    DuplicateReplayIdError,
    OutOfOrderReplayError,
    SequenceGapError,
    SessionReplay,
    replay_fixture,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "lucida"
    / "replay"
    / "fixtures"
    / "session-signal-fictional.json"
)


def _event(event_id: str, timestamp: str, sequence: int) -> dict:
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "phase": "preflight",
        "event_type": "signal.instar",
        "payload": {"sequence": sequence},
        "source": "osc:test",
    }


def _signal(event_id: str, envelope_id: str, timestamp: str, sequence: int) -> dict:
    return {
        "envelope_id": envelope_id,
        "event_id": event_id,
        "timestamp": timestamp,
        "sequence": sequence,
        "source": "test",
        "address": "/lucida/instar/preflight",
        "arguments": ["ready"],
        "transport": "osc",
    }


def test_replay_preserves_provenance_and_normalizes_three_capabilities():
    report = replay_fixture(json.loads(FIXTURE.read_text(encoding="utf-8")))

    assert report["status"] == "PASS"
    assert report["event_count"] == 6
    assert report["signal_count"] == 6
    assert report["proposal_count"] == 10
    assert report["result_count"] == 10
    assert report["capabilities_observed"] == ["IMAGO", "INSTAR", "NAYADE"]
    assert report["final_state"]["lucida_state"]["pending_proposal_ids"] == []
    assert report["safety"] == {
        "replay_only": True,
        "proposal_only": True,
        "sockets_opened": False,
        "resolume_opened": False,
        "external_side_effects": False,
    }

    first = report["records"][0]
    assert first["event"]["event_id"] == "evt-001"
    assert first["signal"]["envelope_id"] == "sig-001"
    assert first["signal"]["sequence"] == 1
    assert first["signal"]["timestamp"] == first["event"]["timestamp"]
    assert first["signal"]["source"] == "fixture"
    assert first["event"]["source"] == "osc:fixture"
    assert first["audit"]["mode"] == "proposal_only"


def test_sequence_gap_is_rejected_without_mutating_replay():
    replay = SessionReplay("session-001")
    replay.append(_event("evt-001", "2026-01-10T20:00:00Z", 1), _signal("evt-001", "sig-001", "2026-01-10T20:00:00Z", 1))

    with pytest.raises(SequenceGapError, match="Sequence gap"):
        replay.append(_event("evt-003", "2026-01-10T20:00:02Z", 3), _signal("evt-003", "sig-003", "2026-01-10T20:00:02Z", 3))

    assert replay.state.next_sequence == 2
    assert len(replay.state.records) == 1


def test_duplicate_event_and_signal_ids_are_rejected():
    replay = SessionReplay("session-001")
    replay.append(_event("evt-001", "2026-01-10T20:00:00Z", 1), _signal("evt-001", "sig-001", "2026-01-10T20:00:00Z", 1))

    with pytest.raises(DuplicateReplayIdError, match="Duplicate event_id"):
        replay.append(_event("evt-001", "2026-01-10T20:00:01Z", 2), _signal("evt-001", "sig-002", "2026-01-10T20:00:01Z", 2))

    with pytest.raises(DuplicateReplayIdError, match="Duplicate envelope_id"):
        replay.append(_event("evt-002", "2026-01-10T20:00:01Z", 2), _signal("evt-002", "sig-001", "2026-01-10T20:00:01Z", 2))


def test_out_of_order_sequence_and_timestamp_are_rejected():
    replay = SessionReplay("session-001")
    replay.append(_event("evt-001", "2026-01-10T20:00:00Z", 1), _signal("evt-001", "sig-001", "2026-01-10T20:00:00Z", 1))

    with pytest.raises(OutOfOrderReplayError, match="Sequence out of order"):
        replay.append(_event("evt-000", "2026-01-10T19:59:00Z", 0), _signal("evt-000", "sig-000", "2026-01-10T19:59:00Z", 0))

    with pytest.raises(OutOfOrderReplayError, match="Timestamp out of order"):
        replay.append(_event("evt-002", "2026-01-10T19:59:00Z", 2), _signal("evt-002", "sig-002", "2026-01-10T19:59:00Z", 2))


def test_replay_is_deterministic():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert replay_fixture(fixture) == replay_fixture(fixture)


def test_event_and_signal_pair_must_preserve_identity():
    replay = SessionReplay("session-001")
    event = VJEvent.from_dict(_event("evt-001", "2026-01-10T20:00:00Z", 1))
    signal = _signal("other-event", "sig-001", "2026-01-10T20:00:00Z", 1)

    with pytest.raises(ValueError, match="ids differ"):
        replay.append(event, signal)

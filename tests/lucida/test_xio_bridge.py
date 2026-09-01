import json
from pathlib import Path

import pytest

from lucida.replay.session import DuplicateReplayIdError, OutOfOrderReplayError, SequenceGapError
from lucida.signals.xio_bridge import (
    XioClockError,
    XioEventConsumer,
    XioSchemaError,
    convert_application_event,
    parse_application_event,
    replay_path,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "lucida"
    / "signals"
    / "fixtures"
    / "xio-application-session-fictional.json"
)


def _application_event(
    event_id: str = "evt-001",
    sequence: int = 1,
    session_id: str = "session-001",
    source_timestamp: str | None = None,
    received_timestamp: str | None = None,
) -> dict:
    source_time = source_timestamp or f"2026-01-10T20:00:{sequence:02d}Z"
    received_time = received_timestamp or f"2026-01-10T20:00:{sequence + 1:02d}Z"
    return {
        "event_id": event_id,
        "source_app": "XIO",
        "event_type": "preflight.completed",
        "channel": "instar",
        "payload": {
            "phase": "preflight",
            "vj_event_type": "phase.completed",
            "status": "pass",
        },
        "source_timestamp": source_time,
        "received_timestamp": received_time,
        "session_id": session_id,
        "peer_id": "peer-001",
        "sequence": sequence,
        "raw_hash": f"sha256:{sequence:03d}",
        "provenance": {"producer": "test", "transport": "offline"},
    }


def test_parse_and_convert_preserves_xio_traceability():
    application_event = parse_application_event(_application_event())
    vj_event = convert_application_event(_application_event())

    assert application_event.event_id == "evt-001"
    assert vj_event.event_id == application_event.event_id
    assert vj_event.timestamp == application_event.source_timestamp
    assert vj_event.source == "xio:XIO"
    assert vj_event.payload["xio_provenance"]["session_id"] == "session-001"
    assert vj_event.payload["xio_provenance"]["peer_id"] == "peer-001"
    assert vj_event.payload["xio_provenance"]["raw_hash"] == "sha256:001"
    assert vj_event.payload["xio_provenance"]["provenance"]["producer"] == "test"


def test_consumer_delivers_event_and_results_to_session_replay():
    consumer = XioEventConsumer("session-001")
    results = (
        {
            "result_id": "res-common",
            "proposal_id": "proposal-evt-001-checkpoint-preflight",
            "recorded_at": "2026-01-10T20:01:00Z",
            "status": "observed",
        },
        {
            "result_id": "res-instar",
            "proposal_id": "lucida-instar-evt-001",
            "recorded_at": "2026-01-10T20:01:01Z",
            "status": "accepted",
        },
    )

    received = consumer.consume(_application_event(), results=results)

    assert received.record.event.event_id == "evt-001"
    assert received.record.signal.transport == "xio"
    assert received.record.audit["metadata"]["session_id"] == "session-001"
    assert received.record.audit["metadata"]["received_timestamp"] == "2026-01-10T20:00:02Z"
    assert received.record.state_after.vj_state.pending_proposal_ids == ()


def test_incomplete_application_event_is_rejected():
    raw = _application_event()
    del raw["provenance"]

    with pytest.raises(XioSchemaError, match="missing fields"):
        parse_application_event(raw)


def test_invalid_clocks_are_rejected():
    raw = _application_event(
        source_timestamp="2026-01-10T20:00:02Z",
        received_timestamp="2026-01-10T20:00:01Z",
    )
    with pytest.raises(XioClockError, match="cannot precede"):
        parse_application_event(raw)

    raw = _application_event(source_timestamp="2026-01-10T20:00:01")
    with pytest.raises(XioClockError, match="timezone"):
        parse_application_event(raw)


def test_invalid_sequence_and_non_ascii_source_are_rejected():
    with pytest.raises(XioSchemaError, match="positive integer"):
        parse_application_event(_application_event(sequence=0))

    raw = _application_event()
    raw["source_app"] = "X" + chr(0xCD) + "O"
    with pytest.raises(XioSchemaError, match="ASCII"):
        parse_application_event(raw)


def test_duplicate_event_id_is_rejected():
    consumer = XioEventConsumer("session-001")
    consumer.consume(_application_event(event_id="evt-001", sequence=1))

    with pytest.raises(DuplicateReplayIdError, match="Duplicate event_id"):
        consumer.consume(_application_event(event_id="evt-001", sequence=2))


def test_sequence_gap_is_rejected():
    consumer = XioEventConsumer("session-001")
    consumer.consume(_application_event(event_id="evt-001", sequence=1))

    with pytest.raises(SequenceGapError, match="Sequence gap"):
        consumer.consume(_application_event(event_id="evt-003", sequence=3))


def test_out_of_order_sequence_is_rejected():
    consumer = XioEventConsumer("session-001", first_sequence=2)
    consumer.consume(_application_event(event_id="evt-002", sequence=2))

    with pytest.raises(OutOfOrderReplayError, match="Sequence out of order"):
        consumer.consume(_application_event(event_id="evt-001", sequence=1))


def test_xio_fixture_replay_is_deterministic_and_proposal_only():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    first = replay_path(FIXTURE)
    second = replay_path(FIXTURE)

    assert first == second
    assert first["status"] == "PASS"
    assert first["replay_type"] == "XioApplicationReplay"
    assert first["source_app"] == "XIO"
    assert first["event_count"] == 6
    assert first["proposal_count"] == 12
    assert first["result_count"] == 12
    assert first["final_state"]["lucida_state"]["pending_proposal_ids"] == []
    assert first["safety"]["proposal_only"] is True
    assert all("session_id" in event for event in fixture["events"])

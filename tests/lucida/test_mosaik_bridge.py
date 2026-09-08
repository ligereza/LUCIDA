import pytest

from lucida.signals.mosaik import (
    MosaikBridgeError,
    MosaikEventConsumer,
    parse_mosaik_event,
    replay_fixture,
)


def _event(event_id="instar-001", sequence=1, source="INSTAR"):
    return {
        "event_id": event_id,
        "timestamp": f"2026-09-02T20:0{sequence}:00Z",
        "phase": "preflight" if source == "INSTAR" else "preparation",
        "event_type": f"{source.lower()}.observed",
        "payload": {
            "sequence": sequence,
            "provenance": {"producer": source, "protocol": "report"},
            "report": {"overall_status": "PASS"},
        },
        "source": source,
    }


def test_mosaik_event_is_consumed_as_a_proposal_only_replay_signal():
    result = MosaikEventConsumer("show-001").consume(_event())

    assert result.signal.transport == "mosaik"
    assert result.signal.address == "/mosaik/instar/instar.observed"
    assert result.record.audit["metadata"]["source_app"] == "MOSAIK"
    assert result.record.audit["external_side_effects"] is False


def test_replay_fixture_preserves_order_and_is_deterministic():
    fixture = {"session_id": "show-001", "events": [_event()]}
    first = replay_fixture(fixture)
    second = replay_fixture(fixture)

    assert first == second
    assert first["replay_type"] == "MosaikProjectReplay"
    assert first["event_count"] == 1
    assert first["safety"]["proposal_only"] is True


def test_bridge_rejects_non_mosaik_sources_and_missing_sequence():
    with pytest.raises(MosaikBridgeError, match="source must be one of"):
        parse_mosaik_event(_event(source="XIO"))

    raw = _event()
    del raw["payload"]["sequence"]
    with pytest.raises(MosaikBridgeError, match="payload.sequence"):
        parse_mosaik_event(raw)

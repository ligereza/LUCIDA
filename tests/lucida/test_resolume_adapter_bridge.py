import pytest

from lucida.signals.resolume_adapter import (
    ResolumeAdapterBridgeError,
    ResolumeAdapterEventConsumer,
    parse_resolume_adapter_event,
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


def test_resolume_adapter_event_is_consumed_as_a_proposal_only_replay_signal():
    result = ResolumeAdapterEventConsumer("show-001").consume(_event())

    assert result.signal.transport == "resolume_adapter"
    assert result.signal.address == "/resolume_adapter/instar/instar.observed"
    assert result.record.audit["metadata"]["source_app"] == "RESOLUME_ADAPTER"
    assert result.record.audit["external_side_effects"] is False


def test_replay_fixture_preserves_order_and_is_deterministic():
    fixture = {"session_id": "show-001", "events": [_event()]}
    first = replay_fixture(fixture)
    second = replay_fixture(fixture)

    assert first == second
    assert first["replay_type"] == "ResolumeAdapterProjectReplay"
    assert first["event_count"] == 1
    assert first["safety"]["proposal_only"] is True


def test_bridge_rejects_non_resolume_adapter_sources_and_missing_sequence():
    with pytest.raises(ResolumeAdapterBridgeError, match="source must be one of"):
        parse_resolume_adapter_event(_event(source="XIO"))

    raw = _event()
    del raw["payload"]["sequence"]
    with pytest.raises(ResolumeAdapterBridgeError, match="payload.sequence"):
        parse_resolume_adapter_event(raw)

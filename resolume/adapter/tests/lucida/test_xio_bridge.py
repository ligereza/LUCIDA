import json
from pathlib import Path

import pytest

from lucida.replay import validate_public_report
from lucida.replay.session import DuplicateReplayIdError, OutOfOrderReplayError, SequenceGapError
from lucida.signals.xio_bridge import (
    XioClockError,
    XioEventConsumer,
    XioSchemaError,
    convert_application_event,
    parse_application_event,
    replay_path,
    validate_xio_consume_result,
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
    assert received.overlay_update["contract_type"] == "LucidaOverlayUpdate"
    assert received.overlay_update["cursor"]["sequence"] == 1
    assert received.overlay_update["view_digest"]
    assert received.to_dict()["overlay_update"] == received.overlay_update


def test_xio_consumer_public_report_uses_redacted_common_contract():
    consumer = XioEventConsumer("session-001")
    raw = _application_event()
    raw["payload"]["private_token"] = "must-not-share"
    raw["provenance"]["private_token"] = "must-not-share"
    consumer.consume(raw)

    public = consumer.public_report()
    validated = validate_public_report(public)
    serialized = json.dumps(public, sort_keys=True)

    assert validated == public
    assert public["session_id"] == "session-001"
    assert public["event_count"] == 1
    assert "private_token" not in serialized
    assert "payload" not in public["records"][0]["event"]
    assert "arguments" not in public["records"][0]["signal"]
    assert public["safety"]["external_side_effects"] is False


def test_validate_xio_consume_result_accepts_generated_roundtrip():
    result = XioEventConsumer("session-001").consume(_application_event()).to_dict()

    validated = validate_xio_consume_result(result)

    assert validated == result
    assert validated is not result


def test_validate_xio_consume_result_rejects_cross_contract_sequence_tampering():
    result = XioEventConsumer("session-001").consume(_application_event()).to_dict()
    result["overlay_update"]["cursor"]["sequence"] = 2

    with pytest.raises(XioSchemaError, match="overlay_update position"):
        validate_xio_consume_result(result)


def test_validate_xio_consume_result_rejects_invalid_overlay_digest():
    result = XioEventConsumer("session-001").consume(_application_event()).to_dict()
    result["overlay_update"]["view_digest"] = "0" * 64

    with pytest.raises(XioSchemaError, match="view_digest"):
        validate_xio_consume_result(result)


def test_validate_xio_consume_result_rejects_signal_identity_tampering():
    result = XioEventConsumer("session-001").consume(_application_event()).to_dict()
    result["signal"]["event_id"] = "evt-other"

    with pytest.raises(XioSchemaError, match="signal identity"):
        validate_xio_consume_result(result)


def test_validate_xio_consume_result_rejects_provenance_session_tampering():
    result = XioEventConsumer("session-001").consume(_application_event()).to_dict()
    result["vj_event"]["payload"]["xio_provenance"]["session_id"] = "session-other"

    with pytest.raises(XioSchemaError, match="provenance"):
        validate_xio_consume_result(result)


def test_xio_consumer_exposes_bounded_overlay_and_revision_cursor():
    consumer = XioEventConsumer("session-001")
    raw = _application_event()
    raw["payload"]["secret_payload"] = "must-not-leak"
    raw["provenance"]["private_token"] = "must-not-leak"
    consumer.consume(raw)

    overlay = consumer.read_overlay()
    cursor = consumer.read_overlay_cursor()
    serialized = json.dumps({"overlay": overlay, "cursor": cursor}, sort_keys=True)

    assert overlay["contract_type"] == "LucidaOverlayView"
    assert overlay["session_id"] == "session-001"
    assert "state" not in overlay
    assert "secret_payload" not in serialized
    assert "private_token" not in serialized
    assert cursor["contract_type"] == "LucidaOverlayCursor"
    assert cursor["sequence"] == 1
    assert cursor["last_event_id"] == "evt-001"
    assert consumer.read_overlay() == overlay
    assert consumer.read_overlay_cursor() == cursor


def test_xio_consume_update_is_deterministic_and_redacted():
    first = XioEventConsumer("session-001").consume(_application_event())
    second = XioEventConsumer("session-001").consume(_application_event())

    assert first.overlay_update == second.overlay_update
    serialized = json.dumps(first.overlay_update, sort_keys=True)
    assert "payload" not in serialized
    assert "provenance" not in serialized


def test_xio_consume_result_schema_references_the_atomic_overlay_contract():
    contracts_dir = Path(__file__).parents[2] / "lucida" / "signals" / "contracts"
    schema = json.loads(
        (contracts_dir / "xio-consume-result.schema.json").read_text(encoding="utf-8")
    )
    result = XioEventConsumer("session-001").consume(_application_event()).to_dict()

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(result)
    assert schema["properties"]["application_event"]["$ref"] == "urn:lucida:signals:application-event"
    assert schema["properties"]["vj_event"]["$ref"] == "urn:vj-interface-layer:contracts:vj-event"
    assert schema["properties"]["signal"]["$ref"] == "urn:lucida:signals:signal-envelope"
    assert schema["properties"]["record"]["$ref"] == "urn:lucida:signals:session-replay-record"
    assert schema["properties"]["overlay_update"]["$ref"] == "urn:resolume_adapter:lucida:overlay-update"


def test_xio_result_schema_references_resolve_to_registered_contract_ids():
    repo_root = Path(__file__).parents[2]
    schema_files = list(repo_root.glob("**/*.schema.json"))
    registry = {
        json.loads(path.read_text(encoding="utf-8"))["$id"]: path for path in schema_files
    }
    contracts_dir = repo_root / "lucida" / "signals" / "contracts"
    schema = json.loads(
        (contracts_dir / "xio-consume-result.schema.json").read_text(encoding="utf-8")
    )

    for property_schema in schema["properties"].values():
        reference = property_schema.get("$ref")
        if reference and not reference.startswith("http"):
            assert reference in registry, reference


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

import json
from pathlib import Path

import pytest

from adapters.vj.contracts import VJEvent
from lucida.replay import (
    PublicReplayReportError,
    public_replay_fixture,
    validate_public_report,
)
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


def test_public_report_omits_payload_arguments_metadata_and_free_form_notes():
    replay = SessionReplay("session-public", metadata={"private_path": "C:\\private"})
    event = _event("evt-public", "2026-01-10T20:00:00Z", 1)
    event["payload"]["secret_profile_value"] = "do-not-share"
    signal = _signal("evt-public", "sig-public", "2026-01-10T20:00:00Z", 1)
    signal["arguments"] = ["secret-argument"]
    replay.append(event, signal, results=[])
    replay.record_audit(
        {
            "audit_id": "audit-public",
            "event_id": "evt-public",
            "metadata": {"private": "do-not-share"},
            "notes": "do-not-share",
            "reason": "private-reason",
            "provenance": {"private": "do-not-share"},
            "status": "accepted",
            "execution_asserted": False,
            "mode": "proposal_only",
            "external_side_effects": False,
        }
    )
    replay.record_audit({"audit_id": "audit-private", "mode": "secret-mode"})

    public = replay.public_report()
    record = public["records"][0]
    serialized = json.dumps(public, sort_keys=True)

    assert public["contract_type"] == "LucidaPublicSessionReplayReport"
    assert "payload" not in record["event"]
    assert "arguments" not in record["signal"]
    assert "metadata" not in record["event"]
    assert "metadata" not in record["audit"]
    assert "reason" not in record["audit"]
    assert "provenance" not in record["audit"]
    assert "secret_profile_value" not in serialized
    assert "secret-argument" not in serialized
    assert "do-not-share" not in serialized
    assert "secret-mode" not in serialized
    host_audit = next(item for item in public["audit_log"] if item.get("status") == "accepted")
    assert host_audit["execution_asserted"] is False
    assert public["safety"] == {
        "replay_only": True,
        "proposal_only": True,
        "external_side_effects": False,
        "raw_payloads_included": False,
        "signal_arguments_included": False,
        "metadata_included": False,
    }
    assert record["state_after"]["mode"] == "read_only"
    assert all("reason" not in proposal for proposal in record["proposals"])


def test_public_fixture_wrapper_uses_the_same_replay_engine():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    public = public_replay_fixture(fixture)
    internal = replay_fixture(fixture)

    assert public["contract_type"] == "LucidaPublicSessionReplayReport"
    assert public["event_count"] == internal["event_count"]
    assert public["signal_count"] == internal["signal_count"]
    assert public["proposal_count"] == internal["proposal_count"]
    assert public["result_count"] == internal["result_count"]
    assert public["safety"]["raw_payloads_included"] is False
    assert public_replay_fixture(fixture) == public


def test_public_report_validator_rejects_unsafe_tampering_and_detaches_input():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    public = public_replay_fixture(fixture)

    validated = validate_public_report(public)
    assert validated == public
    assert validated is not public

    unsafe_payload = json.loads(json.dumps(public))
    unsafe_payload["records"][0]["event"]["payload"] = {"secret": "must-reject"}
    with pytest.raises(PublicReplayReportError):
        validate_public_report(unsafe_payload)

    unsafe_safety = json.loads(json.dumps(public))
    unsafe_safety["safety"]["proposal_only"] = False
    with pytest.raises(PublicReplayReportError):
        validate_public_report(unsafe_safety)

    unsafe_link = json.loads(json.dumps(public))
    unsafe_link["records"][0]["state_after"]["session_id"] = "other-session"
    with pytest.raises(PublicReplayReportError):
        validate_public_report(unsafe_link)


def test_public_report_accepts_a_delayed_result_for_an_earlier_proposal():
    replay = SessionReplay("session-delayed-result")
    first = replay.append(
        _event("evt-delayed-1", "2026-01-10T20:00:00Z", 1),
        _signal("evt-delayed-1", "sig-delayed-1", "2026-01-10T20:00:00Z", 1),
    )
    proposal_id = first.proposals[0].proposal_id
    replay.append(
        _event("evt-delayed-2", "2026-01-10T20:00:01Z", 2),
        _signal("evt-delayed-2", "sig-delayed-2", "2026-01-10T20:00:01Z", 2),
        results=[
            {
                "result_id": "res-delayed",
                "proposal_id": proposal_id,
                "recorded_at": "2026-01-10T20:00:01Z",
                "status": "observed",
            }
        ],
    )

    public = replay.public_report()

    assert public["result_count"] == 1
    assert public["records"][1]["results"][0]["proposal_id"] == proposal_id


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

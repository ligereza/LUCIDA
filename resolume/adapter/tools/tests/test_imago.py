import json
from pathlib import Path

import pytest

from tools.resolume_adapter.imago import (
    ImagoError,
    build_show_session,
    next_proposal,
    record_event,
    record_result,
    validate_session,
    write_session,
)


def test_imago_records_show_incident_recovery_and_closure():
    session = build_show_session(
        {"profile_id": "profile-01", "private_payload": "must-not-copy"},
        session_id="show-01",
        name="Fictional Show",
        created_at="2026-01-10T22:00:00Z",
    )
    session = record_event(session, event_type="show_started", recorded_at="2026-01-10T22:00:00Z")
    session = record_result(
        session,
        proposal_id="proposal-event-001-observe_show",
        result="accepted",
        recorded_at="2026-01-10T22:01:00Z",
    )
    session = record_event(
        session,
        event_type="incident_detected",
        payload={"category": "signal_review", "private_payload": "drop"},
        recorded_at="2026-01-10T22:15:00Z",
    )
    assert session["status"] == "incident"
    assert session["open_incidents"]
    session = record_event(session, event_type="recovery_started", recorded_at="2026-01-10T22:16:00Z")
    session = record_event(session, event_type="recovery_verified", recorded_at="2026-01-10T22:17:00Z")
    session = record_event(session, event_type="show_closed", recorded_at="2026-01-10T23:00:00Z")

    assert session["status"] == "closed"
    assert session["open_incidents"] == []
    assert session["sequence"] == 5
    assert "private_payload" not in json.dumps(session)


def test_imago_rejects_invalid_transition_and_requires_pending_result():
    session = build_show_session(session_id="show-01", name="Show", created_at="2026-01-10T22:00:00Z")
    with pytest.raises(ImagoError, match="transition not allowed"):
        record_event(session, event_type="cue_fired", recorded_at="2026-01-10T22:00:00Z")
    session = record_event(session, event_type="show_started", recorded_at="2026-01-10T22:00:00Z")
    proposal = next_proposal(session)
    with pytest.raises(ImagoError, match="not pending"):
        record_result(session, proposal_id="missing", result="accepted", recorded_at="2026-01-10T22:01:00Z")
    assert proposal["execution_mode"] == "proposal_only"


def test_imago_records_a_guard_window_as_a_reversible_proposal():
    session = build_show_session(session_id="show-guard", name="Guard window", created_at="2026-01-10T22:00:00Z")
    session = record_event(session, event_type="show_started", recorded_at="2026-01-10T22:00:00Z")
    session = record_event(
        session,
        event_type="guard_window_requested",
        payload={"duration_ms": 5000, "base_clip_id": "clip-base-01", "test_scope": "effect"},
        recorded_at="2026-01-10T22:01:00Z",
    )

    proposal = next(item for item in session["proposals"] if item["operation"] == "prepare_guard_window")
    assert session["status"] == "showing"
    assert session["events"][-1]["payload"]["duration_ms"] == 5000.0
    assert proposal["requires_explicit_approval"] is True
    assert proposal["reversible"] is True
    assert proposal["execution_mode"] == "proposal_only"
    session = record_result(session, proposal_id=proposal["proposal_id"], result="accepted", recorded_at="2026-01-10T22:01:01Z")
    assert proposal["proposal_id"] not in session["pending_proposal_ids"]


def test_imago_rejects_an_unsafe_guard_window_duration():
    session = build_show_session(session_id="show-guard", name="Guard window", created_at="2026-01-10T22:00:00Z")
    session = record_event(session, event_type="show_started", recorded_at="2026-01-10T22:00:00Z")
    with pytest.raises(ImagoError, match="duration_ms"):
        record_event(
            session,
            event_type="guard_window_requested",
            payload={"duration_ms": 60001},
            recorded_at="2026-01-10T22:01:00Z",
        )


def test_imago_result_and_checkpoint_are_serializable(tmp_path):
    session = build_show_session(session_id="show-01", name="Show", created_at="2026-01-10T22:00:00Z")
    output = write_session(session, tmp_path / "imago.json")
    loaded = json.loads(Path(output).read_text(encoding="utf-8"))
    validate_session(loaded)
    assert loaded["read_only"] is True
    assert loaded["commands_sent"] is False


def test_imago_schema_matches_generated_session():
    root = Path(__file__).parents[2]
    schema = json.loads((root / "schemas" / "imago-show-session.schema.json").read_text(encoding="utf-8"))
    session = build_show_session(session_id="show-01", name="Show", created_at="2026-01-10T22:00:00Z")
    assert set(schema["required"]) == set(session)
    assert schema["properties"]["commands_sent"]["const"] is False

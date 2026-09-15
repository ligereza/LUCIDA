import json

import pytest

from adapters.vj import (
    ImagoInputError,
    ImagoInputProjector,
    ShowInputProjector,
    VJAdapter,
    VJEvent,
    build_imago_event,
    project_imago_show_input,
)


def _session(status="showing"):
    return {
        "schema_version": "0.1",
        "session_type": "ImagoShowSession",
        "session_id": "show-001",
        "name": "Private live show",
        "created_at": "2026-09-02T22:00:00Z",
        "updated_at": "2026-09-02T22:15:00Z",
        "read_only": True,
        "commands_sent": False,
        "profile": {
            "profile_id": "profile-001",
            "venue_id": "venue-001",
            "private_path": "C:\\Private\\profile.json",
        },
        "status": status,
        "sequence": 3,
        "last_event_id": "event-003",
        "last_timestamp": "2026-09-02T22:14:00Z",
        "checkpoint_id": "checkpoint-event-003",
        "open_incidents": ["event-002"],
        "pending_proposal_ids": ["proposal-event-003-capture_incident"],
        "proposals": [
            {
                "proposal_id": "proposal-event-001-observe_show",
                "event_id": "event-001",
                "operation": "observe_show",
                "reason": "Private reason must not cross",
                "requires_explicit_approval": True,
                "reversible": True,
                "execution_mode": "proposal_only",
            },
            {
                "proposal_id": "proposal-event-003-capture_incident",
                "event_id": "event-003",
                "operation": "capture_incident",
                "reason": "Capture evidence",
                "requires_explicit_approval": True,
                "reversible": True,
                "execution_mode": "proposal_only",
            },
        ],
        "results": [
            {
                "result_id": "result-001",
                "proposal_id": "proposal-event-001-observe_show",
                "created_at": "2026-09-02T22:01:00Z",
                "result": "accepted",
                "notes": "Private operator note C:\\Private\\note.txt",
            }
        ],
        "events": [
            {
                "event_id": "event-001",
                "created_at": "2026-09-02T22:00:00Z",
                "event_type": "show_started",
                "payload": {"private": "drop"},
                "status_after": "showing",
                "checkpoint_id": "checkpoint-event-001",
            },
            {
                "event_id": "event-002",
                "created_at": "2026-09-02T22:14:00Z",
                "event_type": "incident_detected",
                "payload": {"category": "signal_review"},
                "status_after": "incident",
                "checkpoint_id": "checkpoint-event-002",
            },
        ],
        "unknowns": ["physical screen state"],
    }


def _preparation_event():
    return VJEvent.from_dict(
        {
            "event_id": "prep-001",
            "timestamp": "2026-09-02T22:10:00Z",
            "phase": "preparation",
            "event_type": "soundcheck.observed",
            "payload": {"sequence": 1, "transport": "unknown"},
            "source": "NAYADE",
        }
    )


def test_build_imago_event_derives_phase_and_whitelists_show_state():
    event = build_imago_event(_session(), event_id="imago-001", sequence=6)

    assert event.phase == "show"
    assert event.event_type == "imago.show.observed"
    show = event.payload["show"]
    assert show["status"] == "showing"
    assert show["session_sequence"] == 3
    assert show["open_incident_count"] == 1
    assert show["pending_proposal_count"] == 1
    assert show["proposals"]["operations"] == {
        "observe_show": 1,
        "capture_incident": 1,
    }
    assert show["events"]["types"] == {"show_started": 1, "incident_detected": 1}
    serialized = json.dumps(event.to_dict())
    assert "C:\\Private" not in serialized
    assert "private_path" not in serialized
    assert "Private reason" not in serialized
    assert '"private"' not in serialized


def test_imago_projection_reaches_show_input_and_preserves_phase_order():
    preparation = ShowInputProjector().project(_preparation_event())
    projection = project_imago_show_input(
        _session(),
        event_id="imago-001",
        sequence=6,
        previous=preparation,
    )

    assert projection["show_state"] == "showing"
    assert projection["show_phase"] == "show"
    assert projection["sequence"] == 6
    assert projection["provenance"] == {
        "producer": "IMAGO",
        "protocol": "session-snapshot",
        "source": "IMAGO",
        "transport": "unknown",
    }


def test_imago_bridge_preserves_guard_window_event_type_as_bounded_summary():
    session = _session()
    session["events"].append(
        {
            "event_id": "event-003",
            "created_at": "2026-09-02T22:16:00Z",
            "event_type": "guard_window_requested",
            "payload": {"duration_ms": 5000, "base_clip_id": "clip-01"},
            "status_after": "showing",
            "checkpoint_id": "checkpoint-event-003",
        }
    )

    event = build_imago_event(session, event_id="imago-guard-001", sequence=6)

    assert event.payload["show"]["events"]["types"]["guard_window_requested"] == 1


def test_imago_event_can_be_consumed_after_soundcheck_without_action():
    adapter = VJAdapter()
    state = adapter.initial_state("session-001")
    state, _ = adapter.process(_preparation_event(), state)
    state, proposals = adapter.process(
        ImagoInputProjector().event(_session(), event_id="imago-001", sequence=2),
        state,
    )

    assert state.phase == "show"
    assert state.sequence == 2
    assert proposals == ()
    assert state.pending_proposal_ids == ()


def test_imago_bridge_rejects_non_read_only_or_executable_proposals():
    invalid_session = _session()
    invalid_session["commands_sent"] = True
    with pytest.raises(ImagoInputError, match="sent commands"):
        build_imago_event(invalid_session, event_id="imago-001", sequence=1)

    invalid_proposal_session = _session()
    invalid_proposal_session["proposals"][0]["execution_mode"] = "execute"
    with pytest.raises(ImagoInputError, match="proposal_only"):
        build_imago_event(invalid_proposal_session, event_id="imago-001", sequence=1)

import json

import pytest

from adapters.vj import (
    NayadeInputError,
    NayadeInputProjector,
    VJAdapter,
    build_nayade_event,
    project_nayade_show_input,
)


def _session():
    return {
        "schema_version": "0.1",
        "session_type": "NayadeSoundcheckSession",
        "session_id": "session-nayade-001",
        "name": "Private venue soundcheck",
        "created_at": "2026-09-02T20:00:00Z",
        "updated_at": "2026-09-02T20:15:00Z",
        "read_only_source": True,
        "source": {
            "source_type": "mapping_summary",
            "private_path": "C:\\Private\\show\\mapping.json",
        },
        "composition": {"width": 1920, "height": 1080},
        "seed": 42,
        "targets": {
            "slices": [
                {"slice_id": "slice-001", "input_group_id": "group-a"},
                {"slice_id": "slice-002", "input_group_id": "group-a"},
            ],
            "input_groups": ["group-a"],
        },
        "planned_steps": [
            {"step_id": "step-001", "result": "approved"},
            {"step_id": "step-002", "result": "review"},
        ],
        "events": [
            {
                "event_id": "event-001",
                "operation": "baseline",
                "scope": "input_group",
                "targets": ["group-a"],
                "result": "approved",
                "notes": "Private operator note C:\\Private\\note.txt",
            }
        ],
        "limitations": ["processor state is not confirmed"],
    }


def _processor_observation():
    return {
        "model": "VX600",
        "firmware": "1.3.0",
        "transport": "manual",
        "confidence": "medium",
        "evidence": ["operator_label", "software_screenshot"],
        "read_only": True,
        "commands_sent": False,
        "input_signal": {"resolution": "1920x1080", "range": "limited"},
        "output_signal": {"resolution": "1920x1080", "fps": 60},
        "module_profile": {
            "indoor_outdoor": "indoor",
            "pixel_pitch_mm": 2.6,
            "gamma": 2.2,
            "color_range": "full",
        },
        "private_payload": "must-not-cross",
    }


def test_build_nayade_event_whitelists_session_and_processor_evidence():
    event = build_nayade_event(
        _session(),
        event_id="nayade-001",
        sequence=5,
        processor_observation=_processor_observation(),
    )

    assert event.phase == "preparation"
    assert event.event_type == "nayade.soundcheck.observed"
    soundcheck = event.payload["soundcheck"]
    assert soundcheck["session_id"] == "session-nayade-001"
    assert soundcheck["slice_count"] == 2
    assert soundcheck["input_group_count"] == 1
    assert soundcheck["event_results"] == {"approved": 1}
    assert soundcheck["readiness"]["status"] == "REVIEW"
    assert soundcheck["readiness"]["risk_steps"] == [{"step_id": "step-002", "status": "review"}]
    assert soundcheck["readiness"]["next_step"]["step_id"] == "step-002"
    assert soundcheck["processor"]["model"] == "VX600"
    assert soundcheck["processor"]["module_profile"]["pixel_pitch_mm"] == 2.6
    serialized = json.dumps(event.to_dict())
    assert "C:\\Private" not in serialized
    assert "private_path" not in serialized
    assert "private_payload" not in serialized
    assert "operator note" not in serialized


def test_nayade_projection_reaches_preparation_show_input():
    projection = project_nayade_show_input(
        _session(),
        event_id="nayade-001",
        sequence=5,
        processor_observation=_processor_observation(),
    )

    assert projection["show_state"] == "ready"
    assert projection["show_phase"] == "preparation"
    assert projection["sequence"] == 5
    assert projection["provenance"] == {
        "producer": "NAYADE",
        "protocol": "session-report",
        "source": "NAYADE",
        "transport": "unknown",
    }


def test_nayade_event_can_advance_vj_adapter_without_hardware_action():
    adapter = VJAdapter()
    state = adapter.initial_state("session-001")
    next_state, proposals = adapter.process(
        NayadeInputProjector().event(
            _session(),
            event_id="nayade-001",
            sequence=1,
            processor_observation=_processor_observation(),
        ),
        state,
    )

    assert next_state.phase == "preparation"
    assert next_state.sequence == 1
    assert proposals == ()
    assert next_state.pending_proposal_ids == ()


def test_nayade_bridge_rejects_non_read_only_observation_and_unsafe_ids():
    observation = _processor_observation()
    observation["commands_sent"] = True
    with pytest.raises(NayadeInputError, match="sent commands"):
        build_nayade_event(_session(), event_id="nayade-001", sequence=1, processor_observation=observation)

    invalid = _session()
    invalid["session_id"] = "C:\\Private\\session"
    with pytest.raises(NayadeInputError, match="unsupported text|stable identifier"):
        build_nayade_event(invalid, event_id="nayade-001", sequence=1)

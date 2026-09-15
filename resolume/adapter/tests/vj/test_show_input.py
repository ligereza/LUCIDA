import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from adapters.vj import (
    ShowInputError,
    ShowInputProjector,
    StaleShowInputError,
    project_osc_show_input,
    validate_show_input,
)
from adapters.vj.replay import replay_show_input_path
from lucida.signals import OscResolumeBoundary


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "adapters"
    / "vj"
    / "replay"
    / "fixtures"
    / "show-input-fictional.json"
)


def _event(sequence=1, **payload):
    return {
        "event_id": f"event-{sequence}",
        "timestamp": f"2026-09-02T20:00:{sequence:02d}Z",
        "phase": "show",
        "event_type": "show.started",
        "payload": {"transport": "osc", "sequence": sequence, **payload},
        "source": "test-source",
    }


def test_projection_reuses_osc_normalization_and_exposes_only_bounded_metadata():
    event = OscResolumeBoundary().normalize(
        {
            "address": "/composition/1/layer/1/clip/1/connect",
            "arguments": [1],
            "timestamp": "2026-09-02T22:00:00Z",
            "sequence": 3,
            "source": "fixture",
        }
    )

    projection = ShowInputProjector().project(event).to_dict()

    assert projection["show_state"] == "showing"
    assert projection["show_phase"] == "show"
    assert projection["sequence"] == 3
    assert projection["provenance"] == {"source": "osc:fixture", "transport": "osc"}
    assert "address" not in json.dumps(projection)
    assert "arguments" not in json.dumps(projection)


def test_project_osc_helper_reuses_existing_boundary_without_transport():
    projection = project_osc_show_input(
        {
            "address": "/composition/1/layer/1/clip/1/connect",
            "arguments": [1],
            "timestamp": "2026-09-02T22:00:00Z",
            "sequence": 3,
            "source": "fixture",
        }
    )

    assert projection["show_state"] == "showing"
    assert projection["provenance"] == {"source": "osc:fixture", "transport": "osc"}


def test_project_osc_helper_wraps_invalid_boundary_input():
    with pytest.raises(ShowInputError, match="OSC input invalid"):
        ShowInputProjector().project_osc(
            {
                "address": "/not-a-supported-route",
                "arguments": [],
                "timestamp": "2026-09-02T22:00:00Z",
                "sequence": 1,
                "source": "fixture",
            }
        )


def test_synthetic_replay_is_deterministic_and_preserves_phase_and_order():
    first = replay_show_input_path(FIXTURE)
    second = replay_show_input_path(FIXTURE)

    assert first == second
    assert first["status"] == "PASS"
    assert first["phase_order"] == [
        "preflight",
        "preparation",
        "show",
        "incident",
        "recovery",
        "closure",
    ]
    assert first["sequence_order"] == [1, 2, 3, 4, 5, 6]
    assert [item["provenance"]["transport"] for item in first["projections"]] == [
        "osc",
        "artnet",
        "timecode",
        "osc",
        "sacn",
        "osc",
    ]
    assert first["safety"] == {
        "external_side_effects": False,
        "network_opened": False,
        "host_actions": False,
    }


def test_stale_sequence_and_timestamp_are_rejected():
    projector = ShowInputProjector()
    current = projector.project(_event(2))

    with pytest.raises(StaleShowInputError, match="stale show input"):
        projector.project(_event(1), current)

    older_timestamp = _event(3)
    older_timestamp["timestamp"] = "2026-09-02T19:59:00Z"
    with pytest.raises(StaleShowInputError, match="stale show input"):
        projector.project(older_timestamp, current)


def test_phase_order_reuses_vj_transition_contract():
    projector = ShowInputProjector()
    current = projector.project(_event(1))
    closure = _event(2)
    closure["phase"] = "closure"
    closure["event_type"] = "show.closed"
    projector.project(closure, current)

    invalid = _event(3)
    with pytest.raises(ShowInputError, match="show phase transition not allowed"):
        projector.project(invalid, projector.project(closure, current))


def test_stale_check_rejects_malformed_previous_projection():
    previous = ShowInputProjector().project(_event(1)).to_dict()
    previous["provenance"]["private"] = "must-reject"

    with pytest.raises(ShowInputError, match="unsupported fields"):
        ShowInputProjector().project(_event(2), previous)


def test_provenance_is_canonicalized_and_conflicts_are_rejected():
    projection = ShowInputProjector().project(
        _event(
            1,
            transport="timecode",
            provenance={"source": "test-source", "transport": "timecode", "clock_id": "clock-1"},
        )
    )
    assert projection.provenance == {
        "clock_id": "clock-1",
        "source": "test-source",
        "transport": "timecode",
    }

    conflicting = _event(1, provenance={"transport": "artnet"})
    with pytest.raises(ShowInputError, match="must match event transport"):
        ShowInputProjector().project(conflicting)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda event: event["payload"].pop("sequence"),
        lambda event: event["payload"].update(transport="midi"),
        lambda event: event["payload"].update(preview_candidate="C:/clip.mp4"),
        lambda event: event["payload"].update(provenance={"private": "value"}),
        lambda event: event.update(phase="not-a-phase"),
    ],
)
def test_invalid_input_is_rejected(mutation):
    invalid = copy.deepcopy(_event())
    mutation(invalid)

    with pytest.raises(ShowInputError):
        ShowInputProjector().project(invalid)


def test_projection_matches_schema():
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "adapters"
            / "vj"
            / "contracts"
            / "show-input.schema.json"
        ).read_text(encoding="utf-8")
    )
    projection = replay_show_input_path(FIXTURE)["projections"][2]

    assert list(Draft202012Validator(schema).iter_errors(projection)) == []


def test_projection_kill_test_never_opens_transport_or_spawns_process(monkeypatch):
    import socket
    import subprocess

    def fail(*args, **kwargs):
        raise AssertionError("show input projection attempted an external action")

    monkeypatch.setattr(socket, "socket", fail)
    monkeypatch.setattr(subprocess, "Popen", fail)
    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setattr(subprocess, "check_output", fail)

    projection = ShowInputProjector().project(_event())

    assert projection.sequence == 1


@pytest.mark.parametrize("field", ["contract_type", "show_phase", "provenance"])
def test_public_projection_validator_rejects_tampered_snapshots(field):
    projection = replay_show_input_path(FIXTURE)["projections"][2]
    assert validate_show_input(projection) == projection
    tampered = copy.deepcopy(projection)
    if field == "contract_type":
        tampered[field] = "Other"
    elif field == "show_phase":
        tampered[field] = "not-a-phase"
    else:
        tampered[field]["unexpected"] = "value"

    with pytest.raises(ShowInputError):
        validate_show_input(tampered)

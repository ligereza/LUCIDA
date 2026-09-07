import copy
import json
import socket
import subprocess
from pathlib import Path

import pytest

from lucida.signals import OscBridgeState, OscResolumeBoundary
from lucida.signals.replay import SignalReplayError, replay_fixture, replay_path


OSC_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "lucida"
    / "signals"
    / "fixtures"
    / "osc-session-fictional.json"
)
REPORT_FIXTURE = Path(__file__).resolve().parent / "fixtures/mosaik-semantic-light-field-report.json"


def _runtime_fixture():
    fixture = json.loads(OSC_FIXTURE.resolve().read_text(encoding="utf-8"))
    report = json.loads(REPORT_FIXTURE.read_text(encoding="utf-8"))
    fixture["semantic_reports"] = [report]
    return fixture


def test_existing_signal_replay_dispatches_report_to_pending_resolume_surface(tmp_path):
    replay_json = tmp_path / "runtime-replay.json"
    replay_json.write_text(json.dumps(_runtime_fixture()), encoding="utf-8")
    result = replay_path(replay_json)
    assert result == replay_path(replay_json)

    assert result["semantic_report_count"] == 1
    assert result["semantic_transitions"][0]["proposal_ids"] == [
        "proposal-cli-light-field-001",
    ]
    assert result["final_state"]["lucida_state"]["vj_state"]["pending_proposal_ids"] == [
        "proposal-cli-light-field-001",
    ]
    overlay = result["semantic_transitions"][0]["overlay"]
    assert overlay["resolume_preview"]["status"] == "pending_approval"
    assert overlay["resolume_preview"]["proposal"]["execution_mode"] == "proposal_only"
    assert "frames" not in overlay["resolume_preview"]["proposal"]
    assert overlay["resolume_preview"]["safety"]["resolume_opened"] is False


@pytest.mark.parametrize(
    ("operation", "result_status", "metadata_status"),
    [
        ("approve_proposal", "accepted", "approved"),
        ("reject_proposal", "rejected", "rejected"),
        ("undo_proposal", "skipped", "undone"),
    ],
)
def test_runtime_pending_proposal_requires_explicit_decision(
    operation, result_status, metadata_status
):
    replayed = replay_fixture(_runtime_fixture())
    boundary = OscResolumeBoundary()
    state = OscBridgeState.from_dict(replayed["final_state"])

    decided = getattr(boundary, operation)(
        state,
        proposal_id="proposal-cli-light-field-001",
        result_id="runtime-result-" + result_status,
        recorded_at="2026-09-07T20:00:00Z",
    )

    assert "proposal-cli-light-field-001" not in decided.lucida_state.vj_state.pending_proposal_ids
    assert decided.lucida_state.vj_state.results[-1].status == result_status
    assert decided.lucida_state.metadata[
        "resolume_semantic_light_field_pending"
    ][0]["status"] == metadata_status


def test_runtime_dispatch_rejects_invalid_payload_and_hash_without_external_effects(
    monkeypatch,
):
    def blocked(*_args, **_kwargs):
        raise AssertionError("host side effect attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)

    wrong_hash = _runtime_fixture()
    wrong_hash["semantic_reports"][0]["pending"]["tape_sha256"] = "0" * 64
    with pytest.raises(SignalReplayError, match="hash"):
        replay_fixture(wrong_hash)

    wrong_schema = copy.deepcopy(_runtime_fixture())
    wrong_schema["semantic_reports"][0]["pending"]["tape"]["schema"] = (
        "farmaxia:wrong-tape:0.1"
    )
    with pytest.raises(SignalReplayError, match="schema"):
        replay_fixture(wrong_schema)

    invalid_report = copy.deepcopy(_runtime_fixture())
    invalid_report["semantic_reports"][0]["schema_version"] = "0.2"
    with pytest.raises(SignalReplayError, match="schema version"):
        replay_fixture(invalid_report)

import copy
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from adapters.vj import VJAdapter
from adapters.vj.replay import (
    replay_semantic_light_field_fixture,
    replay_semantic_light_field_path,
)
from adapters.vj.replay.engine import ReplayError, load_fixture


TOOLS_ROOT = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_ROOT))
from resolume_adapter_cli import main  # noqa: E402


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "adapters"
    / "vj"
    / "replay"
    / "fixtures"
    / "semantic-light-field.json"
)


def test_existing_vj_replay_dispatcher_stages_semantic_pending_proposal(capsys):
    exit_code = main(["vj-replay", str(FIXTURE)])

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["replay_type"] == "ResolumeAdapterSemanticLightFieldReplayReport"
    assert report["status"] == "PASS"
    assert report["state"]["pending_proposal_ids"] == ["proposal-cli-light-field-001"]
    assert report["pending"]["status"] == "pending_approval"
    assert report["pending"]["proposal"]["execution_mode"] == "proposal_only"
    assert "frames" not in report["proposal"]
    assert report["safety"] == {
        "external_side_effects": False,
        "irreversible_actions_executed": False,
        "automatic_decision": False,
        "execution_mode": "proposal_only",
    }


@pytest.mark.parametrize(
    ("operation", "result_status"),
    [
        ("approve_proposal", "accepted"),
        ("reject_proposal", "rejected"),
        ("undo_proposal", "skipped"),
    ],
)
def test_dispatched_pending_state_accepts_only_explicit_decision_operations(
    operation, result_status
):
    report = replay_semantic_light_field_path(FIXTURE)
    adapter = VJAdapter()
    state = report["state"]
    proposal_id = report["proposal"]["proposal_id"]

    decided = getattr(adapter, operation)(
        state,
        proposal_id=proposal_id,
        result_id="dispatch-result-" + result_status,
        recorded_at="2026-09-07T20:00:00Z",
    )

    assert decided.pending_proposal_ids == ()
    assert decided.results[-1].status == result_status
    assert decided.metadata["semantic_light_field_pending"][0]["status"] in {
        "approved",
        "rejected",
        "undone",
    }


def test_dispatch_rejects_hash_and_schema_mismatch():
    fixture = load_fixture(FIXTURE)

    wrong_hash = copy.deepcopy(fixture)
    wrong_hash["proposal"]["evidence"] = [
        "tape_sha256:" + ("0" * 64)
        if item.startswith("tape_sha256:")
        else item
        for item in wrong_hash["proposal"]["evidence"]
    ]
    with pytest.raises(ReplayError, match="hash"):
        replay_semantic_light_field_fixture(wrong_hash)

    wrong_schema = copy.deepcopy(fixture)
    wrong_schema["tape"]["schema"] = "farmaxia:wrong-tape:0.1"
    with pytest.raises(ReplayError, match="schema"):
        replay_semantic_light_field_fixture(wrong_schema)


def test_dispatch_has_no_host_side_effects(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("host side effect attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)

    report = replay_semantic_light_field_path(FIXTURE)

    assert report["safety"]["external_side_effects"] is False
    assert report["state"]["pending_proposal_ids"]

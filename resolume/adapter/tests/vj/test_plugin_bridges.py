import copy
import json
from pathlib import Path

import pytest

from adapters.vj.replay import replay_plugin_bridge_fixture, replay_plugin_bridge_path
from adapters.vj.replay.engine import ReplayError, load_fixture


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "adapters"
    / "vj"
    / "replay"
    / "fixtures"
    / "plugin-bridges-fictional.json"
)


def test_plugin_bridge_replay_covers_the_three_stage_flow_without_actions():
    report = replay_plugin_bridge_path(FIXTURE)

    assert report["status"] == "PASS"
    assert report["stage_order"] == ["instar", "nayade", "imago", "imago", "imago", "imago"]
    assert report["phase_order"] == [
        "preflight",
        "preparation",
        "show",
        "incident",
        "recovery",
        "closure",
    ]
    assert report["record_count"] == 6
    assert report["final_state"]["open_incidents"] == []
    assert report["safety"] == {
        "external_side_effects": False,
        "irreversible_actions_executed": False,
        "proposal_count": 0,
    }
    first_imago = report["transitions"][2]["event"]["payload"]["show"]
    assert first_imago["events"]["types"]["guard_window_requested"] == 1


def test_plugin_bridge_replay_is_deterministic_and_contains_no_private_paths():
    first = replay_plugin_bridge_path(FIXTURE)
    second = replay_plugin_bridge_path(FIXTURE)

    assert first == second
    serialized = json.dumps(first)
    assert "C:\\" not in serialized
    assert "Z:\\" not in serialized
    assert ".mp4" not in serialized


def test_plugin_bridge_replay_rejects_duplicate_or_out_of_order_sequences():
    fixture = load_fixture(FIXTURE)
    duplicate = copy.deepcopy(fixture)
    duplicate["records"][1]["event_id"] = duplicate["records"][0]["event_id"]
    with pytest.raises(ReplayError, match="duplicate bridge event_id"):
        replay_plugin_bridge_fixture(duplicate)

    out_of_order = copy.deepcopy(fixture)
    out_of_order["records"][2]["sequence"] = 1
    with pytest.raises(ReplayError, match="strictly increasing"):
        replay_plugin_bridge_fixture(out_of_order)


def test_plugin_bridge_replay_rejects_unknown_record_fields():
    fixture = load_fixture(FIXTURE)
    invalid = copy.deepcopy(fixture)
    invalid["records"][0]["private_payload"] = "must-not-cross"

    with pytest.raises(ReplayError, match="record fields"):
        replay_plugin_bridge_fixture(invalid)

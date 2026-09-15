import json
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.resolume_adapter.cue_plan import build_cue_plan


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "instar-resolume-cue-plan.schema.json"


def _profile(cues):
    return {
        "profile_type": "ClipProfile",
        "profile_id": "clip-001",
        "source": {"filename": "C:\\Private\\visual-loop.mp4"},
        "technical": {"video": {"duration_seconds": 12.0}},
        "events": {"cue_suggestions": {"cues": cues}},
    }


def test_cue_plan_assigns_semantic_slots_and_loop_pair():
    plan = build_cue_plan(
        _profile(
            [
                {"id": "clean-01", "role": "change", "style": "clean", "position_s": 2.0, "confidence": 0.8},
                {"id": "impact-01", "role": "change", "style": "impact", "position_s": 4.0, "confidence": 0.9},
                {"id": "strobe-01", "role": "strobe_window", "position_s": 6.0, "end_position_s": 7.0, "confidence": 0.7},
                {"id": "loop-01", "role": "loop", "in_position_s": 1.0, "out_position_s": 3.0, "confidence": 0.85},
                {"id": "impact-02", "role": "change", "style": "impact", "position_s": 5.0, "confidence": 0.6},
            ]
        )
    )

    profile = plan["profiles"][0]
    slots = profile["slots"]
    assert [slot["candidate_id"] for slot in slots[:5]] == ["clean-01", "impact-01", "strobe-01", "loop-01", "loop-01"]
    assert slots[3]["position_s"] == 1.0
    assert slots[4]["position_s"] == 3.0
    assert slots[5]["candidate_id"] == "impact-02"
    assert profile["filename"] == "visual-loop.mp4"
    assert plan["safety"]["composition_written"] is False
    assert "Private" not in json.dumps(plan, ensure_ascii=False)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(plan)) == []


def test_cue_plan_leaves_slots_empty_without_candidates():
    plan = build_cue_plan(_profile([]))

    assert all(slot["status"] == "empty" for slot in plan["profiles"][0]["slots"])
    assert plan["statistics"]["assigned_slots"] == 0

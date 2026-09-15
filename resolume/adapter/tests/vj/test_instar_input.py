import json

import pytest

from adapters.vj import (
    InstarInputError,
    InstarInputProjector,
    VJAdapter,
    build_instar_event,
    project_instar_show_input,
)


def _report():
    return {
        "schema_version": "0.1",
        "generated_at": "2026-09-02T20:00:00Z",
        "overall_status": "WARN",
        "files_found": 1,
        "cache_hits": 0,
        "media_root": "C:\\Private\\Show\\media",
        "items": [
            {
                "path": "C:\\Private\\Show\\media\\clip.mov",
                "status": "WARN",
                "error": "C:\\Private\\Show\\media\\clip.mov needs review",
                "report": {
                    "video": {
                        "codec": "dxv",
                        "average_fps": "60",
                        "width": 1920,
                        "height": 1080,
                    },
                    "alpha": {"status": "NONE"},
                    "clip_profile": {
                        "profile_id": "clip-001",
                        "visual": {"status": "ANALYZED", "loop": {"status": "CANDIDATE"}},
                        "events": {"cue_suggestions": {"cues": [{"role": "change"}]}},
                        "source": {"path": "C:\\Private\\Show\\media\\clip.mov"},
                    },
                },
            }
        ],
    }


def test_build_instar_event_preserves_safe_summary_without_paths():
    event = build_instar_event(_report(), event_id="instar-001", sequence=4)

    assert event.phase == "preflight"
    assert event.event_type == "instar.preflight.observed"
    assert event.source == "INSTAR"
    assert event.payload["sequence"] == 4
    assert event.payload["report"]["items"] == [
        {
            "asset_id": "clip-001",
            "status": "WARN",
            "codec": "dxv",
            "fps": 60,
            "width": 1920,
            "height": 1080,
            "alpha": "NONE",
            "visual_status": "ANALYZED",
            "loop_status": "CANDIDATE",
            "cue_count": 1,
        }
    ]
    serialized = json.dumps(event.to_dict())
    assert "C:\\Private" not in serialized
    assert "media_root" not in serialized


def test_instar_projection_reaches_bounded_show_input_contract():
    projection = project_instar_show_input(_report(), event_id="instar-001", sequence=4)

    assert projection["show_state"] == "ready"
    assert projection["show_phase"] == "preflight"
    assert projection["sequence"] == 4
    assert projection["preview_candidate"] is None
    assert projection["provenance"] == {
        "producer": "INSTAR",
        "protocol": "report",
        "source": "INSTAR",
        "transport": "unknown",
    }


def test_instar_event_can_be_consumed_by_vj_adapter_without_action():
    adapter = VJAdapter()
    state = adapter.initial_state("session-001")
    next_state, proposals = adapter.process(
        InstarInputProjector().event(_report(), event_id="instar-001", sequence=1),
        state,
    )

    assert next_state.phase == "preflight"
    assert next_state.sequence == 1
    assert proposals == ()
    assert next_state.pending_proposal_ids == ()


def test_instar_bridge_rejects_unbounded_or_unsafe_report_data():
    invalid = _report()
    invalid["items"] = [{"asset_id": "C:\\Private\\clip.mov", "status": "WARN"}]
    with pytest.raises(InstarInputError, match="stable identifier"):
        build_instar_event(invalid, event_id="instar-001", sequence=1)

    oversized = _report()
    oversized["items"] = [
        {"asset_id": f"clip-{index:03d}", "status": "PASS"}
        for index in range(101)
    ]
    with pytest.raises(InstarInputError, match="more than 100"):
        build_instar_event(oversized, event_id="instar-001", sequence=1)

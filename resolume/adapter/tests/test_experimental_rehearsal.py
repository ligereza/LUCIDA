from __future__ import annotations

import pytest

from adapters.vj.experimental_rehearsal import (
    RehearsalBridgeError,
    build_rehearsal_projection,
    validate_resolume_cue,
)


def states(count: int = 2) -> list[dict]:
    return [
        {
            "sequence": 1,
            "timestamp": "2026-01-01T00:00:00.000Z",
            "timecode": "00:00:00:00",
            "event_id": "pulse-001",
            "signal_state": "present",
            "lights": [
                {
                    "fixture_id": f"ble-{index + 1:02d}",
                    "angle_degrees": float((index * 180) % 360),
                    "phase": 0.25,
                    "intensity": 0.8,
                    "pulse": 1.0,
                }
                for index in range(count)
            ],
        },
        {
            "sequence": 2,
            "timestamp": "2026-01-01T00:00:00.200Z",
            "timecode": "00:00:00:05",
            "event_id": "pulse-002",
            "signal_state": "present",
            "lights": [
                {
                    "fixture_id": f"ble-{index + 1:02d}",
                    "angle_degrees": float((index * 180 + 20) % 360),
                    "phase": 0.5,
                    "intensity": 0.6,
                    "pulse": 0.0,
                }
                for index in range(count)
            ],
        },
    ]


def test_projection_is_deterministic_and_replays_through_resolume_adapter():
    left = build_rehearsal_projection("session-01", states(), source_event_digest="a" * 64)
    right = build_rehearsal_projection("session-01", states(), source_event_digest="a" * 64)
    assert left["tape_sha256"] == right["tape_sha256"]
    assert left["replay_report"]["status"] == "PASS"
    assert left["safety"]["external_side_effects"] is False


def test_variable_fixture_count_is_supported_between_tapes():
    assert build_rehearsal_projection("two", states(2), source_event_digest="b" * 64)["fixture_count"] == 2
    assert build_rehearsal_projection("three", states(3), source_event_digest="b" * 64)["fixture_count"] == 3


def test_invalid_cue_is_blocked():
    with pytest.raises(RehearsalBridgeError, match="proposal_only"):
        validate_resolume_cue(
            {
                "layer": "phasechaser-main",
                "clip": "synthetic-phasechaser",
                "opacity": 1.0,
                "rotation_degrees": 0.0,
                "strobe": False,
                "transport": "timeline",
                "proposal_only": False,
            }
        )


def test_revoked_permissions_block_proposal_without_side_effects():
    result = build_rehearsal_projection(
        "revoked",
        states(),
        source_event_digest="c" * 64,
        permissions_revoked=True,
    )
    assert result["status"] == "BLOCKED"
    assert result["proposal"] is None
    assert result["safety"]["external_side_effects"] is False

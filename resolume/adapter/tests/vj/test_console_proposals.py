from __future__ import annotations

import copy
import socket
import subprocess

import pytest

from adapters.vj import ConsoleProposalError, build_console_proposals


def frame():
    return {
        "schema": "xio:predictive-semantic-lighting-frame:0.1",
        "proposal_only": True,
        "session_id": "session-001",
        "event_id": "pulse-001",
        "sequence": 1,
        "timestamp": "2026-09-08T00:00:01.250Z",
        "time_seconds": 1.25,
        "timecode": "00:00:01:06",
        "signal_state": "present",
        "scene": {"phase": 0.25, "master_intensity": 1.0, "pulse": 1.0},
        "lights": [
            {"fixture_id": "wash-01", "phase": 0.25, "angle_degrees": 90.0, "intensity": 0.8, "pulse": 1.0},
            {"fixture_id": "wash-02", "phase": 0.75, "angle_degrees": 270.0, "intensity": 0.4, "pulse": 0.0},
        ],
    }


def test_builds_two_native_proposal_surfaces_without_io():
    proposal = build_console_proposals(frame(), resolume_layer=2, resolume_clip=3, avolites_playback=7)

    assert proposal["status"] == "PENDING_APPROVAL"
    assert proposal["decision"]["execution_mode"] == "proposal_only"
    assert proposal["targets"]["resolume"]["transport"] == "OSC"
    assert proposal["targets"]["resolume"]["messages"][0]["address"] == "/composition/layers/2/opacity"
    assert proposal["targets"]["avolites"]["actions"][0]["operation"] == "Playbacks.PlayPlayback"
    assert proposal["targets"]["avolites"]["actions"][0]["query"]["handle_userNumber"] == 7
    assert proposal["safety"]["external_side_effects"] is False


def test_revocation_blocks_both_targets():
    proposal = build_console_proposals(frame(), permissions_revoked=True)
    assert proposal["status"] == "BLOCKED"
    assert proposal["blockers"] == ["permissions_revoked"]
    assert proposal["targets"] == {}


def test_invalid_frame_and_host_side_effects_are_guarded(monkeypatch):
    invalid = copy.deepcopy(frame())
    invalid["lights"][0]["intensity"] = 2.0
    with pytest.raises(ConsoleProposalError, match="outside safe bounds"):
        build_console_proposals(invalid)

    def blocked(*_args, **_kwargs):
        raise AssertionError("host side effect attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)
    proposal = build_console_proposals(frame())
    assert proposal["safety"]["resolume_opened"] is False
    assert proposal["safety"]["avolites_contacted"] is False

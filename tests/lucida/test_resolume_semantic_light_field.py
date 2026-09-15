import copy
import json
import socket
import subprocess
from pathlib import Path

import pytest

from adapters.vj.contracts import VJResult
from lucida.signals import (
    OscBridgeState,
    OscResolumeBoundary,
    SemanticLightFieldSurfaceError,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "resolume_adapter-semantic-light-field-report.json"


def _report():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_resolume_adapter_report_projects_to_resolume_pending_surface_without_frames():
    boundary = OscResolumeBoundary()
    state = boundary.initial_state("semantic-light-field-cli-001")

    next_state, overlay = boundary.ingest_semantic_light_field_report(_report(), state)

    assert next_state.lucida_state.vj_state.pending_proposal_ids == (
        "proposal-cli-light-field-001",
    )
    assert overlay["surface"] == "LUCIDA"
    assert overlay["resolume_preview"]["surface"] == "RESOLUME"
    assert overlay["resolume_preview"]["status"] == "pending_approval"
    assert overlay["resolume_preview"]["projection"] == {
        "contract_type": "SurfaceProjection",
        "schema_version": "1.0",
        "host_id": "LUCIDA",
        "surface_id": "RESOLUME",
        "status": "pending_approval",
        "proposal": {
            "proposal_id": "proposal-cli-light-field-001",
            "reason": "Review deterministic semantic light-field tape",
            "evidence": [
                "consumer:resolume_adapter-vj",
                "tape_schema:farmaxia:semantic-light-field-tape:0.1",
                "tape_sha256:f69e170a3447924a7e30126572c659bf61a353d6628ae9e4cd1359aa035bbaec",
                "frame_count:1",
            ],
            "execution_mode": "proposal_only",
            "requires_explicit_approval": True,
            "reversible": True,
        },
        "safety": {
            "proposal_only": True,
            "automatic_actions": False,
            "external_side_effects": False,
            "host_opened": False,
        },
    }
    assert overlay["resolume_preview"]["proposal"]["execution_mode"] == "proposal_only"
    assert "frames" not in overlay["resolume_preview"]["proposal"]
    assert overlay["pending_proposals"][0] == overlay["resolume_preview"]["proposal"]
    assert overlay["resolume_preview"]["tape"]["frame_count"] == 1
    assert overlay["resolume_preview"]["safety"] == {
        "proposal_only": True,
        "reversible": True,
        "automatic_actions": False,
        "resolume_opened": False,
        "external_side_effects": False,
    }
    assert overlay["safety"]["resolume_opened"] is False
    restored_state = OscBridgeState.from_dict(next_state.to_dict())
    restored_overlay = boundary.read_overlay(restored_state)
    assert restored_overlay["resolume_preview"] == overlay["resolume_preview"]


def test_projected_resolume_proposal_can_only_be_resolved_explicitly():
    boundary = OscResolumeBoundary()
    state = boundary.initial_state("semantic-light-field-cli-001")
    pending_state, _overlay = boundary.ingest_semantic_light_field_report(_report(), state)

    result = VJResult(
        result_id="result-semantic-light-field-accepted",
        proposal_id="proposal-cli-light-field-001",
        recorded_at="2026-09-07T20:00:00Z",
        status="accepted",
        notes="Explicit RESOLUME preview approval; no execution.",
    )
    decided = boundary.register_result(pending_state, result)

    assert decided.lucida_state.vj_state.pending_proposal_ids == ()
    assert decided.lucida_state.vj_state.results[-1].status == "accepted"
    assert decided.lucida_state.proposals[0].execution_mode == "proposal_only"
    assert "resolume_preview" not in boundary.read_overlay(decided)


def test_invalid_hash_and_schema_are_rejected_without_state_mutation():
    boundary = OscResolumeBoundary()
    state = boundary.initial_state("semantic-light-field-cli-001")

    wrong_hash = _report()
    wrong_hash["pending"]["tape_sha256"] = "0" * 64
    with pytest.raises(SemanticLightFieldSurfaceError, match="hash"):
        boundary.ingest_semantic_light_field_report(wrong_hash, state)

    wrong_schema = copy.deepcopy(_report())
    wrong_schema["pending"]["tape"]["schema"] = "farmaxia:wrong-tape:0.1"
    with pytest.raises(SemanticLightFieldSurfaceError, match="schema"):
        boundary.ingest_semantic_light_field_report(wrong_schema, state)

    wrong_mode = copy.deepcopy(_report())
    wrong_mode["proposal"]["execution_mode"] = "execute"
    wrong_mode["pending"]["proposal"]["execution_mode"] = "execute"
    with pytest.raises(SemanticLightFieldSurfaceError, match="proposal contract"):
        boundary.ingest_semantic_light_field_report(wrong_mode, state)

    assert state.lucida_state.vj_state.pending_proposal_ids == ()
    assert state.lucida_state.proposals == ()


def test_resolume_projection_has_no_host_side_effects(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("host side effect attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)

    boundary = OscResolumeBoundary()
    state = boundary.initial_state("semantic-light-field-cli-001")
    next_state, overlay = boundary.ingest_semantic_light_field_report(_report(), state)

    assert next_state.lucida_state.vj_state.pending_proposal_ids
    assert overlay["resolume_preview"]["safety"]["external_side_effects"] is False

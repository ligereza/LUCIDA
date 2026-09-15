import json
import os
import socket
import sys
import subprocess
from pathlib import Path

import pytest

from adapters.vj import VJAdapter
from adapters.vj.adapter import VJAdapterError
from adapters.vj.semantic_light_field import SemanticLightFieldBridgeError


XIO_ROOT_VALUE = os.environ.get("LUCIDA_XIO_ROOT")
if not XIO_ROOT_VALUE:
    pytest.skip("set LUCIDA_XIO_ROOT to an explicit XIO checkout", allow_module_level=True)
XIO_ROOT = Path(XIO_ROOT_VALUE).expanduser().resolve()
XIO_SHOWCONTROL = XIO_ROOT / "xio" / "new-plugins" / "showcontrol"
XIO_FIXTURE = XIO_SHOWCONTROL / "fixtures" / "semantic_light_field_replay.json"

if not XIO_FIXTURE.is_file():
    pytest.skip("requires the local XIO semantic light-field fixture", allow_module_level=True)

sys.path.insert(0, str(XIO_SHOWCONTROL))
from semantic_light_field import (  # noqa: E402
    SemanticLightField,
    build_vj_preview_proposal,
    serialize_tape,
)


def _source_artifacts():
    fixture = json.loads(XIO_FIXTURE.read_text(encoding="utf-8"))
    field = SemanticLightField(fixture["fixtures"])
    tape = field.render_tape(fixture["frames"], sample_hz=fixture["sample_hz"])
    proposal = build_vj_preview_proposal(
        tape,
        proposal_id="proposal-light-field-001",
        event_id="event-light-field-001",
    )
    digest = next(item.split(":", 1)[1] for item in proposal["evidence"]
                  if item.startswith("tape_sha256:"))
    return fixture, tape, proposal, digest


def test_replay_json_to_vj_pending_proposal_without_execution():
    _fixture, tape, proposal, digest = _source_artifacts()
    adapter = VJAdapter()
    state = adapter.initial_state("resolume_adapter-semantic-light-field")

    next_state, pending = adapter.ingest_semantic_light_field(
        proposal, state, {digest: tape})

    assert next_state.pending_proposal_ids == ("proposal-light-field-001",)
    assert next_state.metadata["semantic_light_field_pending"][0] == {
        "proposal_id": "proposal-light-field-001",
        "tape_sha256": digest,
        "tape_schema": "farmaxia:semantic-light-field-tape:0.1",
        "frame_count": 2,
        "execution_mode": "proposal_only",
        "status": "pending_approval",
    }
    assert pending["status"] == "pending_approval"
    assert pending["proposal"] == proposal
    assert "frames" not in pending["proposal"]
    assert pending["tape"] == json.loads(serialize_tape(tape))
    assert pending["safety"] == {
        "proposal_only": True,
        "automatic_actions": False,
        "external_side_effects": False,
    }
    assert state.pending_proposal_ids == ()

    rejected = adapter.register_result(
        next_state,
        {
            "result_id": "result-light-field-rejected",
            "proposal_id": "proposal-light-field-001",
            "recorded_at": "2026-09-07T20:00:00Z",
            "status": "rejected",
        },
    )
    assert rejected.pending_proposal_ids == ()
    assert rejected.results[0].status == "rejected"


@pytest.mark.parametrize(
    ("operation", "result_status", "metadata_status"),
    [
        ("approve_proposal", "accepted", "approved"),
        ("reject_proposal", "rejected", "rejected"),
        ("undo_proposal", "skipped", "undone"),
    ],
)
def test_real_adapter_entrypoint_records_explicit_decision(
    operation, result_status, metadata_status
):
    _fixture, tape, proposal, digest = _source_artifacts()
    adapter = VJAdapter()
    state = adapter.initial_state("resolume_adapter-semantic-light-field")
    pending_state, pending = adapter.ingest_semantic_light_field(
        proposal, state, {digest: tape}
    )

    decided = getattr(adapter, operation)(
        pending_state,
        proposal_id=proposal["proposal_id"],
        result_id="result-light-field-" + result_status,
        recorded_at="2026-09-07T20:00:00Z",
    )

    assert pending["proposal"]["execution_mode"] == "proposal_only"
    assert decided.pending_proposal_ids == ()
    assert decided.results[-1].status == result_status
    assert decided.metadata["semantic_light_field_pending"][0]["status"] == metadata_status
    assert decided.metadata["semantic_light_field_pending"][0]["execution_mode"] == "proposal_only"


def test_semantic_light_field_cannot_be_registered_as_executed():
    _fixture, tape, proposal, digest = _source_artifacts()
    adapter = VJAdapter()
    state = adapter.initial_state("resolume_adapter-semantic-light-field")
    pending_state, _pending = adapter.ingest_semantic_light_field(
        proposal, state, {digest: tape}
    )

    with pytest.raises(VJAdapterError, match="proposal_only"):
        adapter.register_result(
            pending_state,
            {
                "result_id": "result-light-field-executed",
                "proposal_id": proposal["proposal_id"],
                "recorded_at": "2026-09-07T20:00:00Z",
                "status": "executed",
            },
        )

    assert pending_state.pending_proposal_ids == (proposal["proposal_id"],)


def test_hash_schema_and_execution_mode_rejections_do_not_mutate_state():
    _fixture, tape, proposal, digest = _source_artifacts()
    adapter = VJAdapter()
    state = adapter.initial_state("resolume_adapter-semantic-light-field")

    wrong_hash = dict(proposal)
    wrong_hash["evidence"] = [
        "tape_sha256:" + ("0" * 64) if item.startswith("tape_sha256:") else item
        for item in proposal["evidence"]
    ]
    with pytest.raises(SemanticLightFieldBridgeError, match="hash"):
        adapter.ingest_semantic_light_field(wrong_hash, state, {digest: tape})

    bad_schema = {**tape, "schema": "farmaxia:wrong-tape:0.1"}
    with pytest.raises(SemanticLightFieldBridgeError, match="schema"):
        adapter.ingest_semantic_light_field(proposal, state, {digest: bad_schema})

    not_proposal_only = {**proposal, "execution_mode": "execute"}
    with pytest.raises((SemanticLightFieldBridgeError, ValueError), match="proposal_only"):
        adapter.ingest_semantic_light_field(not_proposal_only, state, {digest: tape})

    assert state.pending_proposal_ids == ()
    assert state.metadata == {}


def test_bridge_has_no_host_side_effects(monkeypatch):
    _fixture, tape, proposal, digest = _source_artifacts()
    adapter = VJAdapter()
    state = adapter.initial_state("resolume_adapter-semantic-light-field")

    def blocked(*_args, **_kwargs):
        raise AssertionError("host side effect attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)
    next_state, pending = adapter.ingest_semantic_light_field(
        proposal, state, {digest: tape}
    )

    assert next_state.pending_proposal_ids == (proposal["proposal_id"],)
    assert pending["safety"] == {
        "proposal_only": True,
        "automatic_actions": False,
        "external_side_effects": False,
    }

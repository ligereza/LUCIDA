import json
from pathlib import Path

import pytest

from lucida import LucidaOrchestrator
from lucida.contracts import CapabilityReport, LucidaContractError, LucidaState
from lucida.replay import replay_path


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "lucida"
    / "replay"
    / "fixtures"
    / "session-fictional.json"
)


def test_lucida_replay_covers_three_capabilities_on_one_surface():
    report = replay_path(FIXTURE)

    assert report["status"] == "PASS"
    assert report["surface"] == "single-overlay"
    assert report["capabilities_observed"] == ["IMAGO", "INSTAR", "NAYADE"]
    assert report["event_count"] == 7
    assert report["proposal_count"] == 14
    assert report["result_count"] == 14
    assert report["final_state"]["pending_proposal_ids"] == []
    assert report["safety"] == {
        "external_side_effects": False,
        "automatic_actions": False,
        "resolume_opened": False,
    }


def test_single_surface_reports_observed_state_proposals_expected_results_and_unknowns():
    orchestrator = LucidaOrchestrator()
    state = orchestrator.initial_state("session-001")
    state = orchestrator.propose(
        {
            "event_id": "evt-preflight",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preflight",
            "event_type": "phase.completed",
            "payload": {"status": "pass", "media_status": "ready"},
        },
        state,
    )

    overlay = orchestrator.read_overlay(state)
    assert overlay["surface"] == "LUCIDA"
    assert {item["capability"] for item in overlay["capabilities"]} == {
        "INSTAR",
        "NAYADE",
        "IMAGO",
    }
    instar = next(item for item in overlay["capabilities"] if item["capability"] == "INSTAR")
    assert instar["state"]["media_status"] == "ready"
    assert instar["observed_count"] > 0
    assert instar["expected_result_count"] > 0
    assert instar["unknowns"]


def test_public_overlay_uses_bounded_view_without_private_state_or_metadata():
    orchestrator = LucidaOrchestrator()
    state = orchestrator.initial_state(
        "session-private",
        metadata={"credential": "must-not-leak", "private_path": "C:\\secret"},
    )

    overlay = orchestrator.read_overlay(state)
    serialized = json.dumps(overlay, sort_keys=True)

    assert overlay["contract_type"] == "LucidaOverlayView"
    assert "state" not in overlay
    assert "metadata" not in serialized
    assert "must-not-leak" not in serialized
    assert "C:\\secret" not in serialized


def test_replay_is_deterministic():
    assert replay_path(FIXTURE) == replay_path(FIXTURE)


def test_register_result_only_records_external_outcome():
    orchestrator = LucidaOrchestrator()
    state = orchestrator.initial_state("session-001")
    state = orchestrator.propose(
        {
            "event_id": "evt-preflight",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preflight",
            "event_type": "phase.completed",
            "payload": {"status": "pass"},
        },
        state,
    )
    proposal_id = state.vj_state.pending_proposal_ids[0]
    next_state = orchestrator.register_result(
        state,
        {
            "result_id": "res-001",
            "proposal_id": proposal_id,
            "recorded_at": "2026-01-10T20:01:00Z",
            "status": "observed",
        },
    )

    assert next_state.vj_state.results[-1].result_id == "res-001"
    assert proposal_id not in next_state.vj_state.pending_proposal_ids
    assert not hasattr(orchestrator, "execute")


def test_lucida_state_restore_rejects_divergent_pending_projection():
    orchestrator = LucidaOrchestrator()
    state = orchestrator.propose(
        {
            "event_id": "evt-preflight",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preflight",
            "event_type": "phase.completed",
            "payload": {},
        },
        orchestrator.initial_state("session-001"),
    )
    raw = state.to_dict()
    raw["pending_proposal_ids"] = []

    with pytest.raises(LucidaContractError, match="pending_proposal_ids"):
        LucidaState.from_dict(raw)


def test_lucida_state_restore_rejects_pending_proposal_without_global_record():
    orchestrator = LucidaOrchestrator()
    state = orchestrator.propose(
        {
            "event_id": "evt-preflight",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preflight",
            "event_type": "phase.completed",
            "payload": {},
        },
        orchestrator.initial_state("session-001"),
    )
    raw = state.to_dict()
    raw["proposals"] = []
    for capability in raw["capabilities"]:
        capability["proposals"] = []

    with pytest.raises(LucidaContractError, match="propuesta pendiente"):
        LucidaState.from_dict(raw)


@pytest.mark.parametrize("mutation", ["duplicate", "missing"])
def test_lucida_state_restore_requires_all_capabilities_once(mutation):
    state = LucidaOrchestrator().initial_state("session-001")
    raw = state.to_dict()
    if mutation == "duplicate":
        raw["capabilities"][1]["capability"] = "INSTAR"
    else:
        raw["capabilities"] = raw["capabilities"][:2]

    with pytest.raises(LucidaContractError, match="capabilities"):
        LucidaState.from_dict(raw)


@pytest.mark.parametrize("mutation", ["missing_global", "duplicate_capability"])
def test_lucida_state_restore_binds_capability_proposals_to_global_list(mutation):
    orchestrator = LucidaOrchestrator()
    state = orchestrator.propose(
        {
            "event_id": "evt-preflight",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preflight",
            "event_type": "phase.completed",
            "payload": {},
        },
        orchestrator.initial_state("session-001"),
    )
    raw = state.to_dict()
    if mutation == "missing_global":
        raw["proposals"] = []
        raw["pending_proposal_ids"] = []
        raw["vj_state"]["pending_proposal_ids"] = []
    else:
        proposal = raw["capabilities"][0]["proposals"][0]
        raw["capabilities"][0]["proposals"].append(proposal)

    expected_message = (
        "propuesta de capacidad"
        if mutation == "missing_global"
        else "propuestas de capacidades"
    )
    with pytest.raises(LucidaContractError, match=expected_message):
        LucidaState.from_dict(raw)


@pytest.mark.parametrize("unsafe_value", [{"nested": {1, 2}}, float("nan")])
def test_lucida_state_restore_rejects_non_json_capability_state(unsafe_value):
    raw = LucidaOrchestrator().initial_state("session-001").to_dict()
    raw["capabilities"][0]["state"]["unsafe"] = unsafe_value

    with pytest.raises(LucidaContractError, match="JSON serializables"):
        LucidaState.from_dict(raw)


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_lucida_state_restore_requires_schema_fields_exactly(mutation):
    raw = LucidaOrchestrator().initial_state("session-001").to_dict()
    if mutation == "missing":
        del raw["capabilities"]
    else:
        raw["unexpected"] = True

    with pytest.raises(LucidaContractError, match="campos no soportados o faltantes"):
        LucidaState.from_dict(raw)


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_capability_report_restore_requires_schema_fields_exactly(mutation):
    raw = LucidaOrchestrator().initial_state("session-001").to_dict()["capabilities"][0]
    if mutation == "missing":
        del raw["unknowns"]
    else:
        raw["unexpected"] = True

    with pytest.raises(LucidaContractError, match="campos no soportados o faltantes"):
        CapabilityReport.from_dict(raw)


def test_fixture_contains_only_fictional_session_data():
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    serialized = json.dumps(document)

    assert "C:\\" not in serialized
    assert "Z:\\" not in serialized
    assert ".mp4" not in serialized
    assert ".avc" not in serialized

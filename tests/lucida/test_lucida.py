import json
from pathlib import Path

from lucida import LucidaOrchestrator
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
    assert instar["observed"]
    assert instar["state"]["media_status"] == "ready"
    assert instar["proposals"]
    assert instar["expected_results"]
    assert instar["unknowns"]


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


def test_fixture_contains_only_fictional_session_data():
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    serialized = json.dumps(document)

    assert "C:\\" not in serialized
    assert "Z:\\" not in serialized
    assert ".mp4" not in serialized
    assert ".avc" not in serialized

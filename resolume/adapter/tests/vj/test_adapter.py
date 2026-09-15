import json
from pathlib import Path

import pytest

from adapters.vj import VJAdapter
from adapters.vj.adapter import VJAdapterError
from adapters.vj.contracts import VJEvent, VJProposal, VJState
from adapters.vj.contracts.models import ContractError
from adapters.vj.replay import replay_fixture, replay_path


FIXTURE = Path(__file__).resolve().parents[2] / "adapters" / "vj" / "replay" / "fixtures" / "session-fictional.json"


def test_replay_covers_full_vj_lifecycle_without_side_effects():
    report = replay_path(FIXTURE)

    assert report["status"] == "PASS"
    assert report["phase_order"] == [
        "preflight",
        "preparation",
        "show",
        "incident",
        "recovery",
        "recovery",
        "closure",
    ]
    assert report["event_count"] == 7
    assert report["proposal_count"] == 7
    assert report["result_count"] == 7
    assert report["final_state"]["pending_proposal_ids"] == []
    assert report["final_state"]["open_incidents"] == []
    assert report["safety"] == {
        "external_side_effects": False,
        "irreversible_actions_executed": False,
        "all_proposals_require_explicit_approval": True,
    }


def test_every_proposal_is_explicit_and_recoverable():
    report = replay_path(FIXTURE)
    proposals = [
        proposal
        for transition in report["transitions"]
        for proposal in transition["proposals"]
    ]

    assert proposals
    assert all(proposal["requires_explicit_approval"] for proposal in proposals)
    assert all(proposal["reversible"] for proposal in proposals)
    assert all(proposal["execution_mode"] == "proposal_only" for proposal in proposals)


def test_replay_is_deterministic_for_the_same_fixture():
    first = replay_path(FIXTURE)
    second = replay_path(FIXTURE)

    assert first == second


def test_out_of_order_event_is_rejected():
    adapter = VJAdapter()
    state = adapter.initial_state("session-001")
    state, _ = adapter.process(
        {
            "event_id": "evt-001",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preflight",
            "event_type": "phase.completed",
            "payload": {"status": "pass"},
        },
        state,
    )

    with pytest.raises(VJAdapterError, match="orden temporal"):
        adapter.process(
            {
                "event_id": "evt-002",
                "timestamp": "2026-01-10T19:59:00Z",
                "phase": "preflight",
                "event_type": "phase.completed",
                "payload": {"status": "pass"},
            },
            state,
        )


def test_observational_event_falls_back_to_phase_status():
    adapter = VJAdapter()
    state = VJState(session_id="session-001", phase="show", status="showing")

    state, proposals = adapter.process(
        {
            "event_id": "evt-001",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "closure",
            "event_type": "snapshot.observed",
            "payload": {},
        },
        state,
    )

    assert state.status == "closed"
    assert proposals == ()


def test_result_must_reference_a_pending_proposal():
    adapter = VJAdapter()
    state = adapter.initial_state("session-001")

    with pytest.raises(VJAdapterError, match="no pendiente"):
        adapter.register_result(
            state,
            {
                "result_id": "res-unknown",
                "proposal_id": "proposal-unknown",
                "recorded_at": "2026-01-10T20:01:00Z",
                "status": "accepted",
            },
        )


@pytest.mark.parametrize("sequence", [True, "3", -1])
def test_state_restore_rejects_ambiguous_or_negative_sequence(sequence):
    with pytest.raises(ContractError, match="sequence"):
        VJState.from_dict({"session_id": "session-001", "sequence": sequence})


def test_state_restore_keeps_valid_sequence_without_coercion():
    state = VJState.from_dict({"session_id": "session-001", "sequence": 3})

    assert state.sequence == 3


def test_proposal_restore_rejects_schema_extra_and_missing_required_fields():
    proposal = {
        "proposal_id": "proposal-001",
        "event_id": "event-001",
        "phase": "preflight",
        "operation": "review",
        "reason": "Check the signal.",
        "risk": "low",
        "requires_explicit_approval": True,
        "reversible": True,
        "execution_mode": "proposal_only",
    }

    with pytest.raises(ContractError, match="campos no soportados o faltantes"):
        VJProposal.from_dict({**proposal, "unexpected": True})

    with pytest.raises(ContractError, match="campos no soportados o faltantes"):
        VJProposal.from_dict({key: value for key, value in proposal.items() if key != "risk"})


@pytest.mark.parametrize(
    ("field", "value"),
    [("last_event_id", 7), ("last_timestamp", "not-a-timestamp"), ("checkpoint_id", False)],
)
def test_state_restore_rejects_invalid_optional_identity_fields(field, value):
    with pytest.raises(ContractError, match=field):
        VJState.from_dict({"session_id": "session-001", field: value})


def test_incident_proposal_only_captures_evidence():
    adapter = VJAdapter()
    state = adapter.initial_state("session-001")
    state, _ = adapter.process(
        {
            "event_id": "evt-001",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preflight",
            "event_type": "phase.completed",
            "payload": {"status": "pass"},
        },
        state,
    )
    state, proposals = adapter.process(
        {
            "event_id": "evt-002",
            "timestamp": "2026-01-10T20:01:00Z",
            "phase": "preparation",
            "event_type": "phase.completed",
            "payload": {"status": "pass"},
        },
        state,
    )
    state, proposals = adapter.process(
        {
            "event_id": "evt-003",
            "timestamp": "2026-01-10T20:02:00Z",
            "phase": "show",
            "event_type": "show.started",
            "payload": {},
        },
        state,
    )
    _, proposals = adapter.process(
        {
            "event_id": "evt-004",
            "timestamp": "2026-01-10T20:03:00Z",
            "phase": "incident",
            "event_type": "incident.detected",
            "payload": {"category": "flicker", "symptoms": ["visible scan lines"]},
        },
        state,
    )

    assert len(proposals) == 1
    assert proposals[0].operation == "capture-incident"
    assert proposals[0].execution_mode == "proposal_only"
    assert "no-write" in proposals[0].evidence


def test_fixture_has_no_personal_media_or_machine_paths():
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    serialized = json.dumps(document)

    assert "C:\\" not in serialized
    assert "Z:\\" not in serialized
    assert ".mp4" not in serialized
    assert ".avc" not in serialized

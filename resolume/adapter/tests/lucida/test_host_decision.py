import json

import pytest

from adapters.vj.contracts import VJEvent, VJProposal
from lucida.host.decision import (
    DecisionContractError,
    ProposalDecision,
    ProposalDecisionRecorder,
)
from lucida.replay import validate_public_report
from lucida.replay.session import SessionReplay, SignalEnvelope


def _decision(**overrides):
    value = {
        "decision_id": "decision-001",
        "proposal_id": "proposal-001",
        "status": "accepted",
        "reason": "Host approved the reversible proposal.",
        "sequence": 1,
        "timestamp": "2026-01-10T20:01:00Z",
        "source": "host-test",
        "explicit_confirmation": True,
        "provenance": {"operator": "fixture"},
    }
    value.update(overrides)
    return value


def test_accepted_decision_round_trip():
    decision = ProposalDecision.from_dict(_decision())

    assert ProposalDecision.from_dict(decision.to_dict()) == decision
    assert decision.status == "accepted"
    assert decision.explicit_confirmation is True


def test_rejected_decision_requires_explicit_confirmation():
    decision = ProposalDecision.from_dict(_decision(status="rejected"))

    assert decision.status == "rejected"

    with pytest.raises(DecisionContractError, match="require explicit confirmation"):
        ProposalDecision.from_dict(_decision(status="rejected", explicit_confirmation=False))


def test_unknown_decision_cannot_claim_confirmation():
    decision = ProposalDecision.from_dict(
        _decision(status="unknown", reason="Host did not provide a decision.", explicit_confirmation=False)
    )

    assert decision.status == "unknown"

    with pytest.raises(DecisionContractError, match="cannot have explicit confirmation"):
        ProposalDecision.from_dict(_decision(status="unknown", explicit_confirmation=True))


def test_missing_confirmation_is_rejected():
    raw = _decision()
    del raw["explicit_confirmation"]

    with pytest.raises(DecisionContractError, match="missing fields"):
        ProposalDecision.from_dict(raw)


def test_invalid_proposal_id_is_rejected():
    with pytest.raises(DecisionContractError, match="proposal_id"):
        ProposalDecision.from_dict(_decision(proposal_id=""))


def test_invalid_timestamp_and_sequence_are_rejected():
    with pytest.raises(DecisionContractError, match="timezone"):
        ProposalDecision.from_dict(_decision(timestamp="2026-01-10T20:01:00"))

    with pytest.raises(DecisionContractError, match="positive integer"):
        ProposalDecision.from_dict(_decision(sequence=0))


def test_recorder_adds_audit_receipt_without_mutating_proposal():
    replay = SessionReplay("session-001")
    proposal = VJProposal(
        proposal_id="proposal-001",
        event_id="event-001",
        phase="preflight",
        operation="review",
        reason="Review a reversible proposal.",
    )
    original_proposal = proposal.to_dict()
    recorder = ProposalDecisionRecorder(audit_sink=replay.record_audit)

    decision = recorder.record(_decision(proposal_id=proposal.proposal_id))

    assert proposal.to_dict() == original_proposal
    assert recorder.decisions == (decision,)
    assert replay.state.lucida_state.proposals == ()
    assert replay.state.audit_log[-1]["decision_id"] == decision.decision_id
    assert replay.state.audit_log[-1]["execution_asserted"] is False
    assert replay.state.audit_log[-1]["mode"] == "proposal_only"
    assert not hasattr(decision, "execute")


def test_recorder_rejects_duplicate_decision_id_without_second_audit_entry():
    replay = SessionReplay("session-001")
    recorder = ProposalDecisionRecorder(audit_sink=replay.record_audit)

    recorder.record(_decision())

    with pytest.raises(DecisionContractError, match="duplicate decision_id"):
        recorder.record(_decision())

    assert len(recorder.decisions) == 1
    assert len(replay.state.audit_log) == 1


def test_public_replay_preserves_only_safe_host_decision_status():
    replay = SessionReplay("session-001")
    replay.append(
        VJEvent(
            event_id="event-001",
            timestamp="2026-01-10T20:00:00Z",
            phase="preflight",
            event_type="phase.completed",
            payload={"private": "must-not-share"},
            source="host-test",
        ),
        SignalEnvelope(
            envelope_id="signal-001",
            event_id="event-001",
            timestamp="2026-01-10T20:00:00Z",
            sequence=1,
            source="host-test",
            address="/lucida/instar/preflight",
            arguments=("private-argument",),
            transport="osc",
        ),
    )
    recorder = ProposalDecisionRecorder(audit_sink=replay.record_audit)
    recorder.record(
        _decision(
            proposal_id="lucida-instar-event-001-checkpoint-preflight",
            provenance={"private": "must-not-share"},
            reason="Private host reason.",
        )
    )

    public = replay.public_report()
    validate_public_report(public)
    serialized = json.dumps(public, sort_keys=True)

    assert any(item.get("status") == "accepted" for item in public["audit_log"])
    assert all("decision_id" not in item for item in public["audit_log"])
    assert all("reason" not in item for item in public["audit_log"])
    assert "must-not-share" not in serialized
    assert "private-argument" not in serialized

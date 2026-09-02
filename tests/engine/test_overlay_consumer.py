from __future__ import annotations

from dataclasses import replace

import pytest

from lucida.engine import (
    AdapterRegistry,
    ContractRegistry,
    LucidaPipeline,
    OverlayConsumerConflictError,
    OverlayConsumerError,
    OverlayConsumerGapError,
    OverlayConsumerNotInitializedError,
    OverlayConsumerStaleError,
    OverlayFrame,
    OverlayFrameConsumer,
    OverlayFrameError,
    build_overlay_frame,
    overlay_frame_digest,
    register_vizz_pupila_routes,
    validate_overlay_frame,
)


def _frame():
    adapters = AdapterRegistry()
    contracts = ContractRegistry()
    register_vizz_pupila_routes(adapters, contracts)
    pipeline = LucidaPipeline(adapters, contracts)
    state = pipeline.initial_state("consumer-session")
    value = {
        "session_id": "consumer-session",
        "event_id": "pupila-consumer-1",
        "timestamp": "2026-09-02T12:00:00Z",
        "sequence": 1,
        "event_type": "coordination.proposal",
        "summary": {"participant_count": 2, "proposal_kind": "shared-checkpoint", "proposal_state": "proposed"},
        "proposal": {
            "proposal_id": "consumer-proposal-1",
            "kind": "shared_checkpoint",
            "title": "Shared checkpoint",
            "body": "Review this proposal",
            "priority": 60,
            "ttl_ms": 3000,
            "requires_confirmation": True,
            "reversible": True,
        },
    }
    plan = pipeline.apply(
        adapter_id="pupila.coordination",
        contract_id="pupila.coordination.v1",
        value=value,
        state=state,
    ).plan
    return build_overlay_frame(plan)


def test_overlay_frame_direct_construction_enforces_safety():
    with pytest.raises(OverlayFrameError, match="safety flags"):
        OverlayFrame(
            session_id="session-1",
            revision=0,
            automatic_actions=True,
        )
    with pytest.raises(OverlayFrameError, match="transparent"):
        OverlayFrame(
            session_id="session-1",
            revision=0,
            click_through=False,
        )


def test_overlay_frame_round_trip_and_digest_are_deterministic():
    frame = _frame()
    serialized = frame.to_dict()

    assert validate_overlay_frame(serialized) == frame
    assert overlay_frame_digest(frame) == overlay_frame_digest(serialized)


def test_consumer_requires_snapshot_before_updates():
    consumer = OverlayFrameConsumer()

    with pytest.raises(OverlayConsumerNotInitializedError):
        consumer.apply_frame(_frame())


def test_consumer_accepts_snapshot_and_next_revision_atomically():
    consumer = OverlayFrameConsumer()
    frame = _frame()
    consumer.accept_snapshot(frame)
    next_frame = replace(frame, revision=frame.revision + 1)

    state = consumer.apply_frame(next_frame)

    assert state.initialized is True
    assert state.applied_frame_count == 1
    assert state.last_operation == "frame"
    assert state.frame == next_frame.to_dict()


def test_consumer_accepts_exact_duplicate_but_rejects_same_revision_conflict():
    consumer = OverlayFrameConsumer()
    frame = _frame()
    consumer.accept_snapshot(frame)

    duplicate = consumer.apply_frame(frame)
    assert duplicate.last_operation == "duplicate"
    assert duplicate.applied_frame_count == 0

    conflicting = replace(frame, warnings=("Review warning",))
    with pytest.raises(OverlayConsumerConflictError, match="same revision"):
        consumer.apply_frame(conflicting)
    assert consumer.frame == frame.to_dict()


def test_consumer_rejects_stale_and_gap_revisions():
    consumer = OverlayFrameConsumer()
    frame = _frame()
    consumer.accept_snapshot(frame)

    with pytest.raises(OverlayConsumerStaleError):
        consumer.apply_frame(replace(frame, revision=frame.revision - 1))
    with pytest.raises(OverlayConsumerGapError):
        consumer.apply_frame(replace(frame, revision=frame.revision + 2))


def test_consumer_rejects_tampered_safety_and_keeps_state():
    consumer = OverlayFrameConsumer()
    frame = _frame()
    consumer.accept_snapshot(frame)
    before = consumer.state
    tampered = frame.to_dict()
    tampered["blocking"] = True
    tampered["revision"] = frame.revision + 1

    with pytest.raises(OverlayConsumerError, match="transparent|blocking|click-through"):
        consumer.apply_frame(tampered)
    assert consumer.state == before


def test_recovery_snapshot_can_replace_frame_without_incrementing_count():
    consumer = OverlayFrameConsumer()
    frame = _frame()
    consumer.accept_snapshot(frame)
    replacement = replace(frame, revision=99)

    state = consumer.accept_snapshot(replacement, recovery=True)

    assert state.frame == replacement.to_dict()
    assert state.applied_frame_count == 0
    assert state.last_operation == "recovery_snapshot"

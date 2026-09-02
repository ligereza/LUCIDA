import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lucida.engine import EngineError, LucidaEngine
from lucida.engine.replay import replay_path


FIXTURE = Path(__file__).parent / "fixtures" / "mixed-input.json"


def _event(source="xio", event_id="event-001", sequence=1, timestamp="2026-09-02T12:00:00Z"):
    return {
        "session_id": "session-001",
        "event_id": event_id,
        "timestamp": timestamp,
        "sequence": sequence,
        "source": source,
        "event_type": "state.changed",
        "summary": {"status": "ready"},
    }


def _proposal(event_id="event-001", proposal_id="proposal-001"):
    return {
        "proposal_id": proposal_id,
        "kind": "next_step",
        "title": "Review",
        "body": "Review this proposal",
        "priority": 50,
        "ttl_ms": 1000,
        "requires_confirmation": True,
        "reversible": True,
    }


def test_engine_replays_mixed_sources_without_domain_imports():
    first = replay_path(FIXTURE)
    second = replay_path(FIXTURE)
    assert first == second
    assert first["event_count"] == 3
    assert first["state"]["revision"] == 3
    assert first["final_plan"]["automatic_actions"] is False
    assert first["final_plan"]["raw_payload_forwarded"] is False
    assert [item["source"] for item in first["final_plan"]["items"]] == ["mosaik", "pupila"]


def test_engine_keeps_order_per_source_and_allows_independent_sources():
    engine = LucidaEngine()
    state = engine.initial_state("session-001")
    state, _ = engine.apply(_event(source="xio", event_id="xio-1"), state)
    state, _ = engine.apply(_event(source="mosaik", event_id="mosaik-1"), state)
    assert state.revision == 2
    with pytest.raises(EngineError):
        engine.apply(_event(source="xio", event_id="xio-duplicate", sequence=1), state)


def test_engine_records_sequence_gap_without_fabricating_missing_events():
    engine = LucidaEngine()
    state = engine.initial_state("session-001")
    state, _ = engine.apply(_event(sequence=1), state)
    state, _ = engine.apply(_event(event_id="event-003", sequence=3), state)
    assert "sequence_gap:xio:2-2" in state.warnings
    assert "event-002" not in state.seen_event_ids


def test_engine_expires_proposal_at_explicit_time():
    engine = LucidaEngine()
    state = engine.initial_state("session-001")
    event = _event()
    event["proposal"] = _proposal()
    state, plan = engine.apply(event, state)
    assert len(plan.items) == 1
    future = (datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")) + timedelta(seconds=2)).isoformat().replace("+00:00", "Z")
    assert engine.render_plan(state, at=future).items == ()


def test_engine_prunes_expired_proposals_when_a_later_event_arrives():
    engine = LucidaEngine()
    state = engine.initial_state("session-001")
    first = _event()
    first["proposal"] = _proposal()
    state, _ = engine.apply(first, state)

    later = _event(
        event_id="event-002",
        sequence=2,
        timestamp="2026-09-02T12:00:02Z",
    )
    state, plan = engine.apply(later, state)

    assert state.active_proposals == ()
    assert plan.items == ()


def test_engine_rejects_unsafe_proposal():
    engine = LucidaEngine()
    state = engine.initial_state("session-001")
    event = _event()
    unsafe = _proposal()
    unsafe["requires_confirmation"] = False
    event["proposal"] = unsafe
    with pytest.raises(EngineError):
        engine.apply(event, state)


def test_engine_does_not_accept_nested_raw_payload():
    engine = LucidaEngine()
    state = engine.initial_state("session-001")
    event = _event()
    event["summary"] = {"nested": {"raw": "payload"}}
    with pytest.raises(EngineError):
        engine.apply(event, state)

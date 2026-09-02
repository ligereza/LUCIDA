from __future__ import annotations

from dataclasses import replace

import pytest

from lucida.engine import (
    AdapterRegistry,
    ContractRegistry,
    LucidaPipeline,
    RenderPlan,
    build_overlay_frame,
    register_vizz_pupila_routes,
)
from lucida.engine.overlay_frame import OverlayFrameError


def _plan() -> RenderPlan:
    adapters = AdapterRegistry()
    contracts = ContractRegistry()
    register_vizz_pupila_routes(adapters, contracts)
    pipeline = LucidaPipeline(adapters, contracts)
    state = pipeline.initial_state("frame-session")
    value = {
        "session_id": "frame-session",
        "event_id": "pupila-frame-1",
        "timestamp": "2026-09-02T12:00:00Z",
        "sequence": 1,
        "event_type": "coordination.proposal",
        "summary": {"participant_count": 2, "proposal_kind": "shared-checkpoint", "proposal_state": "proposed"},
        "proposal": {
            "proposal_id": "frame-proposal-1",
            "kind": "shared_checkpoint",
            "title": "Shared checkpoint",
            "body": "Review this proposal",
            "priority": 60,
            "ttl_ms": 3000,
            "requires_confirmation": True,
            "reversible": True,
        },
    }
    return pipeline.apply(
        adapter_id="pupila.coordination",
        contract_id="pupila.coordination.v1",
        value=value,
        state=state,
    ).plan


def test_overlay_frame_is_transparent_click_through_and_read_only():
    frame = build_overlay_frame(_plan()).to_dict()

    assert frame["contract_type"] == "LucidaOverlayFrame"
    assert frame["transparent"] is True
    assert frame["click_through"] is True
    assert frame["blocking"] is False
    assert frame["safety"] == {
        "proposal_only": True,
        "automatic_actions": False,
        "external_side_effects": False,
    }
    assert len(frame["elements"]) == 1


def test_overlay_frame_is_deterministic():
    first = build_overlay_frame(_plan()).to_dict()
    second = build_overlay_frame(_plan()).to_dict()

    assert first == second


def test_overlay_frame_accepts_empty_plan():
    frame = build_overlay_frame(RenderPlan(session_id="empty-session", revision=0)).to_dict()

    assert frame["elements"] == []
    assert frame["click_through"] is True


def test_overlay_frame_rejects_unsafe_plan_flags():
    with pytest.raises(OverlayFrameError, match="safety flags"):
        build_overlay_frame(replace(_plan(), automatic_actions=True))
    with pytest.raises(OverlayFrameError, match="safety flags"):
        build_overlay_frame(replace(_plan(), raw_payload_forwarded=True))


def test_overlay_frame_rejects_extra_item_fields():
    plan = _plan()
    unsafe_item = {**plan.items[0], "action": "execute"}

    with pytest.raises(OverlayFrameError, match="unsupported fields"):
        build_overlay_frame(replace(plan, items=(unsafe_item,)))


def test_overlay_frame_rejects_non_iso_expiry_and_non_ascii_text():
    plan = _plan()
    bad_expiry = {**plan.items[0], "expires_at": "later"}
    with pytest.raises(OverlayFrameError, match="ISO-8601"):
        build_overlay_frame(replace(plan, items=(bad_expiry,)))

    bad_text = {**plan.items[0], "body": "bad " + chr(0xF3)}
    with pytest.raises(OverlayFrameError, match="ASCII"):
        build_overlay_frame(replace(plan, items=(bad_text,)))

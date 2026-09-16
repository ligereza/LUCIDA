import pytest

from lucida.engine import (
    AdapterRegistry,
    ContractRegistry,
    DomainAdapterError,
    LucidaPipeline,
    register_resolume_route,
)


def _pipeline() -> LucidaPipeline:
    adapters = AdapterRegistry()
    contracts = ContractRegistry()
    register_resolume_route(adapters, contracts)
    return LucidaPipeline(adapters, contracts)


def _candidate() -> dict:
    return {
        "session_id": "resolume-session-001",
        "event_id": "resolume-event-001",
        "timestamp": "2026-09-16T20:00:00Z",
        "sequence": 1,
        "event_type": "preview.candidate",
        "summary": {
            "surface_id": "LED_MAIN",
            "strategy": "crop",
            "quality": 0.92,
            "proposal_count": 1,
        },
        "proposal": {
            "proposal_id": "proposal-resolume-001",
            "kind": "preview",
            "title": "Review crop preview",
            "body": "Compare the crop preview with the approved mapping.",
            "priority": 80,
            "ttl_ms": 3000,
            "requires_confirmation": True,
            "reversible": True,
        },
    }


def test_resolume_candidate_reaches_common_render_plan():
    pipeline = _pipeline()
    state = pipeline.initial_state("resolume-session-001")

    transition = pipeline.apply(
        adapter_id="resolume.state",
        contract_id="resolume.show.v1",
        value=_candidate(),
        state=state,
    )

    assert transition.event.source == "resolume"
    assert transition.event.capabilities == ("observe.show",)
    assert transition.plan.items[0]["item_id"] == "proposal-resolume-001"
    assert transition.plan.automatic_actions is False
    assert transition.plan.raw_payload_forwarded is False


def test_resolume_route_rejects_raw_or_wrong_phase_proposals():
    pipeline = _pipeline()
    state = pipeline.initial_state("resolume-session-001")

    wrong_phase = _candidate()
    wrong_phase["event_type"] = "show.state"
    with pytest.raises(DomainAdapterError):
        pipeline.apply(
            adapter_id="resolume.state",
            contract_id="resolume.show.v1",
            value=wrong_phase,
            state=state,
        )

    raw = _candidate()
    raw["raw_payload"] = {"composition": "private.avc"}
    with pytest.raises(DomainAdapterError):
        pipeline.apply(
            adapter_id="resolume.state",
            contract_id="resolume.show.v1",
            value=raw,
            state=state,
        )

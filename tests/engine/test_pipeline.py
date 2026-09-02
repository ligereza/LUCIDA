from __future__ import annotations

import pytest

from lucida.engine import (
    AdapterRegistry,
    ContractRegistry,
    EngineEvent,
    InputContract,
    InputContractError,
    LucidaPipeline,
)


EVENT = {
    "session_id": "session-1",
    "event_id": "event-1",
    "timestamp": "2026-09-02T12:00:00Z",
    "sequence": 1,
    "source": "test.source",
    "source_version": "1",
    "event_type": "state.changed",
    "capabilities": ["observe.state"],
}


class StaticAdapter:
    adapter_id = "test.static"

    def adapt(self, value):
        return EngineEvent.from_dict(value)


def make_pipeline():
    adapters = AdapterRegistry()
    adapters.register(StaticAdapter())
    contracts = ContractRegistry()
    contracts.register(
        InputContract(
            contract_id="test.contract.v1",
            source="test.source",
            source_version="1",
            event_types=("state.changed",),
            capabilities=("observe.state",),
        )
    )
    return LucidaPipeline(adapters, contracts)


def test_pipeline_requires_both_explicit_routes_and_returns_provenance():
    pipeline = make_pipeline()
    state = pipeline.initial_state("session-1")

    transition = pipeline.apply(
        adapter_id="test.static",
        contract_id="test.contract.v1",
        value=EVENT,
        state=state,
    )

    assert transition.adapter_id == "test.static"
    assert transition.contract_id == "test.contract.v1"
    assert transition.event.event_id == "event-1"
    assert transition.state.revision == 1
    assert transition.plan.automatic_actions is False


def test_contract_rejection_happens_before_reducer():
    pipeline = make_pipeline()
    state = pipeline.initial_state("session-1")

    with pytest.raises(InputContractError, match="event_type"):
        pipeline.apply(
            adapter_id="test.static",
            contract_id="test.contract.v1",
            value={**EVENT, "event_type": "undeclared.event"},
            state=state,
        )

    assert state.revision == 0
    assert state.seen_event_ids == ()


def test_pipeline_does_not_infer_an_adapter_or_contract():
    pipeline = make_pipeline()
    state = pipeline.initial_state("session-1")

    with pytest.raises(ValueError, match="unknown adapter"):
        pipeline.apply(
            adapter_id="other.adapter",
            contract_id="test.contract.v1",
            value=EVENT,
            state=state,
        )
    with pytest.raises(InputContractError, match="unknown contract"):
        pipeline.apply(
            adapter_id="test.static",
            contract_id="other.contract.v1",
            value=EVENT,
            state=state,
        )

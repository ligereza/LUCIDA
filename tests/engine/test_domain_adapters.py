from __future__ import annotations

import json

import pytest

from lucida.engine import (
    AdapterRegistry,
    ContractRegistry,
    LucidaPipeline,
    replay_pipeline_fixture,
)
from lucida.engine.domain_adapters import (
    DomainAdapterError,
    PUPILA_ADAPTER_ID,
    PUPILA_CONTRACT_ID,
    VIZZ_ADAPTER_ID,
    VIZZ_CONTRACT_ID,
    register_vizz_pupila_routes,
)


def _registries() -> tuple[AdapterRegistry, ContractRegistry]:
    adapters = AdapterRegistry()
    contracts = ContractRegistry()
    register_vizz_pupila_routes(adapters, contracts)
    return adapters, contracts


def _vizz_event(event_id: str = "vizz-1", sequence: int = 1) -> dict[str, object]:
    return {
        "session_id": "domain-session",
        "event_id": event_id,
        "timestamp": f"2026-09-02T12:00:0{sequence}Z",
        "sequence": sequence,
        "event_type": "focus.state",
        "summary": {"focused": True, "confidence": 0.9, "signal_age_ms": 20},
    }


def _pupila_event(event_id: str = "pupila-1", sequence: int = 1) -> dict[str, object]:
    return {
        "session_id": "domain-session",
        "event_id": event_id,
        "timestamp": f"2026-09-02T12:00:0{sequence}Z",
        "sequence": sequence,
        "event_type": "coordination.proposal",
        "summary": {"participant_count": 2, "proposal_kind": "shared-checkpoint", "proposal_state": "proposed"},
        "proposal": {
            "proposal_id": "pupila-proposal-1",
            "kind": "shared_checkpoint",
            "title": "Shared checkpoint",
            "body": "Review the next shared step",
            "priority": 60,
            "ttl_ms": 1000,
            "requires_confirmation": True,
            "reversible": True,
        },
    }


def test_registers_explicit_vizz_and_pupila_routes():
    adapters, contracts = _registries()

    assert adapters.snapshot() == (PUPILA_ADAPTER_ID, VIZZ_ADAPTER_ID)
    assert [item["contract_id"] for item in contracts.snapshot()] == [
        PUPILA_CONTRACT_ID,
        VIZZ_CONTRACT_ID,
    ]


def test_vizz_adapter_accepts_only_redacted_metadata():
    adapters, contracts = _registries()
    event = adapters.adapt(VIZZ_ADAPTER_ID, _vizz_event())
    contracts.validate(VIZZ_CONTRACT_ID, event)

    assert event.source == "vizz"
    assert event.capabilities == ("observe.perception",)
    assert event.summary["focused"] is True


def test_vizz_adapter_rejects_coordinates_and_raw_fields():
    adapters, _ = _registries()
    value = _vizz_event()
    value["summary"] = {"focused": True, "gaze_x": 0.5}

    with pytest.raises(DomainAdapterError, match="undeclared keys"):
        adapters.adapt(VIZZ_ADAPTER_ID, value)


def test_vizz_adapter_rejects_non_finite_metadata():
    adapters, _ = _registries()
    value = _vizz_event()
    value["summary"] = {"focused": True, "confidence": float("nan")}

    with pytest.raises(DomainAdapterError, match="finite"):
        adapters.adapt(VIZZ_ADAPTER_ID, value)


def test_domain_adapters_reject_unhashable_event_type_as_contract_error():
    adapters, _ = _registries()
    value = _vizz_event()
    value["event_type"] = ["focus.state"]

    with pytest.raises(DomainAdapterError, match="event_type"):
        adapters.adapt(VIZZ_ADAPTER_ID, value)


def test_pupila_adapter_accepts_a_reversible_proposal():
    adapters, contracts = _registries()
    event = adapters.adapt(PUPILA_ADAPTER_ID, _pupila_event())
    contracts.validate(PUPILA_CONTRACT_ID, event)

    assert event.proposal is not None
    assert event.proposal.requires_confirmation is True
    assert event.proposal.reversible is True


def test_pupila_adapter_rejects_executable_proposal_fields():
    adapters, _ = _registries()
    value = _pupila_event()
    value["proposal"] = {**value["proposal"], "action": "run"}

    with pytest.raises(DomainAdapterError, match="undeclared keys"):
        adapters.adapt(PUPILA_ADAPTER_ID, value)


def test_pupila_state_cannot_smuggle_a_proposal():
    adapters, _ = _registries()
    value = _pupila_event()
    value["event_type"] = "coordination.state"
    value["summary"] = {"participant_count": 2, "proposal_count": 1}

    with pytest.raises(DomainAdapterError, match="cannot carry"):
        adapters.adapt(PUPILA_ADAPTER_ID, value)


def test_pipeline_composes_vizz_observation_and_pupila_proposal():
    adapters, contracts = _registries()
    pipeline = LucidaPipeline(adapters, contracts)
    state = pipeline.initial_state("domain-session")

    first = pipeline.apply(
        adapter_id=VIZZ_ADAPTER_ID,
        contract_id=VIZZ_CONTRACT_ID,
        value=_vizz_event(),
        state=state,
    )
    second = pipeline.apply(
        adapter_id=PUPILA_ADAPTER_ID,
        contract_id=PUPILA_CONTRACT_ID,
        value=_pupila_event(),
        state=first.state,
    )

    assert second.state.revision == 2
    assert len(second.plan.items) == 1
    assert second.plan.items[0]["source"] == "pupila"


def test_domain_pipeline_replay_is_deterministic_and_side_effect_free():
    adapters, contracts = _registries()
    fixture = {
        "session_id": "domain-session",
        "steps": [
            {"adapter_id": VIZZ_ADAPTER_ID, "contract_id": VIZZ_CONTRACT_ID, "value": _vizz_event()},
            {"adapter_id": PUPILA_ADAPTER_ID, "contract_id": PUPILA_CONTRACT_ID, "value": _pupila_event()},
        ],
    }

    first = replay_pipeline_fixture(fixture, adapters=adapters, contracts=contracts)
    second = replay_pipeline_fixture(fixture, adapters=adapters, contracts=contracts)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["state"]["revision"] == 2
    assert first["side_effects"] == {
        "network_opened": False,
        "gui_opened": False,
        "host_actions_executed": False,
    }

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lucida.engine import (
    AdapterRegistry,
    ContractRegistry,
    EngineEvent,
    InputContract,
    ReplayError,
    replay_pipeline_fixture,
)


FIXTURE = Path(__file__).parent / "fixtures" / "pipeline-mixed.json"


class FixtureAdapter:
    def __init__(self, adapter_id: str):
        self.adapter_id = adapter_id

    def adapt(self, value):
        return EngineEvent.from_dict(value)


def make_registries():
    adapters = AdapterRegistry()
    adapters.register(FixtureAdapter("fixture.xio"))
    adapters.register(FixtureAdapter("fixture.mosaik"))
    contracts = ContractRegistry()
    contracts.register(
        InputContract(
            contract_id="fixture.xio.v1",
            source="fixture.xio",
            source_version="1",
            event_types=("signal.observed",),
            capabilities=("observe.signal",),
        )
    )
    contracts.register(
        InputContract(
            contract_id="fixture.mosaik.v1",
            source="fixture.mosaik",
            source_version="1",
            event_types=("show.state",),
            capabilities=("observe.show",),
        )
    )
    return adapters, contracts


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_pipeline_replay_keeps_per_source_order_and_explicit_routes():
    adapters, contracts = make_registries()

    report = replay_pipeline_fixture(load_fixture(), adapters=adapters, contracts=contracts)

    assert report["step_count"] == 3
    assert [route["adapter_id"] for route in report["routes"]] == [
        "fixture.xio",
        "fixture.mosaik",
        "fixture.xio",
    ]
    assert report["state"]["last_sequence_by_source"] == {
        "fixture.xio": 2,
        "fixture.mosaik": 1,
    }
    assert report["side_effects"] == {
        "network_opened": False,
        "gui_opened": False,
        "host_actions_executed": False,
    }


def test_pipeline_replay_is_byte_stable_as_json():
    adapters, contracts = make_registries()
    fixture = load_fixture()

    first = replay_pipeline_fixture(fixture, adapters=adapters, contracts=contracts)
    second = replay_pipeline_fixture(fixture, adapters=adapters, contracts=contracts)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_pipeline_replay_rejects_malformed_step_before_processing():
    adapters, contracts = make_registries()
    fixture = load_fixture()
    fixture["steps"][1] = {"adapter_id": "fixture.mosaik"}

    with pytest.raises(ReplayError, match="adapter_id, contract_id and value"):
        replay_pipeline_fixture(fixture, adapters=adapters, contracts=contracts)

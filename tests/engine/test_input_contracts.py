from __future__ import annotations

import pytest

from lucida.engine import (
    ContractRegistry,
    EngineEvent,
    InputContract,
    InputContractError,
)


def make_event(**overrides):
    value = {
        "session_id": "session-1",
        "event_id": "event-1",
        "timestamp": "2026-09-02T12:00:00Z",
        "sequence": 1,
        "source": "test.source",
        "source_version": "1",
        "event_type": "state.changed",
        "capabilities": ["observe.state"],
    }
    value.update(overrides)
    return EngineEvent.from_dict(value)


def make_contract():
    return InputContract(
        contract_id="test.contract.v1",
        source="test.source",
        source_version="1",
        event_types=("state.changed",),
        capabilities=("observe.state",),
    )


def test_contract_accepts_only_declared_event_vocabulary():
    contract = make_contract()

    contract.validate(make_event())

    with pytest.raises(InputContractError, match="event_type"):
        contract.validate(make_event(event_type="action.requested"))
    with pytest.raises(InputContractError, match="capabilities"):
        contract.validate(make_event(capabilities=["execute.host"]))


def test_registry_requires_explicit_contract_id_and_preserves_declarations():
    registry = ContractRegistry()
    registry.register(make_contract())

    registry.validate("test.contract.v1", make_event())
    assert registry.snapshot()[0]["contract_id"] == "test.contract.v1"

    with pytest.raises(InputContractError, match="unknown contract"):
        registry.validate("other.contract.v1", make_event())
    with pytest.raises(InputContractError, match="already registered"):
        registry.register(make_contract())


def test_contract_rejects_source_and_version_mismatch():
    contract = make_contract()

    with pytest.raises(InputContractError, match="source"):
        contract.validate(make_event(source="other.source"))
    with pytest.raises(InputContractError, match="source_version"):
        contract.validate(make_event(source_version="2"))


def test_contract_identifiers_and_declarations_are_ascii_and_bounded():
    with pytest.raises(ValueError, match="ASCII"):
        InputContract(
            contract_id="contr" + chr(225) + "to",
            source="test.source",
            source_version="1",
            event_types=("state.changed",),
        )
    with pytest.raises(InputContractError, match="duplicates"):
        InputContract(
            contract_id="test.contract.v1",
            source="test.source",
            source_version="1",
            event_types=("state.changed", "state.changed"),
        )

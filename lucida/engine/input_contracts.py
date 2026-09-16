"""Explicit input contracts for domain-to-engine boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import EngineEvent, _ascii_text


class InputContractError(ValueError):
    """Raised when an input contract or event violates its declaration."""


MAX_DECLARED_ITEMS = 32


@dataclass(frozen=True)
class InputContract:
    """Declare the event vocabulary accepted from one domain source."""

    contract_id: str
    source: str
    source_version: str
    event_types: tuple[str, ...]
    capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_items(self.contract_id, "contract_id", 1)
        _validate_items(self.source, "source", 1)
        _validate_items(self.source_version, "source_version", 1)
        _validate_items(self.event_types, "event_types", 1)
        _validate_items(self.capabilities, "capabilities", 0)

    def validate(self, event: EngineEvent) -> None:
        """Fail closed when an event is outside this declared vocabulary."""

        if not isinstance(event, EngineEvent):
            raise InputContractError("event must be an EngineEvent")
        if event.source != self.source:
            raise InputContractError("event source does not match the contract")
        if event.source_version != self.source_version:
            raise InputContractError("event source_version does not match the contract")
        if event.event_type not in self.event_types:
            raise InputContractError("event_type is not declared by the contract")
        undeclared = set(event.capabilities).difference(self.capabilities)
        if undeclared:
            raise InputContractError("event has undeclared capabilities")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "InputContract",
            "schema_version": "0.1",
            "contract_id": self.contract_id,
            "source": self.source,
            "source_version": self.source_version,
            "event_types": list(self.event_types),
            "capabilities": list(self.capabilities),
        }


class ContractRegistry:
    """Resolve and validate contracts only by an explicit contract id."""

    def __init__(self) -> None:
        self._contracts: dict[str, InputContract] = {}

    def register(self, contract: InputContract) -> None:
        if not isinstance(contract, InputContract):
            raise InputContractError("registry accepts InputContract only")
        if contract.contract_id in self._contracts:
            raise InputContractError(f"contract already registered: {contract.contract_id}")
        self._contracts[contract.contract_id] = contract

    def validate(self, contract_id: str, event: EngineEvent) -> None:
        key = _ascii_text(contract_id, "contract_id")
        contract = self._contracts.get(key)
        if contract is None:
            raise InputContractError(f"unknown contract: {key}")
        contract.validate(event)

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        """Return deterministic declarations for diagnostics and replay metadata."""

        return tuple(self._contracts[key].to_dict() for key in sorted(self._contracts))


def _validate_items(value: Any, field_name: str, minimum: int) -> None:
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, (list, tuple)):
        values = tuple(value)
    else:
        raise InputContractError(f"{field_name} must be a tuple of ASCII text")
    if len(values) < minimum or len(values) > MAX_DECLARED_ITEMS:
        raise InputContractError(f"{field_name} has an invalid item count")
    normalized = tuple(_ascii_text(item, field_name) for item in values)
    if len(set(normalized)) != len(normalized):
        raise InputContractError(f"{field_name} must not contain duplicates")

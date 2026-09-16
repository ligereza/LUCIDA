"""Deterministic adapter, contract and reducer pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .adapters import AdapterRegistry
from .input_contracts import ContractRegistry
from .models import EngineEvent, EngineState, RenderPlan
from .reducer import LucidaEngine


@dataclass(frozen=True)
class EngineTransition:
    """One accepted transition with its explicit routing metadata."""

    adapter_id: str
    contract_id: str
    event: EngineEvent
    state: EngineState
    plan: RenderPlan


class LucidaPipeline:
    """Join domain translation, contract validation and pure reduction."""

    def __init__(
        self,
        adapters: AdapterRegistry,
        contracts: ContractRegistry,
        engine: LucidaEngine | None = None,
    ) -> None:
        if not isinstance(adapters, AdapterRegistry):
            raise TypeError("adapters must be an AdapterRegistry")
        if not isinstance(contracts, ContractRegistry):
            raise TypeError("contracts must be a ContractRegistry")
        if engine is not None and not isinstance(engine, LucidaEngine):
            raise TypeError("engine must be a LucidaEngine")
        self._adapters = adapters
        self._contracts = contracts
        self._engine = engine or LucidaEngine()

    def initial_state(self, session_id: str) -> EngineState:
        return self._engine.initial_state(session_id)

    def apply(
        self,
        *,
        adapter_id: str,
        contract_id: str,
        value: Mapping[str, Any],
        state: EngineState,
    ) -> EngineTransition:
        """Apply one explicitly routed event without side effects."""

        event = self._adapters.adapt(adapter_id, value)
        self._contracts.validate(contract_id, event)
        next_state, plan = self._engine.apply(event, state)
        return EngineTransition(
            adapter_id=adapter_id,
            contract_id=contract_id,
            event=event,
            state=next_state,
            plan=plan,
        )

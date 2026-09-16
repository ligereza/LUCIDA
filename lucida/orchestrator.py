"""LUCIDA's single-surface, proposal-only orchestrator."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from adapters.vj import VJAdapter
from adapters.vj.contracts import VJEvent, VJResult, VJState

from .capabilities import ImagoCapability, InstarCapability, NayadeCapability
from .contracts import CAPABILITY_NAMES, CapabilityReport, LucidaState


class LucidaError(ValueError):
    """Raised when LUCIDA cannot advance its integration state."""


class LucidaOrchestrator:
    """Coordinate three capability facades without executing external work."""

    def __init__(self, capabilities: tuple[Any, ...] | None = None) -> None:
        self._vj_adapter = VJAdapter()
        self._capabilities = capabilities or (
            InstarCapability(),
            NayadeCapability(),
            ImagoCapability(),
        )
        names = tuple(capability.name for capability in self._capabilities)
        if names != CAPABILITY_NAMES:
            raise LucidaError(f"Las capacidades deben estar ordenadas como {CAPABILITY_NAMES}.")

    def initial_state(self, session_id: str, metadata: Mapping[str, Any] | None = None) -> LucidaState:
        vj_state = self._vj_adapter.initial_state(session_id, metadata=metadata)
        capabilities = tuple(
            CapabilityReport(
                capability=name,
                observed=("Sin eventos procesados.",),
                state={"status": "idle"},
                unknowns=("The capability has not received an event yet.",),
            )
            for name in CAPABILITY_NAMES
        )
        return LucidaState(
            session_id=vj_state.session_id,
            vj_state=vj_state,
            capabilities=capabilities,
            metadata=dict(metadata or {}),
        )

    def process_event(
        self,
        event: VJEvent | Mapping[str, Any],
        state: LucidaState | Mapping[str, Any],
    ) -> LucidaState:
        parsed_event = event if isinstance(event, VJEvent) else VJEvent.from_dict(event)
        current = state if isinstance(state, LucidaState) else LucidaState.from_dict(state)
        vj_state, lifecycle_proposals = self._vj_adapter.process(parsed_event, current.vj_state)
        reports = tuple(
            capability.evaluate(parsed_event, vj_state) for capability in self._capabilities
        )
        capability_proposals = tuple(
            proposal for report in reports for proposal in report.proposals
        )
        all_proposals = (*lifecycle_proposals, *capability_proposals)
        pending = list(vj_state.pending_proposal_ids)
        for proposal in capability_proposals:
            if proposal.proposal_id not in pending:
                pending.append(proposal.proposal_id)
        vj_state = replace(vj_state, pending_proposal_ids=tuple(pending))
        status = "proposal_pending" if all_proposals else "observing"
        return replace(
            current,
            vj_state=vj_state,
            capabilities=reports,
            proposals=(*current.proposals, *all_proposals),
            overlay_status=status,
        )

    def propose(
        self,
        event: VJEvent | Mapping[str, Any],
        state: LucidaState | Mapping[str, Any],
    ) -> LucidaState:
        """Consume an event and publish proposals; never execute them."""

        return self.process_event(event, state)

    def register_result(
        self,
        state: LucidaState | Mapping[str, Any],
        result: VJResult | Mapping[str, Any],
    ) -> LucidaState:
        current = state if isinstance(state, LucidaState) else LucidaState.from_dict(state)
        parsed_result = result if isinstance(result, VJResult) else VJResult.from_dict(result)
        vj_state = self._vj_adapter.register_result(current.vj_state, parsed_result)
        return replace(current, vj_state=vj_state, overlay_status="result_recorded")

    def read_overlay(self, state: LucidaState | Mapping[str, Any]) -> dict[str, Any]:
        """Return one read-only structured surface for a future host overlay."""

        current = state if isinstance(state, LucidaState) else LucidaState.from_dict(state)
        return {
            "surface": "LUCIDA",
            "mode": "read_only",
            "state": current.to_dict(),
            "capabilities": [capability.to_dict() for capability in current.capabilities],
            "pending_proposals": [
                proposal.to_dict()
                for proposal in current.proposals
                if proposal.proposal_id in current.vj_state.pending_proposal_ids
            ],
            "safety": {
                "external_side_effects": False,
                "automatic_actions": False,
                "resolume_opened": False,
            },
        }

    def read_state(self, state: LucidaState | Mapping[str, Any]) -> dict[str, Any]:
        """Expose the same state contract without any UI or host dependency."""

        current = state if isinstance(state, LucidaState) else LucidaState.from_dict(state)
        return current.to_dict()

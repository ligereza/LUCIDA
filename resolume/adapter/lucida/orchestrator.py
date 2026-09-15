"""LUCIDA's single-surface, proposal-only orchestrator."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from adapters.vj import VJAdapter
from adapters.vj.contracts import VJEvent, VJResult, VJState

from .capabilities import (
    _PROFILE_CONTEXT_KEY,
    _bounded_profile_state,
    _profile_state,
    ImagoCapability,
    InstarCapability,
    NayadeCapability,
)
from .contracts import CAPABILITY_NAMES, CapabilityReport, LucidaState
from .overlay import (
    MAX_DIFF_CHANGES,
    build_overlay_view,
    build_overlay_cursor,
    build_overlay_update as build_projected_overlay_update,
    diff_overlay_view as diff_projected_overlay_view,
)


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
        profile_state = _profile_state(parsed_event.payload)
        vj_metadata = dict(vj_state.metadata)
        if profile_state:
            vj_metadata[_PROFILE_CONTEXT_KEY] = profile_state
        else:
            inherited_context = _bounded_profile_state(vj_metadata.get(_PROFILE_CONTEXT_KEY))
            if inherited_context:
                vj_metadata[_PROFILE_CONTEXT_KEY] = inherited_context
            else:
                vj_metadata.pop(_PROFILE_CONTEXT_KEY, None)
        vj_state = replace(vj_state, metadata=vj_metadata)
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
        """Return the bounded redacted overlay surface."""

        return self.read_overlay_view(state)

    def read_overlay_view(self, state: LucidaState | Mapping[str, Any]) -> dict[str, Any]:
        """Return a bounded projection suitable for a future invisible overlay."""

        return build_overlay_view(state)

    def read_overlay_cursor(self, state: LucidaState | Mapping[str, Any]) -> dict[str, Any]:
        """Return a safe revision cursor for incremental overlay consumption."""

        return build_overlay_cursor(state)

    def diff_overlay_view(
        self,
        previous_state: LucidaState | Mapping[str, Any],
        current_state: LucidaState | Mapping[str, Any],
        *,
        max_changes: int = MAX_DIFF_CHANGES,
    ) -> list[dict[str, Any]]:
        """Diff two states through the bounded, read-only overlay projection."""

        return diff_projected_overlay_view(
            self.read_overlay_view(previous_state),
            self.read_overlay_view(current_state),
            max_changes=max_changes,
        )

    def build_overlay_update(
        self,
        previous_state: LucidaState | Mapping[str, Any],
        current_state: LucidaState | Mapping[str, Any],
        *,
        max_changes: int = MAX_DIFF_CHANGES,
    ) -> dict[str, Any]:
        """Build one atomic, read-only update for an incremental host."""

        return build_projected_overlay_update(
            previous_state,
            current_state,
            max_changes=max_changes,
        )

    def read_state(self, state: LucidaState | Mapping[str, Any]) -> dict[str, Any]:
        """Expose the same state contract without any UI or host dependency."""

        current = state if isinstance(state, LucidaState) else LucidaState.from_dict(state)
        return current.to_dict()

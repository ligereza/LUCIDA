"""Pure state machine for VJ events.

This module intentionally has no network, subprocess, MIDI, DMX, Resolume, or
processor dependency. It produces auditable proposals for a human/operator or
another explicitly authorized executor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .contracts import VJEvent, VJProposal, VJResult, VJState
from .contracts.models import ContractError


class VJAdapterError(ContractError):
    """Raised when a VJ event cannot be applied to the current state."""


_ALLOWED_NEXT_PHASES = {
    "preflight": {"preflight", "preparation"},
    "preparation": {"preparation", "show"},
    "show": {"show", "incident", "closure"},
    "incident": {"incident", "recovery"},
    "recovery": {"recovery", "show", "closure"},
    "closure": {"closure"},
}


class VJAdapter:
    """Translate VJ lifecycle events into recoverable, explicit proposals."""

    name = "vj-interface-layer"

    def initial_state(self, session_id: str, metadata: Mapping[str, Any] | None = None) -> VJState:
        if not isinstance(session_id, str) or not session_id.strip():
            raise VJAdapterError("session_id must be non-empty text.")
        return VJState(session_id=session_id.strip(), metadata=dict(metadata or {}))

    def process(self, event: VJEvent | Mapping[str, Any], state: VJState | Mapping[str, Any]) -> tuple[VJState, tuple[VJProposal, ...]]:
        parsed_event = event if isinstance(event, VJEvent) else VJEvent.from_dict(event)
        current = state if isinstance(state, VJState) else VJState.from_dict(state)
        self._validate_event_order(parsed_event, current)

        completed = list(current.completed_phases)
        if parsed_event.event_type == "phase.completed" and parsed_event.phase not in completed:
            completed.append(parsed_event.phase)

        incidents = list(current.open_incidents)
        if parsed_event.event_type == "incident.detected" and parsed_event.event_id not in incidents:
            incidents.append(parsed_event.event_id)
        if parsed_event.event_type == "recovery.verified":
            incidents.clear()

        checkpoint_id = current.checkpoint_id
        if parsed_event.event_type in {"phase.completed", "incident.detected", "recovery.verified"}:
            checkpoint_id = f"checkpoint-{parsed_event.event_id}"

        next_state = VJState(
            session_id=current.session_id,
            phase=parsed_event.phase,
            status=self._status_for(parsed_event),
            sequence=current.sequence + 1,
            last_event_id=parsed_event.event_id,
            last_timestamp=parsed_event.timestamp,
            checkpoint_id=checkpoint_id,
            completed_phases=tuple(completed),
            open_incidents=tuple(incidents),
            pending_proposal_ids=current.pending_proposal_ids,
            results=current.results,
            metadata={**current.metadata, "last_event_type": parsed_event.event_type},
        )
        proposals = self._proposals_for(parsed_event)
        pending = list(next_state.pending_proposal_ids)
        for proposal in proposals:
            if proposal.proposal_id not in pending:
                pending.append(proposal.proposal_id)
        next_state = VJState(
            **{
                **next_state.__dict__,
                "pending_proposal_ids": tuple(pending),
            }
        )
        return next_state, proposals

    def register_result(self, state: VJState | Mapping[str, Any], result: VJResult | Mapping[str, Any]) -> VJState:
        current = state if isinstance(state, VJState) else VJState.from_dict(state)
        parsed_result = result if isinstance(result, VJResult) else VJResult.from_dict(result)
        if parsed_result.proposal_id not in current.pending_proposal_ids:
            raise VJAdapterError(
                f"El resultado {parsed_result.result_id} referencia una propuesta no pendiente: "
                f"{parsed_result.proposal_id}"
            )
        if any(item.result_id == parsed_result.result_id for item in current.results):
            raise VJAdapterError(f"Resultado duplicado: {parsed_result.result_id}")
        pending = tuple(item for item in current.pending_proposal_ids if item != parsed_result.proposal_id)
        return VJState(
            **{
                **current.__dict__,
                "pending_proposal_ids": pending,
                "results": (*current.results, parsed_result),
            }
        )

    @staticmethod
    def _validate_event_order(event: VJEvent, state: VJState) -> None:
        if state.last_timestamp:
            current_time = datetime.fromisoformat(state.last_timestamp.replace("Z", "+00:00"))
            event_time = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
            if event_time < current_time:
                raise VJAdapterError("Los eventos deben llegar en orden temporal.")
        if event.phase not in _ALLOWED_NEXT_PHASES[state.phase]:
            raise VJAdapterError(f"Transition not allowed: {state.phase} -> {event.phase}")
        if state.status == "closed":
            raise VJAdapterError("Events cannot be processed after closure.")

    @staticmethod
    def _status_for(event: VJEvent) -> str:
        statuses = {
            "phase.completed": "ready",
            "show.started": "showing",
            "incident.detected": "incident",
            "recovery.started": "recovering",
            "recovery.verified": "recovered",
            "show.closed": "closed",
        }
        return statuses.get(event.event_type, "active")

    @staticmethod
    def _proposal(event: VJEvent, operation: str, reason: str, risk: str, evidence: tuple[str, ...] = ()) -> VJProposal:
        return VJProposal(
            proposal_id=f"proposal-{event.event_id}-{operation}",
            event_id=event.event_id,
            phase=event.phase,
            operation=operation,
            reason=reason,
            risk=risk,
            evidence=evidence,
        )

    def _proposals_for(self, event: VJEvent) -> tuple[VJProposal, ...]:
        if event.event_type == "phase.completed" and event.phase in {"preflight", "preparation"}:
            return (
                self._proposal(
                    event,
                    f"checkpoint-{event.phase}",
                    f"Conservar el estado aprobado de {event.phase} antes de continuar.",
                    "low",
                    ("state-transition", "checkpoint"),
                ),
            )
        if event.event_type == "show.started":
            return (
                self._proposal(
                    event,
                    "observe-show",
                    "Record the show start to support replay and later analysis.",
                    "low",
                    ("show-start", "timestamp"),
                ),
            )
        if event.event_type == "incident.detected":
            category = str(event.payload.get("category", "unclassified"))
            return (
                self._proposal(
                    event,
                    "capture-incident",
                    f"Capturar evidencia del incidente sin alterar la salida: {category}.",
                    "low",
                    ("incident", "evidence", "no-write"),
                ),
            )
        if event.event_type == "recovery.started":
            return (
                self._proposal(
                    event,
                    "prepare-recovery",
                    "Compare the current state with the last checkpoint before proposing recovery.",
                    "medium",
                    ("checkpoint", "recovery", "operator-approval"),
                ),
            )
        if event.event_type == "recovery.verified":
            return (
                self._proposal(
                    event,
                    "verify-recovery",
                    "Record that post-recovery tests were verified.",
                    "low",
                    ("recovery", "verification"),
                ),
            )
        if event.event_type == "show.closed":
            return (
                self._proposal(
                    event,
                    "close-session",
                    "Preserve the session summary and results for replay.",
                    "low",
                    ("closure", "replay"),
                ),
            )
        return ()

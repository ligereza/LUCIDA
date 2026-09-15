"""Pure state machine for VJ events.

This module intentionally has no network, subprocess, MIDI, DMX, Resolume, or
processor dependency. It produces auditable proposals for a human/operator or
another explicitly authorized executor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .contracts import ALLOWED_NEXT_PHASES, VJEvent, VJProposal, VJResult, VJState
from .contracts.models import ContractError


class VJAdapterError(ContractError):
    """Raised when a VJ event cannot be applied to the current state."""


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
        semantic_pending = current.metadata.get("semantic_light_field_pending")
        matching: list[Mapping[str, Any]] = []
        if isinstance(semantic_pending, list):
            matching = [
                item
                for item in semantic_pending
                if isinstance(item, Mapping)
                and item.get("proposal_id") == parsed_result.proposal_id
            ]
            if matching and parsed_result.status == "executed":
                raise VJAdapterError(
                    "semantic light-field proposals remain proposal_only and cannot execute."
                )
        pending = tuple(item for item in current.pending_proposal_ids if item != parsed_result.proposal_id)
        next_metadata = dict(current.metadata)
        if matching:
            status_by_result = {
                "accepted": "approved",
                "rejected": "rejected",
                "skipped": "undone",
                "observed": "observed",
                "failed": "failed",
            }
            semantic_status = status_by_result.get(parsed_result.status, parsed_result.status)
            next_metadata["semantic_light_field_pending"] = [
                {
                    **item,
                    "status": semantic_status,
                    "result_id": parsed_result.result_id,
                }
                if isinstance(item, Mapping)
                and item.get("proposal_id") == parsed_result.proposal_id
                else item
                for item in semantic_pending
            ]
        return VJState(
            **{
                **current.__dict__,
                "pending_proposal_ids": pending,
                "results": (*current.results, parsed_result),
                "metadata": next_metadata,
            }
        )

    def approve_proposal(
        self,
        state: VJState | Mapping[str, Any],
        proposal_id: str,
        result_id: str,
        recorded_at: str,
        notes: str = "Explicit approval recorded; no action executed.",
        evidence: tuple[str, ...] = (),
    ) -> VJState:
        """Record explicit approval; proposal_only never executes the operation."""
        return self._record_decision(
            state, proposal_id, result_id, recorded_at, "accepted", notes, evidence
        )

    def reject_proposal(
        self,
        state: VJState | Mapping[str, Any],
        proposal_id: str,
        result_id: str,
        recorded_at: str,
        notes: str = "Explicit rejection recorded; no action executed.",
        evidence: tuple[str, ...] = (),
    ) -> VJState:
        """Record explicit rejection without invoking a host or device action."""
        return self._record_decision(
            state, proposal_id, result_id, recorded_at, "rejected", notes, evidence
        )

    def undo_proposal(
        self,
        state: VJState | Mapping[str, Any],
        proposal_id: str,
        result_id: str,
        recorded_at: str,
        notes: str = "Explicit undo recorded; no action executed.",
        evidence: tuple[str, ...] = (),
    ) -> VJState:
        """Cancel a pending proposal explicitly; no executed action is undone."""
        return self._record_decision(
            state, proposal_id, result_id, recorded_at, "skipped", notes, evidence
        )

    def _record_decision(
        self,
        state: VJState | Mapping[str, Any],
        proposal_id: str,
        result_id: str,
        recorded_at: str,
        status: str,
        notes: str,
        evidence: tuple[str, ...],
    ) -> VJState:
        return self.register_result(
            state,
            {
                "result_id": result_id,
                "proposal_id": proposal_id,
                "recorded_at": recorded_at,
                "status": status,
                "notes": notes,
                "evidence": list(evidence),
            },
        )

    def ingest_semantic_light_field(
        self,
        proposal: VJProposal | Mapping[str, Any],
        state: VJState | Mapping[str, Any],
        tape_resolver: Any,
    ) -> tuple[VJState, dict[str, Any]]:
        """Stage an XIO semantic light-field proposal without executing it."""
        from .semantic_light_field import adapt_semantic_light_field

        return adapt_semantic_light_field(proposal, state, tape_resolver)

    @staticmethod
    def _validate_event_order(event: VJEvent, state: VJState) -> None:
        if state.last_timestamp:
            current_time = datetime.fromisoformat(state.last_timestamp.replace("Z", "+00:00"))
            event_time = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
            if event_time < current_time:
                raise VJAdapterError("Los eventos deben llegar en orden temporal.")
        if event.phase not in ALLOWED_NEXT_PHASES[state.phase]:
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
        if event.event_type in statuses:
            return statuses[event.event_type]
        phase_statuses = {
            "preflight": "ready",
            "preparation": "ready",
            "show": "showing",
            "incident": "incident",
            "recovery": "recovering",
            "closure": "closed",
        }
        return phase_statuses.get(event.phase, "active")

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

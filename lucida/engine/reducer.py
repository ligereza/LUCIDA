"""Pure LUCIDA reducer with deterministic rendering and no side effects."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Mapping

from .models import EngineContractError, EngineEvent, EngineState, RenderPlan, _utc


class EngineError(EngineContractError):
    """Base error for reducer violations."""


class DuplicateEventError(EngineError):
    """Raised when an event id is applied twice."""


class SessionMismatchError(EngineError):
    """Raised when an event belongs to another session."""


class OutOfOrderEventError(EngineError):
    """Raised when one source moves backwards in sequence or time."""


def _at_timestamp(value: str | None, fallback: str) -> datetime:
    return _utc(value or fallback)


class LucidaEngine:
    """Reduce bounded domain events into a host-neutral render plan."""

    def initial_state(self, session_id: str) -> EngineState:
        if not isinstance(session_id, str) or not session_id.strip():
            raise EngineError("session_id must be non-empty text.")
        try:
            session_id.encode("ascii")
        except UnicodeEncodeError as exc:
            raise EngineError("session_id must contain ASCII only.") from exc
        return EngineState(session_id=session_id.strip())

    def apply(
        self,
        event: EngineEvent | Mapping[str, Any],
        state: EngineState,
    ) -> tuple[EngineState, RenderPlan]:
        if isinstance(event, EngineEvent):
            parsed = event
        else:
            try:
                parsed = EngineEvent.from_dict(event)
            except EngineContractError as exc:
                raise EngineError(str(exc)) from exc
        if not isinstance(state, EngineState):
            raise EngineError("state must be an EngineState.")
        if parsed.session_id != state.session_id:
            raise SessionMismatchError("event session does not match engine state.")
        if parsed.event_id in state.seen_event_ids:
            raise DuplicateEventError(f"duplicate event_id: {parsed.event_id}")

        previous_sequence = state.last_sequence_by_source.get(parsed.source)
        if previous_sequence is not None and parsed.sequence <= previous_sequence:
            raise OutOfOrderEventError(
                f"source sequence must increase: {parsed.source}:{parsed.sequence}"
            )
        previous_timestamp = state.last_timestamp_by_source.get(parsed.source)
        if previous_timestamp and _utc(parsed.timestamp) < _utc(previous_timestamp):
            raise OutOfOrderEventError(f"source timestamp moved backwards: {parsed.source}")

        warnings = list(state.warnings)
        if previous_sequence is not None and parsed.sequence > previous_sequence + 1:
            warnings.append(f"sequence_gap:{parsed.source}:{previous_sequence + 1}-{parsed.sequence - 1}")

        sequences = dict(state.last_sequence_by_source)
        timestamps = dict(state.last_timestamp_by_source)
        sequences[parsed.source] = parsed.sequence
        timestamps[parsed.source] = parsed.timestamp
        now = _utc(parsed.timestamp)
        active = [
            item
            for item in state.active_proposals
            if _utc(item.expires_at()) > now
        ]
        if parsed.proposal is not None:
            active = [item for item in active if item.proposal_id != parsed.proposal.proposal_id]
            active.append(parsed.proposal)

        next_state = replace(
            state,
            revision=state.revision + 1,
            last_sequence_by_source=sequences,
            last_timestamp_by_source=timestamps,
            seen_event_ids=(*state.seen_event_ids, parsed.event_id),
            active_proposals=tuple(active),
            warnings=tuple(warnings[-32:]),
        )
        return next_state, self.render_plan(next_state, at=parsed.timestamp)

    def render_plan(self, state: EngineState, *, at: str | None = None) -> RenderPlan:
        reference = at or next(iter(state.last_timestamp_by_source.values()), "1970-01-01T00:00:00Z")
        now = _at_timestamp(at, reference)
        items: list[dict[str, Any]] = []
        for proposal in sorted(
            state.active_proposals,
            key=lambda item: (-item.priority, item.proposal_id),
        ):
            if _utc(proposal.expires_at()) <= now:
                continue
            items.append(
                {
                    "item_id": proposal.proposal_id,
                    "kind": proposal.kind,
                    "title": proposal.title,
                    "body": proposal.body,
                    "priority": proposal.priority,
                    "source": proposal.source,
                    "expires_at": proposal.expires_at(),
                    "requires_confirmation": True,
                    "reversible": True,
                }
            )
        return RenderPlan(
            session_id=state.session_id,
            revision=state.revision,
            items=tuple(items),
            warnings=state.warnings,
        )

"""Replay a recorded VJ lifecycle without touching external systems."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..adapter import VJAdapter, VJAdapterError
from ..contracts import VJEvent
from ..contracts.models import ContractError


class ReplayError(ValueError):
    """Raised when a replay fixture is malformed or cannot be completed."""


def load_fixture(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path).expanduser().resolve()
    if not fixture_path.is_file():
        raise ReplayError(f"No existe el fixture de replay: {fixture_path}")
    try:
        value = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayError(f"No se pudo leer el fixture: {fixture_path}") from exc
    if not isinstance(value, dict):
        raise ReplayError("El fixture de replay debe ser un objeto JSON.")
    return value


def replay_path(path: str | Path) -> dict[str, Any]:
    return replay_fixture(load_fixture(path))


def replay_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(fixture, Mapping):
        raise ReplayError("El fixture de replay debe ser un objeto.")
    session_id = fixture.get("session_id")
    events = fixture.get("events")
    results = fixture.get("results", [])
    if not isinstance(session_id, str) or not session_id.strip():
        raise ReplayError("El fixture necesita session_id.")
    if not isinstance(events, list) or not events:
        raise ReplayError("The fixture needs a non-empty events list.")
    if not isinstance(results, list):
        raise ReplayError("results debe ser una lista.")

    results_by_event: dict[str, list[Mapping[str, Any]]] = {}
    for result in results:
        if not isinstance(result, Mapping):
            raise ReplayError("Cada result debe ser un objeto.")
        event_id = result.get("after_event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ReplayError("Cada result necesita after_event_id.")
        results_by_event.setdefault(event_id, []).append(result)

    adapter = VJAdapter()
    state = adapter.initial_state(session_id, metadata={"fixture": True})
    transitions: list[dict[str, Any]] = []
    proposal_count = 0
    result_count = 0
    seen_event_ids: set[str] = set()

    try:
        for raw_event in events:
            event = VJEvent.from_dict(raw_event)
            if event.event_id in seen_event_ids:
                raise ReplayError(f"event_id duplicado: {event.event_id}")
            seen_event_ids.add(event.event_id)
            state, proposals = adapter.process(event, state)
            proposal_count += len(proposals)
            registered_results: list[str] = []
            for raw_result in results_by_event.get(event.event_id, []):
                result_data = dict(raw_result)
                result_data.pop("after_event_id", None)
                state = adapter.register_result(state, result_data)
                registered_results.append(result_data["result_id"])
                result_count += 1
            transitions.append({
                "event": event.to_dict(),
                "state_after": state.to_dict(),
                "proposals": [proposal.to_dict() for proposal in proposals],
                "registered_result_ids": registered_results,
            })
    except (ContractError, VJAdapterError, KeyError, TypeError) as exc:
        raise ReplayError(str(exc)) from exc

    unknown_result_events = set(results_by_event) - seen_event_ids
    if unknown_result_events:
        raise ReplayError(f"Resultados asociados a eventos inexistentes: {sorted(unknown_result_events)}")

    final_state = state.to_dict()
    complete = (
        final_state["phase"] == "closure"
        and final_state["status"] == "closed"
        and not final_state["pending_proposal_ids"]
        and not final_state["open_incidents"]
    )
    return {
        "replay_type": "VJReplay",
        "schema_version": "0.1",
        "session_id": session_id,
        "status": "PASS" if complete else "REVIEW",
        "event_count": len(events),
        "proposal_count": proposal_count,
        "result_count": result_count,
        "phase_order": [item["event"]["phase"] for item in transitions],
        "transitions": transitions,
        "final_state": final_state,
        "safety": {
            "external_side_effects": False,
            "irreversible_actions_executed": False,
            "all_proposals_require_explicit_approval": all(
                proposal["requires_explicit_approval"]
                for transition in transitions
                for proposal in transition["proposals"]
            ),
        },
    }

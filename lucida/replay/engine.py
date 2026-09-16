"""Deterministic LUCIDA replay with no external side effects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from adapters.vj.contracts import VJEvent

from ..orchestrator import LucidaOrchestrator


class ReplayError(ValueError):
    """Raised when a LUCIDA fixture cannot be replayed."""


def load_fixture(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path).expanduser().resolve()
    if not fixture_path.is_file():
        raise ReplayError(f"No existe el fixture de replay: {fixture_path}")
    try:
        value = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayError(f"No se pudo leer el fixture: {fixture_path}") from exc
    if not isinstance(value, dict):
        raise ReplayError("El fixture debe ser un objeto JSON.")
    return value


def replay_path(path: str | Path) -> dict[str, Any]:
    return replay_fixture(load_fixture(path))


def replay_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(fixture, Mapping):
        raise ReplayError("El fixture debe ser un objeto.")
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

    orchestrator = LucidaOrchestrator()
    state = orchestrator.initial_state(session_id, metadata={"fixture": True})
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
            state = orchestrator.process_event(event, state)
            new_proposals = [
                proposal
                for proposal in state.proposals
                if proposal.event_id == event.event_id
            ]
            proposal_count += len(new_proposals)
            registered_result_ids: list[str] = []
            for raw_result in results_by_event.get(event.event_id, []):
                result_data = dict(raw_result)
                result_data.pop("after_event_id", None)
                state = orchestrator.register_result(state, result_data)
                registered_result_ids.append(result_data["result_id"])
                result_count += 1
            transitions.append(
                {
                    "event": event.to_dict(),
                    "overlay": orchestrator.read_overlay(state),
                    "registered_result_ids": registered_result_ids,
                }
            )
    except (ValueError, TypeError, KeyError) as exc:
        raise ReplayError(str(exc)) from exc

    unknown_result_events = set(results_by_event) - seen_event_ids
    if unknown_result_events:
        raise ReplayError(
            f"Resultados asociados a eventos inexistentes: {sorted(unknown_result_events)}"
        )

    final_state = state.to_dict()
    active_capabilities = {
        report["capability"]
        for transition in transitions
        for report in transition["overlay"]["capabilities"]
        if report["proposals"]
    }
    complete = (
        final_state["vj_state"]["phase"] == "closure"
        and final_state["vj_state"]["status"] == "closed"
        and not final_state["pending_proposal_ids"]
        and active_capabilities == {"INSTAR", "NAYADE", "IMAGO"}
    )
    return {
        "replay_type": "LucidaVJReplay",
        "schema_version": "0.1",
        "session_id": session_id,
        "surface": "single-overlay",
        "status": "PASS" if complete else "REVIEW",
        "event_count": len(events),
        "proposal_count": proposal_count,
        "result_count": result_count,
        "capabilities_observed": sorted(active_capabilities),
        "phase_order": [item["event"]["phase"] for item in transitions],
        "transitions": transitions,
        "final_state": final_state,
        "safety": {
            "external_side_effects": False,
            "automatic_actions": False,
            "resolume_opened": False,
        },
    }

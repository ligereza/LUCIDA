"""Deterministic replay for the host-neutral VJ show input projection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..contracts import VJEvent
from ..contracts.models import ContractError
from ..show_input import ShowInputError, ShowInputProjector
from .engine import ReplayError, load_fixture


def replay_show_input_path(path: str | Path) -> dict[str, Any]:
    return replay_show_input_fixture(load_fixture(path))


def replay_show_input_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(fixture, Mapping):
        raise ReplayError("The show input fixture must be an object.")
    session_id = fixture.get("session_id")
    events = fixture.get("events")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ReplayError("The show input fixture needs session_id.")
    if not isinstance(events, list) or not events:
        raise ReplayError("The show input fixture needs a non-empty events list.")

    projector = ShowInputProjector()
    previous = None
    projections: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()
    try:
        for raw_event in events:
            event = VJEvent.from_dict(raw_event)
            if event.event_id in seen_event_ids:
                raise ReplayError(f"event_id duplicated: {event.event_id}")
            seen_event_ids.add(event.event_id)
            projection = projector.project(event, previous)
            projections.append(projection.to_dict())
            previous = projection
    except (ContractError, ShowInputError, TypeError, KeyError) as exc:
        raise ReplayError(str(exc)) from exc

    return {
        "replay_type": "ResolumeAdapterShowInputReplay",
        "schema_version": "0.1",
        "session_id": session_id,
        "status": "PASS",
        "projection_count": len(projections),
        "phase_order": [item["show_phase"] for item in projections],
        "sequence_order": [item["sequence"] for item in projections],
        "projections": projections,
        "safety": {
            "external_side_effects": False,
            "network_opened": False,
            "host_actions": False,
        },
    }

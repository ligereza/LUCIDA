"""Deterministic replay for the LUCIDA engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .reducer import LucidaEngine


class ReplayError(ValueError):
    """Raised when an engine fixture is malformed."""


def replay_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(fixture, Mapping):
        raise ReplayError("fixture must be an object.")
    session_id = fixture.get("session_id")
    events = fixture.get("events")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ReplayError("fixture needs session_id.")
    if not isinstance(events, list) or not events:
        raise ReplayError("fixture needs non-empty events.")
    engine = LucidaEngine()
    state = engine.initial_state(session_id)
    plans = []
    for raw_event in events:
        state, plan = engine.apply(raw_event, state)
        plans.append(plan.to_dict())
    final_plan = engine.render_plan(state, at=events[-1]["timestamp"])
    return {
        "replay_type": "LucidaEngineReplay",
        "session_id": session_id,
        "event_count": len(events),
        "state": state.to_dict(),
        "plans": plans,
        "final_plan": final_plan.to_dict(),
        "side_effects": {
            "network_opened": False,
            "gui_opened": False,
            "host_actions_executed": False,
        },
    }


def replay_path(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path).expanduser().resolve()
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayError(f"fixture cannot be read: {fixture_path}") from exc
    return replay_fixture(fixture)

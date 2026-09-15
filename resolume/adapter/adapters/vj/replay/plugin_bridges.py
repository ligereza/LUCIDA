"""Replay the three RESOLUME_ADAPTER plugin bridges as one side-effect-free flow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..adapter import VJAdapter, VJAdapterError
from ..contracts import VJEvent
from ..imago_input import ImagoInputError, ImagoInputProjector
from ..instar_input import InstarInputError, InstarInputProjector
from ..nayade_input import NayadeInputError, NayadeInputProjector
from .engine import ReplayError, load_fixture


BRIDGE_STAGES = ("instar", "nayade", "imago")


def replay_plugin_bridge_path(path: str | Path) -> dict[str, Any]:
    """Load and replay a fictional INSTAR/NAYADE/IMAGO bridge fixture."""

    return replay_plugin_bridge_fixture(load_fixture(path))


def _record_event(record: Mapping[str, Any]) -> VJEvent:
    if set(record) not in (
        {"stage", "event_id", "sequence", "data"},
        {"stage", "event_id", "sequence", "data", "processor_observation"},
    ):
        raise ReplayError("plugin bridge record fields are invalid.")
    stage = record.get("stage")
    if stage not in BRIDGE_STAGES:
        raise ReplayError(f"unsupported plugin bridge stage: {stage}")
    event_id = record.get("event_id")
    sequence = record.get("sequence")
    data = record.get("data")
    try:
        if stage == "instar":
            return InstarInputProjector().event(data, event_id=event_id, sequence=sequence)
        if stage == "nayade":
            return NayadeInputProjector().event(
                data,
                event_id=event_id,
                sequence=sequence,
                processor_observation=record.get("processor_observation"),
            )
        return ImagoInputProjector().event(data, event_id=event_id, sequence=sequence)
    except (InstarInputError, NayadeInputError, ImagoInputError, TypeError) as exc:
        raise ReplayError(str(exc)) from exc


def replay_plugin_bridge_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Replay bridge records through the shared VJ state machine."""

    if not isinstance(fixture, Mapping):
        raise ReplayError("plugin bridge fixture must be an object.")
    if fixture.get("replay_type") != "ResolumeAdapterPluginBridgeReplay":
        raise ReplayError("plugin bridge fixture identity is invalid.")
    session_id = fixture.get("session_id")
    records = fixture.get("records")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ReplayError("plugin bridge fixture needs session_id.")
    if not isinstance(records, list) or not records:
        raise ReplayError("plugin bridge fixture needs a non-empty records list.")

    adapter = VJAdapter()
    state = adapter.initial_state(session_id, metadata={"fixture": True, "bridge_replay": True})
    transitions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    last_payload_sequence = -1
    for raw_record in records:
        if not isinstance(raw_record, Mapping):
            raise ReplayError("each plugin bridge record must be an object.")
        event = _record_event(raw_record)
        if event.event_id in seen_ids:
            raise ReplayError(f"duplicate bridge event_id: {event.event_id}")
        seen_ids.add(event.event_id)
        payload_sequence = event.payload.get("sequence")
        if isinstance(payload_sequence, bool) or not isinstance(payload_sequence, int):
            raise ReplayError("bridge event sequence must be an integer.")
        if payload_sequence <= last_payload_sequence:
            raise ReplayError("bridge event sequences must be strictly increasing.")
        last_payload_sequence = payload_sequence
        try:
            state, proposals = adapter.process(event, state)
        except (VJAdapterError, TypeError, KeyError) as exc:
            raise ReplayError(str(exc)) from exc
        transitions.append(
            {
                "stage": raw_record["stage"],
                "event": event.to_dict(),
                "state_after": state.to_dict(),
                "proposals": [proposal.to_dict() for proposal in proposals],
            }
        )

    final_state = state.to_dict()
    complete = (
        final_state["phase"] == "closure"
        and final_state["status"] == "closed"
        and not final_state["open_incidents"]
        and not final_state["pending_proposal_ids"]
    )
    return {
        "replay_type": "ResolumeAdapterPluginBridgeReplayReport",
        "schema_version": "0.1",
        "session_id": session_id,
        "status": "PASS" if complete else "REVIEW",
        "record_count": len(records),
        "stage_order": [item["stage"] for item in transitions],
        "phase_order": [item["event"]["phase"] for item in transitions],
        "transitions": transitions,
        "final_state": final_state,
        "safety": {
            "external_side_effects": False,
            "irreversible_actions_executed": False,
            "proposal_count": sum(len(item["proposals"]) for item in transitions),
        },
    }


__all__ = ["BRIDGE_STAGES", "replay_plugin_bridge_fixture", "replay_plugin_bridge_path"]

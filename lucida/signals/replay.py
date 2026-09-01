"""Deterministic offline replay for injected OSC/Resolume envelopes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .boundary import OscResolumeBoundary, OscEnvelope


class SignalReplayError(ValueError):
    """Raised when a signal replay fixture is malformed."""


def load_fixture(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path).expanduser().resolve()
    if not fixture_path.is_file():
        raise SignalReplayError(f"Signal fixture does not exist: {fixture_path}")
    try:
        value = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SignalReplayError(f"Signal fixture cannot be read: {fixture_path}") from exc
    if not isinstance(value, dict):
        raise SignalReplayError("Signal fixture must be a JSON object.")
    return value


def replay_path(path: str | Path) -> dict[str, Any]:
    return replay_fixture(load_fixture(path))


def replay_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(fixture, Mapping):
        raise SignalReplayError("Signal fixture must be an object.")
    session_id = fixture.get("session_id")
    envelopes = fixture.get("envelopes")
    results = fixture.get("results", [])
    if not isinstance(session_id, str) or not session_id.strip():
        raise SignalReplayError("Signal fixture needs session_id.")
    if not isinstance(envelopes, list) or not envelopes:
        raise SignalReplayError("Signal fixture needs non-empty envelopes.")
    if not isinstance(results, list):
        raise SignalReplayError("Signal fixture results must be a list.")

    results_by_sequence: dict[int, list[Mapping[str, Any]]] = {}
    for result in results:
        if not isinstance(result, Mapping):
            raise SignalReplayError("Each signal result must be an object.")
        sequence = result.get("after_sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise SignalReplayError("Each signal result needs a valid after_sequence.")
        results_by_sequence.setdefault(sequence, []).append(result)

    boundary = OscResolumeBoundary()
    state = boundary.initial_state(session_id, metadata={"fixture": True})
    transitions: list[dict[str, Any]] = []
    proposal_count = 0
    result_count = 0
    seen_sequences: set[int] = set()

    try:
        for raw_envelope in envelopes:
            envelope = OscEnvelope.from_dict(raw_envelope)
            if envelope.sequence in seen_sequences:
                raise SignalReplayError(f"Duplicate sequence in fixture: {envelope.sequence}.")
            seen_sequences.add(envelope.sequence)
            received = boundary.receive(envelope, state)
            state = received.state
            proposal_count += len(received.proposals)
            registered_result_ids: list[str] = []
            for raw_result in results_by_sequence.get(envelope.sequence, []):
                result_data = dict(raw_result)
                result_data.pop("after_sequence", None)
                state = boundary.register_result(state, result_data)
                registered_result_ids.append(result_data["result_id"])
                result_count += 1
            transitions.append(
                {
                    "envelope": envelope.to_dict(),
                    "event": received.event.to_dict(),
                    "overlay": boundary.read_overlay(state),
                    "proposal_ids": [proposal.proposal_id for proposal in received.proposals],
                    "registered_result_ids": registered_result_ids,
                    "sender_called": received.sender_called,
                }
            )
    except (ValueError, TypeError, KeyError) as exc:
        raise SignalReplayError(str(exc)) from exc

    unknown_result_sequences = set(results_by_sequence) - seen_sequences
    if unknown_result_sequences:
        raise SignalReplayError(
            f"Results reference missing sequences: {sorted(unknown_result_sequences)}"
        )

    final_state = state.to_dict()
    active_capabilities = {
        report["capability"]
        for transition in transitions
        for report in transition["overlay"]["capabilities"]
        if report["proposals"]
    }
    complete = (
        final_state["lucida_state"]["vj_state"]["phase"] == "closure"
        and final_state["lucida_state"]["vj_state"]["status"] == "closed"
        and not final_state["lucida_state"]["pending_proposal_ids"]
        and active_capabilities == {"INSTAR", "NAYADE", "IMAGO"}
    )
    return {
        "replay_type": "LucidaOscReplay",
        "schema_version": "0.1",
        "session_id": session_id,
        "surface": "single-overlay",
        "status": "PASS" if complete else "REVIEW",
        "envelope_count": len(envelopes),
        "proposal_count": proposal_count,
        "result_count": result_count,
        "capabilities_observed": sorted(active_capabilities),
        "transitions": transitions,
        "final_state": final_state,
        "safety": {
            "sockets_opened": False,
            "external_side_effects": False,
            "automatic_actions": False,
            "resolume_opened": False,
        },
    }

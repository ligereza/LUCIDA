"""Dispatch semantic light-field replay input through the VJ application entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..adapter import VJAdapter, VJAdapterError
from ..semantic_light_field import SemanticLightFieldBridgeError
from .engine import ReplayError, load_fixture


SEMANTIC_REPLAY_TYPE = "ResolumeAdapterSemanticLightFieldReplay"
SEMANTIC_REPLAY_REPORT_TYPE = "ResolumeAdapterSemanticLightFieldReplayReport"
SEMANTIC_REPLAY_SCHEMA_VERSION = "0.1"


def replay_semantic_light_field_path(path: str | Path) -> dict[str, Any]:
    """Load one semantic replay envelope through the existing VJ replay dispatcher."""
    return replay_semantic_light_field_fixture(load_fixture(path))


def replay_semantic_light_field_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Stage one semantic proposal and tape without making an automatic decision."""
    if not isinstance(fixture, Mapping):
        raise ReplayError("semantic light-field replay must be an object.")
    required = {"replay_type", "schema_version", "session_id", "proposal", "tape"}
    if set(fixture) != required:
        raise ReplayError("semantic light-field replay fields are invalid.")
    if fixture.get("replay_type") != SEMANTIC_REPLAY_TYPE:
        raise ReplayError("semantic light-field replay identity is invalid.")
    if fixture.get("schema_version") != SEMANTIC_REPLAY_SCHEMA_VERSION:
        raise ReplayError("semantic light-field replay schema version is unsupported.")
    session_id = fixture.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ReplayError("semantic light-field replay needs session_id.")
    proposal = fixture.get("proposal")
    tape = fixture.get("tape")
    if not isinstance(proposal, Mapping) or not isinstance(tape, Mapping):
        raise ReplayError("semantic light-field replay proposal and tape must be objects.")

    evidence = proposal.get("evidence")
    if not isinstance(evidence, (list, tuple)):
        raise ReplayError("semantic light-field replay proposal evidence must be a list.")
    digest_values = [
        item.split(":", 1)[1]
        for item in evidence
        if isinstance(item, str) and item.startswith("tape_sha256:")
    ]
    if len(digest_values) != 1:
        raise ReplayError("semantic light-field replay needs one tape_sha256 evidence value.")

    adapter = VJAdapter()
    state = adapter.initial_state(
        session_id,
        metadata={"fixture": True, "semantic_light_field_replay": True},
    )
    try:
        state, pending = adapter.ingest_semantic_light_field(
            proposal,
            state,
            {digest_values[0]: tape},
        )
    except (SemanticLightFieldBridgeError, VJAdapterError, TypeError, KeyError) as exc:
        raise ReplayError(f"semantic light-field dispatch failed: {exc}") from exc

    return {
        "replay_type": SEMANTIC_REPLAY_REPORT_TYPE,
        "schema_version": SEMANTIC_REPLAY_SCHEMA_VERSION,
        "session_id": session_id,
        "status": "PASS",
        "proposal": pending["proposal"],
        "pending": pending,
        "state": state.to_dict(),
        "safety": {
            "external_side_effects": False,
            "irreversible_actions_executed": False,
            "automatic_decision": False,
            "execution_mode": "proposal_only",
        },
    }


__all__ = [
    "SEMANTIC_REPLAY_REPORT_TYPE",
    "SEMANTIC_REPLAY_SCHEMA_VERSION",
    "SEMANTIC_REPLAY_TYPE",
    "replay_semantic_light_field_fixture",
    "replay_semantic_light_field_path",
]

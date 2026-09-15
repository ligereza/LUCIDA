"""Proposal-only semantic light-field input for the VJ adapter."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Callable, Mapping

from .contracts import VJProposal, VJState
from .contracts.models import ContractError


TAPE_SCHEMA = "farmaxia:semantic-light-field-tape:0.1"
PENDING_CONTRACT_TYPE = "ResolumeAdapterVJSemanticLightFieldPending"
PENDING_SCHEMA_VERSION = "0.1"


class SemanticLightFieldBridgeError(ContractError):
    """Raised when a semantic light-field proposal cannot be staged safely."""


def _canonical_json(value: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        normalized = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SemanticLightFieldBridgeError(
            "semantic light-field tape must contain finite JSON values."
        ) from exc
    if not isinstance(normalized, dict):
        raise SemanticLightFieldBridgeError("semantic light-field tape must be an object.")
    return encoded, normalized


def _evidence(proposal: VJProposal) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in proposal.evidence:
        key, separator, value = item.partition(":")
        if not separator or not key or not value or key in values:
            raise SemanticLightFieldBridgeError(
                "semantic light-field proposal evidence is invalid."
            )
        values[key] = value
    required = {"consumer", "tape_schema", "tape_sha256", "frame_count"}
    if not required <= values.keys():
        raise SemanticLightFieldBridgeError(
            "semantic light-field proposal evidence is incomplete."
        )
    if values["consumer"] != "resolume_adapter-vj":
        raise SemanticLightFieldBridgeError(
            "semantic light-field proposal consumer is not resolume_adapter-vj."
        )
    if values["tape_schema"] != TAPE_SCHEMA:
        raise SemanticLightFieldBridgeError(
            "semantic light-field proposal tape schema is unsupported."
        )
    digest = values["tape_sha256"]
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise SemanticLightFieldBridgeError(
            "semantic light-field proposal tape hash is invalid."
        )
    frame_count = values["frame_count"]
    if not frame_count.isascii() or not frame_count.isdecimal() or int(frame_count) <= 0:
        raise SemanticLightFieldBridgeError(
            "semantic light-field proposal frame count is invalid."
        )
    return values


def resolve_semantic_light_field_tape(
    tape_resolver: Mapping[str, Mapping[str, Any]] | Callable[[str], Mapping[str, Any]],
    digest: str,
) -> Mapping[str, Any]:
    """Resolve one tape by digest through a store mapping or replay callback."""
    try:
        if isinstance(tape_resolver, Mapping):
            tape = tape_resolver.get(digest)
        elif callable(tape_resolver):
            tape = tape_resolver(digest)
        else:
            raise TypeError("tape_resolver must be a mapping or callable")
    except Exception as exc:
        if isinstance(exc, SemanticLightFieldBridgeError):
            raise
        raise SemanticLightFieldBridgeError(
            "semantic light-field tape resolver failed."
        ) from exc
    if not isinstance(tape, Mapping):
        raise SemanticLightFieldBridgeError(
            "semantic light-field tape was not found for the proposal hash."
        )
    return tape


def _validate_tape(
    tape: Mapping[str, Any], evidence: Mapping[str, str]
) -> tuple[dict[str, Any], str]:
    if tape.get("schema") != TAPE_SCHEMA:
        raise SemanticLightFieldBridgeError(
            "semantic light-field tape schema is unsupported."
        )
    if tape.get("proposal_only") is not True:
        raise SemanticLightFieldBridgeError(
            "semantic light-field tape must be proposal-only."
        )
    if tape.get("calibration_status") != "not_calibrated":
        raise SemanticLightFieldBridgeError(
            "semantic light-field tape calibration status is invalid."
        )
    sample_hz = tape.get("sample_hz")
    if (
        isinstance(sample_hz, bool)
        or not isinstance(sample_hz, (int, float))
        or not math.isfinite(sample_hz)
        or sample_hz <= 0
    ):
        raise SemanticLightFieldBridgeError(
            "semantic light-field tape sample_hz is invalid."
        )
    frames = tape.get("frames")
    if not isinstance(frames, list) or not frames:
        raise SemanticLightFieldBridgeError(
            "semantic light-field tape frames must be non-empty."
        )
    for index, frame in enumerate(frames):
        if not isinstance(frame, Mapping):
            raise SemanticLightFieldBridgeError(
                "semantic light-field tape frame %d is invalid." % index
            )
        if frame.get("proposal_only") is not True:
            raise SemanticLightFieldBridgeError(
                "semantic light-field tape frame %d is not proposal-only." % index
            )
    encoded, normalized = _canonical_json(tape)
    digest = hashlib.sha256(encoded.encode("ascii")).hexdigest()
    if digest != evidence["tape_sha256"]:
        raise SemanticLightFieldBridgeError(
            "semantic light-field tape hash does not match the proposal."
        )
    if len(frames) != int(evidence["frame_count"]):
        raise SemanticLightFieldBridgeError(
            "semantic light-field tape frame count does not match the proposal."
        )
    return normalized, digest


def adapt_semantic_light_field(
    proposal: Mapping[str, Any] | VJProposal,
    state: Mapping[str, Any] | VJState,
    tape_resolver: Mapping[str, Mapping[str, Any]] | Callable[[str], Mapping[str, Any]],
) -> tuple[VJState, dict[str, Any]]:
    """Stage a semantic light-field tape as a reversible pending proposal."""
    if isinstance(proposal, VJProposal):
        raw_proposal = proposal.to_dict()
    elif isinstance(proposal, Mapping):
        raw_proposal = proposal
    else:
        raise SemanticLightFieldBridgeError("proposal payload must be a mapping")
    if raw_proposal.get("execution_mode") != "proposal_only":
        raise SemanticLightFieldBridgeError("proposal execution_mode must be proposal_only")
    try:
        parsed_proposal = (
            proposal if isinstance(proposal, VJProposal) else VJProposal.from_dict(proposal)
        )
        current = state if isinstance(state, VJState) else VJState.from_dict(state)
    except (ContractError, TypeError) as exc:
        raise SemanticLightFieldBridgeError(str(exc)) from exc

    if parsed_proposal.operation != "preview_semantic_light_field":
        raise SemanticLightFieldBridgeError(
            "proposal operation is not semantic light-field preview."
        )
    evidence = _evidence(parsed_proposal)
    if parsed_proposal.proposal_id in current.pending_proposal_ids:
        raise SemanticLightFieldBridgeError("semantic light-field proposal is already pending.")
    if any(result.proposal_id == parsed_proposal.proposal_id for result in current.results):
        raise SemanticLightFieldBridgeError("semantic light-field proposal was already resolved.")

    source_tape = resolve_semantic_light_field_tape(
        tape_resolver, evidence["tape_sha256"]
    )
    normalized_tape, digest = _validate_tape(source_tape, evidence)

    pending_refs = current.metadata.get("semantic_light_field_pending", [])
    if not isinstance(pending_refs, list):
        raise SemanticLightFieldBridgeError(
            "semantic light-field pending metadata is invalid."
        )
    if any(
        isinstance(item, Mapping)
        and item.get("proposal_id") == parsed_proposal.proposal_id
        for item in pending_refs
    ):
        raise SemanticLightFieldBridgeError("semantic light-field proposal is already staged.")
    reference = {
        "proposal_id": parsed_proposal.proposal_id,
        "tape_sha256": digest,
        "tape_schema": TAPE_SCHEMA,
        "frame_count": len(normalized_tape["frames"]),
        "execution_mode": parsed_proposal.execution_mode,
        "status": "pending_approval",
    }
    next_metadata = {
        **current.metadata,
        "semantic_light_field_pending": [*pending_refs, reference],
    }
    next_state = VJState(
        **{
            **current.__dict__,
            "pending_proposal_ids": (*current.pending_proposal_ids, parsed_proposal.proposal_id),
            "metadata": next_metadata,
        }
    )
    pending = {
        "contract_type": PENDING_CONTRACT_TYPE,
        "schema_version": PENDING_SCHEMA_VERSION,
        "status": "pending_approval",
        "reversible": True,
        "proposal": parsed_proposal.to_dict(),
        "tape": normalized_tape,
        "tape_sha256": digest,
        "safety": {
            "proposal_only": True,
            "automatic_actions": False,
            "external_side_effects": False,
        },
    }
    return next_state, pending


__all__ = [
    "PENDING_CONTRACT_TYPE",
    "PENDING_SCHEMA_VERSION",
    "SemanticLightFieldBridgeError",
    "TAPE_SCHEMA",
    "adapt_semantic_light_field",
    "resolve_semantic_light_field_tape",
]

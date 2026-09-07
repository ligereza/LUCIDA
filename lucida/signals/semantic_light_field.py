"""Proposal-only semantic light-field projection for the RESOLUME surface."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from typing import Any, Mapping

from adapters.vj.contracts import VJProposal

from ..contracts import LucidaState
from ..surface_projection import (
    SurfaceProjectionProposalV1,
    SurfaceProjectionSafetyV1,
    SurfaceProjectionV1,
)


SEMANTIC_REPLAY_REPORT_TYPE = "MosaikSemanticLightFieldReplayReport"
SEMANTIC_REPLAY_SCHEMA_VERSION = "0.1"
SEMANTIC_TAPE_SCHEMA = "farmaxia:semantic-light-field-tape:0.1"
PENDING_METADATA_KEY = "resolume_semantic_light_field_pending"


class SemanticLightFieldSurfaceError(ValueError):
    """Raised when a MOSAIK semantic proposal cannot be projected safely."""


@dataclass(frozen=True)
class SemanticLightFieldPreview:
    """Bounded RESOLUME preview metadata with no tape frame payload."""

    proposal: VJProposal
    tape_sha256: str
    frame_count: int

    def to_dict(self) -> dict[str, Any]:
        projection = SurfaceProjectionV1(
            host_id="LUCIDA",
            surface_id="RESOLUME",
            status="pending_approval",
            proposal=SurfaceProjectionProposalV1(
                proposal_id=self.proposal.proposal_id,
                reason=self.proposal.reason,
                evidence=tuple(self.proposal.evidence),
                execution_mode=self.proposal.execution_mode,
                requires_explicit_approval=self.proposal.requires_explicit_approval,
                reversible=self.proposal.reversible,
            ),
            safety=SurfaceProjectionSafetyV1(
                proposal_only=True,
                automatic_actions=False,
                external_side_effects=False,
                host_opened=False,
            ),
        )
        return {
            "surface": "RESOLUME",
            "status": "pending_approval",
            "proposal": self.proposal.to_dict(),
            "projection": projection.to_dict(),
            "tape": {
                "schema": SEMANTIC_TAPE_SCHEMA,
                "sha256": self.tape_sha256,
                "frame_count": self.frame_count,
                "calibration_status": "not_calibrated",
            },
            "safety": {
                "proposal_only": True,
                "reversible": True,
                "automatic_actions": False,
                "resolume_opened": False,
                "external_side_effects": False,
            },
        }


def project_semantic_light_field_report(
    state: LucidaState | Mapping[str, Any],
    report: Mapping[str, Any],
) -> tuple[LucidaState, dict[str, Any]]:
    """Project one validated MOSAIK report into the existing LUCIDA state surface."""
    current = state if isinstance(state, LucidaState) else LucidaState.from_dict(state)
    preview = _validate_report(report)
    if preview.proposal.proposal_id in current.vj_state.pending_proposal_ids:
        raise SemanticLightFieldSurfaceError(
            "semantic light-field proposal is already pending on the RESOLUME surface."
        )
    if any(item.proposal_id == preview.proposal.proposal_id for item in current.proposals):
        raise SemanticLightFieldSurfaceError(
            "semantic light-field proposal already exists on the RESOLUME surface."
        )

    reference = {
        "proposal_id": preview.proposal.proposal_id,
        "tape_schema": SEMANTIC_TAPE_SCHEMA,
        "tape_sha256": preview.tape_sha256,
        "frame_count": preview.frame_count,
        "status": "pending_approval",
        "execution_mode": "proposal_only",
    }
    existing_refs = current.metadata.get(PENDING_METADATA_KEY, [])
    if not isinstance(existing_refs, list):
        raise SemanticLightFieldSurfaceError(
            "RESOLUME semantic light-field metadata is invalid."
        )
    next_vj_state = replace(
        current.vj_state,
        pending_proposal_ids=(
            *current.vj_state.pending_proposal_ids,
            preview.proposal.proposal_id,
        ),
    )
    next_state = replace(
        current,
        vj_state=next_vj_state,
        proposals=(*current.proposals, preview.proposal),
        overlay_status="proposal_pending",
        metadata={
            **current.metadata,
            PENDING_METADATA_KEY: [*existing_refs, reference],
        },
    )
    return next_state, preview.to_dict()


def semantic_light_field_preview_from_state(
    state: LucidaState | Mapping[str, Any],
) -> dict[str, Any] | None:
    """Rebuild the bounded preview from persisted pending surface state."""
    current = state if isinstance(state, LucidaState) else LucidaState.from_dict(state)
    refs = current.metadata.get(PENDING_METADATA_KEY)
    if not isinstance(refs, list):
        return None
    pending_ids = set(current.vj_state.pending_proposal_ids)
    for raw_ref in refs:
        if not isinstance(raw_ref, Mapping):
            continue
        proposal_id = raw_ref.get("proposal_id")
        if (
            raw_ref.get("status") != "pending_approval"
            or not isinstance(proposal_id, str)
            or proposal_id not in pending_ids
        ):
            continue
        proposal = next(
            (
                item
                for item in current.proposals
                if item.proposal_id == proposal_id
                and item.operation == "preview_semantic_light_field"
                and item.execution_mode == "proposal_only"
                and item.requires_explicit_approval is True
                and item.reversible is True
            ),
            None,
        )
        tape_sha256 = raw_ref.get("tape_sha256")
        frame_count = raw_ref.get("frame_count")
        if (
            proposal is None
            or raw_ref.get("tape_schema") != SEMANTIC_TAPE_SCHEMA
            or not isinstance(tape_sha256, str)
            or len(tape_sha256) != 64
            or any(char not in "0123456789abcdef" for char in tape_sha256)
            or isinstance(frame_count, bool)
            or not isinstance(frame_count, int)
            or frame_count <= 0
        ):
            continue
        return SemanticLightFieldPreview(proposal, tape_sha256, frame_count).to_dict()
    return None


def _validate_report(report: Mapping[str, Any]) -> SemanticLightFieldPreview:
    if not isinstance(report, Mapping):
        raise SemanticLightFieldSurfaceError("semantic light-field report must be an object.")
    if report.get("replay_type") != SEMANTIC_REPLAY_REPORT_TYPE:
        raise SemanticLightFieldSurfaceError("semantic light-field report type is invalid.")
    if report.get("schema_version") != SEMANTIC_REPLAY_SCHEMA_VERSION:
        raise SemanticLightFieldSurfaceError(
            "semantic light-field report schema version is unsupported."
        )
    if report.get("status") != "PASS":
        raise SemanticLightFieldSurfaceError("semantic light-field report is not ready.")
    report_state = report.get("state")
    if not isinstance(report_state, Mapping) or not isinstance(
        report_state.get("pending_proposal_ids"), list
    ):
        raise SemanticLightFieldSurfaceError(
            "semantic light-field report state is missing pending proposal ids."
        )
    report_safety = report.get("safety")
    if not isinstance(report_safety, Mapping) or report_safety != {
        "external_side_effects": False,
        "irreversible_actions_executed": False,
        "automatic_decision": False,
        "execution_mode": "proposal_only",
    }:
        raise SemanticLightFieldSurfaceError("semantic light-field report safety is invalid.")
    proposal_value = report.get("proposal")
    pending = report.get("pending")
    if not isinstance(proposal_value, Mapping) or not isinstance(pending, Mapping):
        raise SemanticLightFieldSurfaceError(
            "semantic light-field report needs proposal and pending objects."
        )
    if pending.get("status") != "pending_approval" or pending.get("reversible") is not True:
        raise SemanticLightFieldSurfaceError(
            "semantic light-field report must remain pending and reversible."
        )
    if pending.get("proposal") != dict(proposal_value):
        raise SemanticLightFieldSurfaceError(
            "semantic light-field pending proposal does not match the report proposal."
        )
    safety = pending.get("safety")
    if not isinstance(safety, Mapping) or safety != {
        "proposal_only": True,
        "automatic_actions": False,
        "external_side_effects": False,
    }:
        raise SemanticLightFieldSurfaceError(
            "semantic light-field pending safety contract is invalid."
        )
    try:
        proposal = VJProposal.from_dict(proposal_value)
    except (TypeError, ValueError) as exc:
        raise SemanticLightFieldSurfaceError(
            "semantic light-field proposal contract is invalid."
        ) from exc
    if proposal.operation != "preview_semantic_light_field":
        raise SemanticLightFieldSurfaceError(
            "semantic light-field proposal operation is unsupported."
        )
    if proposal.proposal_id not in report_state["pending_proposal_ids"]:
        raise SemanticLightFieldSurfaceError(
            "semantic light-field report state does not contain the proposal."
        )
    evidence = _proposal_evidence(proposal)
    tape = pending.get("tape")
    if not isinstance(tape, Mapping):
        raise SemanticLightFieldSurfaceError("semantic light-field pending tape is missing.")
    normalized_tape, digest = _validate_tape(tape, evidence)
    pending_digest = pending.get("tape_sha256")
    if pending_digest != digest:
        raise SemanticLightFieldSurfaceError(
            "semantic light-field pending tape hash does not match the tape."
        )
    if len(normalized_tape["frames"]) != int(evidence["frame_count"]):
        raise SemanticLightFieldSurfaceError(
            "semantic light-field pending frame count does not match the proposal."
        )
    return SemanticLightFieldPreview(proposal, digest, len(normalized_tape["frames"]))


def _proposal_evidence(proposal: VJProposal) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in proposal.evidence:
        key, separator, value = item.partition(":")
        if not separator or not key or not value or key in values:
            raise SemanticLightFieldSurfaceError("semantic light-field evidence is invalid.")
        values[key] = value
    required = {"consumer", "tape_schema", "tape_sha256", "frame_count"}
    if not required <= values.keys():
        raise SemanticLightFieldSurfaceError("semantic light-field evidence is incomplete.")
    if values["consumer"] != "mosaik-vj":
        raise SemanticLightFieldSurfaceError("semantic light-field consumer is unsupported.")
    if values["tape_schema"] != SEMANTIC_TAPE_SCHEMA:
        raise SemanticLightFieldSurfaceError("semantic light-field tape schema is unsupported.")
    digest = values["tape_sha256"]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise SemanticLightFieldSurfaceError("semantic light-field tape hash is invalid.")
    count = values["frame_count"]
    if not count.isascii() or not count.isdecimal() or int(count) <= 0:
        raise SemanticLightFieldSurfaceError("semantic light-field frame count is invalid.")
    return values


def _validate_tape(
    tape: Mapping[str, Any], evidence: Mapping[str, str]
) -> tuple[dict[str, Any], str]:
    if tape.get("schema") != SEMANTIC_TAPE_SCHEMA:
        raise SemanticLightFieldSurfaceError("semantic light-field tape schema is unsupported.")
    if tape.get("proposal_only") is not True:
        raise SemanticLightFieldSurfaceError("semantic light-field tape is not proposal_only.")
    if tape.get("calibration_status") != "not_calibrated":
        raise SemanticLightFieldSurfaceError(
            "semantic light-field tape calibration status is invalid."
        )
    sample_hz = tape.get("sample_hz")
    if (
        isinstance(sample_hz, bool)
        or not isinstance(sample_hz, (int, float))
        or not math.isfinite(sample_hz)
        or sample_hz <= 0
    ):
        raise SemanticLightFieldSurfaceError("semantic light-field tape sample_hz is invalid.")
    frames = tape.get("frames")
    if not isinstance(frames, list) or not frames:
        raise SemanticLightFieldSurfaceError("semantic light-field tape frames are invalid.")
    for index, frame in enumerate(frames):
        if not isinstance(frame, Mapping) or frame.get("proposal_only") is not True:
            raise SemanticLightFieldSurfaceError(
                "semantic light-field tape frame %d is not proposal_only." % index
            )
    try:
        encoded = json.dumps(
            tape,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        normalized = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise SemanticLightFieldSurfaceError(
            "semantic light-field tape must contain finite JSON values."
        ) from exc
    digest = hashlib.sha256(encoded.encode("ascii")).hexdigest()
    if digest != evidence["tape_sha256"]:
        raise SemanticLightFieldSurfaceError("semantic light-field tape hash does not match.")
    return normalized, digest


__all__ = [
    "PENDING_METADATA_KEY",
    "SEMANTIC_REPLAY_REPORT_TYPE",
    "SEMANTIC_REPLAY_SCHEMA_VERSION",
    "SEMANTIC_TAPE_SCHEMA",
    "SemanticLightFieldPreview",
    "SemanticLightFieldSurfaceError",
    "project_semantic_light_field_report",
    "semantic_light_field_preview_from_state",
]

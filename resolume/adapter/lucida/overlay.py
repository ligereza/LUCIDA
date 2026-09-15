"""Bounded read-only view for the future LUCIDA overlay surface."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Mapping

from adapters.vj.contracts import VJProposal

from .contracts import CAPABILITY_NAMES, LucidaState


OVERLAY_VIEW_SCHEMA_VERSION = "0.1"
OVERLAY_DIFF_FIELDS = (
    "status",
    "overlay_status",
    "capabilities",
    "pending_proposals",
    "unknowns",
    "next_attention",
    "safety",
)
MAX_DIFF_CHANGES = len(OVERLAY_DIFF_FIELDS)
_OVERLAY_FIELDS = {
    "contract_type",
    "schema_version",
    "surface",
    "mode",
    "session_id",
    "phase",
    "status",
    "overlay_status",
    "capabilities",
    "pending_proposals",
    "unknowns",
    "next_attention",
    "safety",
}
_CAPABILITY_VIEW_FIELDS = {
    "capability",
    "state",
    "observed_count",
    "expected_result_count",
    "unknowns",
}
_PROPOSAL_VIEW_FIELDS = {
    "proposal_id",
    "event_id",
    "phase",
    "operation",
    "reason",
    "risk",
    "requires_explicit_approval",
    "reversible",
    "execution_mode",
}
_NEXT_ATTENTION_FIELDS = {"kind", "id", "reason"}
_SAFETY_FIELDS = {"proposal_only", "automatic_actions", "external_side_effects"}
_CURSOR_FIELDS = {
    "contract_type",
    "schema_version",
    "surface",
    "mode",
    "session_id",
    "sequence",
    "last_event_id",
    "last_timestamp",
    "checkpoint_id",
    "safety",
}
_UPDATE_FIELDS = {
    "contract_type",
    "schema_version",
    "surface",
    "mode",
    "view",
    "view_digest",
    "changes",
    "cursor",
    "safety",
}
_DEFAULT_CAPABILITY_LIMIT = 3
_DEFAULT_PROPOSAL_LIMIT = 8
_DEFAULT_UNKNOWNS_LIMIT = 8
_RISK_ORDER = {"high": 0, "medium": 1, "low": 2}
_SAFE_STATE_KEYS = (
    "status",
    "media_status",
    "signal_status",
    "show_status",
    "recovery_status",
    "profile_status",
    "profile_stage",
    "profile_unknown_count",
    "profile_inferred_count",
    "profile_min_confidence",
    "processor_read_only",
    "profile_comparison_status",
    "profile_changed_count",
    "profile_confidence_drop_count",
    "profile_unknown_delta",
    "profile_recommendation_changed",
    "profile_read_only_changed",
    "profile_stage_changed",
    "profile_context_status",
)


class OverlayDiffError(ValueError):
    """Raised when an overlay diff input is not a projected view."""


class OverlayCursorError(ValueError):
    """Raised when an overlay cursor cannot describe a safe state revision."""


class OverlayUpdateError(ValueError):
    """Raised when an atomic overlay update is incomplete or unsafe."""


def diff_overlay_view(
    previous_view: Mapping[str, Any],
    current_view: Mapping[str, Any],
    *,
    max_changes: int = MAX_DIFF_CHANGES,
) -> list[dict[str, Any]]:
    """Return bounded, deterministic changes between two projected views."""

    if isinstance(max_changes, bool) or not isinstance(max_changes, int) or max_changes < 0:
        raise OverlayDiffError("max_changes must be a non-negative integer")
    previous = _validated_projected_view(previous_view, "previous_view")
    current = _validated_projected_view(current_view, "current_view")
    changes: list[dict[str, Any]] = []
    for field_name in OVERLAY_DIFF_FIELDS:
        before = previous[field_name]
        after = current[field_name]
        if before != after:
            changes.append(
                {
                    "field": field_name,
                    "before": _json_copy(before),
                    "after": _json_copy(after),
                }
            )
    return changes[:max_changes]


def overlay_view_digest(view: Mapping[str, Any]) -> str:
    """Return a deterministic digest for one validated projected view."""

    validated = _validated_projected_view(view, "overlay_view")
    canonical = json.dumps(
        validated,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validated_projected_view(value: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OverlayDiffError(f"{field_name} must be a mapping.")
    unexpected = set(value) - _OVERLAY_FIELDS
    if unexpected:
        raise OverlayDiffError(
            f"{field_name} has unsupported fields: {sorted(unexpected)}."
        )
    required = _OVERLAY_FIELDS
    missing = required - set(value)
    if missing:
        raise OverlayDiffError(f"{field_name} missing fields: {sorted(missing)}.")
    if value.get("contract_type") != "LucidaOverlayView":
        raise OverlayDiffError(f"{field_name}.contract_type must be LucidaOverlayView.")
    if value.get("schema_version") != OVERLAY_VIEW_SCHEMA_VERSION:
        raise OverlayDiffError(
            f"{field_name}.schema_version must be {OVERLAY_VIEW_SCHEMA_VERSION}."
        )
    if value.get("surface") != "LUCIDA":
        raise OverlayDiffError(f"{field_name}.surface must be LUCIDA.")
    if value.get("mode") != "read_only":
        raise OverlayDiffError(f"{field_name}.mode must be read_only.")
    for text_field in ("session_id", "phase", "status", "overlay_status"):
        if not isinstance(value.get(text_field), str):
            raise OverlayDiffError(f"{field_name}.{text_field} must be text.")
    for list_field in ("capabilities", "pending_proposals", "unknowns"):
        if not isinstance(value.get(list_field), list):
            raise OverlayDiffError(f"{field_name}.{list_field} must be a list.")
    for capability in value["capabilities"]:
        if not isinstance(capability, Mapping):
            raise OverlayDiffError(f"{field_name}.capabilities items must be objects.")
        if set(capability) != _CAPABILITY_VIEW_FIELDS:
            raise OverlayDiffError(f"{field_name}.capabilities contains unsupported fields.")
        if not isinstance(capability.get("state"), Mapping):
            raise OverlayDiffError(f"{field_name}.capabilities state must be an object.")
        if not set(capability["state"]).issubset(_SAFE_STATE_KEYS):
            raise OverlayDiffError(f"{field_name}.capabilities state contains unsafe fields.")
        if not isinstance(capability.get("unknowns"), list):
            raise OverlayDiffError(f"{field_name}.capabilities unknowns must be a list.")
    for proposal in value["pending_proposals"]:
        if not isinstance(proposal, Mapping):
            raise OverlayDiffError(f"{field_name}.pending_proposals items must be objects.")
        if set(proposal) != _PROPOSAL_VIEW_FIELDS:
            raise OverlayDiffError(f"{field_name}.pending_proposals contains unsupported fields.")
        if proposal.get("requires_explicit_approval") is not True:
            raise OverlayDiffError(f"{field_name}.pending_proposals must require approval.")
        if proposal.get("reversible") is not True:
            raise OverlayDiffError(f"{field_name}.pending_proposals must be reversible.")
        if proposal.get("execution_mode") != "proposal_only":
            raise OverlayDiffError(f"{field_name}.pending_proposals must be proposal_only.")
    next_attention = value.get("next_attention")
    if not isinstance(next_attention, Mapping):
        raise OverlayDiffError(f"{field_name}.next_attention must be an object.")
    if set(next_attention) != _NEXT_ATTENTION_FIELDS:
        raise OverlayDiffError(f"{field_name}.next_attention contains unsupported fields.")
    if not all(isinstance(next_attention.get(key), str) for key in _NEXT_ATTENTION_FIELDS):
        raise OverlayDiffError(f"{field_name}.next_attention must contain text fields.")
    safety = value.get("safety")
    if not isinstance(safety, Mapping):
        raise OverlayDiffError(f"{field_name}.safety must be an object.")
    if set(safety) != _SAFETY_FIELDS:
        raise OverlayDiffError(f"{field_name}.safety contains unsupported fields.")
    if safety.get("proposal_only") is not True:
        raise OverlayDiffError(f"{field_name}.safety must remain proposal_only.")
    if safety.get("automatic_actions") is not False or safety.get("external_side_effects") is not False:
        raise OverlayDiffError(f"{field_name}.safety must remain read_only.")
    return _json_copy(dict(value))


def _json_copy(value: Any) -> Any:
    try:
        serialized = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise OverlayDiffError("overlay values must be JSON serializable.") from exc
    return json.loads(serialized)


def build_overlay_view(
    state: LucidaState | Mapping[str, Any],
    *,
    max_capabilities: int = _DEFAULT_CAPABILITY_LIMIT,
    max_proposals: int = _DEFAULT_PROPOSAL_LIMIT,
    max_unknowns: int = _DEFAULT_UNKNOWNS_LIMIT,
) -> dict[str, Any]:
    """Project internal state into bounded data for a read-only overlay.

    The projection deliberately omits event payloads, arbitrary metadata,
    filesystem paths, credentials, and host execution details.
    """

    current = state if isinstance(state, LucidaState) else LucidaState.from_dict(state)
    limits = (
        (max_capabilities, "max_capabilities"),
        (max_proposals, "max_proposals"),
        (max_unknowns, "max_unknowns"),
    )
    for limit, name in limits:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    capability_order = {name: index for index, name in enumerate(CAPABILITY_NAMES)}
    reports = sorted(
        current.capabilities,
        key=lambda report: (capability_order.get(report.capability, len(CAPABILITY_NAMES)), report.capability),
    )[:max_capabilities]
    capability_views = [
        {
            "capability": report.capability,
            "state": _safe_state(report.state),
            "observed_count": len(report.observed),
            "expected_result_count": len(report.expected_results),
            "unknowns": sorted(set(report.unknowns))[:max_unknowns],
        }
        for report in reports
    ]

    pending_ids = set(current.vj_state.pending_proposal_ids)
    proposals = [
        proposal
        for proposal in current.proposals
        if proposal.proposal_id in pending_ids
    ]
    proposals.sort(
        key=lambda proposal: (
            _RISK_ORDER.get(proposal.risk, len(_RISK_ORDER)),
            proposal.phase,
            proposal.operation,
            proposal.proposal_id,
        )
    )
    proposal_views = [_proposal_view(proposal) for proposal in proposals[:max_proposals]]

    unknowns = sorted(
        {
            unknown
            for report in current.capabilities
            for unknown in report.unknowns
            if isinstance(unknown, str) and unknown.strip()
        }
    )[:max_unknowns]
    next_attention = _next_attention(proposal_views, unknowns, current.vj_state.phase)

    return {
        "contract_type": "LucidaOverlayView",
        "schema_version": OVERLAY_VIEW_SCHEMA_VERSION,
        "surface": "LUCIDA",
        "mode": "read_only",
        "session_id": current.session_id,
        "phase": current.vj_state.phase,
        "status": current.vj_state.status,
        "overlay_status": current.overlay_status,
        "capabilities": capability_views,
        "pending_proposals": proposal_views,
        "unknowns": unknowns,
        "next_attention": next_attention,
        "safety": {
            "proposal_only": True,
            "automatic_actions": False,
            "external_side_effects": False,
        },
    }


def build_overlay_cursor(state: LucidaState | Mapping[str, Any]) -> dict[str, Any]:
    """Project the safe state position for incremental overlay consumers."""

    current = state if isinstance(state, LucidaState) else LucidaState.from_dict(state)
    vj_state = current.vj_state
    if isinstance(vj_state.sequence, bool) or not isinstance(vj_state.sequence, int) or vj_state.sequence < 0:
        raise OverlayCursorError("state sequence must be a non-negative integer.")
    for field_name in ("last_event_id", "last_timestamp", "checkpoint_id"):
        value = getattr(vj_state, field_name)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise OverlayCursorError(f"{field_name} must be text or null.")
    return validate_overlay_cursor(
        {
            "contract_type": "LucidaOverlayCursor",
            "schema_version": OVERLAY_VIEW_SCHEMA_VERSION,
            "surface": "LUCIDA",
            "mode": "read_only",
            "session_id": current.session_id,
            "sequence": vj_state.sequence,
            "last_event_id": vj_state.last_event_id,
            "last_timestamp": vj_state.last_timestamp,
            "checkpoint_id": vj_state.checkpoint_id,
            "safety": {
                "proposal_only": True,
                "automatic_actions": False,
                "external_side_effects": False,
            },
        }
    )


def validate_overlay_cursor(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and copy a cursor without exposing internal state."""

    if not isinstance(value, Mapping):
        raise OverlayCursorError("overlay cursor must be a mapping.")
    if set(value) != _CURSOR_FIELDS:
        raise OverlayCursorError("overlay cursor contains unsupported or missing fields.")
    if value.get("contract_type") != "LucidaOverlayCursor":
        raise OverlayCursorError("overlay cursor contract_type is invalid.")
    if value.get("schema_version") != OVERLAY_VIEW_SCHEMA_VERSION:
        raise OverlayCursorError("overlay cursor schema_version is invalid.")
    if value.get("surface") != "LUCIDA" or value.get("mode") != "read_only":
        raise OverlayCursorError("overlay cursor surface or mode is invalid.")
    if not isinstance(value.get("session_id"), str) or not value["session_id"].strip():
        raise OverlayCursorError("overlay cursor session_id must be non-empty text.")
    sequence = value.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise OverlayCursorError("overlay cursor sequence must be a non-negative integer.")
    for field_name in ("last_event_id", "last_timestamp", "checkpoint_id"):
        field_value = value.get(field_name)
        if field_value is not None and (
            not isinstance(field_value, str) or not field_value.strip()
        ):
            raise OverlayCursorError(f"overlay cursor {field_name} must be text or null.")
    if value["last_timestamp"] is not None:
        try:
            datetime.fromisoformat(value["last_timestamp"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise OverlayCursorError("overlay cursor last_timestamp must be ISO-8601.") from exc
    safety = value.get("safety")
    if not isinstance(safety, Mapping) or set(safety) != _SAFETY_FIELDS:
        raise OverlayCursorError("overlay cursor safety is invalid.")
    if (
        safety.get("proposal_only") is not True
        or safety.get("automatic_actions") is not False
        or safety.get("external_side_effects") is not False
    ):
        raise OverlayCursorError("overlay cursor safety must remain read_only.")
    return _json_copy(dict(value))


def build_overlay_update(
    previous_state: LucidaState | Mapping[str, Any],
    current_state: LucidaState | Mapping[str, Any],
    *,
    max_changes: int = MAX_DIFF_CHANGES,
) -> dict[str, Any]:
    """Build one self-contained view, diff, and cursor envelope.

    Atomic updates reject a truncated diff. The complete projected view is
    included so a host can verify the result before accepting the delta.
    """

    if (
        isinstance(max_changes, bool)
        or not isinstance(max_changes, int)
        or max_changes < 0
        or max_changes > MAX_DIFF_CHANGES
    ):
        raise OverlayUpdateError("max_changes must be between 0 and the safe field bound.")
    previous_view = build_overlay_view(previous_state)
    current_view = build_overlay_view(current_state)
    complete_changes = diff_overlay_view(
        previous_view,
        current_view,
        max_changes=MAX_DIFF_CHANGES,
    )
    changes = diff_overlay_view(
        previous_view,
        current_view,
        max_changes=max_changes,
    )
    if changes != complete_changes:
        raise OverlayUpdateError("max_changes would truncate an atomic overlay update.")
    return validate_overlay_update(
        {
            "contract_type": "LucidaOverlayUpdate",
            "schema_version": OVERLAY_VIEW_SCHEMA_VERSION,
            "surface": "LUCIDA",
            "mode": "read_only",
            "view": current_view,
            "view_digest": overlay_view_digest(current_view),
            "changes": changes,
            "cursor": build_overlay_cursor(current_state),
            "safety": {
                "proposal_only": True,
                "automatic_actions": False,
                "external_side_effects": False,
            },
        }
    )


def validate_overlay_update(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an atomic update envelope without applying it."""

    if not isinstance(value, Mapping):
        raise OverlayUpdateError("overlay update must be a mapping.")
    if set(value) != _UPDATE_FIELDS:
        raise OverlayUpdateError("overlay update contains unsupported or missing fields.")
    if value.get("contract_type") != "LucidaOverlayUpdate":
        raise OverlayUpdateError("overlay update contract_type is invalid.")
    if value.get("schema_version") != OVERLAY_VIEW_SCHEMA_VERSION:
        raise OverlayUpdateError("overlay update schema_version is invalid.")
    if value.get("surface") != "LUCIDA" or value.get("mode") != "read_only":
        raise OverlayUpdateError("overlay update surface or mode is invalid.")
    try:
        view = _validated_projected_view(value["view"], "overlay update view")
    except OverlayDiffError as exc:
        raise OverlayUpdateError(str(exc)) from exc
    try:
        cursor = validate_overlay_cursor(value["cursor"])
    except OverlayCursorError as exc:
        raise OverlayUpdateError(str(exc)) from exc
    if view["session_id"] != cursor["session_id"]:
        raise OverlayUpdateError("overlay update view and cursor sessions differ.")
    view_digest = value["view_digest"]
    if not isinstance(view_digest, str) or len(view_digest) != 64:
        raise OverlayUpdateError("overlay update view_digest must be a SHA-256 hex digest.")
    if any(character not in "0123456789abcdef" for character in view_digest):
        raise OverlayUpdateError("overlay update view_digest must be lowercase hexadecimal.")
    if view_digest != overlay_view_digest(view):
        raise OverlayUpdateError("overlay update view_digest does not match the view.")
    changes = value["changes"]
    if not isinstance(changes, list):
        raise OverlayUpdateError("overlay update changes must be a list.")
    if len(changes) > MAX_DIFF_CHANGES:
        raise OverlayUpdateError("overlay update changes exceed the safe field bound.")
    copied_changes: list[dict[str, Any]] = []
    for change in changes:
        if not isinstance(change, Mapping) or set(change) != {"field", "before", "after"}:
            raise OverlayUpdateError("each overlay update change must have field, before, and after.")
        if change["field"] not in OVERLAY_DIFF_FIELDS:
            raise OverlayUpdateError("overlay update change field is not safe.")
        try:
            copied_changes.append(_json_copy(dict(change)))
        except OverlayDiffError as exc:
            raise OverlayUpdateError(str(exc)) from exc
    safety = value["safety"]
    if not isinstance(safety, Mapping) or set(safety) != _SAFETY_FIELDS:
        raise OverlayUpdateError("overlay update safety is invalid.")
    if (
        safety.get("proposal_only") is not True
        or safety.get("automatic_actions") is not False
        or safety.get("external_side_effects") is not False
    ):
        raise OverlayUpdateError("overlay update safety must remain read_only.")
    return {
        "contract_type": "LucidaOverlayUpdate",
        "schema_version": OVERLAY_VIEW_SCHEMA_VERSION,
        "surface": "LUCIDA",
        "mode": "read_only",
        "view": view,
        "view_digest": view_digest,
        "changes": copied_changes,
        "cursor": cursor,
        "safety": _json_copy(dict(safety)),
    }


def _safe_state(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    safe: dict[str, Any] = {}
    for key in _SAFE_STATE_KEYS:
        item = value.get(key)
        if isinstance(item, (str, int, float, bool)) or item is None:
            safe[key] = item
    return safe


def _proposal_view(proposal: VJProposal) -> dict[str, Any]:
    return {
        "proposal_id": proposal.proposal_id,
        "event_id": proposal.event_id,
        "phase": proposal.phase,
        "operation": proposal.operation,
        "reason": proposal.reason,
        "risk": proposal.risk,
        "requires_explicit_approval": True,
        "reversible": True,
        "execution_mode": "proposal_only",
    }


def _next_attention(
    proposals: list[dict[str, Any]],
    unknowns: list[str],
    phase: str,
) -> dict[str, Any]:
    if proposals:
        proposal = proposals[0]
        return {
            "kind": "proposal",
            "id": proposal["proposal_id"],
            "reason": proposal["reason"],
        }
    if unknowns:
        return {"kind": "unknown", "id": "unknown-001", "reason": unknowns[0]}
    return {"kind": "phase", "id": f"phase-{phase}", "reason": "Awaiting the next event."}


__all__ = [
    "MAX_DIFF_CHANGES",
    "OVERLAY_DIFF_FIELDS",
    "OVERLAY_VIEW_SCHEMA_VERSION",
    "OverlayCursorError",
    "OverlayDiffError",
    "OverlayUpdateError",
    "build_overlay_cursor",
    "build_overlay_update",
    "build_overlay_view",
    "diff_overlay_view",
    "overlay_view_digest",
    "validate_overlay_cursor",
    "validate_overlay_update",
]

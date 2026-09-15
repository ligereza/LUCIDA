"""Host-neutral consumer for the bounded LUCIDA overlay contract."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Mapping

from .overlay import (
    MAX_DIFF_CHANGES,
    OVERLAY_DIFF_FIELDS,
    OVERLAY_VIEW_SCHEMA_VERSION,
    diff_overlay_view,
    overlay_view_digest,
    validate_overlay_cursor,
    validate_overlay_update,
)


class OverlayConsumerError(ValueError):
    """Base error for invalid overlay consumer input or state transitions."""


class OverlayConsumerNotInitializedError(OverlayConsumerError):
    """Raised when a delta is received before an initial snapshot."""


class OverlayConsumerStaleError(OverlayConsumerError):
    """Raised when an incoming cursor is older than the current cursor."""


class OverlayConsumerGapError(OverlayConsumerError):
    """Raised when an incoming cursor skips a state sequence."""


class OverlayConsumerConflictError(OverlayConsumerError):
    """Raised when a delta cannot be applied to the current safe view."""


@dataclass(frozen=True)
class OverlayConsumerState:
    """Recoverable local state held by an overlay consumer."""

    view: dict[str, Any] | None = None
    cursor: dict[str, Any] | None = None
    applied_delta_count: int = 0
    last_operation: str = "empty"

    @property
    def initialized(self) -> bool:
        return self.view is not None and self.cursor is not None


class OverlayConsumer:
    """Apply safe LUCIDA snapshots and deltas without executing actions."""

    def __init__(self, *, max_changes: int = MAX_DIFF_CHANGES) -> None:
        if (
            isinstance(max_changes, bool)
            or not isinstance(max_changes, int)
            or max_changes < 0
            or max_changes > MAX_DIFF_CHANGES
        ):
            raise OverlayConsumerError("max_changes must be a non-negative integer.")
        self._max_changes = max_changes
        self._state = OverlayConsumerState()

    @property
    def state(self) -> OverlayConsumerState:
        return replace(
            self._state,
            view=_copy_value(self._state.view) if self._state.view is not None else None,
            cursor=_copy_value(self._state.cursor) if self._state.cursor is not None else None,
        )

    @property
    def view(self) -> dict[str, Any] | None:
        return _copy_value(self._state.view) if self._state.view is not None else None

    @property
    def cursor(self) -> dict[str, Any] | None:
        return _copy_value(self._state.cursor) if self._state.cursor is not None else None

    def accept_snapshot(
        self,
        view: Mapping[str, Any],
        cursor: Mapping[str, Any],
        *,
        recovery: bool = False,
    ) -> OverlayConsumerState:
        """Accept an initial or explicitly authorized recovery snapshot."""

        if self._state.initialized and not recovery:
            raise OverlayConsumerConflictError(
                "A recovery snapshot requires recovery=True."
            )
        validated_view = _validated_view(view)
        validated_cursor = validate_overlay_cursor(cursor)
        if validated_view["session_id"] != validated_cursor["session_id"]:
            raise OverlayConsumerConflictError("snapshot view and cursor sessions differ.")
        self._state = OverlayConsumerState(
            view=validated_view,
            cursor=validated_cursor,
            applied_delta_count=self._state.applied_delta_count,
            last_operation="recovery_snapshot" if recovery else "initial_snapshot",
        )
        return self._state

    def apply_delta(
        self,
        changes: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        cursor: Mapping[str, Any],
    ) -> OverlayConsumerState:
        """Apply one deterministic delta if its cursor is the next valid revision."""

        if not self._state.initialized:
            raise OverlayConsumerNotInitializedError(
                "An initial overlay snapshot is required before applying a delta."
            )
        if not isinstance(changes, (list, tuple)):
            raise OverlayConsumerConflictError("overlay changes must be a list.")
        if len(changes) > self._max_changes:
            raise OverlayConsumerConflictError("overlay changes exceed the configured bound.")

        validated_cursor = validate_overlay_cursor(cursor)
        _assert_cursor_progress(self._state.cursor, validated_cursor)
        current_view = _validated_view(self._state.view)
        try:
            next_view = _apply_changes(current_view, changes)
        except ValueError as exc:
            raise OverlayConsumerConflictError(str(exc)) from exc
        try:
            expected_changes = diff_overlay_view(
                current_view,
                next_view,
                max_changes=self._max_changes,
            )
        except ValueError as exc:
            raise OverlayConsumerConflictError(str(exc)) from exc
        supplied_changes = [_copy_value(dict(change)) for change in changes]
        if expected_changes != supplied_changes:
            raise OverlayConsumerConflictError(
                "overlay changes do not match the current bounded view."
            )
        self._state = replace(
            self._state,
            view=next_view,
            cursor=validated_cursor,
            applied_delta_count=self._state.applied_delta_count + 1,
            last_operation="delta",
        )
        return self._state

    def apply_update(self, update: Mapping[str, Any]) -> OverlayConsumerState:
        """Apply one atomic view, diff, and cursor envelope.

        The candidate view is verified against the envelope before delegating
        to the existing delta state machine, so a failed update is atomic.
        """

        if not self._state.initialized:
            raise OverlayConsumerNotInitializedError(
                "An initial overlay snapshot is required before applying an update."
            )
        try:
            validated = validate_overlay_update(update)
        except ValueError as exc:
            raise OverlayConsumerConflictError(str(exc)) from exc
        current_view = _validated_view(self._state.view)
        try:
            candidate_view = _apply_changes(current_view, validated["changes"])
        except ValueError as exc:
            raise OverlayConsumerConflictError(str(exc)) from exc
        if candidate_view != validated["view"]:
            raise OverlayConsumerConflictError(
                "overlay update view does not match its changes."
            )
        return self.apply_delta(validated["changes"], validated["cursor"])

    def checkpoint(self) -> dict[str, Any]:
        """Return a safe checkpoint that can be stored and restored explicitly."""

        if not self._state.initialized:
            return {
                "contract_type": "LucidaOverlayConsumerCheckpoint",
                "schema_version": OVERLAY_VIEW_SCHEMA_VERSION,
                "status": "empty",
                "applied_delta_count": 0,
                "last_operation": "empty",
                "view": None,
                "view_digest": None,
                "cursor": None,
                "safety": _safety(),
            }
        return {
            "contract_type": "LucidaOverlayConsumerCheckpoint",
            "schema_version": OVERLAY_VIEW_SCHEMA_VERSION,
            "status": "ready",
            "applied_delta_count": self._state.applied_delta_count,
            "last_operation": self._state.last_operation,
            "view": _copy_value(self._state.view),
            "view_digest": overlay_view_digest(self._state.view),
            "cursor": _copy_value(self._state.cursor),
            "safety": _safety(),
        }

    def restore_checkpoint(self, checkpoint: Mapping[str, Any]) -> OverlayConsumerState:
        """Restore only a validated consumer checkpoint; never execute an action."""

        if not isinstance(checkpoint, Mapping):
            raise OverlayConsumerError("consumer checkpoint must be a mapping.")
        required = {
            "contract_type",
            "schema_version",
            "status",
            "applied_delta_count",
            "last_operation",
            "view",
            "view_digest",
            "cursor",
            "safety",
        }
        if set(checkpoint) != required:
            raise OverlayConsumerError("consumer checkpoint contains unsupported fields.")
        if checkpoint.get("contract_type") != "LucidaOverlayConsumerCheckpoint":
            raise OverlayConsumerError("consumer checkpoint contract_type is invalid.")
        if checkpoint.get("schema_version") != OVERLAY_VIEW_SCHEMA_VERSION:
            raise OverlayConsumerError("consumer checkpoint schema_version is invalid.")
        if checkpoint.get("status") not in {"empty", "ready"}:
            raise OverlayConsumerError("consumer checkpoint status is invalid.")
        count = checkpoint.get("applied_delta_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise OverlayConsumerError("applied_delta_count must be a non-negative integer.")
        if checkpoint.get("last_operation") not in {
            "empty",
            "initial_snapshot",
            "recovery_snapshot",
            "delta",
        }:
            raise OverlayConsumerError("consumer checkpoint last_operation is invalid.")
        if checkpoint.get("safety") != _safety():
            raise OverlayConsumerError("consumer checkpoint safety is invalid.")
        view = checkpoint.get("view")
        view_digest = checkpoint.get("view_digest")
        cursor = checkpoint.get("cursor")
        if checkpoint["status"] == "empty":
            if (
                view is not None
                or view_digest is not None
                or cursor is not None
                or count != 0
                or checkpoint["last_operation"] != "empty"
            ):
                raise OverlayConsumerError("empty checkpoint cannot contain state.")
            self._state = OverlayConsumerState()
            return self._state
        if not isinstance(view, Mapping) or not isinstance(cursor, Mapping):
            raise OverlayConsumerError("ready checkpoint needs view and cursor.")
        if checkpoint["last_operation"] == "empty":
            raise OverlayConsumerError("ready checkpoint needs a non-empty last_operation.")
        validated_view = _validated_view(view)
        if view_digest != overlay_view_digest(validated_view):
            raise OverlayConsumerError("checkpoint view_digest does not match the view.")
        validated_cursor = validate_overlay_cursor(cursor)
        if validated_view["session_id"] != validated_cursor["session_id"]:
            raise OverlayConsumerError("checkpoint view and cursor sessions differ.")
        self._state = OverlayConsumerState(
            view=validated_view,
            cursor=validated_cursor,
            applied_delta_count=count,
            last_operation=checkpoint["last_operation"],
        )
        return self._state


def _validated_view(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        diff_overlay_view(value, value)
    except ValueError as exc:
        raise OverlayConsumerError(str(exc)) from exc
    return _copy_value(dict(value))


def _apply_changes(
    current_view: dict[str, Any],
    changes: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    next_view = _copy_value(current_view)
    seen_fields: set[str] = set()
    for change in changes:
        if not isinstance(change, Mapping):
            raise OverlayConsumerConflictError("each overlay change must be an object.")
        if set(change) != {"field", "before", "after"}:
            raise OverlayConsumerConflictError("each overlay change must have field, before, and after.")
        field_name = change["field"]
        if field_name not in OVERLAY_DIFF_FIELDS:
            raise OverlayConsumerConflictError("overlay change field is not safe.")
        if field_name in seen_fields:
            raise OverlayConsumerConflictError("overlay changes cannot repeat a field.")
        seen_fields.add(field_name)
        if current_view[field_name] != change["before"]:
            raise OverlayConsumerConflictError(
                f"overlay change before value does not match {field_name}."
            )
        next_view[field_name] = _copy_value(change["after"])
    return next_view


def _assert_cursor_progress(
    current: Mapping[str, Any] | None,
    incoming: Mapping[str, Any],
) -> None:
    if current is None:
        raise OverlayConsumerNotInitializedError("Current overlay cursor is missing.")
    if incoming["session_id"] != current["session_id"]:
        raise OverlayConsumerConflictError("overlay cursor sessions differ.")
    if incoming["sequence"] < current["sequence"]:
        raise OverlayConsumerStaleError("overlay cursor is older than the current cursor.")
    if incoming["sequence"] > current["sequence"] + 1:
        raise OverlayConsumerGapError("overlay cursor skips one or more sequences.")
    if incoming["sequence"] == current["sequence"]:
        for field_name in ("last_event_id", "last_timestamp", "checkpoint_id"):
            if incoming[field_name] != current[field_name]:
                raise OverlayConsumerConflictError(
                    "same sequence cannot change cursor identity fields."
                )
    if current["last_timestamp"] and incoming["last_timestamp"]:
        try:
            current_time = datetime.fromisoformat(current["last_timestamp"].replace("Z", "+00:00"))
            incoming_time = datetime.fromisoformat(incoming["last_timestamp"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise OverlayConsumerConflictError("overlay cursor timestamp is invalid.") from exc
        if incoming_time < current_time:
            raise OverlayConsumerStaleError("overlay cursor timestamp is older than the current cursor.")


def _safety() -> dict[str, bool]:
    return {
        "proposal_only": True,
        "automatic_actions": False,
        "external_side_effects": False,
    }


def _copy_value(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        )
    except (TypeError, ValueError) as exc:
        raise OverlayConsumerError("overlay consumer values must be JSON serializable.") from exc


__all__ = [
    "OverlayConsumer",
    "OverlayConsumerConflictError",
    "OverlayConsumerError",
    "OverlayConsumerGapError",
    "OverlayConsumerNotInitializedError",
    "OverlayConsumerStaleError",
    "OverlayConsumerState",
]

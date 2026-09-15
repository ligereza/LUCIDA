"""Deterministic replay of LUCIDA overlay JSON records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import LucidaState
from .overlay import (
    OVERLAY_VIEW_SCHEMA_VERSION,
    build_overlay_cursor,
    build_overlay_update,
    build_overlay_view,
    diff_overlay_view,
    validate_overlay_cursor,
    validate_overlay_update,
)
from .overlay_consumer import OverlayConsumer, OverlayConsumerError


class OverlayReplayError(ValueError):
    """Raised when an overlay replay envelope cannot be consumed safely."""


class OverlayReplayRecorder:
    """Build a deterministic replay envelope from successive LUCIDA states."""

    def __init__(self, session_id: str | None = None) -> None:
        if session_id is not None and (
            not isinstance(session_id, str) or not session_id.strip()
        ):
            raise OverlayReplayError("session_id must be non-empty text or null.")
        self._session_id = session_id
        self._state: LucidaState | None = None
        self._consumer = OverlayConsumer()
        self._records: list[dict[str, Any]] = []

    @property
    def record_count(self) -> int:
        return len(self._records)

    def start(self, state: LucidaState | Mapping[str, Any]) -> dict[str, Any]:
        """Start a recording with one explicit initial snapshot."""

        if self._records:
            raise OverlayReplayError("the replay recorder has already started.")
        current = _recorder_state(state)
        self._assert_session(current)
        record = _snapshot_record(current, recovery=False)
        try:
            self._consumer.accept_snapshot(record["view"], record["cursor"])
        except (OverlayConsumerError, KeyError, TypeError, ValueError) as exc:
            raise OverlayReplayError(f"initial snapshot cannot be recorded: {exc}") from exc
        self._state = current
        self._records.append(record)
        return _copy_json(record)

    def record(
        self,
        state: LucidaState | Mapping[str, Any],
        *,
        recovery: bool = False,
    ) -> dict[str, Any]:
        """Record one update or explicitly authorized recovery snapshot."""

        if self._state is None:
            raise OverlayReplayError("start() must be called before record().")
        if not isinstance(recovery, bool):
            raise OverlayReplayError("recovery must be boolean.")
        current = _recorder_state(state)
        self._assert_session(current)
        if recovery:
            record = _snapshot_record(current, recovery=True)
            try:
                self._consumer.accept_snapshot(
                    record["view"],
                    record["cursor"],
                    recovery=True,
                )
            except (OverlayConsumerError, KeyError, TypeError, ValueError) as exc:
                raise OverlayReplayError(f"recovery snapshot cannot be recorded: {exc}") from exc
        else:
            try:
                update = build_overlay_update(self._state, current)
                self._consumer.apply_update(update)
            except (OverlayConsumerError, KeyError, TypeError, ValueError) as exc:
                raise OverlayReplayError(f"atomic update cannot be recorded: {exc}") from exc
            record = {"kind": "update", "update": update}
        self._state = current
        self._records.append(record)
        return _copy_json(record)

    def envelope(self) -> dict[str, Any]:
        """Return the strict replay envelope without private state."""

        if not self._records:
            raise OverlayReplayError("the replay recorder has no records.")
        return {
            "contract_type": "LucidaOverlayReplay",
            "schema_version": OVERLAY_VIEW_SCHEMA_VERSION,
            "records": _copy_json(self._records),
        }

    def to_json(self) -> str:
        """Serialize the replay envelope with stable JSON formatting."""

        return json.dumps(
            self.envelope(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )

    def _assert_session(self, state: LucidaState) -> None:
        if self._session_id is None:
            self._session_id = state.session_id
        if state.session_id != self._session_id:
            raise OverlayReplayError("recorder state sessions differ.")


def replay_overlay_json(source: str | bytes | bytearray | Mapping[str, Any]) -> dict[str, Any]:
    """Replay an overlay envelope from JSON text or an already parsed mapping."""

    if isinstance(source, Mapping):
        envelope = source
    elif isinstance(source, (str, bytes, bytearray)):
        try:
            envelope = json.loads(source)
        except (TypeError, json.JSONDecodeError) as exc:
            raise OverlayReplayError("overlay replay input must be valid JSON.") from exc
    else:
        raise OverlayReplayError("overlay replay input must be JSON text or a mapping.")
    return replay_overlay_records(envelope)


def validate_overlay_replay(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a replay envelope without applying any record."""

    records = _validated_envelope(envelope)
    if not isinstance(records[0], Mapping) or records[0].get("kind") != "snapshot":
        raise OverlayReplayError("the first replay record must be a snapshot.")
    for index, record in enumerate(records):
        if record.get("kind") == "snapshot" and index != 0 and record["recovery"] is not True:
            raise OverlayReplayError("non-initial snapshots require recovery=true.")
    return {
        "contract_type": "LucidaOverlayReplay",
        "schema_version": OVERLAY_VIEW_SCHEMA_VERSION,
        "records": _copy_json(records),
    }


def replay_overlay_path(path: str | Path) -> dict[str, Any]:
    """Replay one local JSON file without opening a transport or host."""

    replay_path = Path(path).expanduser().resolve()
    if not replay_path.is_file():
        raise OverlayReplayError(f"overlay replay file does not exist: {replay_path}")
    try:
        source = replay_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise OverlayReplayError(f"overlay replay file cannot be read: {replay_path}") from exc
    return replay_overlay_json(source)


def _recorder_state(state: LucidaState | Mapping[str, Any]) -> LucidaState:
    try:
        return state if isinstance(state, LucidaState) else LucidaState.from_dict(state)
    except (KeyError, TypeError, ValueError) as exc:
        raise OverlayReplayError(f"recorder state is invalid: {exc}") from exc


def _snapshot_record(state: LucidaState, *, recovery: bool) -> dict[str, Any]:
    return {
        "kind": "snapshot",
        "recovery": recovery,
        "view": build_overlay_view(state),
        "cursor": build_overlay_cursor(state),
    }


def _copy_json(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as exc:
        raise OverlayReplayError("replay recorder values must be JSON serializable.") from exc


def replay_overlay_records(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Replay snapshot, delta, and atomic update records safely."""

    records = _validated_envelope(envelope)
    consumer = OverlayConsumer()
    operations: list[dict[str, Any]] = []
    snapshot_count = 0
    delta_count = 0
    update_count = 0

    for index, record in enumerate(records):
        kind = record.get("kind")
        try:
            if kind == "snapshot":
                if index != 0 and record["recovery"] is not True:
                    raise OverlayReplayError(
                        "non-initial snapshots require recovery=true."
                    )
                consumer.accept_snapshot(
                    record["view"],
                    record["cursor"],
                    recovery=record["recovery"],
                )
                snapshot_count += 1
                change_count = 0
            elif kind == "delta":
                if not consumer.state.initialized:
                    raise OverlayReplayError("the first replay record must be a snapshot.")
                consumer.apply_delta(record["changes"], record["cursor"])
                delta_count += 1
                change_count = len(record["changes"])
            else:
                if not consumer.state.initialized:
                    raise OverlayReplayError("the first replay record must be a snapshot.")
                consumer.apply_update(record["update"])
                update_count += 1
                change_count = len(record["update"]["changes"])
        except OverlayReplayError:
            raise
        except (OverlayConsumerError, KeyError, TypeError, ValueError) as exc:
            raise OverlayReplayError(f"record {index} cannot be applied: {exc}") from exc
        current_cursor = consumer.cursor
        operations.append(
            {
                "index": index,
                "kind": kind,
                "sequence": current_cursor["sequence"],
                "change_count": change_count,
                "last_operation": consumer.state.last_operation,
            }
        )

    if not consumer.state.initialized:
        raise OverlayReplayError("overlay replay needs at least one snapshot.")
    return {
        "contract_type": "LucidaOverlayReplayReport",
        "schema_version": OVERLAY_VIEW_SCHEMA_VERSION,
        "status": "PASS",
        "record_count": len(records),
        "snapshot_count": snapshot_count,
        "delta_count": delta_count,
        "update_count": update_count,
        "applied_delta_count": consumer.state.applied_delta_count,
        "operations": operations,
        "final_view": consumer.view,
        "final_cursor": consumer.cursor,
        "checkpoint": consumer.checkpoint(),
        "safety": {
            "replay_only": True,
            "proposal_only": True,
            "automatic_actions": False,
            "external_side_effects": False,
        },
    }


def _validated_envelope(envelope: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if not isinstance(envelope, Mapping):
        raise OverlayReplayError("overlay replay envelope must be an object.")
    required = {"contract_type", "schema_version", "records"}
    if set(envelope) != required:
        raise OverlayReplayError("overlay replay envelope contains unsupported fields.")
    if envelope.get("contract_type") != "LucidaOverlayReplay":
        raise OverlayReplayError("overlay replay contract_type is invalid.")
    if envelope.get("schema_version") != OVERLAY_VIEW_SCHEMA_VERSION:
        raise OverlayReplayError("overlay replay schema_version is invalid.")
    records = envelope.get("records")
    if not isinstance(records, list) or not records:
        raise OverlayReplayError("overlay replay needs a non-empty records list.")
    if records[0].get("kind") != "snapshot":
        raise OverlayReplayError("the first replay record must be a snapshot.")
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise OverlayReplayError(f"record {index} must be an object.")
        kind = record.get("kind")
        if kind == "snapshot":
            if set(record) != {"kind", "view", "cursor", "recovery"}:
                raise OverlayReplayError(f"snapshot record {index} has unsupported fields.")
            if not isinstance(record.get("recovery"), bool):
                raise OverlayReplayError(f"snapshot record {index} recovery must be boolean.")
            try:
                diff_overlay_view(record["view"], record["view"])
                cursor = validate_overlay_cursor(record["cursor"])
            except ValueError as exc:
                raise OverlayReplayError(f"snapshot record {index} is invalid: {exc}") from exc
            if record["view"]["session_id"] != cursor["session_id"]:
                raise OverlayReplayError(f"snapshot record {index} view and cursor sessions differ.")
        elif kind == "delta":
            if set(record) != {"kind", "changes", "cursor"}:
                raise OverlayReplayError(f"delta record {index} has unsupported fields.")
            if not isinstance(record.get("changes"), list):
                raise OverlayReplayError(f"delta record {index} changes must be a list.")
        elif kind == "update":
            if set(record) != {"kind", "update"}:
                raise OverlayReplayError(f"update record {index} has unsupported fields.")
            try:
                validate_overlay_update(record["update"])
            except ValueError as exc:
                raise OverlayReplayError(f"update record {index} is invalid: {exc}") from exc
        else:
            raise OverlayReplayError(f"record {index} kind is invalid.")
    return records


__all__ = [
    "OverlayReplayError",
    "OverlayReplayRecorder",
    "replay_overlay_json",
    "replay_overlay_path",
    "replay_overlay_records",
    "validate_overlay_replay",
]

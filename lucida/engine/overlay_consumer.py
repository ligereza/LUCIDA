"""Atomic consumer for the generic LUCIDA overlay frame contract."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any, Mapping

from .overlay_frame import OverlayFrame, OverlayFrameError, overlay_frame_digest, validate_overlay_frame


class OverlayConsumerError(ValueError):
    """Base error for invalid overlay consumer state or input."""


class OverlayConsumerNotInitializedError(OverlayConsumerError):
    """Raised when an update arrives before an initial snapshot."""


class OverlayConsumerStaleError(OverlayConsumerError):
    """Raised when an older frame arrives after a newer frame."""


class OverlayConsumerGapError(OverlayConsumerError):
    """Raised when a frame skips one or more revisions."""


class OverlayConsumerConflictError(OverlayConsumerError):
    """Raised when a revision is reused with different content."""


@dataclass(frozen=True)
class OverlayConsumerState:
    """Recoverable state held by a local frame consumer."""

    frame: dict[str, Any] | None = None
    digest: str | None = None
    applied_frame_count: int = 0
    last_operation: str = "empty"

    @property
    def initialized(self) -> bool:
        return self.frame is not None and self.digest is not None


class OverlayFrameConsumer:
    """Apply complete frames atomically without executing host actions."""

    def __init__(self) -> None:
        self._state = OverlayConsumerState()

    @property
    def state(self) -> OverlayConsumerState:
        return replace(self._state, frame=_copy_value(self._state.frame))

    @property
    def frame(self) -> dict[str, Any] | None:
        return _copy_value(self._state.frame)

    def accept_snapshot(
        self,
        frame: OverlayFrame | Mapping[str, Any],
        *,
        recovery: bool = False,
    ) -> OverlayConsumerState:
        """Accept the first frame or an explicitly authorized recovery frame."""

        if self._state.initialized and not recovery:
            raise OverlayConsumerConflictError("recovery snapshot requires recovery=True")
        validated = _parse_frame(frame)
        self._state = OverlayConsumerState(
            frame=validated.to_dict(),
            digest=overlay_frame_digest(validated),
            applied_frame_count=self._state.applied_frame_count,
            last_operation="recovery_snapshot" if recovery else "initial_snapshot",
        )
        return self.state

    def apply_frame(self, frame: OverlayFrame | Mapping[str, Any]) -> OverlayConsumerState:
        """Apply the next frame, accept an exact duplicate, or fail closed."""

        if not self._state.initialized:
            raise OverlayConsumerNotInitializedError("an initial overlay snapshot is required")
        validated = _parse_frame(frame)
        incoming = validated.to_dict()
        incoming_digest = overlay_frame_digest(validated)
        current = validate_overlay_frame(self._state.frame or {})
        if validated.session_id != current.session_id:
            raise OverlayConsumerConflictError("overlay frame sessions differ")
        if validated.revision < current.revision:
            raise OverlayConsumerStaleError("overlay frame is older than the current frame")
        if validated.revision == current.revision:
            if incoming_digest == self._state.digest:
                self._state = replace(self._state, last_operation="duplicate")
                return self.state
            raise OverlayConsumerConflictError("same revision cannot change frame content")
        if validated.revision > current.revision + 1:
            raise OverlayConsumerGapError("overlay frame skips one or more revisions")
        self._state = OverlayConsumerState(
            frame=incoming,
            digest=incoming_digest,
            applied_frame_count=self._state.applied_frame_count + 1,
            last_operation="frame",
        )
        return self.state


def _parse_frame(value: OverlayFrame | Mapping[str, Any]) -> OverlayFrame:
    if isinstance(value, OverlayFrame):
        return value
    try:
        return validate_overlay_frame(value)
    except OverlayFrameError as error:
        raise OverlayConsumerError(str(error)) from error


def _copy_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        return json.loads(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        )
    except (TypeError, ValueError) as error:
        raise OverlayConsumerError("overlay consumer values must be JSON serializable") from error


__all__ = [
    "OverlayConsumerConflictError",
    "OverlayConsumerError",
    "OverlayConsumerGapError",
    "OverlayConsumerNotInitializedError",
    "OverlayConsumerStaleError",
    "OverlayConsumerState",
    "OverlayFrameConsumer",
]

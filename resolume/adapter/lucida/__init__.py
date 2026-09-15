"""Single-surface LUCIDA integration for the VJ adapter."""

from .capabilities import ImagoCapability, InstarCapability, NayadeCapability
from .contracts import CapabilityReport, LucidaState
from .orchestrator import LucidaOrchestrator
from .overlay import (
    OverlayCursorError,
    OverlayDiffError,
    OverlayUpdateError,
    build_overlay_cursor,
    build_overlay_update,
    build_overlay_view,
    diff_overlay_view,
    overlay_view_digest,
    validate_overlay_update,
)
from .overlay_consumer import (
    OverlayConsumer,
    OverlayConsumerConflictError,
    OverlayConsumerError,
    OverlayConsumerGapError,
    OverlayConsumerNotInitializedError,
    OverlayConsumerStaleError,
    OverlayConsumerState,
)
from .overlay_replay import (
    OverlayReplayError,
    OverlayReplayRecorder,
    replay_overlay_json,
    replay_overlay_path,
    replay_overlay_records,
    validate_overlay_replay,
)

__all__ = [
    "CapabilityReport",
    "ImagoCapability",
    "InstarCapability",
    "LucidaOrchestrator",
    "LucidaState",
    "NayadeCapability",
    "OverlayCursorError",
    "OverlayDiffError",
    "OverlayUpdateError",
    "build_overlay_cursor",
    "build_overlay_update",
    "build_overlay_view",
    "diff_overlay_view",
    "overlay_view_digest",
    "validate_overlay_update",
    "OverlayConsumer",
    "OverlayConsumerConflictError",
    "OverlayConsumerError",
    "OverlayConsumerGapError",
    "OverlayConsumerNotInitializedError",
    "OverlayConsumerStaleError",
    "OverlayConsumerState",
    "OverlayReplayError",
    "OverlayReplayRecorder",
    "replay_overlay_json",
    "replay_overlay_path",
    "replay_overlay_records",
    "validate_overlay_replay",
]

"""Host-neutral Python reducer for the LUCIDA surface."""

from .adapters import AdapterRegistry, AdapterRegistryError, EventAdapter
from .input_contracts import ContractRegistry, InputContract, InputContractError
from .models import EngineEvent, EngineProposal, EngineState, RenderPlan
from .pipeline import EngineTransition, LucidaPipeline
from .reducer import LucidaEngine, EngineError
from .replay import ReplayError, replay_fixture, replay_path, replay_pipeline_fixture
from .domain_adapters import (
    DomainAdapterError,
    PupilaCoordinationAdapter,
    VizzMetadataAdapter,
    register_vizz_pupila_routes,
)
from .overlay_frame import (
    MAX_FRAME_ELEMENTS,
    OVERLAY_FRAME_SCHEMA_VERSION,
    OverlayFrame,
    OverlayFrameError,
    build_overlay_frame,
    overlay_frame_digest,
    validate_overlay_frame,
)
from .overlay_consumer import (
    OverlayConsumerConflictError,
    OverlayConsumerError,
    OverlayConsumerGapError,
    OverlayConsumerNotInitializedError,
    OverlayConsumerStaleError,
    OverlayConsumerState,
    OverlayFrameConsumer,
)

__all__ = [
    "AdapterRegistry",
    "AdapterRegistryError",
    "EventAdapter",
    "ContractRegistry",
    "EngineError",
    "EngineEvent",
    "EngineProposal",
    "EngineState",
    "InputContract",
    "InputContractError",
    "EngineTransition",
    "LucidaPipeline",
    "ReplayError",
    "replay_fixture",
    "replay_path",
    "replay_pipeline_fixture",
    "DomainAdapterError",
    "PupilaCoordinationAdapter",
    "VizzMetadataAdapter",
    "register_vizz_pupila_routes",
    "OverlayFrame",
    "OverlayFrameError",
    "build_overlay_frame",
    "overlay_frame_digest",
    "validate_overlay_frame",
    "MAX_FRAME_ELEMENTS",
    "OVERLAY_FRAME_SCHEMA_VERSION",
    "OverlayConsumerConflictError",
    "OverlayConsumerError",
    "OverlayConsumerGapError",
    "OverlayConsumerNotInitializedError",
    "OverlayConsumerStaleError",
    "OverlayConsumerState",
    "OverlayFrameConsumer",
    "LucidaEngine",
    "RenderPlan",
]

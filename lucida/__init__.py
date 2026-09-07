"""Single-surface LUCIDA integration for the VJ adapter."""

from .capabilities import ImagoCapability, InstarCapability, NayadeCapability
from .contracts import CapabilityReport, LucidaState
from .orchestrator import LucidaOrchestrator
from .surface_projection import (
    SurfaceProjectionError,
    SurfaceProjectionProposalV1,
    SurfaceProjectionSafetyV1,
    SurfaceProjectionV1,
)

__all__ = [
    "CapabilityReport",
    "ImagoCapability",
    "InstarCapability",
    "LucidaOrchestrator",
    "LucidaState",
    "NayadeCapability",
    "SurfaceProjectionError",
    "SurfaceProjectionProposalV1",
    "SurfaceProjectionSafetyV1",
    "SurfaceProjectionV1",
]

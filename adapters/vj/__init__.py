"""Reusable VJ adapter for the VJ interface layer.

The adapter is deliberately side-effect free: it consumes events and states,
returns proposals, and records results. It never talks to a live show by
itself.
"""

from .adapter import VJAdapter, VJAdapterError
from .contracts import VJEvent, VJResult, VJState, VJProposal

__all__ = [
    "VJAdapter",
    "VJAdapterError",
    "VJEvent",
    "VJResult",
    "VJState",
    "VJProposal",
]

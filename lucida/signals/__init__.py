"""Injected OSC/Resolume signal boundary for LUCIDA."""

from .boundary import (
    DuplicateEnvelopeError,
    EnvelopeValidationError,
    OscBridgeState,
    OscEnvelope,
    OscResolumeBoundary,
    OutgoingSenderError,
    SequenceOrderError,
    SignalReceive,
    UnknownAddressError,
)
from .replay import SignalReplayError, replay_fixture, replay_path

_XIO_EXPORTS = {
    "ApplicationEvent",
    "XioClockError",
    "XioConsumeResult",
    "XioConsumerError",
    "XioEventConsumer",
    "XioMappingError",
    "XioSchemaError",
    "convert_application_event",
    "consume_application_event",
    "parse_application_event",
}


def __getattr__(name: str):
    if name in _XIO_EXPORTS:
        from . import xio_bridge

        return getattr(xio_bridge, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "DuplicateEnvelopeError",
    "EnvelopeValidationError",
    "OscBridgeState",
    "OscEnvelope",
    "OscResolumeBoundary",
    "OutgoingSenderError",
    "SequenceOrderError",
    "SignalReceive",
    "SignalReplayError",
    "UnknownAddressError",
    "ApplicationEvent",
    "XioClockError",
    "XioConsumeResult",
    "XioConsumerError",
    "XioEventConsumer",
    "XioMappingError",
    "XioSchemaError",
    "convert_application_event",
    "consume_application_event",
    "parse_application_event",
    "replay_fixture",
    "replay_path",
]

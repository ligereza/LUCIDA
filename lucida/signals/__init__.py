"""Injected signal boundaries for the proposal-only LUCIDA surface."""

from .adobe import (
    ADOBE_PHASES,
    ADOBE_SIGNAL_SCHEMA_VERSION,
    ADOBE_SOURCES,
    ADOBE_SOURCE_FIXTURES,
    DEFAULT_ADOBE_FIXTURE,
    AdobeConsumeResult,
    AdobeSignal,
    AdobeSignalConsumer,
    AdobeSignalError,
    consume_adobe_signal,
    convert_adobe_signal,
    parse_adobe_signal,
)

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
from .semantic_light_field import (
    SemanticLightFieldPreview,
    SemanticLightFieldSurfaceError,
    project_semantic_light_field_report,
)
from .mosaik import (
    MOSAIK_SOURCES,
    MosaikBridgeError,
    MosaikConsumeResult,
    MosaikEventConsumer,
    parse_mosaik_event,
    replay_fixture as replay_mosaik_fixture,
    replay_path as replay_mosaik_path,
)

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
    "ADOBE_PHASES",
    "ADOBE_SIGNAL_SCHEMA_VERSION",
    "ADOBE_SOURCES",
    "ADOBE_SOURCE_FIXTURES",
    "DEFAULT_ADOBE_FIXTURE",
    "AdobeConsumeResult",
    "AdobeSignal",
    "AdobeSignalConsumer",
    "AdobeSignalError",
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
    "SemanticLightFieldPreview",
    "SemanticLightFieldSurfaceError",
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
    "project_semantic_light_field_report",
    "consume_adobe_signal",
    "convert_adobe_signal",
    "parse_adobe_signal",
    "MOSAIK_SOURCES",
    "MosaikBridgeError",
    "MosaikConsumeResult",
    "MosaikEventConsumer",
    "parse_mosaik_event",
    "replay_mosaik_fixture",
    "replay_mosaik_path",
]

"""Public XIO to LUCIDA bridge facade."""

from __future__ import annotations

from typing import Any, Mapping

from adapters.vj.contracts import VJEvent, VJResult

from .xio import (
    ApplicationEvent,
    XioClockError,
    XioConsumeResult,
    XioConsumerError,
    XioEventConsumer,
    XioMappingError,
    XioSchemaError,
    replay_fixture,
    replay_path,
)


def parse_application_event(value: Mapping[str, Any]) -> ApplicationEvent:
    """Validate and parse one canonical XIO ApplicationEvent."""

    return ApplicationEvent.from_dict(value)


def convert_application_event(value: Mapping[str, Any]) -> VJEvent:
    """Convert one validated XIO event to the VJ event contract."""

    return XioEventConsumer.to_vj_event(parse_application_event(value))


def consume_application_event(
    consumer: XioEventConsumer,
    value: ApplicationEvent | Mapping[str, Any],
    results: tuple[VJResult | Mapping[str, Any], ...] | list[VJResult | Mapping[str, Any]] = (),
) -> XioConsumeResult:
    """Deliver one XIO event and optional recorded results to SessionReplay."""

    return consumer.consume(value, results=results)


__all__ = [
    "ApplicationEvent",
    "XioClockError",
    "XioConsumeResult",
    "XioConsumerError",
    "XioEventConsumer",
    "XioMappingError",
    "XioSchemaError",
    "consume_application_event",
    "convert_application_event",
    "parse_application_event",
    "replay_fixture",
    "replay_path",
]

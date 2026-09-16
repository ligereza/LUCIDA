"""Explicit adapter registry for bounded domain inputs."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .models import EngineEvent, _ascii_text


class AdapterRegistryError(ValueError):
    """Raised when an adapter registration or lookup is invalid."""


class EventAdapter(Protocol):
    """Minimal contract for a domain-to-engine adapter."""

    adapter_id: str

    def adapt(self, value: Mapping[str, Any]) -> EngineEvent:
        """Convert one domain value into a bounded engine event."""


class AdapterRegistry:
    """Resolve adapters only by an explicit, ASCII adapter id."""

    def __init__(self) -> None:
        self._adapters: dict[str, EventAdapter] = {}

    def register(self, adapter: EventAdapter) -> None:
        adapter_id = _adapter_id(adapter)
        if adapter_id in self._adapters:
            raise AdapterRegistryError(f"adapter already registered: {adapter_id}")
        self._adapters[adapter_id] = adapter

    def adapt(self, adapter_id: str, value: Mapping[str, Any]) -> EngineEvent:
        key = _adapter_id(adapter_id)
        adapter = self._adapters.get(key)
        if adapter is None:
            raise AdapterRegistryError(f"unknown adapter: {key}")
        event = adapter.adapt(value)
        if not isinstance(event, EngineEvent):
            raise AdapterRegistryError(f"adapter returned a non-event: {key}")
        return event

    def snapshot(self) -> tuple[str, ...]:
        """Return a deterministic list for diagnostics and replay metadata."""

        return tuple(sorted(self._adapters))


def _adapter_id(value: Any) -> str:
    try:
        raw_value = value if isinstance(value, str) else value.adapter_id
    except AttributeError as exc:
        raise AdapterRegistryError("adapter must expose adapter_id") from exc
    try:
        return _ascii_text(raw_value, "adapter_id")
    except ValueError as exc:
        raise AdapterRegistryError(str(exc)) from exc

from __future__ import annotations

import pytest

from lucida.engine import (
    AdapterRegistry,
    AdapterRegistryError,
    EngineEvent,
)


EVENT = {
    "session_id": "session-1",
    "event_id": "event-1",
    "timestamp": "2026-09-02T12:00:00Z",
    "sequence": 1,
    "source": "test",
    "event_type": "heartbeat",
}


class StaticAdapter:
    adapter_id = "test.static"

    def adapt(self, value):
        return EngineEvent.from_dict(value)


def test_registry_requires_explicit_adapter_id():
    registry = AdapterRegistry()
    registry.register(StaticAdapter())

    event = registry.adapt("test.static", EVENT)

    assert event.event_id == "event-1"
    assert registry.snapshot() == ("test.static",)


def test_registry_does_not_guess_or_replace_an_adapter():
    registry = AdapterRegistry()
    registry.register(StaticAdapter())

    with pytest.raises(AdapterRegistryError, match="unknown adapter"):
        registry.adapt("other", EVENT)
    with pytest.raises(AdapterRegistryError, match="already registered"):
        registry.register(StaticAdapter())


def test_registry_rejects_non_ascii_adapter_id():
    registry = AdapterRegistry()
    adapter = StaticAdapter()
    adapter.adapter_id = "adáptér"

    with pytest.raises(ValueError, match="ASCII"):
        registry.register(adapter)


def test_registry_rejects_non_event_adapter_output():
    registry = AdapterRegistry()

    class BrokenAdapter:
        adapter_id = "test.broken"

        def adapt(self, value):
            return value

    registry.register(BrokenAdapter())

    with pytest.raises(AdapterRegistryError, match="non-event"):
        registry.adapt("test.broken", EVENT)

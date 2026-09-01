from datetime import datetime, timezone
import unittest

from XIO_LAYER.adapters import (
    DuplicateSourceAdapterError,
    InvalidSourceAdapterError,
    SourceAdapterRegistry,
    UndeclaredEventTypeError,
    UnknownSourceAdapterError,
)
from XIO_LAYER.core.contracts import content_hash
from XIO_LAYER.core.events import ApplicationEvent


T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


class _TestAdapter:
    source_app = "adobe"
    supported_event_types = {"timeline.cue"}
    capabilities = {"source.observe"}

    def __init__(self):
        self.calls = []

    def convert(self, record, event_type):
        self.calls.append(event_type)
        return ApplicationEvent(
            event_id=record["event_id"],
            source_app=self.source_app,
            event_type=event_type,
            channel=record["channel"],
            payload=record["payload"],
            source_timestamp=record["source_timestamp"],
            received_timestamp=record["received_timestamp"],
            session_id=record["session_id"],
            peer_id=record["peer_id"],
            sequence=record["sequence"],
            raw_hash=record["raw_hash"],
            provenance=record["provenance"],
        )


def _record():
    payload = {"cue": "intro"}
    return {
        "event_id": "event-1",
        "channel": "timeline",
        "payload": payload,
        "source_timestamp": T0,
        "received_timestamp": T0,
        "session_id": "session-1",
        "peer_id": "peer-1",
        "sequence": 1,
        "raw_hash": content_hash(payload),
        "provenance": {"origin": "test"},
    }


class SourceAdapterRegistryTests(unittest.TestCase):
    def test_route_preserves_canonical_event_metadata(self):
        registry = SourceAdapterRegistry()
        adapter = _TestAdapter()
        registry.register(adapter)
        event = registry.route("adobe", "timeline.cue", _record())

        self.assertEqual(event.sequence, 1)
        self.assertEqual(event.source_timestamp, T0)
        self.assertEqual(event.raw_hash, _record()["raw_hash"])
        self.assertEqual(event.provenance, {"origin": "test"})
        self.assertEqual(adapter.calls, ["timeline.cue"])

    def test_unknown_or_undeclared_route_does_not_call_adapter(self):
        registry = SourceAdapterRegistry()
        adapter = _TestAdapter()
        registry.register(adapter)

        with self.assertRaises(UnknownSourceAdapterError):
            registry.route("resolume", "timeline.cue", _record())
        with self.assertRaises(UndeclaredEventTypeError):
            registry.route("adobe", "timeline.frame", _record())
        self.assertEqual(adapter.calls, [])

    def test_duplicate_and_invalid_registration_do_not_mutate_registry(self):
        registry = SourceAdapterRegistry()
        registry.register(_TestAdapter())
        before = registry.source_apps()

        with self.assertRaises(DuplicateSourceAdapterError):
            registry.register(_TestAdapter())

        invalid = _TestAdapter()
        invalid.source_app = "adobe" + chr(0xE9)
        with self.assertRaises(InvalidSourceAdapterError):
            registry.register(invalid)
        self.assertEqual(registry.source_apps(), before)


if __name__ == "__main__":
    unittest.main()

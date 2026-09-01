from datetime import datetime, timezone
import json
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
    def test_empty_registry_has_empty_json_safe_snapshot(self):
        snapshot = SourceAdapterRegistry().snapshot()

        self.assertEqual(snapshot, [])
        self.assertEqual(json.loads(json.dumps(snapshot, sort_keys=True)), [])

    def test_snapshot_is_sorted_and_repeated_calls_are_identical(self):
        registry = SourceAdapterRegistry()
        resolume = _TestAdapter()
        resolume.source_app = "resolume"
        resolume.supported_event_types = {"z.event", "a.event"}
        resolume.capabilities = {"z.capability", "a.capability"}
        adobe = _TestAdapter()
        adobe.source_app = "adobe"
        adobe.supported_event_types = {"timeline.frame", "timeline.cue"}
        adobe.capabilities = {"source.send", "source.observe"}
        registry.register(resolume)
        registry.register(adobe)

        first = registry.snapshot()
        second = registry.snapshot()

        self.assertEqual(first, second)
        self.assertEqual(
            first,
            [
                {
                    "source_app": "adobe",
                    "supported_event_types": ["timeline.cue", "timeline.frame"],
                    "capabilities": ["source.observe", "source.send"],
                },
                {
                    "source_app": "resolume",
                    "supported_event_types": ["a.event", "z.event"],
                    "capabilities": ["a.capability", "z.capability"],
                },
            ],
        )
        self.assertEqual(json.loads(json.dumps(first, sort_keys=True)), first)

    def test_snapshot_mutation_does_not_change_registry_or_expose_adapter(self):
        registry = SourceAdapterRegistry()
        registry.register(_TestAdapter())
        expected = registry.snapshot()
        snapshot = registry.snapshot()
        snapshot[0]["supported_event_types"].append("unregistered.event")
        snapshot[0]["capabilities"].clear()
        snapshot.append({"source_app": "leak", "supported_event_types": [], "capabilities": []})

        self.assertEqual(registry.snapshot(), expected)
        self.assertNotIn("adapter", json.dumps(snapshot))
        self.assertNotIn("convert", json.dumps(snapshot))

    def test_candidates_match_event_type_and_required_capabilities(self):
        registry = SourceAdapterRegistry()
        resolume = _TestAdapter()
        resolume.source_app = "resolume"
        resolume.supported_event_types = {"timeline.cue"}
        resolume.capabilities = {"source.observe", "source.render"}
        adobe = _TestAdapter()
        adobe.source_app = "adobe"
        adobe.supported_event_types = {"timeline.cue"}
        adobe.capabilities = {"source.observe"}
        other = _TestAdapter()
        other.source_app = "other-app"
        other.supported_event_types = {"timeline.frame"}
        other.capabilities = {"source.observe"}
        for adapter in (resolume, adobe, other):
            registry.register(adapter)

        self.assertEqual(
            [item["source_app"] for item in registry.candidates("timeline.cue")],
            ["adobe", "resolume"],
        )
        self.assertEqual(
            [item["source_app"] for item in registry.candidates(
                "timeline.cue", {"source.render"}
            )],
            ["resolume"],
        )
        self.assertEqual(registry.candidates("timeline.cue", {"source.missing"}), [])

    def test_candidates_are_sorted_json_safe_and_copy_isolated(self):
        registry = SourceAdapterRegistry()
        for name in ("z-app", "a-app"):
            adapter = _TestAdapter()
            adapter.source_app = name
            adapter.supported_event_types = {"z.event", "a.event"}
            adapter.capabilities = {"z.cap", "a.cap"}
            registry.register(adapter)

        first = registry.candidates("a.event")
        second = registry.candidates("a.event")
        first[0]["supported_event_types"].append("leaked.event")
        first[0]["capabilities"].clear()
        first.append({"source_app": "leaked", "supported_event_types": [], "capabilities": []})

        self.assertEqual(second, registry.candidates("a.event"))
        self.assertEqual([item["source_app"] for item in second], ["a-app", "z-app"])
        self.assertEqual(json.loads(json.dumps(second, sort_keys=True)), second)

    def test_empty_and_no_match_candidates_are_explicit_empty_lists(self):
        self.assertEqual(SourceAdapterRegistry().candidates("timeline.cue"), [])
        registry = SourceAdapterRegistry()
        registry.register(_TestAdapter())

        self.assertEqual(registry.candidates("timeline.frame"), [])

    def test_invalid_candidate_queries_are_rejected(self):
        registry = SourceAdapterRegistry()
        registry.register(_TestAdapter())

        with self.assertRaises(InvalidSourceAdapterError):
            registry.candidates("evento." + chr(0xE9))
        with self.assertRaises(InvalidSourceAdapterError):
            registry.candidates("")
        with self.assertRaises(InvalidSourceAdapterError):
            registry.candidates("timeline.cue", {"cap." + chr(0xE9)})
        with self.assertRaises(InvalidSourceAdapterError):
            registry.candidates("timeline.cue", "source.observe")

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

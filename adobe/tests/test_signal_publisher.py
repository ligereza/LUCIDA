import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "integrations" / "signal-publisher" / "signal_publisher.py"
SPEC = importlib.util.spec_from_file_location("lucida_signal_publisher", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"accepted": true}'


class SignalPublisherTest(unittest.TestCase):
    def test_client_maps_xio_metrics_and_never_sends_raw_content(self):
        publisher = MODULE.SignalPublisher(base_url="http://127.0.0.1:47921")
        with patch.object(MODULE.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
            result = publisher.publish_event(
                "xio",
                "session-001",
                "radio.sample",
                metadata={
                    "wifi_signal_percent": 84,
                    "gateway_loss_percent": 1.5,
                    "text": "private",
                    "payload": {"secret": True},
                },
            )
        self.assertTrue(result["accepted"])
        body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(body["metadata"]["signalPercent"], 84)
        self.assertEqual(body["metadata"]["lossPercent"], 1.5)
        self.assertNotIn("text", body["metadata"])
        self.assertNotIn("payload", body)

    def test_proposals_are_reduced_to_confirmation_data(self):
        publisher = MODULE.SignalPublisher()
        with patch.object(MODULE.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
            publisher.publish_event(
                "vizz",
                "session-002",
                "attention.shift",
                proposal={
                    "kind": "visual.reorder",
                    "title": "Prioritize canvas",
                    "reason": "Focus changed",
                    "command": "execute-host-action",
                },
            )
        body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(body["proposal"]["kind"], "visual.reorder")
        self.assertNotIn("command", body["proposal"])

    def test_low_level_publish_also_rebuilds_the_envelope(self):
        publisher = MODULE.SignalPublisher()
        with patch.object(MODULE.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
            publisher.publish({
                "source": "pupila",
                "session_id": "session-003",
                "event": "workflow.handoff",
                "payload": {"raw": "must not cross"},
                "metadata": {"participant_count": 2},
            })
        body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(body["eventType"], "workflow.handoff")
        self.assertEqual(body["metadata"]["participantCount"], 2)
        self.assertNotIn("payload", body)


if __name__ == "__main__":
    unittest.main()

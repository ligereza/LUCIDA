import importlib.util
import json
from pathlib import Path

from lucida.signals.xio import XioEventConsumer


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "validate_schema_graph.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_schema_graph", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _application_event():
    return {
        "event_id": "evt-001",
        "source_app": "XIO",
        "event_type": "preflight.completed",
        "channel": "instar",
        "payload": {
            "phase": "preflight",
            "vj_event_type": "phase.completed",
            "status": "pass",
        },
        "source_timestamp": "2026-01-10T20:00:01Z",
        "received_timestamp": "2026-01-10T20:00:02Z",
        "session_id": "session-001",
        "peer_id": "peer-001",
        "sequence": 1,
        "raw_hash": "sha256:001",
        "provenance": {"producer": "test", "transport": "offline"},
    }


def test_schema_graph_cli_checks_all_local_refs():
    module = _load_module()

    assert module.main(["--root", str(ROOT)]) == 0


def test_schema_graph_cli_validates_generated_xio_result(tmp_path):
    module = _load_module()
    result = XioEventConsumer("session-001").consume(_application_event()).to_dict()
    instance_path = tmp_path / "xio-result.json"
    instance_path.write_text(json.dumps(result), encoding="utf-8")

    assert module.main(
        [
            "--root",
            str(ROOT),
            "--schema",
            "lucida/signals/contracts/xio-consume-result.schema.json",
            "--instance",
            str(instance_path),
        ]
    ) == 0


def test_schema_graph_cli_validates_the_nayade_case_fixture():
    module = _load_module()

    assert module.main(
        [
            "--root",
            str(ROOT),
            "--schema",
            "schemas/nayade-processor-case.schema.json",
            "--instance",
            "data/cases/soundcheck-2026-08-29-vc2.json",
        ]
    ) == 0

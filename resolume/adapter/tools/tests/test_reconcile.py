import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tools.resolume_adapter.media import ResolumeAdapterError
from tools.resolume_adapter.reconcile import reconcile_signal_chain


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_FIXTURE = ROOT / "adapters" / "vj" / "replay" / "fixtures" / "plugin-bridges-fictional.json"
RECONCILIATION_SCHEMA = ROOT / "schemas" / "nayade-signal-chain-reconciliation.schema.json"


def _fact(value, origin="observed", confidence=1.0):
    return {"value": value, "origin": origin, "confidence": confidence}


def _signal_profile():
    return {
        "schema_version": "0.1",
        "profile_id": "signal-001",
        "stage": "NAYADE",
        "generated_at": "2026-09-02T20:00:00Z",
        "source": {
            "resolution": _fact("1920x1080"),
            "fps": _fact(60),
            "color_model": _fact("RGB"),
            "range": _fact("full"),
            "transfer": _fact("sRGB"),
            "primaries": _fact("BT.709"),
            "bit_depth": _fact(8),
        },
        "capture": {
            "resolution": _fact("1920x1080"),
            "refresh_hz": _fact(60),
            "format": _fact("RGB"),
            "lock": _fact("locked"),
        },
        "house": {
            "input": _fact("HDMI-1"),
            "bus": _fact("unknown", "unknown", 0),
            "destinations": _fact(["screen-1"]),
            "outputs": _fact(["processor-1"]),
        },
        "processor": {
            "vendor": _fact("NovaStar"),
            "model": _fact("VX600"),
            "read_only": True,
            "capabilities": {},
        },
        "recommendation": {
            "range_transform": "identity",
            "gamma_transform": "identity",
            "deband": False,
            "deflicker": False,
        },
    }


def _module_profile():
    return {
        "schema_version": "0.1",
        "profile_type": "ResolumeAdapterModuleProfile",
        "profile_id": "module-001",
        "environment": _fact("indoor", "declared", 0.9),
        "fixtures": [
            {
                "fixture_id": "cabinet-001",
                "pixel_resolution": {"width": 1920, "height": 1080},
                "physical_size_mm": {"width": 499.2, "height": 280.8},
                "pixel_pitch_mm": _fact(0.26, "declared", 0.9),
                "environment": _fact("indoor", "declared", 0.9),
            }
        ],
        "provenance": [{"kind": "measurement", "detail": "fictional fixture"}],
    }


def _documents():
    observation = json.loads(BRIDGE_FIXTURE.read_text(encoding="utf-8"))["records"][1]["processor_observation"]
    return {
        "signal_profile": _signal_profile(),
        "processor_observation": observation,
        "processor_snapshot": {
            "read_only": True,
            "identification": {"manufacturer": _fact("NovaStar"), "model": _fact("VX600")},
        },
        "module_profile": _module_profile(),
        "mapping": {
            "composition": {"width": 1920, "height": 1080},
            "validation": {"status": "PASS"},
        },
        "output_probe": {
            "output_signal": {
                "resolution": "1920x1080",
                "refresh_hz": 60,
                "color_range": "unknown",
                "color_space": "unknown",
            }
        },
    }


def test_reconciliation_crosses_signal_processor_module_and_mapping():
    report = reconcile_signal_chain(_documents())

    assert report["status"] == "PASS"
    assert report["summary"]["conflict_count"] == 0
    assert any(item["kind"] == "pixel_pitch" for item in report["calculations"])
    assert any(item["subject"] == "gpu.output" for item in report["facts"])
    assert report["safety"] == {
        "read_only": True,
        "commands_sent": False,
        "writes_attempted": False,
        "external_side_effects": False,
        "raw_documents_included": False,
        "source_paths_exposed": False,
    }
    schema = json.loads(RECONCILIATION_SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(report)) == []


def test_reconciliation_elevates_range_conflict_without_executing_a_fix():
    documents = _documents()
    documents["processor_observation"] = copy.deepcopy(documents["processor_observation"])
    documents["processor_observation"]["input_signal"]["range"] = "limited"

    report = reconcile_signal_chain(documents)

    assert report["status"] == "FAIL"
    assert [item["id"] for item in report["conflicts"]] == ["range_mismatch"]
    assert report["recommendations"][0]["execution_mode"] == "proposal_only"
    assert report["safety"]["commands_sent"] is False


def test_reconciliation_requires_at_least_one_document():
    with pytest.raises(ResolumeAdapterError, match="al menos un documento"):
        reconcile_signal_chain({})

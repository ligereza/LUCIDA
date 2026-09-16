import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tools.resolume_adapter.media import ResolumeAdapterError
from tools.resolume_adapter.nayade import create_session
from tools.resolume_adapter.protocol import build_soundcheck_protocol, protocol_session_steps


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "nayade-soundcheck-protocol.schema.json"
SESSION_SCHEMA_PATH = ROOT / "schemas" / "nayade-soundcheck-session.schema.json"


def _validate(report):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(report)) == []


def test_protocol_has_safe_baseline_without_evidence():
    report = build_soundcheck_protocol()

    assert report["status"] == "READY"
    assert report["source_documents"] == []
    assert report["steps"][0]["pattern"] == "blackout"
    assert report["summary"]["step_count"] == len(report["steps"])
    assert report["safety"]["patterns_emitted"] is False
    _validate(report)


def test_protocol_promotes_checks_from_chain_evidence():
    report = build_soundcheck_protocol(
        reconciliation={
            "status": "FAIL",
            "conflicts": [
                {"id": "range_mismatch", "severity": "high"},
                {"id": "resolution_mismatch_signal_source_mapping_composition", "severity": "review"},
            ],
            "calculations": [{"id": "processor_scaling", "value": True}],
            "facts": [
                {"subject": "gpu.output", "property": "color_range", "value": "unknown"},
            ],
        },
        mapping={"mapping_distortion_risk": True, "validation": {"status": "FAIL"}},
    )

    by_pattern = {step["pattern"]: step for step in report["steps"]}
    assert report["status"] == "REVIEW"
    assert {"range_mismatch", "processor_scaling", "mapping_distortion_risk"}.issubset(report["evidence_ids"])
    assert by_pattern["pluge_near_black"]["priority"] == "required"
    assert "range_mismatch" in by_pattern["pluge_near_black"]["triggered_by"]
    assert by_pattern["resolution_scaling"]["priority"] == "required"
    assert by_pattern["geometry_grid"]["priority"] == "required"
    assert all(step["execution_mode"] == "plan_only" for step in report["steps"])
    _validate(report)


def test_protocol_rejects_non_object_documents():
    with pytest.raises(ResolumeAdapterError, match="debe ser un objeto"):
        build_soundcheck_protocol(reconciliation=["not-an-object"])


def test_protocol_does_not_copy_source_paths():
    report = build_soundcheck_protocol(
        case_report={"findings": [{"id": "raised_black_level", "detail": "C:\\private\\case.json"}]},
        reconciliation={"conflicts": []},
    )

    serialized = json.dumps(report, ensure_ascii=False)
    assert "private" not in serialized
    assert report["safety"]["source_paths_exposed"] is False


def test_protocol_can_be_attached_to_a_nayade_session(tmp_path):
    source_path = tmp_path / "mapping.json"
    protocol_path = tmp_path / "protocol.json"
    session_path = tmp_path / "session.json"
    source_path.write_text(
        json.dumps(
            {
                "testcard_type": "InstarResolumeGeometryTestCard",
                "composition": {"width": 1920, "height": 1080},
                "slices_detail": [
                    {"slice_id": "slice-a", "input_group_id": "group-a", "bounds": {"x": 0, "y": 0, "width": 1920, "height": 1080}}
                ],
            }
        ),
        encoding="utf-8",
    )
    protocol_path.write_text(
        json.dumps(build_soundcheck_protocol(reconciliation={"conflicts": [{"id": "range_mismatch", "severity": "high"}]})),
        encoding="utf-8",
    )

    session = create_session(source_path, session_path, protocol_path=protocol_path)

    assert session["protocol"]["status"] == "REVIEW"
    assert session["planned_steps"][0]["operation"] == "processor_check"
    assert session["planned_steps"][0]["parameters"]["pattern"] == "blackout"
    assert any(step["operation"] == "baseline" for step in session["planned_steps"])
    schema = json.loads(SESSION_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(session)) == []


def test_session_can_start_directly_from_advanced_output_xml(tmp_path):
    source_path = tmp_path / "advanced-output.xml"
    session_path = tmp_path / "session.json"
    source_path.write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<XmlState><ScreenSetup><CurrentCompositionTextureSize width="1000" height="500"/><screens>
<Screen name="Screen" uniqueId="screen-1"><Params name="Params"><Param name="Name" value="Screen"/><Param name="Enabled" value="1"/></Params>
<OutputDevice><OutputDeviceVirtual name="Virtual" deviceId="Virtual" width="1920" height="1080"/></OutputDevice><layers>
<Slice uniqueId="slice-1"><Params name="Common"><Param name="Name" value="MAIN"/><Param name="Enabled" value="1"/></Params>
<Params name="Input"/><InputRect><v x="0" y="0"/><v x="100" y="0"/><v x="100" y="100"/><v x="0" y="100"/></InputRect>
<OutputRect><v x="0" y="0"/><v x="400" y="0"/><v x="400" y="200"/><v x="0" y="200"/></OutputRect></Slice>
</layers></Screen></screens></ScreenSetup></XmlState>''',
        encoding="utf-8",
    )

    session = create_session(source_path, session_path)

    assert session["source"]["type"] == "ResolumeAdvancedOutputMap"
    assert session["targets"]["slices"][0]["slice_name"] == "MAIN"
    assert session["targets"]["input_groups"] == ["input-group-001"]
    assert session_path.is_file()


def test_session_bridge_rejects_incomplete_protocol():
    with pytest.raises(ResolumeAdapterError, match="Protocolo NAYADE inválido"):
        protocol_session_steps({"protocol_type": "NayadeSoundcheckProtocol", "steps": []})

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tools.resolume_adapter.media import ResolumeAdapterError
from tools.resolume_adapter.nayade import build_session_report, record_event


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "nayade-soundcheck-session-report.schema.json"


def _session(result="planned"):
    return {
        "session_type": "NayadeSoundcheckSession",
        "session_id": "session-001",
        "name": "Venue soundcheck",
        "updated_at": "2026-09-02T20:00:00Z",
        "planned_steps": [
            {
                "step_id": "processor-check-001",
                "operation": "processor_check",
                "scope": "chain",
                "targets": ["group-a"],
                "parameters": {"pattern": "blackout", "priority": "required"},
                "expected_checks": ["blackout_status"],
                "result": result,
            },
            {
                "step_id": "step-002",
                "operation": "baseline",
                "scope": "input_group",
                "targets": ["group-a"],
                "parameters": {},
                "expected_checks": ["geometry"],
                "result": "approved" if result == "approved" else "planned",
            },
        ],
        "events": [{"notes": "private C:\\venue\\note.txt", "result": result}],
    }


def test_session_report_marks_required_work_for_review(tmp_path):
    path = tmp_path / "session.json"
    path.write_text(json.dumps(_session()), encoding="utf-8")

    report = build_session_report(path)

    assert report["status"] == "REVIEW"
    assert report["summary"]["pending_required_count"] == 1
    assert report["next_step"]["step_id"] == "processor-check-001"
    assert report["risks"] == []
    assert report["safety"]["source_paths_exposed"] is False
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(report)) == []


def test_session_report_distinguishes_blocked_from_review(tmp_path):
    path = tmp_path / "session.json"
    path.write_text(json.dumps(_session("rejected")), encoding="utf-8")

    report = build_session_report(path)

    assert report["status"] == "BLOCKED"
    assert report["summary"]["risk_count"] == 1
    assert report["risks"][0]["severity"] == "high"
    assert "private" not in json.dumps(report, ensure_ascii=False)


def test_record_event_can_create_a_recoverable_session_version(tmp_path):
    source = tmp_path / "session.json"
    derived = tmp_path / "session-after.json"
    source.write_text(json.dumps(_session()), encoding="utf-8")

    event = record_event(
        source,
        operation="processor_check",
        scope="chain",
        targets=["group-a"],
        result="approved",
        notes="PLUGE approved",
        step_id="processor-check-001",
        output_path=derived,
    )

    original = json.loads(source.read_text(encoding="utf-8"))
    updated = json.loads(derived.read_text(encoding="utf-8"))
    assert event["planned_step_id"] == "processor-check-001"
    assert len(original["events"]) == 1
    assert len(updated["events"]) == 2
    assert updated["planned_steps"][0]["result"] == "approved"

    with pytest.raises(ResolumeAdapterError, match="ya existe"):
        record_event(
            source,
            operation="processor_check",
            result="approved",
            output_path=derived,
        )

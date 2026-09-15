import json
import sys
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from resolume_adapter.incidents import build_incident_plan, incident_text_report
from resolume_adapter_cli import main
from jsonschema import Draft202012Validator


def test_gray_black_plan_separates_evidence_hypotheses_and_proposals():
    plan = build_incident_plan("gray_black_levels", stage="soundcheck")

    assert plan["plan_type"] == "ResolumeAdapterIncidentPlan"
    assert plan["safety"]["read_only"] is True
    assert plan["safety"]["hardware_changed"] is False
    assert len(plan["evidence_questions"]) >= 3
    assert len(plan["hypotheses"]) == 3
    assert all(item["execution_mode"] == "proposal_only" for item in plan["proposals"])
    assert "PLUGE" in incident_text_report(plan)


def test_incident_plan_cli_writes_reversible_json(tmp_path, capsys):
    report_path = tmp_path / "flicker-plan.json"

    exit_code = main(["incident-plan", "flicker", "--stage", "show", "--report", str(report_path)])

    assert exit_code == 0
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["category"] == "flicker"
    assert saved["stage"] == "show"
    assert saved["safety"]["automatic_execution"] is False
    assert "RESOLUME_ADAPTER INCIDENT PLAN" in capsys.readouterr().out


def test_every_incident_category_matches_the_published_schema():
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "resolume_adapter-incident-plan.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    for category in ("flicker", "tearing", "frames_dropped", "lost_media", "gray_black_levels", "geometry_scaling", "signal_loss"):
        plan = build_incident_plan(category)
        assert list(validator.iter_errors(plan)) == []

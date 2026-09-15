import json
import sys
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from resolume_adapter_cli import main
from resolume_adapter.protocol import build_soundcheck_protocol


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "adapters"
    / "vj"
    / "replay"
    / "fixtures"
    / "plugin-bridges-fictional.json"
)


def test_vj_replay_cli_prints_and_writes_a_report(tmp_path, capsys):
    report_path = tmp_path / "vj-replay.json"

    exit_code = main(["vj-replay", str(FIXTURE), "--report", str(report_path)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"status": "PASS"' in output
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["phase_order"][-1] == "closure"


def test_vj_replay_cli_returns_a_clean_error_for_invalid_fixture(tmp_path, capsys):
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"replay_type":"wrong"}\n', encoding="utf-8")

    exit_code = main(["vj-replay", str(invalid)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "RESOLUME_ADAPTER ERROR" in captured.err
    assert "identity" in captured.err


def test_vj_project_cli_projects_a_real_stage_report(tmp_path, capsys):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    input_path = tmp_path / "instar-report.json"
    output_path = tmp_path / "projection.json"
    input_path.write_text(json.dumps(fixture["records"][0]["data"]), encoding="utf-8")

    exit_code = main(
        [
            "vj-project",
            "instar",
            str(input_path),
            "--event-id",
            "instar-001",
            "--sequence",
            "1",
            "--mode",
            "projection",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["show_phase"] == "preflight"
    assert "preflight" in capsys.readouterr().out


def test_vj_project_replay_cli_replays_a_manifest(tmp_path, capsys):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = []
    for index, source in enumerate(fixture["records"]):
        input_path = tmp_path / f"report-{index}.json"
        input_path.write_text(json.dumps(source["data"]), encoding="utf-8")
        record = {
            "stage": source["stage"],
            "event_id": source["event_id"],
            "sequence": source["sequence"],
            "input": input_path.name,
        }
        if "processor_observation" in source:
            observation_path = tmp_path / f"observation-{index}.json"
            observation_path.write_text(json.dumps(source["processor_observation"]), encoding="utf-8")
            record["processor_observation"] = observation_path.name
        records.append(record)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "replay_type": "ResolumeAdapterVJProjectReplay",
                "schema_version": "0.1",
                "session_id": "cli-project-session",
                "records": records,
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "replay.json"

    exit_code = main(["vj-project-replay", str(manifest_path), "--report", str(report_path)])

    assert exit_code == 0
    assert json.loads(report_path.read_text(encoding="utf-8"))["status"] == "PASS"
    assert '"source_paths_exposed": false' in capsys.readouterr().out


def test_nayade_validate_case_cli_returns_a_safe_summary(capsys):
    case = Path(__file__).resolve().parents[2] / "data" / "cases" / "soundcheck-2026-08-29-vc2.json"

    exit_code = main(["nayade-processor", "validate-case", str(case)])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is True
    assert output["safety"]["source_path_exposed"] is False


def test_nayade_reconcile_cli_writes_a_bounded_report(tmp_path, capsys):
    observation_path = tmp_path / "processor-observation.json"
    report_path = tmp_path / "reconciliation.json"
    observation_path.write_text(
        json.dumps(
            {
                "model": "VX600",
                "firmware": "1.3.0",
                "transport": "manual",
                "confidence": "medium",
                "input_signal": {"resolution": "1920x1080", "fps": 60, "range": "full"},
                "output_signal": {"resolution": "1280x720", "fps": 60},
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "nayade-processor",
            "reconcile",
            "--processor-observation",
            str(observation_path),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    output = json.loads(report_path.read_text(encoding="utf-8"))
    assert output["status"] == "REVIEW"
    assert output["safety"]["source_paths_exposed"] is False
    assert "scaling" in capsys.readouterr().out


def test_nayade_protocol_cli_writes_operator_plan(tmp_path, capsys):
    reconciliation_path = tmp_path / "reconciliation.json"
    report_path = tmp_path / "protocol.json"
    reconciliation_path.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "conflicts": [{"id": "range_mismatch", "severity": "high"}],
                "calculations": [],
                "facts": [],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "nayade-processor",
            "protocol",
            "--reconciliation",
            str(reconciliation_path),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    output = json.loads(report_path.read_text(encoding="utf-8"))
    assert output["protocol_type"] == "NayadeSoundcheckProtocol"
    assert output["status"] == "REVIEW"
    assert any(step["pattern"] == "pluge_near_black" for step in output["steps"])
    assert "range_mismatch" in capsys.readouterr().out


def test_nayade_session_cli_attaches_protocol_before_visual_matrix(tmp_path, capsys):
    source_path = tmp_path / "testcard.json"
    protocol_path = tmp_path / "protocol.json"
    session_path = tmp_path / "session.json"
    source_path.write_text(
        json.dumps(
            {
                "testcard_type": "InstarResolumeGeometryTestCard",
                "composition": {"width": 1280, "height": 720},
                "slices_detail": [{"slice_id": "slice-a", "input_group_id": "group-a", "bounds": {"width": 1280, "height": 720}}],
            }
        ),
        encoding="utf-8",
    )
    protocol_path.write_text(json.dumps(build_soundcheck_protocol()), encoding="utf-8")

    exit_code = main(
        [
            "nayade-session",
            "init",
            str(source_path),
            "--output",
            str(session_path),
            "--protocol",
            str(protocol_path),
        ]
    )

    assert exit_code == 0
    session = json.loads(session_path.read_text(encoding="utf-8"))
    assert session["planned_steps"][0]["operation"] == "processor_check"
    assert any(step["operation"] == "baseline" for step in session["planned_steps"])
    assert "Pasos planificados" in capsys.readouterr().out


def test_nayade_session_report_cli_writes_bounded_status(tmp_path, capsys):
    session_path = tmp_path / "session.json"
    report_path = tmp_path / "status.json"
    session_path.write_text(
        json.dumps(
            {
                "session_type": "NayadeSoundcheckSession",
                "session_id": "session-cli-001",
                "name": "CLI soundcheck",
                "updated_at": "2026-09-02T20:00:00Z",
                "planned_steps": [
                    {
                        "step_id": "processor-check-001",
                        "operation": "processor_check",
                        "scope": "chain",
                        "targets": ["group-a"],
                        "parameters": {"priority": "required", "pattern": "pluge_near_black"},
                        "expected_checks": ["near_black_bars"],
                        "result": "review",
                    }
                ],
                "events": [{"result": "review", "notes": "C:\\private\\note.txt"}],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["nayade-session", "report", str(session_path), "--report", str(report_path)])

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "REVIEW"
    assert report["next_step"]["pattern"] == "pluge_near_black"
    assert "private" not in report_path.read_text(encoding="utf-8")
    assert "riesgos: 1" in capsys.readouterr().out


def test_instar_cue_plan_cli_writes_six_slot_plan(tmp_path, capsys):
    profile_path = tmp_path / "clip-profile.json"
    report_path = tmp_path / "cue-plan.json"
    profile_path.write_text(
        json.dumps(
            {
                "profile_type": "ClipProfile",
                "profile_id": "clip-cli-001",
                "source": {"filename": "visual.mp4"},
                "technical": {"video": {"duration_seconds": 8}},
                "events": {
                    "cue_suggestions": {
                        "cues": [
                            {"id": "change-01", "role": "change", "style": "clean", "position_s": 1.5, "confidence": 0.8}
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["instar-cue-plan", str(profile_path), "--report", str(report_path)])

    assert exit_code == 0
    plan = json.loads(report_path.read_text(encoding="utf-8"))
    assert plan["plan_type"] == "InstarResolumeCuePlan"
    assert len(plan["profiles"][0]["slots"]) == 6
    assert "Position1" in capsys.readouterr().out


def test_imago_guard_window_cli_records_proposal(tmp_path, capsys):
    session_path = tmp_path / "imago.json"
    assert main(
        [
            "imago-session",
            "init",
            "--output",
            str(session_path),
            "--session-id",
            "show-cli-guard",
            "--created-at",
            "2026-01-10T22:00:00Z",
        ]
    ) == 0
    capsys.readouterr()
    assert main(
        [
            "imago-session",
            "event",
            str(session_path),
            "--event-type",
            "show_started",
            "--recorded-at",
            "2026-01-10T22:00:00Z",
        ]
    ) == 0
    capsys.readouterr()
    assert main(
        [
            "imago-session",
            "event",
            str(session_path),
            "--event-type",
            "guard_window_requested",
            "--payload",
            '{"duration_ms":5000,"base_clip_id":"clip-01","test_scope":"effect"}',
            "--recorded-at",
            "2026-01-10T22:01:00Z",
        ]
    ) == 0

    session = json.loads(session_path.read_text(encoding="utf-8"))
    assert session["events"][-1]["event_type"] == "guard_window_requested"
    assert any(item["operation"] == "prepare_guard_window" for item in session["proposals"])
    assert "status" in capsys.readouterr().out

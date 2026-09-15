import json
from pathlib import Path

import pytest

from adapters.vj.replay import ReplayError, replay_project_manifest_path


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "adapters"
    / "vj"
    / "replay"
    / "fixtures"
    / "plugin-bridges-fictional.json"
)


def _write_stage_reports(tmp_path):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = fixture["records"]
    paths = []
    for index, record in enumerate(records):
        input_path = tmp_path / f"report-{index}.json"
        input_path.write_text(json.dumps(record["data"]), encoding="utf-8")
        observation = None
        if "processor_observation" in record:
            observation = tmp_path / f"observation-{index}.json"
            observation.write_text(json.dumps(record["processor_observation"]), encoding="utf-8")
        paths.append((input_path, observation))
    return fixture, paths


def test_project_manifest_replays_real_stage_reports_without_paths(tmp_path):
    fixture, paths = _write_stage_reports(tmp_path)
    records = []
    for source, (input_path, observation_path) in zip(fixture["records"], paths):
        record = {
            "stage": source["stage"],
            "event_id": source["event_id"],
            "sequence": source["sequence"],
            "input": input_path.name,
        }
        if observation_path:
            record["processor_observation"] = observation_path.name
        records.append(record)
    manifest = {
        "replay_type": "ResolumeAdapterVJProjectReplay",
        "schema_version": "0.1",
        "session_id": "project-session-001",
        "records": records,
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = replay_project_manifest_path(manifest_path)

    assert report["status"] == "PASS"
    assert report["phase_order"] == [
        "preflight",
        "preparation",
        "show",
        "incident",
        "recovery",
        "closure",
    ]
    assert report["safety"]["source_paths_exposed"] is False
    assert str(tmp_path) not in json.dumps(report)


def test_project_manifest_rejects_non_increasing_sequences(tmp_path):
    manifest = {
        "replay_type": "ResolumeAdapterVJProjectReplay",
        "schema_version": "0.1",
        "session_id": "project-session-001",
        "records": [
            {"stage": "instar", "event_id": "one", "sequence": 1, "input": "one.json"},
            {"stage": "nayade", "event_id": "two", "sequence": 1, "input": "two.json"},
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReplayError, match="aumentar estrictamente"):
        replay_project_manifest_path(path)


def test_project_manifest_rejects_input_path_escape(tmp_path):
    manifest = {
        "replay_type": "ResolumeAdapterVJProjectReplay",
        "schema_version": "0.1",
        "session_id": "project-session-001",
        "records": [
            {"stage": "instar", "event_id": "one", "sequence": 1, "input": "../outside.json"},
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReplayError, match="salir del directorio"):
        replay_project_manifest_path(path)


def test_project_manifest_rejects_processor_observation_path_escape(tmp_path):
    (tmp_path / "input.json").write_text("{}", encoding="utf-8")
    manifest = {
        "replay_type": "ResolumeAdapterVJProjectReplay",
        "schema_version": "0.1",
        "session_id": "project-session-001",
        "records": [
            {
                "stage": "instar",
                "event_id": "one",
                "sequence": 1,
                "input": "input.json",
                "processor_observation": "../outside.json",
            },
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReplayError, match="salir del directorio"):
        replay_project_manifest_path(path)

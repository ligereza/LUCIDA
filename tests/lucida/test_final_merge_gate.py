import json
from pathlib import Path
import subprocess

from lucida.evidence_bundle import _sha256


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = REPOSITORY_ROOT / "resolume" / "final-merge-gate.json"
ALLOWED_DECISIONS = {"READY_FOR_EXPLICIT_MERGE", "BLOCKED"}
EXPECTED_BASE = "e2f2cb15a51b0b82be72973de40e96f40675ab23"
EXPECTED_CANDIDATE = "a155762d946cff2cf41f2cc68c721ad77f3b4445"
EXPECTED_PARENT = "7722ce7ae5c619c63e7587b8f08854bb403fed4a"
EXPECTED_HASHES = {
    "semantic_report_fixture_sha256": "c0939a24b4b80850b30a351bc497323dad8dd7aaa7d9e8bfa57e6d64f1db2286",
    "signal_envelope_fixture_sha256": "0b806342e2d51dd6dce4bf330579aec6bf60b494c50bb2196357eee736c5023f",
    "surface_projection_schema_sha256": "3bca2f33944f062acfbb9aef6444e4b84d5977bb7eede7f31673d7360e7a356e",
    "tape_sha256": "f69e170a3447924a7e30126572c659bf61a353d6628ae9e4cd1359aa035bbaec",
}


def _load_gate():
    raw = GATE_PATH.read_bytes()
    raw.decode("ascii")
    return raw, json.loads(raw.decode("ascii"))


def _git(*args, text=True):
    return subprocess.check_output(["git", *args], cwd=REPOSITORY_ROOT, text=text)


def _git_blob(commit, path):
    return _git("show", f"{commit}:{path}", text=False)


def test_final_merge_gate_is_sorted_ascii_and_matches_candidate_tree():
    raw, gate = _load_gate()
    assert json.dumps(gate, ensure_ascii=True, sort_keys=True, indent=2) + "\n" == raw.decode(
        "ascii"
    )
    assert gate["base_commit"] == EXPECTED_BASE
    assert gate["candidate_commit"] == EXPECTED_CANDIDATE
    assert gate["candidate_parent_commit"] == EXPECTED_PARENT
    assert gate["proposed_merge_targets"] == [EXPECTED_CANDIDATE]
    for commit in (EXPECTED_BASE, EXPECTED_PARENT, EXPECTED_CANDIDATE):
        assert subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=REPOSITORY_ROOT,
        ).returncode == 0
    assert _git("rev-parse", f"{EXPECTED_CANDIDATE}^").strip() == EXPECTED_PARENT
    assert subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_BASE, EXPECTED_CANDIDATE],
        cwd=REPOSITORY_ROOT,
    ).returncode == 0

    classes = gate["changed_file_classes"]
    assert set(classes) == {"runtime", "contract", "test", "documentation", "contamination"}
    assert classes["contamination"] == []
    classified = [path for name, paths in classes.items() if name != "contamination" for path in paths]
    assert len(classified) == len(set(classified)) == gate["changed_file_count"] == 26
    actual = {
        line.split("\t", 1)[1]
        for line in _git("diff", "--name-status", EXPECTED_BASE, EXPECTED_CANDIDATE).splitlines()
    }
    assert set(classified) == actual
    for path in classified:
        _git_blob(EXPECTED_CANDIDATE, path).decode("ascii")


def test_final_merge_gate_has_passing_regression_and_safety_checks():
    _, gate = _load_gate()
    assert gate["decision"] in ALLOWED_DECISIONS
    assert gate["decision"] == "READY_FOR_EXPLICIT_MERGE"
    assert gate["blockers"] == []
    assert all(gate["regression_checks"].values())
    assert gate["main_checkout_untouched"] is True
    assert gate["contamination_checks"]["forbidden_paths"] == []
    assert gate["contamination_checks"]["dependency_drift"] is False
    assert gate["contamination_checks"]["unexpected_subprocess_behavior"] is False
    assert all(value is False for value in gate["side_effects"].values())
    assert gate["test_counts"]["pre_merge"]["passed"] == 63
    assert gate["test_counts"]["post_merge_candidate"]["passed"] == 116
    assert gate["test_counts"]["gate_worktree"]["passed"] == 119
    assert gate["test_counts"]["delta"] == {
        "collected": 53,
        "explained": True,
        "gate_tests": 3,
        "passed": 53,
    }
    assert gate["test_counts"]["bundle"]["passed"] == 119
    assert gate["test_counts"]["focused_boundary"]["passed"] == 49
    assert gate["merge_command"] == (
        "git merge --ff-only a155762d946cff2cf41f2cc68c721ad77f3b4445"
    )


def test_final_merge_gate_replay_hashes_match_current_candidate():
    _, gate = _load_gate()
    assert gate["replay_hashes"] == EXPECTED_HASHES
    paths = {
        "surface_projection_schema_sha256": REPOSITORY_ROOT
        / "lucida/contracts/surface-projection-v1.schema.json",
        "signal_envelope_fixture_sha256": REPOSITORY_ROOT
        / "lucida/replay/fixtures/session-signal-envelope-v1-fictional.json",
        "semantic_report_fixture_sha256": REPOSITORY_ROOT
        / "tests/lucida/fixtures/mosaik-semantic-light-field-report.json",
    }
    for key, path in paths.items():
        assert _sha256(path) == gate["replay_hashes"][key]
    report = json.loads(paths["semantic_report_fixture_sha256"].read_text(encoding="ascii"))
    assert report["pending"]["tape_sha256"] == gate["replay_hashes"]["tape_sha256"]

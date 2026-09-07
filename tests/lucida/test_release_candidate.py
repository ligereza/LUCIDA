import json
from pathlib import Path
import subprocess


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPOSITORY_ROOT / "resolume" / "release-candidate-manifest.json"


def _git(*args):
    return subprocess.check_output(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        text=True,
    ).splitlines()


def test_release_candidate_manifest_matches_base_to_candidate_diff():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    base = manifest["base_commit"]
    candidate = manifest["candidate_commit"]
    expected = [
        {"status": line[0], "path": line[1]}
        for line in (item.split("\t", 1) for item in _git("diff", "--name-status", base, candidate))
    ]

    assert manifest["candidate_diff"]["files"] == expected
    assert manifest["candidate_diff"]["file_count"] == len(expected) == 26
    assert all(not item["path"].startswith("adobe/") for item in expected)
    assert all("/assets/" not in item["path"] for item in expected)
    assert all("/media/" not in item["path"] for item in expected)


def test_release_candidate_is_fast_forwardable_and_metadata_is_consistent():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    base = manifest["base_commit"]
    candidate = manifest["candidate_commit"]

    assert _git("merge-base", "--is-ancestor", base, candidate) == []
    assert manifest["merge_rehearsal"]["result"] == "fast_forward"
    assert manifest["merge_rehearsal"]["conflicts"] == []
    assert manifest["bundle_evidence"]["artifact_source_commit"] == candidate
    assert manifest["bundle_evidence"]["tests_collected"] == 116
    assert manifest["bundle_evidence"]["tests_passed"] == 116
    assert manifest["rehearsal_verification"]["tests_collected"] == 118
    assert manifest["rehearsal_verification"]["tests_passed"] == 118
    assert manifest["rehearsal_verification"]["tests_failed"] == 0
    assert manifest["safe_integration"]["command"] == (
        "git merge --ff-only a155762d946cff2cf41f2cc68c721ad77f3b4445"
    )
    assert manifest["safe_integration"]["untracked_path_observed_and_preserved"] == "adobe/"

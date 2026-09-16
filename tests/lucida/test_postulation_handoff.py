import json
from pathlib import Path
import subprocess


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HANDOFF_PATH = REPOSITORY_ROOT / "resolume" / "postulation-handoff.json"
RELEASE_PATH = REPOSITORY_ROOT / "resolume" / "release-candidate-manifest.json"


def _git(*args):
    return subprocess.check_output(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        text=True,
    ).splitlines()


def test_postulation_handoff_matches_release_candidate_and_current_history():
    handoff = json.loads(HANDOFF_PATH.read_text(encoding="utf-8"))
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))

    assert handoff["commit_provenance"]["base_commit"] == release["base_commit"]
    assert handoff["commit_provenance"]["candidate_commit"] == release["candidate_commit"]
    assert handoff["commit_provenance"]["candidate_parent_commit"] == release[
        "candidate_parent_commit"
    ]
    assert handoff["commit_provenance"]["rehearsal_commit"] == (
        "ef6262a7d408db873dc8f25e969253a954cf95bb"
    )
    assert _git(
        "merge-base",
        "--is-ancestor",
        handoff["commit_provenance"]["base_commit"],
        handoff["commit_provenance"]["candidate_commit"],
    ) == []
    assert handoff["candidate_scope"]["file_count"] == 26
    assert handoff["candidate_scope"]["files"] == [
        item["path"] for item in release["candidate_diff"]["files"]
    ]
    assert handoff["candidate_scope"]["forbidden_paths"] == []
    assert handoff["candidate_scope"]["adobe_changes"] is False


def test_postulation_handoff_proves_one_bounded_offline_story():
    handoff = json.loads(HANDOFF_PATH.read_text(encoding="utf-8"))
    implementation = handoff["verified_implementation"]
    evidence = handoff["evidence"]
    boundary = handoff["architecture_boundary"]

    assert implementation["recorded_signal_envelope_v1"] is True
    assert implementation["deterministic_replay"] is True
    assert implementation["proposal_only"] is True
    assert implementation["explicit_approval"] is True
    assert implementation["reversible"] is True
    assert implementation["external_side_effects"] is False
    assert implementation["live_resolume"] is False
    assert evidence["tape_sha256"] == "f69e170a3447924a7e30126572c659bf61a353d6628ae9e4cd1359aa035bbaec"
    assert evidence["projection_schema_sha256"] == "3bca2f33944f062acfbb9aef6444e4b84d5977bb7eede7f31673d7360e7a356e"
    assert evidence["overlay_status"] == "pending_approval"
    assert boundary["surface_projection"] == "lucida.surface_projection.SurfaceProjectionV1"
    assert boundary["duplication_assessment"].startswith("Distinct")
    assert "tape" in boundary["resolume_specific_boundary"]

    mapping = handoff["postulation_mapping"]
    assert mapping["mathematical_layout"]["status"] == "partial_offline_support"
    assert mapping["software_feasibility"]["status"] == "offline_supported"
    assert mapping["reversible_proposal_behavior"]["status"] == "offline_verified"
    assert mapping["light_audio_venue"]["status"] == "prospective"
    assert handoff["safe_integration"]["authorization_required"] is True
    assert handoff["safe_integration"]["must_not_execute_automatically"] is True


def test_postulation_handoff_is_ascii_and_has_explicit_limitations():
    raw = HANDOFF_PATH.read_bytes()
    assert raw.decode("ascii")
    handoff = json.loads(raw.decode("ascii"))
    limitations = " ".join(handoff["limitations"])
    assert "live Resolume" in limitations
    assert "hardware" in limitations
    assert "artifact source commit" in limitations
    assert handoff["contamination_check"]["adobe_path_read"] is False
    assert handoff["contamination_check"]["adobe_path_modified"] is False

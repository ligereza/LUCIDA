import json
from pathlib import Path
import subprocess

from lucida.evidence_bundle import _sha256


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPOSITORY_ROOT / "resolume" / "postulation-integration-manifest.json"
HANDOFF_PATH = REPOSITORY_ROOT / "resolume" / "postulation-handoff.json"
NOTE_PATH = REPOSITORY_ROOT / "resolume" / "postulation-evidence-note.md"
MATRIX_PATH = REPOSITORY_ROOT / "resolume" / "postulation-evidence-matrix.json"
ALLOWED_ARTIFACT_STATUSES = {"VERIFIED", "PROSPECTIVE", "OPERATOR_DEPENDENT"}
ALLOWED_TRANSFER_CLASSES = {"internal_reference", "candidate_attachment"}
ALLOWED_SCOPE_STATUSES = {"VERIFIED", "INSPECTABLE_ONLY", "NOT_REPRODUCIBLE"}
FORBIDDEN_POSITIVE_LIVE_CLAIMS = (
    "live resolume was validated",
    "live resolume was tested",
    "audio synchronization was validated",
    "lighting control was validated",
    "camera calibration was validated",
    "gpu performance was validated",
    "network transport was validated",
    "artistic success was verified",
)


def _load_ascii_json(path: Path):
    raw = path.read_bytes()
    raw.decode("ascii")
    return raw, json.loads(raw.decode("ascii"))


def test_transfer_manifest_is_sorted_ascii_and_hash_complete():
    raw, manifest = _load_ascii_json(MANIFEST_PATH)
    handoff_raw, handoff = _load_ascii_json(HANDOFF_PATH)

    assert json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n" == raw.decode(
        "ascii"
    )
    assert handoff_raw.decode("ascii")
    assert manifest["source_commit"] == "73f6708cfef083f512f8a4fea1c880edb6b07d86"
    assert manifest["source_commit_meaning"].startswith("Revision audited before")
    assert subprocess.run(
        ["git", "cat-file", "-e", manifest["source_commit"] + "^{commit}"],
        cwd=REPOSITORY_ROOT,
    ).returncode == 0
    assert manifest["handoff_sha256"] == _sha256(HANDOFF_PATH)
    assert manifest["handoff_sha256"] == "23c9f12f44c60f8d9bb71b0837106681e024153911b1821d042eab07f1176540"
    expected = {
        "resolume/postulation-evidence-matrix.json": MATRIX_PATH,
        "resolume/postulation-evidence-note.md": NOTE_PATH,
        "resolume/postulation-handoff.json": HANDOFF_PATH,
    }
    records = manifest["included_artifacts"]
    assert len(records) == 3
    assert {record["path"] for record in records} == set(expected)
    for record in records:
        path = expected[record["path"]]
        assert path.is_file()
        assert record["sha256"] == _sha256(path)


def test_transfer_manifest_schema_scope_and_operator_guards():
    _, manifest = _load_ascii_json(MANIFEST_PATH)

    assert manifest["target_package_relative_path"] == "evidence/lucida-resolume/"
    assert ".." not in manifest["target_package_relative_path"]
    assert manifest["reproducibility_scope"]["full_lucida_worktree"]["status"] == "VERIFIED"
    assert manifest["reproducibility_scope"]["transfer_artifact_set"]["status"] == (
        "INSPECTABLE_ONLY"
    )
    assert manifest["reproducibility_scope"]["candidate_package"]["status"] == (
        "NOT_REPRODUCIBLE"
    )
    assert manifest["reproducibility_scope"]["candidate_package"]["commands_executable"] == []
    assert manifest["attachment_recommendation"]["runtime_material_transferred"] is False
    assert manifest["operator_action"]["merge_executed"] is False
    assert manifest["operator_action"]["push_executed"] is False
    assert manifest["operator_action"]["contact_remote_package"] is False
    assert manifest["evidence_boundary"]["live_validation_claim"] is False
    for record in manifest["included_artifacts"]:
        assert record["status"] in ALLOWED_ARTIFACT_STATUSES
        assert record["transfer_class"] in ALLOWED_TRANSFER_CLASSES
    assert all(
        scope["status"] in ALLOWED_SCOPE_STATUSES
        for scope in manifest["reproducibility_scope"].values()
    )


def test_transfer_artifacts_do_not_claim_live_validation_or_runtime_transfer():
    manifest = _load_ascii_json(MANIFEST_PATH)[1]
    included_paths = [REPOSITORY_ROOT / record["path"] for record in manifest["included_artifacts"]]
    searchable = " ".join(path.read_text(encoding="ascii") for path in included_paths).lower()

    assert not any(term in searchable for term in FORBIDDEN_POSITIVE_LIVE_CLAIMS)
    assert "python source modules" in manifest["excluded_runtime_material"]
    assert "credentials" in manifest["excluded_runtime_material"]
    assert "media and personal data" in manifest["excluded_runtime_material"]
    assert "live validation results" in manifest["excluded_runtime_material"]

    note = NOTE_PATH.read_text(encoding="ascii")
    assert "solo desde el full LUCIDA worktree" in note
    assert "no es ejecutable por si solo" in note
    matrix = _load_ascii_json(MATRIX_PATH)[1]
    assert matrix["verification_scope"] == "full_lucida_worktree_only"

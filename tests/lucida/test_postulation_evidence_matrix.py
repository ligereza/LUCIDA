import json
from pathlib import Path

from lucida.evidence_bundle import _sha256


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPOSITORY_ROOT / "resolume" / "postulation-evidence-matrix.json"
HANDOFF_PATH = REPOSITORY_ROOT / "resolume" / "postulation-handoff.json"
ALLOWED_STATUSES = {"VERIFIED", "PROSPECTIVE", "OPERATOR_DEPENDENT"}
REQUIRED_RECORD_FIELDS = {
    "claim_id",
    "claim",
    "evidence_refs",
    "status",
    "allowed_use",
    "limit",
    "verification_command",
}
FORBIDDEN_VERIFIED_TERMS = (
    "live resolume",
    "live audio",
    "lighting control",
    "camera calibration",
    "gpu performance",
    "network transport",
    "artistic success",
    "venue geometry",
    "hardware validation",
)


def _load_ascii_json(path: Path):
    raw = path.read_bytes()
    raw.decode("ascii")
    return raw, json.loads(raw.decode("ascii"))


def test_matrix_is_sorted_ascii_and_references_the_current_handoff():
    raw, matrix = _load_ascii_json(MATRIX_PATH)
    handoff_raw, handoff = _load_ascii_json(HANDOFF_PATH)

    assert json.dumps(matrix, ensure_ascii=True, sort_keys=True, indent=2) + "\n" == raw.decode(
        "ascii"
    )
    assert matrix["handoff_file"] == "resolume/postulation-handoff.json"
    assert matrix["handoff_sha256"] == _sha256(HANDOFF_PATH)
    assert matrix["handoff_sha256"] == "23c9f12f44c60f8d9bb71b0837106681e024153911b1821d042eab07f1176540"
    provenance = handoff["commit_provenance"]
    assert matrix["commit_refs"] == {
        "base_commit": provenance["base_commit"],
        "candidate_commit": provenance["candidate_commit"],
        "candidate_parent_commit": provenance["candidate_parent_commit"],
        "current_handoff_snapshot_commit": provenance["current_handoff_snapshot_commit"],
        "rehearsal_commit": provenance["rehearsal_commit"],
        "runtime_integration_base_commit": provenance["runtime_integration_base_commit_value"],
    }
    assert handoff_raw.decode("ascii")


def test_matrix_records_have_allowed_statuses_and_required_fields():
    _, matrix = _load_ascii_json(MATRIX_PATH)
    records = matrix["records"]

    assert matrix["claim_status_vocabulary"] == sorted(ALLOWED_STATUSES)
    assert records
    claim_ids = [record["claim_id"] for record in records]
    assert len(claim_ids) == len(set(claim_ids))
    for record in records:
        assert set(record) == REQUIRED_RECORD_FIELDS
        assert record["status"] in ALLOWED_STATUSES
        assert record["claim_id"]
        assert record["claim"]
        assert record["allowed_use"]
        assert record["limit"]
        assert record["verification_command"].startswith("python ")
        assert record["evidence_refs"]
        assert all(ref.startswith("postulation-handoff.json#/") for ref in record["evidence_refs"])


def test_verified_records_do_not_make_forbidden_live_claims():
    _, matrix = _load_ascii_json(MATRIX_PATH)

    for record in matrix["records"]:
        if record["status"] != "VERIFIED":
            continue
        searchable = " ".join(
            [record["claim"], record["allowed_use"], record["limit"]]
        ).lower()
        assert not any(term in searchable for term in FORBIDDEN_VERIFIED_TERMS)

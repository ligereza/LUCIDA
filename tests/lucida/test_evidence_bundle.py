import copy
import hashlib
from pathlib import Path

from lucida.evidence_bundle import (
    SURFACE_PROJECTION_SCHEMA,
    build_evidence_bundle,
    render_bundle_json,
    render_bundle_report,
)


TEST_COUNTS = {
    "collected": 112,
    "passed": 112,
    "failed": 0,
    "skipped": 0,
    "errors": 0,
}


def test_bundle_is_deterministic_and_separates_evidence_layers():
    first = build_evidence_bundle(source_commit="a" * 40, test_counts=TEST_COUNTS)
    second = build_evidence_bundle(source_commit="a" * 40, test_counts=TEST_COUNTS)

    assert first == second
    assert first["bundle_type"] == "LucidaOfflineEvidenceBundle"
    assert first["source_commit"] == "a" * 40
    assert {key: first["tests"][key] for key in TEST_COUNTS} == TEST_COUNTS
    assert first["tests"]["command"] == "python -m pytest -q"
    assert first["replay_evidence"]["conformance"]["consumer_count"] == 2
    assert first["replay_evidence"]["preview"]["projection"]["surface_id"] == "RESOLUME"
    assert "tape" not in first["replay_evidence"]["preview"]["projection"]
    assert first["proposed_live_behavior"]["status"] == "postulation_only"
    assert first["untested_hardware_venue_assumptions"]

    report = render_bundle_report(first)
    assert "source_commit=" + "a" * 40 in report
    assert "tests_passed=112" in report
    assert "live_behavior=postulation_only" in report
    assert "live_hardware_validation=false" in report
    assert render_bundle_json(first) == render_bundle_json(copy.deepcopy(first))


def test_bundle_records_actual_contract_and_tape_hashes():
    bundle = build_evidence_bundle(source_commit="b" * 40, test_counts=TEST_COUNTS)
    hashes = bundle["replay_evidence"]["hashes"]
    expected_schema_hash = hashlib.sha256(Path(SURFACE_PROJECTION_SCHEMA).read_bytes()).hexdigest()

    assert hashes["surface_projection_schema_sha256"] == expected_schema_hash
    assert hashes["tape_sha256"] == bundle["replay_evidence"]["smoke"]["tape_sha256"]
    assert hashes["signal_envelope_fixture_sha256"]
    assert hashes["semantic_report_fixture_sha256"]

import copy
from pathlib import Path

import pytest

from lucida.evidence_bundle import (
    SURFACE_PROJECTION_SCHEMA,
    EvidenceBundleError,
    _build_commit_metadata,
    build_evidence_bundle,
    render_bundle_json,
    render_bundle_report,
    _sha256,
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
    assert first["commits"]["artifact_source_commit"] == "a" * 40
    assert first["commits"]["runtime_integration_base_commit"] == (
        first["replay_evidence"]["manifest"]["runtime_integration_base_commit"]
    )
    assert "integration_commit" not in first["replay_evidence"]["manifest"]
    assert {key: first["tests"][key] for key in TEST_COUNTS} == TEST_COUNTS
    assert first["tests"]["command"] == "python -m pytest -q"
    assert first["replay_evidence"]["conformance"]["consumer_count"] == 2
    assert first["replay_evidence"]["preview"]["projection"]["surface_id"] == "RESOLUME"
    assert "tape" not in first["replay_evidence"]["preview"]["projection"]
    assert first["proposed_live_behavior"]["status"] == "postulation_only"
    assert first["untested_hardware_venue_assumptions"]

    report = render_bundle_report(first)
    assert "artifact_source_commit=" + "a" * 40 in report
    assert "runtime_integration_base_commit=" in report
    assert "tests_passed=112" in report
    assert "live_behavior=postulation_only" in report
    assert "live_hardware_validation=false" in report
    assert render_bundle_json(first) == render_bundle_json(copy.deepcopy(first))


def test_bundle_records_actual_contract_and_tape_hashes():
    bundle = build_evidence_bundle(source_commit="b" * 40, test_counts=TEST_COUNTS)
    hashes = bundle["replay_evidence"]["hashes"]
    expected_schema_hash = _sha256(Path(SURFACE_PROJECTION_SCHEMA))

    assert hashes["surface_projection_schema_sha256"] == expected_schema_hash
    assert hashes["tape_sha256"] == bundle["replay_evidence"]["smoke"]["tape_sha256"]
    assert hashes["signal_envelope_fixture_sha256"]
    assert hashes["semantic_report_fixture_sha256"]


def test_evidence_hashes_are_stable_across_checkout_line_endings(tmp_path):
    lf_path = tmp_path / "fixture-lf.json"
    crlf_path = tmp_path / "fixture-crlf.json"
    lf_path.write_bytes(b'{"status":"PASS"}\n')
    crlf_path.write_bytes(b'{"status":"PASS"}\r\n')

    assert _sha256(lf_path) == _sha256(crlf_path)


def test_commit_metadata_rejects_ambiguous_or_stale_fields():
    bundle = build_evidence_bundle(source_commit="c" * 40, test_counts=TEST_COUNTS)
    manifest = bundle["replay_evidence"]["manifest"]

    with pytest.raises(EvidenceBundleError, match="ambiguous"):
        _build_commit_metadata(
            "c" * 40,
            {**manifest, "integration_commit": "d" * 40},
        )
    with pytest.raises(EvidenceBundleError, match="stale or inconsistent"):
        _build_commit_metadata(
            "c" * 40,
            {**manifest, "runtime_integration_base_commit": "d" * 40},
        )
    with pytest.raises(EvidenceBundleError, match="abbreviated"):
        build_evidence_bundle(source_commit="abc1234", test_counts=TEST_COUNTS)

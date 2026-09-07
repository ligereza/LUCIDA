"""Deterministic offline evidence bundle for the LUCIDA postulation path."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

from .signals.smoke import (
    DEFAULT_ENVELOPE_FIXTURE,
    DEFAULT_REPORT_FIXTURE,
    build_evidence_manifest,
    RUNTIME_INTEGRATION_BASE_COMMIT,
    run_envelope_backed_preview,
    run_envelope_backed_smoke,
)
from .surface_conformance import run_fixture_conformance


BUNDLE_TYPE = "LucidaOfflineEvidenceBundle"
BUNDLE_SCHEMA_VERSION = "1.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SURFACE_PROJECTION_SCHEMA = (
    REPOSITORY_ROOT / "lucida" / "contracts" / "surface-projection-v1.schema.json"
)
TEST_COMMAND = "python -m pytest -q"


class EvidenceBundleError(ValueError):
    """Raised when offline evidence cannot be assembled safely."""


def build_evidence_bundle(
    *,
    source_commit: str | None = None,
    test_counts: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Assemble one deterministic bundle from existing offline evidence paths."""
    manifest = build_evidence_manifest()
    smoke = run_envelope_backed_smoke()
    preview = run_envelope_backed_preview()
    conformance = run_fixture_conformance()
    counts = dict(test_counts) if test_counts is not None else run_test_suite()
    commit = source_commit or _current_commit()
    commits = _build_commit_metadata(commit, manifest)
    envelope_path = Path(DEFAULT_ENVELOPE_FIXTURE)
    report_path = Path(DEFAULT_REPORT_FIXTURE)
    return {
        "bundle_type": BUNDLE_TYPE,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "commits": commits,
        "commit_semantics": {
            "artifact_source_commit": "Exact local HEAD used to generate this bundle.",
            "runtime_integration_base_commit": (
                "Historical commit that introduced the offline RESOLUME smoke integration; "
                "later commits may extend it."
            ),
        },
        "implemented_code": {
            "projection_contract": "lucida.surface_projection.SurfaceProjectionV1",
            "projection_schema": "lucida/contracts/surface-projection-v1.schema.json",
            "resolume_runtime": "lucida.signals.boundary.OscResolumeBoundary",
            "offline_preview": "lucida.signals.smoke.run_envelope_backed_preview",
            "consumer_conformance": "lucida.surface_conformance.run_conformance",
            "execution_mode": "proposal_only",
            "external_side_effects": False,
        },
        "replay_evidence": {
            "manifest": manifest,
            "smoke": smoke,
            "preview": preview,
            "conformance": conformance,
            "hashes": {
                "surface_projection_schema_sha256": _sha256(SURFACE_PROJECTION_SCHEMA),
                "signal_envelope_fixture_sha256": _sha256(envelope_path),
                "semantic_report_fixture_sha256": _sha256(report_path),
                "tape_sha256": smoke["tape_sha256"],
            },
        },
        "tests": {
            "command": TEST_COMMAND,
            "collected": _count_value(counts, "collected"),
            "passed": _count_value(counts, "passed"),
            "failed": _count_value(counts, "failed"),
            "skipped": _count_value(counts, "skipped"),
            "errors": _count_value(counts, "errors"),
        },
        "proposed_live_behavior": {
            "status": "postulation_only",
            "light_behavior": "A future approved consumer may project validated surface state to live light output.",
            "audio_behavior": "A future approved consumer may align live audio or timecode with the proposal.",
            "approval": "Explicit approval remains required before any live action.",
            "implementation_status": "Not implemented or live validated in this bundle.",
        },
        "untested_hardware_venue_assumptions": [
            "Live Resolume was not opened or controlled.",
            "No projector, lighting device, audio device, camera, GPU, or venue network was used.",
            "Venue timing, calibration, photometry, acoustics, and physical routing remain untested.",
            "ADOBE, PUPILA, and VIZZ consumers remain offline contract candidates only.",
        ],
    }


def run_test_suite() -> dict[str, int]:
    """Run the repository suite and capture counts from pytest's runtime."""
    try:
        import pytest
    except ImportError as exc:  # pragma: no cover - environment failure
        raise EvidenceBundleError("pytest is required for the evidence bundle.") from exc

    counter = _PytestCounter()
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        exit_code = pytest.main(["-q"], plugins=[counter])
    if exit_code != 0:
        raise EvidenceBundleError(f"pytest exited with code {int(exit_code)}.")
    return counter.as_dict()


class _PytestCounter:
    def __init__(self) -> None:
        self.collected = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = 0

    def pytest_collection_modifyitems(self, session, config, items) -> None:
        self.collected = len(items)

    def pytest_terminal_summary(self, terminalreporter, exitstatus, config) -> None:
        self.passed = len(terminalreporter.stats.get("passed", []))
        self.failed = len(terminalreporter.stats.get("failed", []))
        self.skipped = len(terminalreporter.stats.get("skipped", []))
        self.errors = len(terminalreporter.stats.get("error", []))

    def as_dict(self) -> dict[str, int]:
        return {
            "collected": self.collected,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def render_bundle_json(bundle: Mapping[str, Any]) -> str:
    """Render stable JSON for machine-readable postulation evidence."""
    return json.dumps(bundle, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def render_bundle_report(bundle: Mapping[str, Any]) -> str:
    """Render a concise human-readable report from the same bundle."""
    replay = bundle["replay_evidence"]
    smoke = replay["smoke"]
    preview = replay["preview"]
    tests = bundle["tests"]
    hashes = replay["hashes"]
    lines = [
        "LUCIDA_OFFLINE_EVIDENCE_BUNDLE",
        f"artifact_source_commit={bundle['commits']['artifact_source_commit']}",
        f"runtime_integration_base_commit={bundle['commits']['runtime_integration_base_commit']}",
        f"projection_schema_sha256={hashes['surface_projection_schema_sha256']}",
        f"signal_envelope_fixture_sha256={hashes['signal_envelope_fixture_sha256']}",
        f"semantic_report_fixture_sha256={hashes['semantic_report_fixture_sha256']}",
        f"tape_sha256={hashes['tape_sha256']}",
        f"replay_status={smoke['replay_status']}",
        f"proposal_id={smoke['proposal_id']}",
        f"projection_surface={preview['projection']['surface_id']}",
        f"proposal_only={smoke['execution_mode'] == 'proposal_only'}",
        f"reversible={smoke['reversible']}",
        f"requires_explicit_approval={smoke['requires_explicit_approval']}",
        f"external_side_effects={smoke['external_side_effects']}",
        f"conformance_consumers={replay['conformance']['consumer_count']}",
        f"tests_collected={tests['collected']}",
        f"tests_passed={tests['passed']}",
        f"tests_failed={tests['failed']}",
        "live_behavior=postulation_only",
        "live_hardware_validation=false",
    ]
    return "\n".join(lines) + "\n"


def _current_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise EvidenceBundleError("cannot read the local source commit.") from exc
    return _validate_commit(result.stdout.strip(), "artifact source commit")


def _build_commit_metadata(
    artifact_source_commit: str,
    manifest: Mapping[str, Any],
) -> dict[str, str]:
    if "integration_commit" in manifest:
        raise EvidenceBundleError(
            "manifest contains ambiguous integration_commit metadata."
        )
    runtime_base = manifest.get("runtime_integration_base_commit")
    if runtime_base != RUNTIME_INTEGRATION_BASE_COMMIT:
        raise EvidenceBundleError(
            "manifest runtime integration base commit is stale or inconsistent."
        )
    return {
        "artifact_source_commit": _validate_commit(
            artifact_source_commit, "artifact source commit"
        ),
        "runtime_integration_base_commit": _validate_commit(
            runtime_base, "runtime integration base commit"
        ),
    }


def _validate_commit(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise EvidenceBundleError(f"{label} is invalid or abbreviated.")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count_value(counts: Mapping[str, int], name: str) -> int:
    value = counts.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EvidenceBundleError(f"test count {name} is invalid.")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic offline LUCIDA postulation evidence."
    )
    output_mode = parser.add_mutually_exclusive_group()
    output_mode.add_argument("--json", action="store_true", help="Emit stable JSON.")
    output_mode.add_argument("--report", action="store_true", help="Emit a human report.")
    args = parser.parse_args(argv)
    try:
        bundle = build_evidence_bundle()
    except (EvidenceBundleError, OSError, ValueError) as exc:
        print(f"evidence_bundle_error={exc}", file=sys.stderr)
        return 2
    print(render_bundle_json(bundle) if args.json else render_bundle_report(bundle), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

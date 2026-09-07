"""Deterministic offline smoke evidence for the LUCIDA RESOLUME surface."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from .replay import SignalReplayError, load_fixture, replay_fixture


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OSC_FIXTURE = (
    REPOSITORY_ROOT / "lucida" / "signals" / "fixtures" / "osc-session-fictional.json"
)
DEFAULT_REPORT_FIXTURE = (
    REPOSITORY_ROOT
    / "tests"
    / "lucida"
    / "fixtures"
    / "mosaik-semantic-light-field-report.json"
)
INTEGRATION_COMMIT = "ac0fb16734483f48517696c2a1d3619d72a5df84"
MANIFEST_SCHEMA_VERSION = "0.1"
MANIFEST_PATH = REPOSITORY_ROOT / "resolume" / "evidence-manifest.json"


def run_smoke(
    osc_fixture: str | Path = DEFAULT_OSC_FIXTURE,
    report_fixture: str | Path = DEFAULT_REPORT_FIXTURE,
) -> dict[str, Any]:
    """Replay the existing fixtures and return bounded proposal evidence."""
    replay_fixture_value = load_fixture(osc_fixture)
    report = load_fixture(report_fixture)
    replay_fixture_value["semantic_reports"] = [report]
    result = replay_fixture(replay_fixture_value)
    if result.get("semantic_report_count") != 1:
        raise SignalReplayError("Offline smoke expected one semantic report.")
    transitions = result.get("semantic_transitions")
    if not isinstance(transitions, list) or len(transitions) != 1:
        raise SignalReplayError("Offline smoke expected one semantic transition.")
    transition = transitions[0]
    overlay = transition.get("overlay")
    if not isinstance(overlay, dict):
        raise SignalReplayError("Offline smoke overlay is invalid.")
    preview = overlay.get("resolume_preview")
    if not isinstance(preview, dict):
        raise SignalReplayError("Offline smoke RESOLUME preview is missing.")
    proposal = preview.get("proposal")
    tape = preview.get("tape")
    safety = preview.get("safety")
    if not isinstance(proposal, dict) or not isinstance(tape, dict):
        raise SignalReplayError("Offline smoke proposal or tape evidence is missing.")
    if not isinstance(safety, dict):
        raise SignalReplayError("Offline smoke safety evidence is missing.")
    if "frames" in proposal:
        raise SignalReplayError("Offline smoke proposal must not contain tape frames.")
    expected_safety = {
        "proposal_only": True,
        "reversible": True,
        "automatic_actions": False,
        "resolume_opened": False,
        "external_side_effects": False,
    }
    if safety != expected_safety:
        raise SignalReplayError("Offline smoke safety evidence is invalid.")
    if preview.get("status") != "pending_approval":
        raise SignalReplayError("Offline smoke preview is not pending approval.")
    if proposal.get("execution_mode") != "proposal_only":
        raise SignalReplayError("Offline smoke proposal is not proposal_only.")
    if proposal.get("reversible") is not True:
        raise SignalReplayError("Offline smoke proposal is not reversible.")
    if proposal.get("requires_explicit_approval") is not True:
        raise SignalReplayError("Offline smoke proposal does not require approval.")
    if overlay.get("surface") != "LUCIDA" or preview.get("surface") != "RESOLUME":
        raise SignalReplayError("Offline smoke surface contract is invalid.")

    return {
        "replay_status": result["status"],
        "proposal_id": proposal["proposal_id"],
        "overlay_status": preview["status"],
        "execution_mode": proposal["execution_mode"],
        "reversible": proposal["reversible"],
        "requires_explicit_approval": proposal["requires_explicit_approval"],
        "tape_schema": tape["schema"],
        "tape_sha256": tape["sha256"],
        "frame_count": tape["frame_count"],
        "frames_copied": False,
        "automatic_actions": safety["automatic_actions"],
        "resolume_opened": safety["resolume_opened"],
        "external_side_effects": safety["external_side_effects"],
    }


def build_evidence_manifest(
    osc_fixture: str | Path = DEFAULT_OSC_FIXTURE,
    report_fixture: str | Path = DEFAULT_REPORT_FIXTURE,
) -> dict[str, Any]:
    """Build the committed machine-readable evidence manifest."""
    evidence = run_smoke(osc_fixture, report_fixture)
    osc_path = Path(osc_fixture).expanduser().resolve()
    report_path = Path(report_fixture).expanduser().resolve()
    return {
        "manifest_type": "LucidaResolumeEvidenceManifest",
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "integration_commit": INTEGRATION_COMMIT,
        "smoke_command": "python -m lucida.signals.smoke --manifest",
        "fixtures": {
            "osc_fixture": _repository_path(osc_path),
            "osc_fixture_sha256": _sha256(osc_path),
            "semantic_report_fixture": _repository_path(report_path),
            "semantic_report_fixture_sha256": _sha256(report_path),
            "tape_schema": evidence["tape_schema"],
            "tape_sha256": evidence["tape_sha256"],
        },
        "evidence": evidence,
        "guarantees": {
            "proposal_only": evidence["execution_mode"] == "proposal_only",
            "reversible": evidence["reversible"],
            "requires_explicit_approval": evidence["requires_explicit_approval"],
            "frames_copied": evidence["frames_copied"],
            "automatic_actions": evidence["automatic_actions"],
            "resolume_opened": evidence["resolume_opened"],
            "external_side_effects": evidence["external_side_effects"],
        },
        "tests": {
            "regression_module": "tests/lucida/test_resolume_smoke.py",
            "focal_command": "python -m pytest -q tests/lucida/test_resolume_smoke.py",
            "full_suite_command": "python -m pytest -q",
            "compile_command": "python -m compileall -q lucida tests",
            "diff_check_command": "git diff --check",
        },
        "limitations": [
            "Live Resolume and hardware were not tested.",
            "No network, GPU, camera, or subprocess execution was performed.",
        ],
    }


def render_manifest(manifest: dict[str, Any]) -> str:
    """Render a stable JSON manifest for files and machine readers."""
    return json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def render_evidence(evidence: dict[str, Any]) -> str:
    """Render stable key-value evidence for a human or a log parser."""
    keys = (
        "replay_status",
        "proposal_id",
        "overlay_status",
        "execution_mode",
        "reversible",
        "requires_explicit_approval",
        "tape_schema",
        "tape_sha256",
        "frame_count",
        "frames_copied",
        "automatic_actions",
        "resolume_opened",
        "external_side_effects",
    )
    lines = ["LUCIDA_RESOLUME_OFFLINE_SMOKE"]
    lines.extend(f"{key}={_render_value(evidence[key])}" for key in keys)
    return "\n".join(lines)


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_path(path: Path) -> str:
    try:
        return path.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay the offline LUCIDA RESOLUME proposal-only smoke fixture."
    )
    parser.add_argument("--osc-fixture", type=Path, default=DEFAULT_OSC_FIXTURE)
    parser.add_argument("--report-fixture", type=Path, default=DEFAULT_REPORT_FIXTURE)
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Emit the machine-readable evidence manifest as JSON.",
    )
    args = parser.parse_args(argv)
    try:
        if args.manifest:
            print(render_manifest(build_evidence_manifest(args.osc_fixture, args.report_fixture)), end="")
            return 0
        evidence = run_smoke(args.osc_fixture, args.report_fixture)
    except (OSError, SignalReplayError) as exc:
        print(f"offline_smoke_error={exc}", file=sys.stderr)
        return 2
    print(render_evidence(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

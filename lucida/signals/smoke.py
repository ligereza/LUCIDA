"""Deterministic offline smoke evidence for the LUCIDA RESOLUME surface."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from lucida.replay import (
    load_fixture as load_session_fixture,
    replay_signal_envelope_v1_fixture,
)

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
DEFAULT_ENVELOPE_FIXTURE = (
    REPOSITORY_ROOT
    / "lucida"
    / "replay"
    / "fixtures"
    / "session-signal-envelope-v1-fictional.json"
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
    return _build_evidence_from_runtime(replay_fixture(replay_fixture_value))


def run_envelope_backed_smoke(
    envelope_fixture: str | Path = DEFAULT_ENVELOPE_FIXTURE,
    report_fixture: str | Path = DEFAULT_REPORT_FIXTURE,
) -> dict[str, Any]:
    """Validate recorded envelopes, then replay them through the runtime dispatcher."""
    session_report, runtime_result = _run_envelope_backed_runtime(
        envelope_fixture,
        report_fixture,
    )
    evidence = _build_evidence_from_runtime(runtime_result)
    transition = runtime_result["semantic_transitions"][0]
    overlay = transition["overlay"]
    preview = overlay["resolume_preview"]
    return {
        **evidence,
        "input_contract": "SignalEnvelopeV1",
        "session_replay_status": session_report["status"],
        "session_signal_count": session_report["signal_count"],
        "runtime_dispatcher": "lucida.signals.replay.replay_fixture",
        "overlay_surface": overlay["surface"],
        "preview_surface": preview["surface"],
    }


def run_envelope_backed_preview(
    envelope_fixture: str | Path = DEFAULT_ENVELOPE_FIXTURE,
    report_fixture: str | Path = DEFAULT_REPORT_FIXTURE,
) -> dict[str, Any]:
    """Return a compact JSON surface from the existing pending overlay."""
    session_report, runtime_result = _run_envelope_backed_runtime(
        envelope_fixture,
        report_fixture,
    )
    _build_evidence_from_runtime(runtime_result)
    transition = runtime_result["semantic_transitions"][0]
    overlay = transition["overlay"]
    preview = overlay["resolume_preview"]
    proposal = preview["proposal"]
    return {
        "surface": overlay["surface"],
        "preview_surface": preview["surface"],
        "status": preview["status"],
        "proposal": {
            "proposal_id": proposal["proposal_id"],
            "reason": proposal["reason"],
            "evidence": list(proposal["evidence"]),
            "execution_mode": proposal["execution_mode"],
            "reversible": proposal["reversible"],
            "requires_explicit_approval": proposal["requires_explicit_approval"],
        },
        "tape": dict(preview["tape"]),
        "safety": dict(preview["safety"]),
        "source": {
            "input_contract": "SignalEnvelopeV1",
            "session_replay_status": session_report["status"],
            "session_signal_count": session_report["signal_count"],
            "runtime_dispatcher": "lucida.signals.replay.replay_fixture",
        },
    }


def _run_envelope_backed_runtime(
    envelope_fixture: str | Path,
    report_fixture: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run validation and the existing runtime once for surface consumers."""
    envelope_document = load_session_fixture(envelope_fixture)
    report = load_fixture(report_fixture)
    session_report = replay_signal_envelope_v1_fixture(envelope_document)
    if session_report["safety"]["proposal_only"] is not True:
        raise SignalReplayError("Envelope-backed session replay is not proposal_only.")
    if session_report["safety"]["external_side_effects"] is not False:
        raise SignalReplayError("Envelope-backed session replay has external effects.")
    runtime_fixture = {
        "session_id": envelope_document["session_id"],
        "envelopes": [record["signal"] for record in session_report["records"]],
        "results": [],
        "semantic_reports": [report],
    }
    runtime_result = replay_fixture(runtime_fixture)
    return session_report, runtime_result


def _build_evidence_from_runtime(result: dict[str, Any]) -> dict[str, Any]:
    """Extract and validate the existing proposal-only overlay evidence."""
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
    envelope_fixture: str | Path = DEFAULT_ENVELOPE_FIXTURE,
) -> dict[str, Any]:
    """Build the committed machine-readable evidence manifest."""
    evidence = run_envelope_backed_smoke(envelope_fixture, report_fixture)
    raw_evidence = run_smoke(osc_fixture, report_fixture)
    osc_path = Path(osc_fixture).expanduser().resolve()
    report_path = Path(report_fixture).expanduser().resolve()
    envelope_path = Path(envelope_fixture).expanduser().resolve()
    return {
        "manifest_type": "LucidaResolumeEvidenceManifest",
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "integration_commit": INTEGRATION_COMMIT,
        "smoke_command": "python -m lucida.signals.smoke --manifest",
        "preview_command": "python -m lucida.signals.smoke --preview",
        "fixtures": {
            "osc_fixture": _repository_path(osc_path),
            "osc_fixture_sha256": _sha256(osc_path),
            "signal_envelope_v1_fixture": _repository_path(envelope_path),
            "signal_envelope_v1_fixture_sha256": _sha256(envelope_path),
            "semantic_report_fixture": _repository_path(report_path),
            "semantic_report_fixture_sha256": _sha256(report_path),
            "tape_schema": evidence["tape_schema"],
            "tape_sha256": evidence["tape_sha256"],
        },
        "evidence": evidence,
        "raw_evidence": raw_evidence,
        "integration_boundary": {
            "adapter": "lucida.replay.session.adapt_signal_envelope_v1",
            "replay": "lucida.replay.session.replay_signal_envelope_v1_fixture",
            "schema": "lucida/replay/contracts/signal-envelope-v1.schema.json",
            "scope": "recorded_osc_timecode_only",
            "live_xio_support": False,
        },
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
            "signal_envelope_v1_command": "python -m pytest -q tests/lucida/test_signal_envelope_v1.py",
            "focal_command": "python -m pytest -q tests/lucida/test_resolume_smoke.py",
            "full_suite_command": "python -m pytest -q",
            "compile_command": "python -m compileall -q lucida tests",
            "diff_check_command": "git diff --check",
        },
        "limitations": [
            "Offline preview only; live Resolume was not tested.",
            "Live Resolume and hardware were not tested.",
            "No network, GPU, camera, or subprocess execution was performed.",
        ],
    }


def render_manifest(manifest: dict[str, Any]) -> str:
    """Render a stable JSON manifest for files and machine readers."""
    return json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def render_preview(preview: dict[str, Any]) -> str:
    """Render a compact deterministic JSON surface for offline inspection."""
    return json.dumps(preview, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"


def render_evidence(evidence: dict[str, Any]) -> str:
    """Render stable key-value evidence for a human or a log parser."""
    path_keys = (
        "input_contract",
        "session_replay_status",
        "session_signal_count",
        "runtime_dispatcher",
        "overlay_surface",
        "preview_surface",
    ) if "input_contract" in evidence else ()
    keys = path_keys + (
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
    parser.add_argument("--envelope-fixture", type=Path, default=DEFAULT_ENVELOPE_FIXTURE)
    parser.add_argument("--report-fixture", type=Path, default=DEFAULT_REPORT_FIXTURE)
    output_mode = parser.add_mutually_exclusive_group()
    output_mode.add_argument(
        "--raw",
        action="store_true",
        help="Use the legacy raw OSC replay path instead of signal-envelope-v1.",
    )
    output_mode.add_argument(
        "--preview",
        action="store_true",
        help="Emit the pending proposal overlay as compact JSON.",
    )
    output_mode.add_argument(
        "--manifest",
        action="store_true",
        help="Emit the machine-readable evidence manifest as JSON.",
    )
    args = parser.parse_args(argv)
    try:
        if args.manifest:
            print(
                render_manifest(
                    build_evidence_manifest(
                        args.osc_fixture,
                        args.report_fixture,
                        args.envelope_fixture,
                    )
                ),
                end="",
            )
            return 0
        if args.preview:
            print(
                render_preview(
                    run_envelope_backed_preview(
                        args.envelope_fixture,
                        args.report_fixture,
                    )
                ),
                end="",
            )
            return 0
        evidence = (
            run_smoke(args.osc_fixture, args.report_fixture)
            if args.raw
            else run_envelope_backed_smoke(args.envelope_fixture, args.report_fixture)
        )
    except (OSError, ValueError) as exc:
        print(f"offline_smoke_error={exc}", file=sys.stderr)
        return 2
    print(render_evidence(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import socket
import subprocess
import json
from pathlib import Path

import pytest

from lucida.signals.smoke import (
    RUNTIME_INTEGRATION_BASE_COMMIT,
    MANIFEST_PATH,
    build_evidence_manifest,
    main,
    render_evidence,
    render_preview,
    run_envelope_backed_smoke,
    run_envelope_backed_preview,
    run_smoke,
)


def test_offline_smoke_is_deterministic_and_reports_pending_overlay():
    first = run_smoke()
    second = run_smoke()

    assert first == second
    assert first == {
        "replay_status": "REVIEW",
        "proposal_id": "proposal-cli-light-field-001",
        "overlay_status": "pending_approval",
        "execution_mode": "proposal_only",
        "reversible": True,
        "requires_explicit_approval": True,
        "tape_schema": "farmaxia:semantic-light-field-tape:0.1",
        "tape_sha256": "f69e170a3447924a7e30126572c659bf61a353d6628ae9e4cd1359aa035bbaec",
        "frame_count": 1,
        "frames_copied": False,
        "automatic_actions": False,
        "resolume_opened": False,
        "external_side_effects": False,
    }

    output = render_evidence(first)
    assert output.splitlines()[0] == "LUCIDA_RESOLUME_OFFLINE_SMOKE"
    assert "overlay_status=pending_approval" in output
    assert "execution_mode=proposal_only" in output
    assert "frames_copied=false" in output
    assert "automatic_actions=false" in output
    assert "external_side_effects=false" in output


def test_smoke_entrypoint_has_no_external_side_effects(monkeypatch, capsys):
    def blocked(*_args, **_kwargs):
        raise AssertionError("host side effect attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)

    assert main([]) == 0
    assert "resolume_opened=false" in capsys.readouterr().out
    assert main(["--preview"]) == 0
    assert "pending_approval" in capsys.readouterr().out


def test_offline_preview_is_stable_and_inspectable():
    first = run_envelope_backed_preview()
    second = run_envelope_backed_preview()

    assert first == second
    assert json.loads(render_preview(first)) == first
    assert first["surface"] == "LUCIDA"
    assert first["preview_surface"] == "RESOLUME"
    assert first["status"] == "pending_approval"
    assert first["proposal"]["reason"] == "Review deterministic semantic light-field tape"
    assert first["proposal"]["evidence"]
    assert first["proposal"]["execution_mode"] == "proposal_only"
    assert first["proposal"]["reversible"] is True
    assert first["proposal"]["requires_explicit_approval"] is True
    assert first["projection"]["contract_type"] == "SurfaceProjection"
    assert first["projection"]["host_id"] == "LUCIDA"
    assert first["projection"]["surface_id"] == "RESOLUME"
    assert first["projection"]["safety"]["external_side_effects"] is False
    assert first["safety"]["external_side_effects"] is False
    assert first["safety"]["resolume_opened"] is False
    assert "frames" not in first["proposal"]


def test_envelope_backed_smoke_matches_raw_proposal_overlay_invariants():
    raw = run_smoke()
    envelope = run_envelope_backed_smoke()
    invariant_keys = (
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

    assert {key: envelope[key] for key in invariant_keys} == {
        key: raw[key] for key in invariant_keys
    }
    assert envelope["input_contract"] == "SignalEnvelopeV1"
    assert envelope["session_signal_count"] == 2
    assert envelope["runtime_dispatcher"] == "lucida.signals.replay.replay_fixture"
    assert envelope["overlay_surface"] == "LUCIDA"
    assert envelope["preview_surface"] == "RESOLUME"


def test_envelope_backed_smoke_rejects_malformed_input_before_dispatch(tmp_path):
    value = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "lucida"
            / "replay"
            / "fixtures"
            / "session-signal-envelope-v1-fictional.json"
        ).read_text(encoding="utf-8")
    )
    value["entries"][1]["signal"]["schema_version"] = "0.2"
    malformed = tmp_path / "malformed-signal-envelope-v1.json"
    malformed.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        run_envelope_backed_smoke(malformed)


def test_committed_manifest_matches_current_smoke_evidence():
    committed = json.loads(Path(MANIFEST_PATH).read_text(encoding="utf-8"))
    generated = build_evidence_manifest()

    assert committed == generated
    assert committed["runtime_integration_base_commit"] == RUNTIME_INTEGRATION_BASE_COMMIT
    assert committed["preview_command"] == "python -m lucida.signals.smoke --preview"
    assert committed["conformance_command"] == "python -m lucida.surface_conformance"
    assert committed["connector_conformance_command"] == "python -m lucida.connector_conformance"
    assert committed["evidence_bundle_command"] == "python -m lucida.evidence_bundle --json"
    assert committed["evidence"] == run_envelope_backed_smoke()
    assert committed["raw_evidence"] == run_smoke()
    assert committed["integration_boundary"] == {
        "adapter": "lucida.replay.session.adapt_signal_envelope_v1",
        "replay": "lucida.replay.session.replay_signal_envelope_v1_fixture",
        "schema": "lucida/replay/contracts/signal-envelope-v1.schema.json",
        "projection_contract": "lucida.surface_projection.SurfaceProjectionV1",
        "projection_schema": "lucida/contracts/surface-projection-v1.schema.json",
        "consumer_conformance": "lucida.surface_conformance.run_conformance",
        "connector_conformance": "lucida.connector_conformance.run_connector_conformance",
        "scope": "recorded_osc_timecode_only",
        "live_xio_support": False,
    }
    assert committed["guarantees"] == {
        "proposal_only": True,
        "reversible": True,
        "requires_explicit_approval": True,
        "frames_copied": False,
        "automatic_actions": False,
        "resolume_opened": False,
        "external_side_effects": False,
    }
    assert committed["limitations"] == [
        "Offline preview only; live Resolume was not tested.",
        "Live Resolume and hardware were not tested.",
        "No network, GPU, camera, or subprocess execution was performed.",
        "ADOBE, PUPILA, and VISUAL host applications were not opened; only bounded summary signals were replayed.",
    ]

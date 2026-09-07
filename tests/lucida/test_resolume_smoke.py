import socket
import subprocess

from lucida.signals.smoke import main, render_evidence, run_smoke


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
        "resolume_opened": False,
        "external_side_effects": False,
    }

    output = render_evidence(first)
    assert output.splitlines()[0] == "LUCIDA_RESOLUME_OFFLINE_SMOKE"
    assert "overlay_status=pending_approval" in output
    assert "execution_mode=proposal_only" in output
    assert "frames_copied=false" in output
    assert "external_side_effects=false" in output


def test_smoke_entrypoint_has_no_external_side_effects(monkeypatch, capsys):
    def blocked(*_args, **_kwargs):
        raise AssertionError("host side effect attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)

    assert main([]) == 0
    assert "resolume_opened=false" in capsys.readouterr().out

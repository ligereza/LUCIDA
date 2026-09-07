import copy
import json
from pathlib import Path

import pytest

from lucida.signals.smoke import run_envelope_backed_preview
from lucida.surface_conformance import (
    main,
    render_conformance,
    run_conformance,
    run_fixture_conformance,
    validate_consumer_projection,
)
from lucida.surface_projection import SurfaceProjectionError


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


def _fixture(name):
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_conformance_accepts_resolume_runtime_and_fictional_projection():
    preview = run_envelope_backed_preview()
    report = run_conformance(
        {
            "resolume": preview["projection"],
            "fictional": _fixture("fictional-surface-projection-v1.json"),
        }
    )

    assert report["consumer_count"] == 2
    assert report["consumers"]["resolume"]["surface_id"] == "RESOLUME"
    assert report["consumers"]["fictional"]["surface_id"] == "FICTIONAL"
    assert "tape" not in preview["projection"]
    assert "tape" in preview


def test_resolume_conformance_fixture_matches_runtime_projection():
    preview = run_envelope_backed_preview()

    assert preview["projection"] == _fixture("resolume-surface-projection-v1.json")
    assert run_fixture_conformance()["consumer_count"] == 2


def test_conformance_ignores_unknown_optional_fields():
    value = _fixture("fictional-surface-projection-v1.json")
    extended = copy.deepcopy(value)
    extended["future_field"] = {"consumer": "PUPILA"}

    assert validate_consumer_projection(extended).to_dict() == validate_consumer_projection(
        value
    ).to_dict()


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("host_id",), None),
        (("surface_id",), None),
        (("proposal", "requires_explicit_approval"), False),
        (("proposal", "reversible"), False),
        (("proposal", "evidence"), []),
    ],
)
def test_conformance_fails_closed_on_required_shared_fields(path, replacement):
    value = _fixture("fictional-surface-projection-v1.json")
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement

    with pytest.raises(SurfaceProjectionError):
        validate_consumer_projection(value)


def test_conformance_command_is_deterministic(capsys):
    assert main([]) == 0
    first = capsys.readouterr().out
    assert main([]) == 0
    second = capsys.readouterr().out

    assert first == second == render_conformance(run_fixture_conformance())

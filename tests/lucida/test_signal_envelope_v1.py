import copy
import json
from pathlib import Path
import socket
import subprocess

import pytest

from lucida.replay import (
    SignalEnvelopeV1Error,
    adapt_signal_envelope_v1,
    replay_signal_envelope_v1_fixture,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "lucida"
    / "replay"
    / "fixtures"
    / "session-signal-envelope-v1-fictional.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_signal_envelope_v1_replays_into_existing_proposal_only_runtime():
    first = replay_signal_envelope_v1_fixture(_fixture())
    second = replay_signal_envelope_v1_fixture(_fixture())

    assert first == second
    assert first["status"] == "REVIEW"
    assert first["signal_count"] == 2
    assert first["safety"] == {
        "replay_only": True,
        "proposal_only": True,
        "sockets_opened": False,
        "resolume_opened": False,
        "external_side_effects": False,
    }
    assert [record["signal"]["transport"] for record in first["records"]] == [
        "osc",
        "timecode",
    ]
    assert all(
        proposal["execution_mode"] == "proposal_only"
        for record in first["records"]
        for proposal in record["proposals"]
    )


def test_signal_envelope_v1_schema_is_recorded_as_the_boundary_contract():
    schema_path = FIXTURE.parents[1] / "contracts" / "signal-envelope-v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["$id"] == "urn:lucida:replay:signal-envelope-v1"
    assert schema["additionalProperties"] is True
    assert schema["properties"]["transport"]["enum"] == ["osc", "timecode", "adobe"]


def test_unknown_optional_fields_are_ignored():
    with_optional_fields = _fixture()
    without_optional_fields = copy.deepcopy(with_optional_fields)
    for entry in without_optional_fields["entries"]:
        entry["signal"].pop("vendor_optional", None)
        entry["signal"].pop("unknown_optional", None)
    assert replay_signal_envelope_v1_fixture(with_optional_fields) == replay_signal_envelope_v1_fixture(
        without_optional_fields
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda signal: signal.update({"schema_version": "0.1"}),
        lambda signal: signal.pop("sequence"),
        lambda signal: signal.update({"transport": "xio"}),
        lambda signal: signal.update({"transport": []}),
        lambda signal: signal.update({"sequence": -1}),
        lambda signal: signal.update({"timestamp": "not-a-timestamp"}),
        lambda signal: signal.update({"timecode": 12}),
    ],
)
def test_malformed_signal_envelope_v1_fails_closed(mutation):
    value = _fixture()["entries"][1]["signal"]
    mutation(value)

    with pytest.raises(SignalEnvelopeV1Error):
        adapt_signal_envelope_v1(value)


def test_signal_envelope_v1_replay_has_no_external_side_effects(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("host side effect attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)

    report = replay_signal_envelope_v1_fixture(_fixture())

    assert report["safety"]["external_side_effects"] is False
    assert report["safety"]["resolume_opened"] is False

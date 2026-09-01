import json
from pathlib import Path

import pytest

from lucida.signals import (
    DuplicateEnvelopeError,
    EnvelopeValidationError,
    OscEnvelope,
    OscResolumeBoundary,
    SequenceOrderError,
    UnknownAddressError,
    replay_path,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "lucida"
    / "signals"
    / "fixtures"
    / "osc-session-fictional.json"
)


def _envelope(sequence: int, address: str = "/lucida/instar/preflight") -> dict:
    return {
        "address": address,
        "arguments": ["ready"],
        "timestamp": f"2026-01-10T20:00:{sequence:02d}Z",
        "sequence": sequence,
        "source": "test",
    }


def test_valid_envelope_normalizes_to_a_vj_event():
    boundary = OscResolumeBoundary()
    envelope = OscEnvelope.from_dict(_envelope(1))

    event = boundary.normalize(envelope)

    assert event.event_id == "osc-test-000001"
    assert event.phase == "preflight"
    assert event.event_type == "signal.instar"
    assert event.payload["transport"] == "osc"


def test_unknown_address_is_rejected():
    with pytest.raises(UnknownAddressError, match="Unknown OSC address"):
        OscResolumeBoundary().receive(
            _envelope(1, "/unknown/route"),
            OscResolumeBoundary().initial_state("session-001"),
        )


def test_invalid_arguments_are_rejected():
    with pytest.raises(EnvelopeValidationError, match="unsupported type"):
        OscEnvelope.from_dict({**_envelope(1), "arguments": [{"not": "scalar"}]})


def test_sequence_out_of_order_is_rejected():
    boundary = OscResolumeBoundary()
    state = boundary.initial_state("session-001")
    state = boundary.receive(_envelope(2), state).state

    with pytest.raises(SequenceOrderError, match="Sequence must increase"):
        boundary.receive(_envelope(1), state)


def test_duplicate_sequence_is_rejected():
    boundary = OscResolumeBoundary()
    state = boundary.initial_state("session-001")
    state = boundary.receive(_envelope(1), state).state

    with pytest.raises(DuplicateEnvelopeError, match="Duplicate sequence"):
        boundary.receive(_envelope(1), state)


def test_sender_is_optional_and_never_executes_resolume():
    boundary = OscResolumeBoundary()
    state = boundary.initial_state("session-001")
    received = boundary.receive(_envelope(1), state)

    assert received.sender_called is False
    assert received.outgoing_message["address"] == "/lucida/proposal"
    assert received.state.lucida_state.vj_state.pending_proposal_ids
    assert not hasattr(boundary, "execute")


def test_injected_sender_receives_only_a_proposal_notice():
    boundary = OscResolumeBoundary()
    state = boundary.initial_state("session-001")
    sent: list[dict] = []

    received = boundary.receive(_envelope(1), state, sender=sent.append)

    assert received.sender_called is True
    assert sent == [received.outgoing_message]
    assert sent[0]["message_type"] == "proposal_notice"


def test_signal_replay_covers_all_capabilities_on_one_surface():
    report = replay_path(FIXTURE)

    assert report["status"] == "PASS"
    assert report["surface"] == "single-overlay"
    assert report["envelope_count"] == 6
    assert report["proposal_count"] == 10
    assert report["result_count"] == 10
    assert report["capabilities_observed"] == ["IMAGO", "INSTAR", "NAYADE"]
    assert report["final_state"]["lucida_state"]["pending_proposal_ids"] == []
    assert report["safety"] == {
        "sockets_opened": False,
        "external_side_effects": False,
        "automatic_actions": False,
        "resolume_opened": False,
    }


def test_signal_replay_is_deterministic():
    assert replay_path(FIXTURE) == replay_path(FIXTURE)


def test_signal_fixture_contains_only_fictional_ascii_data():
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    serialized = json.dumps(document)

    assert "C:\\" not in serialized
    assert "Z:\\" not in serialized
    assert ".mp4" not in serialized
    assert ".avc" not in serialized

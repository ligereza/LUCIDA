from lucida.replay.session import SignalEnvelope
from lucida.signals.host import HostResult, HostSignalBoundary
from lucida.signals.xio_bridge import parse_application_event


def _signal():
    return SignalEnvelope.from_dict(
        {
            "envelope_id": "sig-001",
            "event_id": "evt-001",
            "timestamp": "2026-01-10T20:00:00Z",
            "sequence": 1,
            "source": "host-test",
            "address": "/lucida/instar/preflight",
            "arguments": ["ready"],
            "transport": "osc",
        }
    )


def test_host_boundary_returns_accepted_result_without_execution():
    boundary = HostSignalBoundary("session-001")
    result = boundary.receive(_signal(), provenance={"transport": "offline"})

    assert result.status == "accepted"
    assert result.sequence == 1
    assert result.timestamp == "2026-01-10T20:00:00Z"
    assert result.source == "host-test"
    assert result.provenance["transport"] == "offline"
    assert result.proposal_ids
    assert result.mode == "proposal_only"
    assert not hasattr(boundary, "execute")


def test_host_boundary_classifies_unknown_transport_without_event():
    boundary = HostSignalBoundary("session-001")
    signal = SignalEnvelope.from_dict(
        {
            "envelope_id": "sig-001",
            "event_id": "evt-001",
            "timestamp": "2026-01-10T20:00:00Z",
            "sequence": 1,
            "source": "host-test",
            "address": "/xio/instar/preflight.completed",
            "arguments": ["ready"],
            "transport": "xio",
        }
    )

    result = boundary.receive(signal)

    assert result.status == "unknown"
    assert "canonical VJEvent" in result.reason
    assert result.sequence == 1


def test_host_boundary_accepts_xio_and_preserves_receipt_provenance():
    boundary = HostSignalBoundary("fictional-xio-session-001")
    application_event = parse_application_event(
        {
            "event_id": "evt-001",
            "source_app": "XIO",
            "event_type": "preflight.completed",
            "channel": "instar",
            "payload": {"phase": "preflight", "vj_event_type": "phase.completed", "status": "pass"},
            "source_timestamp": "2026-01-10T20:00:00Z",
            "received_timestamp": "2026-01-10T20:00:01Z",
            "session_id": "fictional-xio-session-001",
            "peer_id": "peer-001",
            "sequence": 1,
            "raw_hash": "sha256:001",
            "provenance": {"producer": "test", "transport": "offline"},
        }
    )
    result = boundary.receive_xio(
        application_event,
        results=(
            {
                "result_id": "res-common",
                "proposal_id": "proposal-evt-001-checkpoint-preflight",
                "recorded_at": "2026-01-10T20:01:00Z",
                "status": "observed",
            },
            {
                "result_id": "res-instar",
                "proposal_id": "lucida-instar-evt-001",
                "recorded_at": "2026-01-10T20:01:01Z",
                "status": "accepted",
            },
        ),
    )

    assert result.status == "accepted"
    assert result.provenance["session_id"] == "fictional-xio-session-001"
    assert result.provenance["raw_hash"] == "sha256:001"
    assert result.overlay["surface"] == "LUCIDA"


def test_host_boundary_rejects_non_vj_xio_without_phase_or_replay_mutation():
    boundary = HostSignalBoundary("fictional-xio-session-001")
    application_event = parse_application_event(
        {
            "event_id": "evt-transport-001",
            "source_app": "Q3",
            "event_type": "connectivity.status",
            "channel": "transport",
            "payload": {"status": "online"},
            "source_timestamp": "2026-01-10T20:00:00Z",
            "received_timestamp": "2026-01-10T20:00:01Z",
            "session_id": "fictional-xio-session-001",
            "peer_id": "peer-transport-001",
            "sequence": 1,
            "raw_hash": "sha256:transport-001",
            "provenance": {"producer": "test", "transport": "offline"},
        }
    )
    initial_report = boundary.report()

    first = boundary.receive_xio(application_event)
    second = boundary.receive_xio(application_event)

    assert first.status == "rejected"
    assert first.reason == "Cannot map channel to a VJ phase: transport."
    assert first.sequence == 1
    assert first.timestamp == "2026-01-10T20:00:00Z"
    assert first.source == "Q3"
    assert first.event_id == "evt-transport-001"
    assert first.provenance["session_id"] == "fictional-xio-session-001"
    assert first.provenance["raw_hash"] == "sha256:transport-001"
    assert first.proposal_ids == ()
    assert first.result_ids == ()
    assert first.mode == "proposal_only"
    assert first == second
    assert HostResult.from_dict(first.to_dict()) == first
    assert boundary.report() == initial_report
    assert boundary.state.records == ()
    assert boundary.state.next_sequence == 1
    assert first.overlay["state"]["vj_state"]["sequence"] == 0
    assert first.overlay["safety"]["external_side_effects"] is False
    assert not hasattr(boundary, "execute")

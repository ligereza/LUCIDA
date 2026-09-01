import pytest

from lucida.signals.host import HostContractError, HostResult


def _host_result(**overrides):
    value = {
        "contract_type": "HostResult",
        "schema_version": "0.1",
        "status": "accepted",
        "reason": "Signal accepted into SessionReplay; no action executed.",
        "sequence": 1,
        "timestamp": "2026-01-10T20:01:00Z",
        "source": "host-test",
        "event_id": "event-001",
        "provenance": {"operator": "fixture"},
        "proposal_ids": ["proposal-001"],
        "result_ids": ["result-001"],
        "overlay": {"surface": "LUCIDA"},
        "mode": "proposal_only",
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize("status", ["accepted", "rejected", "unknown"])
def test_host_result_round_trip_for_all_statuses(status):
    result = HostResult.from_dict(_host_result(status=status))

    assert HostResult.from_dict(result.to_dict()) == result
    assert result.status == status
    assert result.mode == "proposal_only"


def test_host_result_rejects_invalid_status_and_contract_metadata():
    with pytest.raises(HostContractError, match="Unknown host result status"):
        HostResult.from_dict(_host_result(status="executed"))

    with pytest.raises(HostContractError, match="contract_type"):
        HostResult.from_dict(_host_result(contract_type="ExecutionResult"))

    with pytest.raises(HostContractError, match="schema_version"):
        HostResult.from_dict(_host_result(schema_version="9.9"))


def test_host_result_rejects_execution_mode():
    with pytest.raises(HostContractError, match="proposal_only"):
        HostResult.from_dict(_host_result(mode="execute"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sequence", "1"),
        ("proposal_ids", "proposal-001"),
        ("result_ids", [1]),
        ("overlay", []),
    ],
)
def test_host_result_rejects_invalid_field_types(field, value):
    with pytest.raises(HostContractError):
        HostResult.from_dict(_host_result(**{field: value}))


def test_host_result_rejects_non_ascii_technical_text():
    with pytest.raises(HostContractError, match="ASCII"):
        HostResult.from_dict(_host_result(reason="Host " + chr(0xCD) + " decision."))

    with pytest.raises(HostContractError, match="ASCII"):
        HostResult.from_dict(_host_result(proposal_ids=["proposal-" + chr(0xF1)]))


def test_host_result_requires_timezone_and_is_not_an_execution_command():
    with pytest.raises(HostContractError, match="timezone"):
        HostResult.from_dict(_host_result(timestamp="2026-01-10T20:01:00"))

    result = HostResult.from_dict(_host_result())
    assert not hasattr(result, "execute")

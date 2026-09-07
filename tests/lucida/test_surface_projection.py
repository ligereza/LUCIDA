import copy

import pytest

from lucida.surface_projection import (
    SurfaceProjectionError,
    SurfaceProjectionProposalV1,
    SurfaceProjectionSafetyV1,
    SurfaceProjectionV1,
)


def _projection() -> SurfaceProjectionV1:
    return SurfaceProjectionV1(
        host_id="LUCIDA",
        surface_id="RESOLUME",
        status="pending_approval",
        proposal=SurfaceProjectionProposalV1(
            proposal_id="proposal-001",
            reason="Review a deterministic proposal",
            evidence=("source:fixture", "tape_sha256:" + "a" * 64),
            execution_mode="proposal_only",
            requires_explicit_approval=True,
            reversible=True,
        ),
        safety=SurfaceProjectionSafetyV1(
            proposal_only=True,
            automatic_actions=False,
            external_side_effects=False,
            host_opened=False,
        ),
    )


def test_surface_projection_round_trips_deterministically():
    projection = _projection()
    serialized = projection.to_dict()

    assert SurfaceProjectionV1.from_dict(serialized).to_dict() == serialized
    assert projection.to_dict() == _projection().to_dict()


def test_unknown_optional_fields_are_ignored_at_each_contract_level():
    serialized = _projection().to_dict()
    extended = copy.deepcopy(serialized)
    extended["future_optional"] = {"consumer": "ADOBE"}
    extended["proposal"]["future_reason_code"] = "recorded_fixture"
    extended["safety"]["future_transport_state"] = "offline"

    assert SurfaceProjectionV1.from_dict(extended).to_dict() == serialized


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("contract_type",), "OtherProjection"),
        (("schema_version",), "2.0"),
        (("host_id",), ""),
        (("status",), "unknown"),
        (("proposal", "execution_mode"), "execute"),
        (("proposal", "requires_explicit_approval"), False),
        (("proposal", "reversible"), False),
        (("safety", "proposal_only"), False),
        (("safety", "external_side_effects"), True),
        (("safety", "host_opened"), True),
        (("proposal", "evidence"), "not-a-list"),
    ],
)
def test_malformed_projection_fails_closed(path, value):
    serialized = copy.deepcopy(_projection().to_dict())
    target = serialized
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(SurfaceProjectionError):
        SurfaceProjectionV1.from_dict(serialized)


def test_projection_does_not_allow_non_ascii_technical_identity():
    serialized = _projection().to_dict()
    serialized["surface_id"] = "RESOLUME-" + chr(0xF1)

    with pytest.raises(SurfaceProjectionError):
        SurfaceProjectionV1.from_dict(serialized)

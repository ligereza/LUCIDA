import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from resolume_adapter.imago import ImagoError, build_show_session, record_event, record_result


def _session():
    session = build_show_session(
        session_id="show-001",
        name="Fixture show",
        created_at="2026-09-02T20:00:00Z",
    )
    return record_event(session, event_type="show_started", recorded_at="2026-09-02T20:01:00Z")


def test_imago_rejects_event_time_before_last_observation():
    with pytest.raises(ImagoError, match="cannot precede"):
        record_event(_session(), event_type="cue_fired", recorded_at="2026-09-02T20:00:59Z")


def test_imago_rejects_result_time_before_last_observation():
    session = _session()
    proposal_id = session["pending_proposal_ids"][0]

    with pytest.raises(ImagoError, match="cannot precede"):
        record_result(
            session,
            proposal_id=proposal_id,
            result="accepted",
            recorded_at="2026-09-02T20:00:59Z",
        )

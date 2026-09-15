import copy
import json
from pathlib import Path

import pytest

from adapters.vj import VJProjectError, build_stage_event, project_stage_document


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "adapters"
    / "vj"
    / "replay"
    / "fixtures"
    / "plugin-bridges-fictional.json"
)


def _records():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["records"]


def test_build_stage_event_supports_all_three_plugin_documents():
    records = _records()
    instar = build_stage_event("instar", records[0]["data"], event_id="instar-001", sequence=1)
    nayade = build_stage_event(
        "nayade",
        records[1]["data"],
        event_id="nayade-001",
        sequence=2,
        processor_observation=records[1]["processor_observation"],
    )
    imago = build_stage_event("imago", records[2]["data"], event_id="imago-001", sequence=3)

    assert instar["source"] == "INSTAR"
    assert nayade["source"] == "NAYADE"
    assert imago["phase"] == "show"
    assert all("path" not in json.dumps(value) for value in (instar, nayade, imago))


def test_projection_mode_validates_previous_phase_order():
    records = _records()
    first = project_stage_document("instar", records[0]["data"], event_id="instar-001", sequence=1)
    second = project_stage_document(
        "nayade",
        records[1]["data"],
        event_id="nayade-001",
        sequence=2,
        processor_observation=records[1]["processor_observation"],
        previous=first,
    )

    assert first["show_phase"] == "preflight"
    assert second["show_phase"] == "preparation"

    invalid = copy.deepcopy(records[2]["data"])
    invalid["status"] = "closed"
    with pytest.raises(VJProjectError, match="phase transition not allowed"):
        project_stage_document(
            "imago",
            invalid,
            event_id="imago-001",
            sequence=3,
            previous=second,
        )


def test_project_rejects_previous_for_event_mode_at_cli_boundary():
    with pytest.raises(VJProjectError, match="unsupported projection stage"):
        build_stage_event("unknown", {}, event_id="event-001", sequence=1)

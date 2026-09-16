from __future__ import annotations

import json
from pathlib import Path

from lucida.engine import build_overlay_frame
from tests.engine.test_overlay_frame import _plan


SCHEMA = Path(__file__).parents[2] / "lucida" / "engine" / "contracts" / "overlay-frame.schema.json"


def test_overlay_frame_schema_matches_runtime_contract():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    frame = build_overlay_frame(_plan()).to_dict()

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(frame)
    assert schema["properties"]["contract_type"]["const"] == frame["contract_type"]
    assert schema["properties"]["schema_version"]["const"] == frame["schema_version"]
    assert schema["properties"]["transparent"]["const"] is True
    assert schema["properties"]["click_through"]["const"] is True
    assert schema["properties"]["blocking"]["const"] is False
    assert schema["properties"]["elements"]["maxItems"] == 32
    assert schema["properties"]["elements"]["items"]["properties"]["requires_confirmation"]["const"] is True
    assert schema["properties"]["elements"]["items"]["properties"]["reversible"]["const"] is True


def test_overlay_frame_schema_is_ascii():
    assert all(byte < 128 for byte in SCHEMA.read_bytes())

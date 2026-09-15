"""RESOLUME_ADAPTER-side adapter for PhaseChaser rehearsal proposals.

The adapter owns the VJ scene representation: it validates PhaseChaser state,
projects each frame to a bounded Resolume-compatible cue, and stages the
result through RESOLUME_ADAPTER's existing proposal-only semantic replay boundary.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from .replay.semantic_light_field import SEMANTIC_REPLAY_TYPE, replay_semantic_light_field_fixture
from .semantic_light_field import TAPE_SCHEMA


REHEARSAL_SCHEMA = "resolume_adapter:experimental-rehearsal:0.1"
REPLAY_SCHEMA_VERSION = "0.1"
MAX_FIXTURES = 64


class RehearsalBridgeError(ValueError):
    """Raised when a PhaseChaser state is not safe to stage as a VJ proposal."""


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RehearsalBridgeError(f"{field_name} must be non-empty text")
    value = value.strip()
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RehearsalBridgeError(f"{field_name} must be ASCII") from exc
    return value


def _finite(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RehearsalBridgeError(f"{field_name} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise RehearsalBridgeError(f"{field_name} must be finite")
    return result


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RehearsalBridgeError("rehearsal data must be finite JSON") from exc


def sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("ascii")).hexdigest()


def _timestamp(value: Any) -> datetime:
    text = _text(value, "timestamp")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RehearsalBridgeError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise RehearsalBridgeError("timestamp must include a timezone")
    return parsed


def validate_resolume_cue(cue: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the small, proposal-only cue surface consumed by RESOLUME_ADAPTER."""

    if not isinstance(cue, Mapping):
        raise RehearsalBridgeError("resolume cue must be an object")
    required = {"layer", "clip", "opacity", "rotation_degrees", "strobe", "transport", "proposal_only"}
    if set(cue) != required:
        raise RehearsalBridgeError("resolume cue fields are invalid")
    layer = _text(cue["layer"], "cue.layer")
    clip = _text(cue["clip"], "cue.clip")
    opacity = _finite(cue["opacity"], "cue.opacity")
    rotation = _finite(cue["rotation_degrees"], "cue.rotation_degrees")
    if not 0.0 <= opacity <= 1.0:
        raise RehearsalBridgeError("cue.opacity must be between 0 and 1")
    if not 0.0 <= rotation < 360.0:
        raise RehearsalBridgeError("cue.rotation_degrees must be in [0, 360)")
    if not isinstance(cue["strobe"], bool) or not isinstance(cue["proposal_only"], bool):
        raise RehearsalBridgeError("cue boolean fields are invalid")
    if cue["proposal_only"] is not True:
        raise RehearsalBridgeError("cue must remain proposal_only")
    transport = _text(cue["transport"], "cue.transport")
    if transport != "timeline":
        raise RehearsalBridgeError("unsupported cue transport")
    return {
        "layer": layer,
        "clip": clip,
        "opacity": round(opacity, 6),
        "rotation_degrees": round(rotation, 6),
        "strobe": cue["strobe"],
        "transport": transport,
        "proposal_only": True,
    }


def _cue_for_state(state: Mapping[str, Any]) -> dict[str, Any]:
    lights = state["lights"]
    opacity = sum(float(light["intensity"]) for light in lights) / len(lights)
    rotation = sum(float(light["angle_degrees"]) for light in lights) / len(lights)
    rotation %= 360.0
    strobe = any(float(light["pulse"]) >= 0.5 for light in lights)
    return validate_resolume_cue(
        {
            "layer": "phasechaser-main",
            "clip": "synthetic-phasechaser",
            "opacity": opacity,
            "rotation_degrees": rotation,
            "strobe": strobe,
            "transport": "timeline",
            "proposal_only": True,
        }
    )


def _validate_states(states: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(states, Sequence) or isinstance(states, (str, bytes)) or not states:
        raise RehearsalBridgeError("phase states must be a non-empty sequence")
    normalized: list[dict[str, Any]] = []
    previous_sequence = 0
    previous_timestamp: datetime | None = None
    fixture_count: int | None = None
    for index, raw_state in enumerate(states):
        if not isinstance(raw_state, Mapping):
            raise RehearsalBridgeError(f"phase state {index} must be an object")
        sequence = raw_state.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= previous_sequence:
            raise RehearsalBridgeError("phase state sequences must increase strictly")
        timestamp = _timestamp(raw_state.get("timestamp"))
        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise RehearsalBridgeError("phase state timestamps must be ordered")
        timecode = _text(raw_state.get("timecode"), "timecode")
        lights = raw_state.get("lights")
        if not isinstance(lights, list) or not lights:
            raise RehearsalBridgeError(f"phase state {index} lights must be non-empty")
        if len(lights) > MAX_FIXTURES:
            raise RehearsalBridgeError("fixture count exceeds safe rehearsal limit")
        if fixture_count is None:
            fixture_count = len(lights)
        elif len(lights) != fixture_count:
            raise RehearsalBridgeError("fixture count changed within one tape")
        normalized_lights: list[dict[str, Any]] = []
        for light_index, light in enumerate(lights):
            if not isinstance(light, Mapping):
                raise RehearsalBridgeError(f"light {light_index} in state {index} must be an object")
            fixture_id = _text(light.get("fixture_id"), "light.fixture_id")
            angle = _finite(light.get("angle_degrees"), "light.angle_degrees")
            phase = _finite(light.get("phase"), "light.phase")
            intensity = _finite(light.get("intensity"), "light.intensity")
            pulse = _finite(light.get("pulse"), "light.pulse")
            if not 0.0 <= angle < 360.0 or not 0.0 <= phase < 1.0 or not 0.0 <= intensity <= 1.0 or not 0.0 <= pulse <= 1.0:
                raise RehearsalBridgeError(f"light {fixture_id} values are outside safe bounds")
            normalized_lights.append(
                {
                    "fixture_id": fixture_id,
                    "angle_degrees": round(angle, 6),
                    "phase": round(phase, 6),
                    "intensity": round(intensity, 6),
                    "pulse": round(pulse, 6),
                }
            )
        normalized_state = {
            "sequence": sequence,
            "timestamp": timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "timecode": timecode,
            "event_id": _text(raw_state.get("event_id"), "event_id"),
            "signal_state": _text(raw_state.get("signal_state", "present"), "signal_state"),
            "lights": normalized_lights,
        }
        normalized_state["resolume_cue"] = _cue_for_state(normalized_state)
        normalized.append(normalized_state)
        previous_sequence = sequence
        previous_timestamp = timestamp
    return normalized, int(fixture_count or 0)


def build_rehearsal_projection(
    session_id: str,
    phase_states: Sequence[Mapping[str, Any]],
    *,
    source_event_digest: str,
    sample_hz: float = 25.0,
    permissions_revoked: bool = False,
) -> dict[str, Any]:
    """Build a proposal-only RESOLUME_ADAPTER tape and replay report."""

    session_id = _text(session_id, "session_id")
    source_event_digest = _text(source_event_digest, "source_event_digest")
    sample_hz = _finite(sample_hz, "sample_hz")
    if sample_hz <= 0:
        raise RehearsalBridgeError("sample_hz must be > 0")
    states, fixture_count = _validate_states(phase_states)
    if permissions_revoked:
        return {
            "schema": REHEARSAL_SCHEMA,
            "session_id": session_id,
            "status": "BLOCKED",
            "blockers": ["permissions_revoked"],
            "proposal": None,
            "tape": None,
            "resolume_cues": [],
            "safety": {
                "external_side_effects": False,
                "automatic_actions": False,
                "permissions_revoked": True,
            },
        }

    tape = {
        "schema": TAPE_SCHEMA,
        "proposal_only": True,
        "calibration_status": "not_calibrated",
        "sample_hz": round(sample_hz, 6),
        "frames": [
            {
                "proposal_only": True,
                "sequence": state["sequence"],
                "timestamp": state["timestamp"],
                "timecode": state["timecode"],
                "event_id": state["event_id"],
                "signal_state": state["signal_state"],
                "lights": state["lights"],
                "resolume_cue": state["resolume_cue"],
            }
            for state in states
        ],
    }
    tape_digest = sha256_json(tape)
    proposal = {
        "proposal_id": f"proposal-{session_id}-phasechaser-preview",
        "event_id": states[-1]["event_id"],
        "phase": "show",
        "operation": "preview_semantic_light_field",
        "reason": "Preview PhaseChaser light states as reversible Resolume-compatible scene cues.",
        "risk": "medium",
        "requires_explicit_approval": True,
        "reversible": True,
        "execution_mode": "proposal_only",
        "evidence": [
            "consumer:resolume_adapter-vj",
            f"tape_schema:{TAPE_SCHEMA}",
            f"tape_sha256:{tape_digest}",
            f"frame_count:{len(states)}",
            f"fixture_count:{fixture_count}",
            f"source_event_sha256:{source_event_digest}",
        ],
    }
    replay_fixture = {
        "replay_type": SEMANTIC_REPLAY_TYPE,
        "schema_version": REPLAY_SCHEMA_VERSION,
        "session_id": session_id,
        "proposal": proposal,
        "tape": tape,
    }
    replay_report = replay_semantic_light_field_fixture(replay_fixture)
    return {
        "schema": REHEARSAL_SCHEMA,
        "session_id": session_id,
        "status": "PASS",
        "blockers": [],
        "proposal": proposal,
        "tape": tape,
        "tape_sha256": tape_digest,
        "fixture_count": fixture_count,
        "frame_count": len(states),
        "resolume_cues": [state["resolume_cue"] for state in states],
        "replay_fixture": replay_fixture,
        "replay_report": replay_report,
        "safety": {
            "external_side_effects": False,
            "automatic_actions": False,
            "irreversible_actions_executed": False,
            "permissions_revoked": False,
            "proposal_only": True,
            "resolume_opened": False,
            "artnet_emitted": False,
            "osc_emitted": False,
        },
    }


__all__ = [
    "REHEARSAL_SCHEMA",
    "RehearsalBridgeError",
    "build_rehearsal_projection",
    "sha256_json",
    "validate_resolume_cue",
]

"""Proposal-only projections for Resolume Arena and Avolites Titan.

This module consumes the XIO predictive semantic frame.  It intentionally
does not import OSC/HTTP clients or touch a console.  Its output is a reviewable
plan with the native control vocabulary each host can receive after an
operator explicitly approves it.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping


XIO_FRAME_SCHEMA = "xio:predictive-semantic-lighting-frame:0.1"
PROPOSAL_SCHEMA = "resolume_adapter:console-proposals:0.1"
MAX_FIXTURES = 255


class ConsoleProposalError(ValueError):
    """Raised when a semantic frame cannot be projected safely."""


def _finite(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConsoleProposalError(f"{field_name} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise ConsoleProposalError(f"{field_name} must be finite")
    return result


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConsoleProposalError(f"{field_name} must be non-empty text")
    return value.strip()


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ConsoleProposalError("frame must be finite JSON") from exc


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("ascii")).hexdigest()


def _validate_frame(frame: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(frame, Mapping):
        raise ConsoleProposalError("semantic frame must be an object")
    if frame.get("schema") != XIO_FRAME_SCHEMA:
        raise ConsoleProposalError("unsupported XIO semantic frame schema")
    if frame.get("proposal_only") is not True:
        raise ConsoleProposalError("semantic frame must remain proposal_only")
    session_id = _text(frame.get("session_id"), "frame.session_id")
    event_id = _text(frame.get("event_id"), "frame.event_id")
    sequence = frame.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
        raise ConsoleProposalError("frame.sequence must be a positive integer")
    scene = frame.get("scene")
    lights = frame.get("lights")
    if not isinstance(scene, Mapping) or not isinstance(lights, list) or not lights:
        raise ConsoleProposalError("semantic frame scene/lights are invalid")
    if len(lights) > MAX_FIXTURES:
        raise ConsoleProposalError("fixture count exceeds proposal limit")
    normalized_lights: list[dict[str, Any]] = []
    for index, light in enumerate(lights):
        if not isinstance(light, Mapping):
            raise ConsoleProposalError(f"light {index} must be an object")
        fixture_id = _text(light.get("fixture_id"), "light.fixture_id")
        angle = _finite(light.get("angle_degrees"), "light.angle_degrees")
        intensity = _finite(light.get("intensity"), "light.intensity")
        pulse = _finite(light.get("pulse"), "light.pulse")
        phase = _finite(light.get("phase"), "light.phase")
        if not 0.0 <= angle < 360.0 or not 0.0 <= intensity <= 1.0 or not 0.0 <= pulse <= 1.0 or not 0.0 <= phase < 1.0:
            raise ConsoleProposalError(f"light {fixture_id} values are outside safe bounds")
        normalized_lights.append({
            "fixture_id": fixture_id,
            "angle_degrees": round(angle, 6),
            "intensity": round(intensity, 6),
            "pulse": round(pulse, 6),
            "phase": round(phase, 6),
        })
    return {
        "schema": XIO_FRAME_SCHEMA,
        "session_id": session_id,
        "event_id": event_id,
        "sequence": sequence,
        "timecode": _text(frame.get("timecode"), "frame.timecode"),
        "scene": {
            "phase": _finite(scene.get("phase"), "scene.phase"),
            "master_intensity": _finite(scene.get("master_intensity"), "scene.master_intensity"),
            "pulse": _finite(scene.get("pulse"), "scene.pulse"),
        },
        "lights": normalized_lights,
    }


def _scene_summary(frame: Mapping[str, Any]) -> dict[str, Any]:
    lights = frame["lights"]
    opacity = sum(float(item["intensity"]) for item in lights) / len(lights)
    rotation = sum(float(item["angle_degrees"]) for item in lights) / len(lights)
    pulse = max(float(item["pulse"]) for item in lights)
    return {
        "opacity": round(max(0.0, min(1.0, opacity)), 6),
        "rotation_degrees": round(rotation % 360.0, 6),
        "pulse": round(max(0.0, min(1.0, pulse)), 6),
        "phase": round(float(frame["scene"]["phase"]) % 1.0, 6),
    }


def _resolume_projection(frame: Mapping[str, Any], *, layer: int, clip: int) -> dict[str, Any]:
    if isinstance(layer, bool) or not isinstance(layer, int) or layer < 1:
        raise ConsoleProposalError("resolume layer must be a positive integer")
    if isinstance(clip, bool) or not isinstance(clip, int) or clip < 1:
        raise ConsoleProposalError("resolume clip must be a positive integer")
    summary = _scene_summary(frame)
    layer_path = f"/composition/layers/{layer}"
    clip_path = f"{layer_path}/clips/{clip}"
    return {
        "target": "Resolume Arena",
        "transport": "OSC",
        "host": "127.0.0.1",
        "port": 7000,
        "messages": [
            {"address": f"{layer_path}/opacity", "args": [summary["opacity"]]},
            {"address": f"{layer_path}/rotation", "args": [summary["rotation_degrees"]]},
            {"address": f"{clip_path}/transport/position", "args": [summary["phase"]]},
            {"address": f"{clip_path}/connect", "args": [], "when": "pulse >= 0.5"},
        ],
        "mapping": {
            "opacity": "mean fixture intensity",
            "rotation_degrees": "mean fixture angle",
            "transport_position": "global semantic phase",
            "connect": "pulse edge proposal; operator may reject",
        },
        "external_side_effects": False,
    }


def _avolites_projection(frame: Mapping[str, Any], *, playback: int, accuracy: float) -> dict[str, Any]:
    if isinstance(playback, bool) or not isinstance(playback, int) or playback < 1:
        raise ConsoleProposalError("avolites playback must be a positive integer")
    accuracy = _finite(accuracy, "avolites accuracy")
    if accuracy <= 0:
        raise ConsoleProposalError("avolites accuracy must be > 0")
    summary = _scene_summary(frame)
    level = summary["opacity"]
    return {
        "target": "Avolites Titan",
        "transport": "Titan WebAPI proposal",
        "host": "127.0.0.1",
        "port": 4430,
        "actions": [
            {
                "operation": "Playbacks.PlayPlayback",
                "method": "GET",
                "path": "/titan/script/2/Playbacks/PlayPlayback",
                "query": {
                    "handle_userNumber": playback,
                    "level_level": level,
                    "accuracy": accuracy,
                },
                "when": "pulse >= 0.5",
            },
            {
                "operation": "Masters.PlaybackLevel",
                "method": "GET",
                "path": "/titan/script/2/Masters/PlaybackLevel",
                "query": {
                    "oldValue": None,
                    "value": level,
                    "initalise": False,
                },
            },
        ],
        "fixture_intents": [
            {
                "fixture_id": light["fixture_id"],
                "intensity": light["intensity"],
                "angle_degrees": light["angle_degrees"],
                "pulse": light["pulse"],
            }
            for light in frame["lights"]
        ],
        "mapping": {
            "playback_level": "mean fixture intensity",
            "playback_fire": "pulse edge proposal",
            "fixture_intents": "requires Titan patch and explicit fixture mapping",
        },
        "external_side_effects": False,
    }


def build_console_proposals(
    frame: Mapping[str, Any],
    *,
    resolume_layer: int = 1,
    resolume_clip: int = 1,
    avolites_playback: int = 1,
    avolites_accuracy: float = 0.01,
    permissions_revoked: bool = False,
) -> dict[str, Any]:
    """Build reversible Resolume and Titan proposals without contacting hosts."""

    normalized = _validate_frame(frame)
    frame_digest = _sha256(normalized)
    proposal_id = f"proposal-{normalized['session_id']}-frame-{normalized['sequence']:06d}"
    if permissions_revoked:
        return {
            "schema": PROPOSAL_SCHEMA,
            "proposal_id": proposal_id,
            "status": "BLOCKED",
            "blockers": ["permissions_revoked"],
            "targets": {},
            "safety": {
                "proposal_only": True,
                "external_side_effects": False,
                "automatic_actions": False,
                "resolume_opened": False,
                "avolites_contacted": False,
            },
        }
    return {
        "schema": PROPOSAL_SCHEMA,
        "proposal_id": proposal_id,
        "status": "PENDING_APPROVAL",
        "source": {
            "schema": normalized["schema"],
            "frame_sha256": frame_digest,
            "session_id": normalized["session_id"],
            "event_id": normalized["event_id"],
            "sequence": normalized["sequence"],
            "timecode": normalized["timecode"],
        },
        "targets": {
            "resolume": _resolume_projection(normalized, layer=resolume_layer, clip=resolume_clip),
            "avolites": _avolites_projection(normalized, playback=avolites_playback, accuracy=avolites_accuracy),
        },
        "decision": {
            "requires_explicit_approval": True,
            "reversible": True,
            "execution_mode": "proposal_only",
        },
        "safety": {
            "proposal_only": True,
            "external_side_effects": False,
            "automatic_actions": False,
            "resolume_opened": False,
            "avolites_contacted": False,
        },
    }


__all__ = [
    "ConsoleProposalError",
    "PROPOSAL_SCHEMA",
    "XIO_FRAME_SCHEMA",
    "build_console_proposals",
]

"""Planificador seguro de CUES para perfiles INSTAR.

El plan traduce candidatos semánticos a una disposición humana de los slots
de Resolume. No escribe composiciones, no altera el transporte y no dispara
efectos.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .media import ResolumeAdapterError


PLAN_SCHEMA_VERSION = "0.1"
PLAN_TYPE = "InstarResolumeCuePlan"
MAX_SLOTS = 6


def _filename(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "unknown-profile"
    normalized = value.replace("\\", "/").rstrip("/")
    return normalized.rsplit("/", 1)[-1] or "unknown-profile"


def _number(value: Any, *, minimum: float = 0.0) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        return None
    return number


def _profile_suggestions(profile: Mapping[str, Any]) -> tuple[str, str, float | None, list[dict[str, Any]]]:
    profile_id = str(profile.get("profile_id") or _filename((profile.get("source") or {}).get("filename")))
    source = profile.get("source") or {}
    filename = _filename(source.get("filename") or profile_id)
    technical = profile.get("technical") or {}
    video = technical.get("video") or {}
    duration = _number(video.get("duration_seconds"))
    events = profile.get("events") or {}
    suggestions = events.get("cue_suggestions") if isinstance(events, Mapping) else None
    if suggestions is None:
        suggestions = profile.get("cue_suggestions")
    if not isinstance(suggestions, Mapping):
        raise ResolumeAdapterError(f"El perfil {profile_id} no contiene events.cue_suggestions.")
    raw_cues = suggestions.get("cues")
    if not isinstance(raw_cues, list):
        raise ResolumeAdapterError(f"El perfil {profile_id} no contiene una lista de candidatos CUE.")
    candidates: list[dict[str, Any]] = []
    for index, cue in enumerate(raw_cues, start=1):
        if not isinstance(cue, Mapping):
            continue
        role = cue.get("role")
        if role not in {"change", "strobe_window", "loop"}:
            continue
        position = _number(cue.get("position_s"), minimum=0.0)
        if position is None:
            position = _number(cue.get("in_position_s"), minimum=0.0)
        if position is None:
            continue
        end_position = _number(cue.get("end_position_s"), minimum=position)
        if end_position is None:
            end_position = _number(cue.get("out_position_s"), minimum=position)
        if duration is not None and position > duration:
            continue
        candidates.append({
            "candidate_id": str(cue.get("id") or f"cue-{index:03d}"),
            "role": role,
            "style": cue.get("style") if isinstance(cue.get("style"), str) else None,
            "position_s": round(position, 6),
            "position_ms": round(position * 1000.0, 3),
            "end_position_s": round(end_position, 6) if end_position is not None else None,
            "end_position_ms": round(end_position * 1000.0, 3) if end_position is not None else None,
            "confidence": round(max(0.0, min(1.0, _number(cue.get("confidence")) or 0.0)), 6),
            "candidate_requires_review": cue.get("requires_review") is True,
        })
    return profile_id, filename, duration, candidates


def _best(candidates: Sequence[dict[str, Any]], *, role: str, style: str | None = None) -> dict[str, Any] | None:
    filtered = [item for item in candidates if item["role"] == role and (style is None or item.get("style") == style)]
    if not filtered:
        return None
    return sorted(filtered, key=lambda item: (-item["confidence"], item["position_s"], item["candidate_id"]))[0]


def _slot(slot: int, cue_kind: str, candidate: dict[str, Any] | None, *, endpoint: str = "position") -> dict[str, Any]:
    if candidate is None:
        return {
            "slot": slot,
            "status": "empty",
            "cue_kind": cue_kind,
            "candidate_id": None,
            "role": None,
            "position_s": None,
            "position_ms": None,
            "confidence": None,
            "requires_review": True,
            "endpoint": None,
        }
    position_s = candidate["position_s"] if endpoint == "position" else candidate.get("end_position_s")
    position_ms = candidate["position_ms"] if endpoint == "position" else candidate.get("end_position_ms")
    if position_s is None:
        return _slot(slot, cue_kind, None)
    return {
        "slot": slot,
        "status": "assigned",
        "cue_kind": cue_kind,
        "candidate_id": candidate["candidate_id"],
        "role": candidate["role"],
        "position_s": position_s,
        "position_ms": position_ms,
        "confidence": candidate["confidence"],
        "requires_review": True,
        "endpoint": endpoint,
    }


def _plan_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    profile_id, filename, duration, candidates = _profile_suggestions(profile)
    assigned_ids: set[str] = set()
    clean = _best(candidates, role="change", style="clean")
    impact = _best(candidates, role="change", style="impact")
    strobe = _best(candidates, role="strobe_window")
    loop = _best(candidates, role="loop")
    for candidate in (clean, impact, strobe, loop):
        if candidate is not None:
            assigned_ids.add(candidate["candidate_id"])
    slots = [
        _slot(1, "change_clean", clean),
        _slot(2, "change_impact", impact),
        _slot(3, "strobe_start", strobe),
        _slot(4, "loop_in", loop),
        _slot(5, "loop_out", loop, endpoint="end"),
    ]
    remaining = [candidate for candidate in candidates if candidate["candidate_id"] not in assigned_ids]
    remaining.sort(key=lambda item: (-item["confidence"], item["position_s"], item["candidate_id"]))
    slots.append(_slot(6, "additional", remaining[0] if remaining else None))
    assigned_slot_ids = {item["candidate_id"] for item in slots if item["status"] == "assigned"}
    return {
        "profile_id": profile_id,
        "filename": filename,
        "duration_seconds": round(duration, 6) if duration is not None else None,
        "slots": slots,
        "unassigned_candidates": [
            item["candidate_id"] for item in candidates if item["candidate_id"] not in assigned_slot_ids
        ],
        "candidate_count": len(candidates),
        "assigned_slot_count": sum(item["status"] == "assigned" for item in slots),
    }


def build_cue_plan(profiles: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build a deterministic six-slot plan from one or more INSTAR profiles."""

    if isinstance(profiles, Mapping):
        profile_list = [profiles]
    elif isinstance(profiles, Sequence) and not isinstance(profiles, (str, bytes)):
        profile_list = list(profiles)
    else:
        raise ResolumeAdapterError("El plan de CUES necesita uno o más perfiles INSTAR.")
    if not profile_list or any(not isinstance(item, Mapping) for item in profile_list):
        raise ResolumeAdapterError("Cada perfil INSTAR debe ser un objeto JSON.")
    planned = [_plan_profile(profile) for profile in profile_list]
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "plan_type": PLAN_TYPE,
        "read_only_source": True,
        "slot_count": MAX_SLOTS,
        "review_required": True,
        "profiles": planned,
        "statistics": {
            "profiles": len(planned),
            "candidates": sum(item["candidate_count"] for item in planned),
            "assigned_slots": sum(item["assigned_slot_count"] for item in planned),
            "unassigned_candidates": sum(len(item["unassigned_candidates"]) for item in planned),
        },
        "policy": {
            "slot_1": "mejor cambio clean",
            "slot_2": "mejor cambio impact",
            "slot_3": "inicio de ventana strobe",
            "slot_4_slot_5": "extremos in/out del mejor loop; deben tratarse como pareja",
            "slot_6": "mejor candidato restante por confianza",
        },
        "safety": {
            "read_only": True,
            "composition_written": False,
            "transport_changed": False,
            "effects_triggered": False,
            "source_paths_exposed": False,
        },
        "limitations": [
            "El plan no escribe PositionN en el .avc; el operador debe copiar los tiempos después de revisar el clip.",
            "Una ventana loop necesita dos posiciones y no equivale a un único CUE de Resolume.",
            "La detección es heurística: un candidato con alta confianza sigue requiriendo revisión visual y musical.",
        ],
    }


def write_cue_plan(plan: Mapping[str, Any], path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(plan), ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def cue_plan_text_report(plan: Mapping[str, Any]) -> str:
    lines = [
        "RESOLUME_ADAPTER INSTAR - PLAN DE CUES",
        "============================",
        f"Perfiles: {(plan.get('statistics') or {}).get('profiles', 0)}",
        f"Candidatos: {(plan.get('statistics') or {}).get('candidates', 0)}",
        "",
    ]
    for profile in plan.get("profiles") or []:
        lines.append(f"[{profile.get('filename')}]")
        for slot in profile.get("slots") or []:
            if slot.get("status") == "assigned":
                lines.append(
                    f"  Position{slot.get('slot')} {slot.get('cue_kind')}: "
                    f"{slot.get('position_s'):.3f}s ({slot.get('confidence'):.2f}) - revisar"
                )
            else:
                lines.append(f"  Position{slot.get('slot')} {slot.get('cue_kind')}: vacío")
    lines.append("Modo: SOLO PLAN; no se modificó ningún .avc ni se disparó ningún efecto.")
    return "\n".join(lines)


__all__ = ["build_cue_plan", "cue_plan_text_report", "write_cue_plan"]

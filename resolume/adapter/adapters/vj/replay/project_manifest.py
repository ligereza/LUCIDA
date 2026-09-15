"""Replay real stage reports through the safe VJ state machine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..adapter import VJAdapter, VJAdapterError
from ..contracts import VJEvent
from ..contracts.models import ContractError
from ..project import PROJECT_STAGES, VJProjectError, build_stage_event
from .engine import ReplayError


PROJECT_REPLAY_TYPE = "ResolumeAdapterVJProjectReplay"
PROJECT_REPLAY_SCHEMA_VERSION = "0.1"
_REQUIRED_RECORD_FIELDS = {"stage", "event_id", "sequence", "input"}
_OPTIONAL_RECORD_FIELDS = {"processor_observation"}


def load_project_manifest(path: str | Path) -> tuple[dict[str, Any], Path]:
    """Load a manifest and return it with its directory for relative inputs."""

    manifest_path = Path(path).expanduser().resolve()
    if not manifest_path.is_file():
        raise ReplayError(f"No existe el manifest VJ: {manifest_path}")
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReplayError(f"No se pudo leer el manifest VJ: {manifest_path}") from exc
    if not isinstance(value, dict):
        raise ReplayError("El manifest VJ debe ser un objeto JSON.")
    return value, manifest_path.parent


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReplayError(f"{field_name} debe ser texto no vacio.")
    return value.strip()


def _safe_report_path(value: str, *, root: Path, field_name: str) -> Path:
    """Resolve a manifest path without allowing reads outside its package."""

    candidate = Path(value)
    if candidate.is_absolute():
        raise ReplayError(f"{field_name} debe ser una ruta relativa dentro del manifest.")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ReplayError(f"{field_name} no puede salir del directorio del manifest.") from exc
    return resolved


def _records(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if manifest.get("replay_type") != PROJECT_REPLAY_TYPE:
        raise ReplayError("La identidad del manifest VJ no es valida.")
    if manifest.get("schema_version") != PROJECT_REPLAY_SCHEMA_VERSION:
        raise ReplayError("La version del manifest VJ no es valida.")
    _text(manifest.get("session_id"), "session_id")
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        raise ReplayError("El manifest VJ necesita una lista records no vacia.")
    normalized: list[Mapping[str, Any]] = []
    previous_sequence = -1
    for record in records:
        if not isinstance(record, Mapping):
            raise ReplayError("Cada record del manifest VJ debe ser un objeto.")
        fields = set(record)
        if fields - (_REQUIRED_RECORD_FIELDS | _OPTIONAL_RECORD_FIELDS) or not _REQUIRED_RECORD_FIELDS <= fields:
            raise ReplayError("Los campos del record del manifest VJ no son validos.")
        if record["stage"] not in PROJECT_STAGES:
            raise ReplayError(f"Etapa VJ no soportada: {record['stage']}")
        _text(record["event_id"], "event_id")
        sequence = record["sequence"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ReplayError("sequence debe ser un entero no negativo.")
        if sequence <= previous_sequence:
            raise ReplayError("Las secuencias del manifest VJ deben aumentar estrictamente.")
        previous_sequence = sequence
        _text(record["input"], "input")
        if "processor_observation" in record:
            _text(record["processor_observation"], "processor_observation")
        normalized.append(record)
    return normalized


def replay_project_manifest_path(path: str | Path) -> dict[str, Any]:
    """Load and replay one manifest whose report paths are relative to itself."""

    manifest, root = load_project_manifest(path)
    return replay_project_manifest(manifest, root=root)


def replay_project_manifest(
    manifest: Mapping[str, Any],
    *,
    root: str | Path,
) -> dict[str, Any]:
    """Replay stage reports without exposing paths or performing external actions."""

    if not isinstance(manifest, Mapping):
        raise ReplayError("El manifest VJ debe ser un objeto.")
    records = _records(manifest)
    root_path = Path(root).expanduser().resolve()
    session_id = str(manifest["session_id"]).strip()
    adapter = VJAdapter()
    state = adapter.initial_state(session_id, metadata={"manifest_replay": True})
    transitions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for record in records:
        event_id = str(record["event_id"]).strip()
        if event_id in seen_ids:
            raise ReplayError(f"event_id duplicado en manifest VJ: {event_id}")
        seen_ids.add(event_id)
        input_path = _safe_report_path(str(record["input"]), root=root_path, field_name="input")
        try:
            document = json.loads(input_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ReplayError(f"No se pudo leer el reporte VJ: {input_path}") from exc
        if not isinstance(document, Mapping):
            raise ReplayError(f"El reporte VJ debe ser un objeto: {input_path}")

        observation = None
        if "processor_observation" in record:
            observation_path = _safe_report_path(
                str(record["processor_observation"]),
                root=root_path,
                field_name="processor_observation",
            )
            try:
                observation = json.loads(observation_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ReplayError(f"No se pudo leer la observacion VJ: {observation_path}") from exc
            if not isinstance(observation, Mapping):
                raise ReplayError(f"La observacion VJ debe ser un objeto: {observation_path}")

        try:
            event_data = build_stage_event(
                str(record["stage"]),
                document,
                event_id=event_id,
                sequence=record["sequence"],
                processor_observation=observation,
            )
            event = VJEvent.from_dict(event_data)
            state, proposals = adapter.process(event, state)
        except (ContractError, VJAdapterError, VJProjectError, TypeError, KeyError) as exc:
            raise ReplayError(str(exc)) from exc
        transitions.append(
            {
                "stage": record["stage"],
                "event": event.to_dict(),
                "state_after": state.to_dict(),
                "proposals": [proposal.to_dict() for proposal in proposals],
            }
        )

    final_state = state.to_dict()
    complete = (
        final_state["phase"] == "closure"
        and final_state["status"] == "closed"
        and not final_state["open_incidents"]
        and not final_state["pending_proposal_ids"]
    )
    return {
        "replay_type": "ResolumeAdapterVJProjectReplayReport",
        "schema_version": PROJECT_REPLAY_SCHEMA_VERSION,
        "session_id": session_id,
        "status": "PASS" if complete else "REVIEW",
        "record_count": len(records),
        "stage_order": [item["stage"] for item in transitions],
        "phase_order": [item["event"]["phase"] for item in transitions],
        "transitions": transitions,
        "final_state": final_state,
        "safety": {
            "external_side_effects": False,
            "irreversible_actions_executed": False,
            "source_paths_exposed": False,
            "proposal_count": sum(len(item["proposals"]) for item in transitions),
        },
    }


__all__ = [
    "PROJECT_REPLAY_SCHEMA_VERSION",
    "PROJECT_REPLAY_TYPE",
    "load_project_manifest",
    "replay_project_manifest",
    "replay_project_manifest_path",
]

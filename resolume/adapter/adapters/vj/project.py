"""CLI-facing projection helpers for INSTAR, NAYADE, and IMAGO documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .imago_input import ImagoInputError, ImagoInputProjector
from .instar_input import InstarInputError, InstarInputProjector
from .nayade_input import NayadeInputError, NayadeInputProjector
from .show_input import ShowInputError


PROJECT_STAGES = ("instar", "nayade", "imago")


class VJProjectError(ValueError):
    """Raised when a CLI projection document or stage is invalid."""


def load_project_document(path: str | Path) -> dict[str, Any]:
    """Load one JSON document for a stage bridge without executing it."""

    input_path = Path(path).expanduser().resolve()
    if not input_path.is_file():
        raise VJProjectError(f"projection input does not exist: {input_path}")
    try:
        value = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VJProjectError(f"projection input cannot be read: {input_path}") from exc
    if not isinstance(value, dict):
        raise VJProjectError("projection input must be a JSON object.")
    return value


def _projector(stage: str):
    if stage == "instar":
        return InstarInputProjector()
    if stage == "nayade":
        return NayadeInputProjector()
    if stage == "imago":
        return ImagoInputProjector()
    raise VJProjectError(f"unsupported projection stage: {stage}")


def _event(
    stage: str,
    document: Mapping[str, Any],
    *,
    event_id: str,
    sequence: int,
    processor_observation: Mapping[str, Any] | None,
):
    projector = _projector(stage)
    try:
        if stage == "nayade":
            return projector.event(
                document,
                event_id=event_id,
                sequence=sequence,
                processor_observation=processor_observation,
            )
        if processor_observation is not None:
            raise VJProjectError("processor_observation is only supported for the nayade stage.")
        return projector.event(document, event_id=event_id, sequence=sequence)
    except (ShowInputError, InstarInputError, NayadeInputError, ImagoInputError, TypeError) as exc:
        raise VJProjectError(str(exc)) from exc


def build_stage_event(
    stage: str,
    document: Mapping[str, Any],
    *,
    event_id: str,
    sequence: int,
    processor_observation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a canonical event for one stage document."""

    if stage not in PROJECT_STAGES:
        raise VJProjectError(f"unsupported projection stage: {stage}")
    if not isinstance(document, Mapping):
        raise VJProjectError("projection document must be an object.")
    return _event(
        stage,
        document,
        event_id=event_id,
        sequence=sequence,
        processor_observation=processor_observation,
    ).to_dict()


def project_stage_document(
    stage: str,
    document: Mapping[str, Any],
    *,
    event_id: str,
    sequence: int,
    previous: Mapping[str, Any] | None = None,
    processor_observation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the bounded show-input projection for one stage document."""

    if stage not in PROJECT_STAGES:
        raise VJProjectError(f"unsupported projection stage: {stage}")
    if not isinstance(document, Mapping):
        raise VJProjectError("projection document must be an object.")
    projector = _projector(stage)
    try:
        if stage == "nayade":
            projection = projector.project(
                document,
                event_id=event_id,
                sequence=sequence,
                processor_observation=processor_observation,
                previous=previous,
            )
        else:
            if processor_observation is not None:
                raise VJProjectError("processor_observation is only supported for the nayade stage.")
            projection = projector.project(
                document,
                event_id=event_id,
                sequence=sequence,
                previous=previous,
            )
    except (ShowInputError, InstarInputError, NayadeInputError, ImagoInputError, TypeError) as exc:
        raise VJProjectError(str(exc)) from exc
    return projection.to_dict()


__all__ = [
    "PROJECT_STAGES",
    "VJProjectError",
    "build_stage_event",
    "load_project_document",
    "project_stage_document",
]

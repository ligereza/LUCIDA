"""Safe bridge from an INSTAR report to the reusable VJ event contract."""

from __future__ import annotations

from datetime import datetime
import math
import re
from typing import Any, Mapping

from .contracts import VJEvent
from .contracts.models import ContractError
from .show_input import ShowInputError, ShowInputProjection, ShowInputProjector


MAX_REPORT_ITEMS = 100
_ASCII_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]+$")


class InstarInputError(ShowInputError):
    """Raised when an INSTAR report cannot cross the VJ boundary safely."""


def _ascii_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InstarInputError(f"{field_name} must be non-empty ASCII text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise InstarInputError(f"{field_name} must contain ASCII characters only.") from exc
    return text


def _identifier(value: Any, field_name: str) -> str:
    text = _ascii_text(value, field_name)
    if not _ASCII_IDENTIFIER.fullmatch(text):
        raise InstarInputError(f"{field_name} must be a stable identifier.")
    return text


def _timestamp(value: Any) -> str:
    text = _ascii_text(value, "generated_at")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InstarInputError("generated_at must be ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise InstarInputError("generated_at must include a timezone.")
    return text


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InstarInputError(f"{field_name} must be a non-negative integer.")
    return value


def _positive_number(value: Any, field_name: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise InstarInputError(f"{field_name} must be a positive number.")
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError as exc:
            raise InstarInputError(f"{field_name} must be a positive number.") from exc
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
        raise InstarInputError(f"{field_name} must be a positive number.")
    number = float(value)
    return int(number) if number.is_integer() else round(number, 6)


def _optional_status(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    text = _ascii_text(value, field_name)
    if len(text) > 64:
        raise InstarInputError(f"{field_name} is too long.")
    return text


def _item_summary(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    report = item.get("report")
    if report is not None and not isinstance(report, Mapping):
        raise InstarInputError(f"items[{index}].report must be an object.")
    report = report or {}
    clip_profile = report.get("clip_profile")
    if clip_profile is not None and not isinstance(clip_profile, Mapping):
        raise InstarInputError(f"items[{index}].report.clip_profile must be an object.")
    clip_profile = clip_profile or {}

    raw_id = (
        clip_profile.get("profile_id")
        or item.get("asset_id")
        or item.get("id")
        or f"asset-{index + 1:03d}"
    )
    asset_id = _identifier(raw_id, f"items[{index}].asset_id")
    status = _ascii_text(item.get("status", "UNKNOWN"), f"items[{index}].status")
    summary: dict[str, Any] = {
        "asset_id": asset_id,
        "status": status,
    }

    video = report.get("video")
    if video is not None and not isinstance(video, Mapping):
        raise InstarInputError(f"items[{index}].report.video must be an object.")
    video = video or {}
    for source_name, target_name in (
        ("codec", "codec"),
        ("average_fps", "fps"),
        ("width", "width"),
        ("height", "height"),
    ):
        value = video.get(source_name)
        if source_name == "codec":
            normalized = _optional_status(value, f"items[{index}].{target_name}")
        else:
            normalized = _positive_number(value, f"items[{index}].{target_name}")
        if normalized is not None:
            summary[target_name] = normalized

    alpha = report.get("alpha")
    if alpha is not None and not isinstance(alpha, Mapping):
        raise InstarInputError(f"items[{index}].report.alpha must be an object.")
    alpha = alpha or {}
    alpha_status = _optional_status(alpha.get("status"), f"items[{index}].alpha")
    if alpha_status is not None:
        summary["alpha"] = alpha_status

    visual = clip_profile.get("visual")
    if visual is not None and not isinstance(visual, Mapping):
        raise InstarInputError(f"items[{index}].report.clip_profile.visual must be an object.")
    visual = visual or {}
    visual_status = _optional_status(visual.get("status"), f"items[{index}].visual_status")
    if visual_status is not None:
        summary["visual_status"] = visual_status
    loop = visual.get("loop")
    if loop is not None and not isinstance(loop, Mapping):
        raise InstarInputError(f"items[{index}].report.clip_profile.visual.loop must be an object.")
    loop_status = _optional_status((loop or {}).get("status"), f"items[{index}].loop_status")
    if loop_status is not None:
        summary["loop_status"] = loop_status

    events = clip_profile.get("events")
    if events is not None and not isinstance(events, Mapping):
        raise InstarInputError(f"items[{index}].report.clip_profile.events must be an object.")
    cues = (events or {}).get("cue_suggestions") or {}
    if not isinstance(cues, Mapping):
        raise InstarInputError(f"items[{index}].cue_suggestions must be an object.")
    cue_values = cues.get("cues") or []
    if not isinstance(cue_values, (list, tuple)):
        raise InstarInputError(f"items[{index}].cue_suggestions.cues must be a list.")
    summary["cue_count"] = len(cue_values)
    return summary


def _report_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    items = report.get("items")
    if not isinstance(items, (list, tuple)):
        raise InstarInputError("INSTAR report items must be a list.")
    if len(items) > MAX_REPORT_ITEMS:
        raise InstarInputError(f"INSTAR report cannot contain more than {MAX_REPORT_ITEMS} items.")

    summaries = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise InstarInputError(f"items[{index}] must be an object.")
        summaries.append(_item_summary(item, index))
    counts: dict[str, int] = {}
    for item in summaries:
        status = item["status"] or "UNKNOWN"
        counts[status] = counts.get(status, 0) + 1
    return {
        "tool": "INSTAR",
        "report_schema_version": _optional_status(report.get("schema_version"), "schema_version"),
        "overall_status": _optional_status(report.get("overall_status"), "overall_status"),
        "files_found": _non_negative_int(report.get("files_found", len(items)), "files_found"),
        "cache_hits": _non_negative_int(report.get("cache_hits", 0), "cache_hits"),
        "item_status_counts": counts,
        "items": summaries,
    }


def build_instar_event(
    report: Mapping[str, Any],
    *,
    event_id: str,
    sequence: int,
) -> VJEvent:
    """Build one canonical preflight event without retaining report paths."""

    if not isinstance(report, Mapping):
        raise InstarInputError("INSTAR report must be an object.")
    event_id = _identifier(event_id, "event_id")
    sequence = _non_negative_int(sequence, "sequence")
    timestamp = _timestamp(report.get("generated_at"))
    try:
        return VJEvent.from_dict(
            {
                "event_id": event_id,
                "timestamp": timestamp,
                "phase": "preflight",
                "event_type": "instar.preflight.observed",
                "source": "INSTAR",
                "payload": {
                    "sequence": sequence,
                    "transport": "unknown",
                    "provenance": {
                        "source": "INSTAR",
                        "transport": "unknown",
                        "producer": "INSTAR",
                        "protocol": "report",
                    },
                    "report": _report_payload(report),
                },
            }
        )
    except ContractError as exc:
        raise InstarInputError(str(exc)) from exc


class InstarInputProjector:
    """Project an INSTAR report through the existing host-neutral boundary."""

    def __init__(self) -> None:
        self._projector = ShowInputProjector()

    def event(self, report: Mapping[str, Any], *, event_id: str, sequence: int) -> VJEvent:
        return build_instar_event(report, event_id=event_id, sequence=sequence)

    def project(
        self,
        report: Mapping[str, Any],
        *,
        event_id: str,
        sequence: int,
        previous: ShowInputProjection | Mapping[str, Any] | None = None,
    ) -> ShowInputProjection:
        """Return only the bounded projection consumed by a future reducer."""

        return self._projector.project(
            self.event(report, event_id=event_id, sequence=sequence),
            previous,
        )


def project_instar_show_input(
    report: Mapping[str, Any],
    *,
    event_id: str,
    sequence: int,
    previous: ShowInputProjection | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a safe projection for an INSTAR preflight report."""

    return InstarInputProjector().project(
        report,
        event_id=event_id,
        sequence=sequence,
        previous=previous,
    ).to_dict()

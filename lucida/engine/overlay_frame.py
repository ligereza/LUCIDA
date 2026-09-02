"""Host-neutral visual frame derived from a safe LUCIDA RenderPlan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .models import EngineContractError, RenderPlan, _ascii_text, _utc


OVERLAY_FRAME_SCHEMA_VERSION = "0.1"
MAX_FRAME_ELEMENTS = 32
_ITEM_FIELDS = {
    "item_id",
    "kind",
    "title",
    "body",
    "priority",
    "source",
    "expires_at",
    "requires_confirmation",
    "reversible",
}


class OverlayFrameError(ValueError):
    """Raised when a render plan cannot become a safe visual frame."""


def _bounded_ascii(value: Any, field_name: str, maximum: int = 280) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OverlayFrameError(f"{field_name} must be non-empty text")
    text = value.strip()
    if len(text) > maximum:
        raise OverlayFrameError(f"{field_name} exceeds the text bound")
    try:
        text.encode("ascii")
    except UnicodeEncodeError as error:
        raise OverlayFrameError(f"{field_name} must contain ASCII only") from error
    return text


def _validate_item(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise OverlayFrameError(f"items[{index}] must be a mapping")
    if set(item) != _ITEM_FIELDS:
        raise OverlayFrameError(f"items[{index}] has unsupported fields")
    result = {
        "item_id": _bounded_ascii(item["item_id"], f"items[{index}].item_id", 120),
        "kind": _bounded_ascii(item["kind"], f"items[{index}].kind", 80),
        "title": _bounded_ascii(item["title"], f"items[{index}].title"),
        "body": _bounded_ascii(item["body"], f"items[{index}].body"),
        "priority": item["priority"],
        "source": _bounded_ascii(item["source"], f"items[{index}].source", 80),
        "expires_at": _bounded_ascii(item["expires_at"], f"items[{index}].expires_at", 80),
        "requires_confirmation": item["requires_confirmation"],
        "reversible": item["reversible"],
    }
    if isinstance(result["priority"], bool) or not isinstance(result["priority"], int) or not 0 <= result["priority"] <= 100:
        raise OverlayFrameError(f"items[{index}].priority is outside its bound")
    try:
        _utc(result["expires_at"])
    except (TypeError, ValueError) as error:
        raise OverlayFrameError(f"items[{index}].expires_at must be ISO-8601") from error
    if result["requires_confirmation"] is not True or result["reversible"] is not True:
        raise OverlayFrameError(f"items[{index}] must remain confirmation-required and reversible")
    return result


@dataclass(frozen=True)
class OverlayFrame:
    """A bounded visual frame with no host execution semantics."""

    session_id: str
    revision: int
    elements: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()
    transparent: bool = True
    click_through: bool = True
    blocking: bool = False
    automatic_actions: bool = False
    external_side_effects: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "LucidaOverlayFrame",
            "schema_version": OVERLAY_FRAME_SCHEMA_VERSION,
            "surface": "LUCIDA",
            "mode": "read_only",
            "session_id": self.session_id,
            "revision": self.revision,
            "elements": [dict(item) for item in self.elements],
            "warnings": list(self.warnings),
            "transparent": self.transparent,
            "click_through": self.click_through,
            "blocking": self.blocking,
            "safety": {
                "proposal_only": True,
                "automatic_actions": self.automatic_actions,
                "external_side_effects": self.external_side_effects,
            },
        }


def build_overlay_frame(plan: RenderPlan) -> OverlayFrame:
    """Project a reducer plan into a transparent, non-blocking visual frame."""

    if not isinstance(plan, RenderPlan):
        raise OverlayFrameError("plan must be a RenderPlan")
    try:
        session_id = _ascii_text(plan.session_id, "session_id")
    except EngineContractError as error:
        raise OverlayFrameError(str(error)) from error
    if isinstance(plan.revision, bool) or not isinstance(plan.revision, int) or plan.revision < 0:
        raise OverlayFrameError("revision must be a non-negative integer")
    if plan.mode != "read_only":
        raise OverlayFrameError("plan mode must be read_only")
    if plan.automatic_actions is not False or plan.raw_payload_forwarded is not False:
        raise OverlayFrameError("plan safety flags must remain false")
    if not isinstance(plan.items, (tuple, list)) or len(plan.items) > MAX_FRAME_ELEMENTS:
        raise OverlayFrameError("plan items exceed the frame bound")
    if not isinstance(plan.warnings, (tuple, list)):
        raise OverlayFrameError("plan warnings must be a sequence")
    warnings = tuple(_bounded_ascii(item, "warning", 280) for item in plan.warnings)
    elements = tuple(_validate_item(item, index) for index, item in enumerate(plan.items))
    return OverlayFrame(
        session_id=session_id,
        revision=plan.revision,
        elements=elements,
        warnings=warnings,
    )


__all__ = [
    "MAX_FRAME_ELEMENTS",
    "OVERLAY_FRAME_SCHEMA_VERSION",
    "OverlayFrame",
    "OverlayFrameError",
    "build_overlay_frame",
]

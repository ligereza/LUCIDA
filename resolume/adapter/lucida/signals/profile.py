"""Read-only normalization for the shared RESOLUME_ADAPTER signal profile contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
from typing import Any, Mapping


PROFILE_SCHEMA_VERSION = "0.1"
PROFILE_STAGES = frozenset({"INSTAR", "NAYADE", "IMAGO"})
FACT_ORIGINS = frozenset({"declared", "observed", "inferred", "unknown"})
PROCESSOR_CAPABILITIES = frozenset({"yes", "no", "unknown"})
FACT_FIELDS = frozenset({"value", "origin", "confidence", "source"})
EVIDENCE_FIELDS = frozenset({"kind", "status", "detail", "source"})
EVIDENCE_STATUSES = frozenset({"PASS", "WARN", "FAIL", "UNKNOWN"})
SOURCE_FIELDS = frozenset(
    {"resolution", "fps", "color_model", "range", "transfer", "primaries", "bit_depth"}
)
CAPTURE_FIELDS = frozenset({"resolution", "refresh_hz", "format", "lock"})
HOUSE_FIELDS = frozenset({"input", "bus", "destinations", "outputs"})
PROCESSOR_FIELDS = frozenset({"vendor", "model", "read_only", "capabilities"})
RECOMMENDATION_FIELDS = frozenset(
    {"range_transform", "gamma_transform", "deband", "deflicker"}
)
PROFILE_FIELDS = frozenset(
    {
        "schema_version",
        "profile_id",
        "stage",
        "generated_at",
        "source",
        "capture",
        "house",
        "processor",
        "recommendation",
        "evidence",
    }
)
PROFILE_FACT_PATHS = (
    *(f"source.{field}" for field in sorted(SOURCE_FIELDS)),
    *(f"capture.{field}" for field in sorted(CAPTURE_FIELDS)),
    *(f"house.{field}" for field in sorted(HOUSE_FIELDS)),
    "processor.vendor",
    "processor.model",
)


class SignalProfileError(ValueError):
    """Raised when a signal profile is malformed or unsafe to normalize."""


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SignalProfileError(f"{field_name} must be non-empty text.")
    return value.strip()


def _json_copy(value: Any, field_name: str) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise SignalProfileError(f"{field_name} must contain JSON-safe values.") from exc


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SignalProfileError(f"{field_name} must be an object.")
    return dict(value)


def _fields(value: Mapping[str, Any], expected: frozenset[str], field_name: str) -> None:
    if set(value) != expected:
        raise SignalProfileError(f"{field_name} contains unsupported or missing fields.")


def _required_fields(
    value: Mapping[str, Any], required: frozenset[str], allowed: frozenset[str], field_name: str
) -> None:
    keys = set(value)
    if not required.issubset(keys) or not keys.issubset(allowed):
        raise SignalProfileError(f"{field_name} contains unsupported or missing fields.")


def _timestamp(value: Any) -> str:
    text = _text(value, "generated_at")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SignalProfileError("generated_at must be ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise SignalProfileError("generated_at must include a timezone.")
    return text


@dataclass(frozen=True)
class SignalFact:
    """One value with its origin and confidence, never an implicit assertion."""

    value: Any
    origin: str
    confidence: float
    source: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], field_name: str = "fact") -> "SignalFact":
        raw = _mapping(value, field_name)
        _required_fields(raw, frozenset({"value", "origin", "confidence"}), FACT_FIELDS, field_name)
        origin = _text(raw["origin"], f"{field_name}.origin")
        if origin not in FACT_ORIGINS:
            raise SignalProfileError(f"{field_name}.origin is invalid.")
        confidence = raw["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise SignalProfileError(f"{field_name}.confidence must be a number.")
        if not math.isfinite(float(confidence)) or not 0 <= float(confidence) <= 1:
            raise SignalProfileError(f"{field_name}.confidence must be between 0 and 1.")
        if origin == "unknown" and (raw["value"] != "unknown" or float(confidence) != 0):
            raise SignalProfileError(
                f"{field_name} with unknown origin must use value 'unknown' and confidence 0."
            )
        source = raw.get("source")
        if source is not None:
            source = _text(source, f"{field_name}.source")
        return cls(
            value=_json_copy(raw["value"], f"{field_name}.value"),
            origin=origin,
            confidence=float(confidence),
            source=source,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "value": _json_copy(self.value, "fact.value"),
            "origin": self.origin,
            "confidence": self.confidence,
        }
        if self.source is not None:
            result["source"] = self.source
        return result


@dataclass(frozen=True)
class SignalEvidence:
    """A human-readable observation attached to a profile."""

    kind: str
    status: str
    detail: str
    source: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SignalEvidence":
        raw = _mapping(value, "evidence")
        _required_fields(raw, frozenset({"kind", "status", "detail"}), EVIDENCE_FIELDS, "evidence")
        kind = _text(raw["kind"], "evidence.kind")
        status = _text(raw["status"], "evidence.status")
        if status not in EVIDENCE_STATUSES:
            raise SignalProfileError("evidence.status is invalid.")
        source = raw.get("source")
        if source is not None:
            source = _text(source, "evidence.source")
        return cls(
            kind=kind,
            status=status,
            detail=_text(raw["detail"], "evidence.detail"),
            source=source,
        )

    def to_dict(self) -> dict[str, str]:
        result = {"kind": self.kind, "status": self.status, "detail": self.detail}
        if self.source is not None:
            result["source"] = self.source
        return result


def _fact_section(value: Any, fields: frozenset[str], field_name: str) -> dict[str, SignalFact]:
    section = _mapping(value, field_name)
    _fields(section, fields, field_name)
    return {
        field: SignalFact.from_dict(section[field], f"{field_name}.{field}") for field in sorted(fields)
    }


def _fact_section_to_dict(section: Mapping[str, SignalFact]) -> dict[str, dict[str, Any]]:
    return {field: section[field].to_dict() for field in sorted(section)}


@dataclass(frozen=True)
class SignalProfile:
    """Normalized signal facts shared by INSTAR, NAYADE, and IMAGO."""

    profile_id: str
    stage: str
    generated_at: str
    source: dict[str, SignalFact]
    capture: dict[str, SignalFact]
    house: dict[str, SignalFact]
    processor: dict[str, Any]
    recommendation: dict[str, Any]
    evidence: tuple[SignalEvidence, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SignalProfile":
        raw = _mapping(value, "signal_profile")
        _required_fields(raw, PROFILE_FIELDS - {"evidence"}, PROFILE_FIELDS, "signal_profile")
        if raw.get("schema_version") != PROFILE_SCHEMA_VERSION:
            raise SignalProfileError("schema_version is invalid.")
        stage = _text(raw["stage"], "stage")
        if stage not in PROFILE_STAGES:
            raise SignalProfileError("stage is invalid.")

        processor = _mapping(raw["processor"], "processor")
        _required_fields(
            processor,
            frozenset({"vendor", "model", "read_only"}),
            PROCESSOR_FIELDS,
            "processor",
        )
        if not isinstance(processor["read_only"], bool):
            raise SignalProfileError("processor.read_only must be boolean.")
        capabilities = processor.get("capabilities", {})
        if not isinstance(capabilities, Mapping):
            raise SignalProfileError("processor.capabilities must be an object.")
        normalized_capabilities: dict[str, str] = {}
        for name, status in capabilities.items():
            key = _text(name, "processor capability name")
            normalized_status = _text(status, f"processor.capabilities.{key}")
            if normalized_status not in PROCESSOR_CAPABILITIES:
                raise SignalProfileError(f"processor.capabilities.{key} is invalid.")
            normalized_capabilities[key] = normalized_status

        recommendation = _mapping(raw["recommendation"], "recommendation")
        _fields(recommendation, RECOMMENDATION_FIELDS, "recommendation")
        for field_name in ("range_transform", "gamma_transform"):
            _text(recommendation[field_name], f"recommendation.{field_name}")
        for field_name in ("deband", "deflicker"):
            if not isinstance(recommendation[field_name], bool):
                raise SignalProfileError(f"recommendation.{field_name} must be boolean.")

        evidence_value = raw.get("evidence", [])
        if not isinstance(evidence_value, list):
            raise SignalProfileError("evidence must be a list.")
        return cls(
            profile_id=_text(raw["profile_id"], "profile_id"),
            stage=stage,
            generated_at=_timestamp(raw["generated_at"]),
            source=_fact_section(raw["source"], SOURCE_FIELDS, "source"),
            capture=_fact_section(raw["capture"], CAPTURE_FIELDS, "capture"),
            house=_fact_section(raw["house"], HOUSE_FIELDS, "house"),
            processor={
                "vendor": SignalFact.from_dict(processor["vendor"], "processor.vendor"),
                "model": SignalFact.from_dict(processor["model"], "processor.model"),
                "read_only": processor["read_only"],
                "capabilities": dict(sorted(normalized_capabilities.items())),
            },
            recommendation={
                "range_transform": recommendation["range_transform"],
                "gamma_transform": recommendation["gamma_transform"],
                "deband": recommendation["deband"],
                "deflicker": recommendation["deflicker"],
            },
            evidence=tuple(SignalEvidence.from_dict(item) for item in evidence_value),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "stage": self.stage,
            "generated_at": self.generated_at,
            "source": _fact_section_to_dict(self.source),
            "capture": _fact_section_to_dict(self.capture),
            "house": _fact_section_to_dict(self.house),
            "processor": {
                "vendor": self.processor["vendor"].to_dict(),
                "model": self.processor["model"].to_dict(),
                "read_only": self.processor["read_only"],
                "capabilities": dict(self.processor.get("capabilities", {})),
            },
            "recommendation": dict(self.recommendation),
        }
        if self.evidence:
            result["evidence"] = [item.to_dict() for item in self.evidence]
        return result

    def safe_summary(self) -> dict[str, Any]:
        """Return bounded metrics suitable for a read-only capability overlay."""

        facts = [*self.source.values(), *self.capture.values(), *self.house.values()]
        facts.extend((self.processor["vendor"], self.processor["model"]))
        return {
            "profile_status": "valid",
            "profile_stage": self.stage,
            "profile_unknown_count": sum(fact.origin == "unknown" for fact in facts),
            "profile_inferred_count": sum(fact.origin == "inferred" for fact in facts),
            "profile_min_confidence": min(fact.confidence for fact in facts),
            "processor_read_only": self.processor["read_only"],
        }

    def _facts_by_path(self) -> dict[str, SignalFact]:
        facts: dict[str, SignalFact] = {}
        for section_name in ("source", "capture", "house"):
            section = getattr(self, section_name)
            facts.update({f"{section_name}.{field}": fact for field, fact in section.items()})
        facts["processor.vendor"] = self.processor["vendor"]
        facts["processor.model"] = self.processor["model"]
        return facts


def validate_signal_profile(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a detached canonical signal profile mapping."""

    return SignalProfile.from_dict(value).to_dict()


def compare_signal_profiles(
    expected: SignalProfile | Mapping[str, Any], observed: SignalProfile | Mapping[str, Any]
) -> dict[str, Any]:
    """Compare two profiles without returning their raw signal values."""

    expected_profile = (
        expected if isinstance(expected, SignalProfile) else SignalProfile.from_dict(expected)
    )
    observed_profile = (
        observed if isinstance(observed, SignalProfile) else SignalProfile.from_dict(observed)
    )
    expected_facts = expected_profile._facts_by_path()
    observed_facts = observed_profile._facts_by_path()
    changed_fields: list[str] = []
    origin_changes: list[str] = []
    confidence_drops: list[str] = []
    source_changes: list[str] = []
    expected_unknown_count = 0
    observed_unknown_count = 0
    for field_name in PROFILE_FACT_PATHS:
        expected_fact = expected_facts[field_name]
        observed_fact = observed_facts[field_name]
        if expected_fact.value != observed_fact.value:
            changed_fields.append(field_name)
        if expected_fact.origin != observed_fact.origin:
            origin_changes.append(field_name)
        if expected_fact.source != observed_fact.source:
            source_changes.append(field_name)
        if observed_fact.confidence < expected_fact.confidence:
            confidence_drops.append(field_name)
        expected_unknown_count += expected_fact.origin == "unknown"
        observed_unknown_count += observed_fact.origin == "unknown"

    expected_capabilities = expected_profile.processor.get("capabilities", {})
    observed_capabilities = observed_profile.processor.get("capabilities", {})
    processor_capability_changes = [
        f"processor.capabilities.{name}"
        for name in sorted(set(expected_capabilities) | set(observed_capabilities))
        if expected_capabilities.get(name) != observed_capabilities.get(name)
    ]
    recommendation_changed = expected_profile.recommendation != observed_profile.recommendation
    read_only_changed = (
        expected_profile.processor["read_only"] != observed_profile.processor["read_only"]
    )
    stage_changed = expected_profile.stage != observed_profile.stage
    is_changed = bool(
        changed_fields
        or origin_changes
        or source_changes
        or confidence_drops
        or processor_capability_changes
        or recommendation_changed
        or read_only_changed
        or stage_changed
    )
    return {
        "status": "changed" if is_changed else "stable",
        "changed_fields": changed_fields,
        "origin_changes": origin_changes,
        "source_changes": source_changes,
        "confidence_drops": confidence_drops,
        "processor_capability_changes": processor_capability_changes,
        "unknown_delta": observed_unknown_count - expected_unknown_count,
        "recommendation_changed": recommendation_changed,
        "read_only_changed": read_only_changed,
        "stage_changed": stage_changed,
    }


def summarize_signal_profile(value: SignalProfile | Mapping[str, Any]) -> dict[str, Any]:
    """Validate a profile and return only safe metrics for capability state."""

    profile = value if isinstance(value, SignalProfile) else SignalProfile.from_dict(value)
    return profile.safe_summary()

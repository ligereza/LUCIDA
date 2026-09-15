"""Pure, host-agnostic capability facades for the LUCIDA surface."""

from __future__ import annotations

from typing import Any

from adapters.vj.contracts import VJEvent, VJProposal, VJState

from .contracts import CapabilityReport


_PROFILE_CONTEXT_KEY = "_lucida_profile_context"
_PROFILE_STATE_KEYS = frozenset(
    {
        "profile_status",
        "profile_stage",
        "profile_unknown_count",
        "profile_inferred_count",
        "profile_min_confidence",
        "processor_read_only",
        "profile_comparison_status",
        "profile_changed_count",
        "profile_confidence_drop_count",
        "profile_unknown_delta",
        "profile_recommendation_changed",
        "profile_read_only_changed",
        "profile_stage_changed",
        "profile_context_status",
    }
)
_PROFILE_STATUS_VALUES = frozenset({"valid", "invalid"})
_PROFILE_STAGE_VALUES = frozenset({"INSTAR", "NAYADE", "IMAGO"})
_PROFILE_COMPARISON_VALUES = frozenset({"stable", "changed", "invalid"})
_PROFILE_CONTEXT_VALUES = frozenset({"current", "inherited"})
_PROFILE_TEXT_FIELDS = {
    "profile_status",
    "profile_stage",
    "profile_comparison_status",
    "profile_context_status",
}
_PROFILE_NON_NEGATIVE_INT_FIELDS = {
    "profile_unknown_count",
    "profile_inferred_count",
    "profile_changed_count",
    "profile_confidence_drop_count",
}
_PROFILE_BOOLEAN_FIELDS = {
    "processor_read_only",
    "profile_recommendation_changed",
    "profile_read_only_changed",
    "profile_stage_changed",
}


def _bounded_profile_state(value: Any) -> dict[str, Any]:
    """Accept only already-projected profile metrics from session state."""

    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key not in _PROFILE_STATE_KEYS:
            continue
        if key in _PROFILE_TEXT_FIELDS:
            allowed = {
                "profile_status": _PROFILE_STATUS_VALUES,
                "profile_stage": _PROFILE_STAGE_VALUES,
                "profile_comparison_status": _PROFILE_COMPARISON_VALUES,
                "profile_context_status": _PROFILE_CONTEXT_VALUES,
            }[key]
            if isinstance(item, str) and item in allowed:
                result[key] = item
        elif key in _PROFILE_NON_NEGATIVE_INT_FIELDS:
            if isinstance(item, int) and not isinstance(item, bool) and item >= 0:
                result[key] = item
        elif key == "profile_unknown_delta":
            if isinstance(item, int) and not isinstance(item, bool):
                result[key] = item
        elif key == "profile_min_confidence":
            if (
                isinstance(item, (int, float))
                and not isinstance(item, bool)
                and 0 <= float(item) <= 1
            ):
                result[key] = item
        elif key in _PROFILE_BOOLEAN_FIELDS and isinstance(item, bool):
            result[key] = item
    if result.get("profile_status") not in _PROFILE_STATUS_VALUES:
        return {}
    if result["profile_status"] == "valid":
        required_summary = {
            "profile_stage",
            "profile_unknown_count",
            "profile_inferred_count",
            "profile_min_confidence",
            "processor_read_only",
        }
        if not required_summary.issubset(result):
            return {}
    return result


def _profile_state(payload: dict[str, Any]) -> dict[str, Any]:
    """Project optional profile facts into bounded capability metrics."""

    from .signals.profile import SignalProfileError, compare_signal_profiles, summarize_signal_profile

    state: dict[str, Any] = {}
    profile = payload.get("signal_profile")
    if profile is not None:
        try:
            state.update(summarize_signal_profile(profile))
        except SignalProfileError:
            state["profile_status"] = "invalid"
        state["profile_context_status"] = "current"
    baseline = payload.get("baseline_signal_profile")
    if baseline is not None and profile is not None:
        try:
            comparison = compare_signal_profiles(baseline, profile)
        except SignalProfileError:
            state["profile_comparison_status"] = "invalid"
        else:
            affected_fact_paths = {
                *comparison["changed_fields"],
                *comparison["origin_changes"],
                *comparison["source_changes"],
                *comparison["confidence_drops"],
                *comparison["processor_capability_changes"],
            }
            bounded_change_count = len(affected_fact_paths) + sum(
                bool(comparison[field_name])
                for field_name in (
                    "recommendation_changed",
                    "read_only_changed",
                    "stage_changed",
                )
            )
            state.update(
                {
                    "profile_comparison_status": comparison["status"],
                    "profile_changed_count": bounded_change_count,
                    "profile_confidence_drop_count": len(comparison["confidence_drops"]),
                    "profile_unknown_delta": comparison["unknown_delta"],
                    "profile_recommendation_changed": comparison["recommendation_changed"],
                    "profile_read_only_changed": comparison["read_only_changed"],
                    "profile_stage_changed": comparison["stage_changed"],
                }
            )
    return state


def _profile_state_for_event(event: VJEvent, state: VJState, profile_aware: bool) -> dict[str, Any]:
    profile_state = _profile_state(event.payload) if profile_aware else {}
    if profile_aware and not profile_state:
        inherited = _bounded_profile_state(state.metadata.get(_PROFILE_CONTEXT_KEY))
        if inherited:
            inherited["profile_context_status"] = "inherited"
            profile_state = inherited
    return profile_state


class _BaseCapability:
    name = ""
    phases: tuple[str, ...] = ()
    operation = ""
    risk = "low"
    expected = ""
    profile_aware = False

    def supports(self, event: VJEvent) -> bool:
        return event.phase in self.phases

    def evaluate(self, event: VJEvent, state: VJState) -> CapabilityReport:
        if not self.supports(event):
            return CapabilityReport(
                capability=self.name,
                observed=(f"No event directed to {self.name} in this transition.",),
                state={"status": "idle", "last_phase": state.phase},
                expected_results=(),
                unknowns=(f"No evidence for {self.name} is available for this event.",),
            )

        payload = event.payload
        profile_state = _profile_state_for_event(event, state, self.profile_aware)
        proposal = VJProposal(
            proposal_id=f"lucida-{self.name.lower()}-{event.event_id}",
            event_id=event.event_id,
            phase=event.phase,
            operation=self.operation,
            reason=self._reason(event, profile_state),
            risk=self.risk,
            evidence=self._evidence(event, profile_state),
        )
        return CapabilityReport(
            capability=self.name,
            observed=self._observed(event),
            state={
                "status": "observed",
                "phase": event.phase,
                **self._state(payload, profile_state),
            },
            proposals=(proposal,),
            expected_results=(self.expected,),
            unknowns=self._unknowns(),
        )

    def _observed(self, event: VJEvent) -> tuple[str, ...]:
        return (f"{self.name} observed {event.event_type} in phase {event.phase}.",)

    def _reason(self, event: VJEvent, profile_state: dict[str, Any] | None = None) -> str:
        profile_state = profile_state or {}
        if profile_state.get("profile_comparison_status") == "changed":
            changed_count = profile_state.get("profile_changed_count", 0)
            if profile_state.get("profile_context_status") == "inherited":
                return (
                    f"Suggest a {self.name} review because the last soundcheck profile "
                    f"differed from its baseline in {changed_count} bounded field(s); "
                    "no new profile measurement was supplied."
                )
            return (
                f"Suggest a {self.name} review because the signal profile differs "
                f"from its baseline in {changed_count} bounded field(s)."
            )
        return f"Suggest a {self.name} review based on event {event.event_id}."

    def _evidence(
        self, event: VJEvent, profile_state: dict[str, Any] | None = None
    ) -> tuple[str, ...]:
        evidence = ["lucida", self.name.lower(), "offline-observation"]
        profile_state = profile_state or {}
        if profile_state.get("profile_comparison_status") == "changed":
            evidence.append("profile-drift")
            if profile_state.get("profile_context_status") == "inherited":
                evidence.append("profile-context-inherited")
        return tuple(evidence)

    def _state(
        self, payload: dict[str, Any], profile_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {"payload_status": payload.get("status", "unknown")}

    def _unknowns(self) -> tuple[str, ...]:
        return ("The host application and external hardware are not connected in offline mode.",)


class InstarCapability(_BaseCapability):
    """Preflight for media, format, and surface preparation."""

    name = "INSTAR"
    phases = ("preflight",)
    operation = "review-media-and-mapping"
    expected = "El operador confirma medios, proporciones y mapping antes de continuar."

    def _state(
        self, payload: dict[str, Any], profile_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {
            "media_status": payload.get("media_status", payload.get("status", "unknown")),
            "mapping_status": payload.get("mapping_status", "unknown"),
        }


class NayadeCapability(_BaseCapability):
    """Soundcheck for signal, processor, and surface coexistence."""

    name = "NAYADE"
    phases = ("preparation",)
    operation = "review-soundcheck-signal"
    risk = "medium"
    expected = "The operator confirms signal, geometry, and color without writing to the processor."
    profile_aware = True

    def _state(
        self, payload: dict[str, Any], profile_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        state = {
            "signal_status": payload.get("signal_status", payload.get("status", "unknown")),
            "processor_status": payload.get("processor_status", "unknown"),
        }
        state.update(profile_state or {})
        return state


class ImagoCapability(_BaseCapability):
    """Observation of the show, incidents, and live recovery."""

    name = "IMAGO"
    phases = ("show", "incident", "recovery", "closure")
    operation = "review-live-visual-state"
    expected = "El operador confirma la propuesta o registra el resultado observado."
    profile_aware = True

    def _state(
        self, payload: dict[str, Any], profile_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {
            "show_mode": payload.get("mode", "unknown"),
            "incident_category": payload.get("category", "none"),
            **(profile_state or {}),
        }

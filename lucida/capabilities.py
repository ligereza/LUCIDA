"""Pure, host-agnostic capability facades for the LUCIDA surface."""

from __future__ import annotations

from typing import Any

from adapters.vj.contracts import VJEvent, VJProposal, VJState

from .contracts import CapabilityReport


class _BaseCapability:
    name = ""
    phases: tuple[str, ...] = ()
    operation = ""
    risk = "low"
    expected = ""

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
        proposal = VJProposal(
            proposal_id=f"lucida-{self.name.lower()}-{event.event_id}",
            event_id=event.event_id,
            phase=event.phase,
            operation=self.operation,
            reason=self._reason(event),
            risk=self.risk,
            evidence=("lucida", self.name.lower(), "offline-observation"),
        )
        return CapabilityReport(
            capability=self.name,
            observed=self._observed(event),
            state={"status": "observed", "phase": event.phase, **self._state(payload)},
            proposals=(proposal,),
            expected_results=(self.expected,),
            unknowns=self._unknowns(),
        )

    def _observed(self, event: VJEvent) -> tuple[str, ...]:
        return (f"{self.name} observed {event.event_type} in phase {event.phase}.",)

    def _reason(self, event: VJEvent) -> str:
        return f"Suggest a {self.name} review based on event {event.event_id}."

    def _state(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"payload_status": payload.get("status", "unknown")}

    def _unknowns(self) -> tuple[str, ...]:
        return ("The host application and external hardware are not connected in offline mode.",)


class InstarCapability(_BaseCapability):
    """Preflight for media, format, and surface preparation."""

    name = "INSTAR"
    phases = ("preflight",)
    operation = "review-media-and-mapping"
    expected = "El operador confirma medios, proporciones y mapping antes de continuar."

    def _state(self, payload: dict[str, Any]) -> dict[str, Any]:
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

    def _state(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "signal_status": payload.get("signal_status", payload.get("status", "unknown")),
            "processor_status": payload.get("processor_status", "unknown"),
        }


class ImagoCapability(_BaseCapability):
    """Observation of the show, incidents, and live recovery."""

    name = "IMAGO"
    phases = ("show", "incident", "recovery", "closure")
    operation = "review-live-visual-state"
    expected = "El operador confirma la propuesta o registra el resultado observado."

    def _state(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "show_mode": payload.get("mode", "unknown"),
            "incident_category": payload.get("category", "none"),
        }

"""Auditable, deterministic session replay for VJ events and signal envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import json
from typing import Any, Mapping

from adapters.vj.contracts import VJEvent, VJProposal, VJResult

from ..contracts import LUCIDA_SCHEMA_VERSION, LucidaState
from ..orchestrator import LucidaOrchestrator
from ..overlay import build_overlay_view, diff_overlay_view
from ..signals.boundary import OscEnvelope


class SessionReplayError(ValueError):
    """Base error for session replay contract violations."""


class PublicReplayReportError(SessionReplayError):
    """Raised when a public replay report is malformed or unsafe."""


class SequenceGapError(SessionReplayError):
    """Raised when a sequence skips one or more expected values."""


class DuplicateReplayIdError(SessionReplayError):
    """Raised when an event, signal, or sequence is repeated."""


class OutOfOrderReplayError(SessionReplayError):
    """Raised when sequence or timestamps move backwards."""


class EventSignalMismatchError(SessionReplayError):
    """Raised when an event and signal envelope cannot be paired."""


def _ascii_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SessionReplayError(f"{field_name} must be non-empty ASCII text.")
    text = value.strip()
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise SessionReplayError(f"{field_name} must contain ASCII characters only.") from exc
    return text


def _time_value(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _assert_event_technical_fields(event: VJEvent) -> None:
    _ascii_text(event.event_id, "event_id")
    _ascii_text(event.timestamp, "timestamp")
    _ascii_text(event.phase, "phase")
    _ascii_text(event.event_type, "event_type")
    _ascii_text(event.source, "source")


@dataclass(frozen=True)
class SignalEnvelope:
    """Signal provenance paired with one normalized VJ event."""

    envelope_id: str
    event_id: str
    timestamp: str
    sequence: int
    source: str
    address: str
    arguments: tuple[Any, ...] = ()
    transport: str = "osc"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SignalEnvelope":
        if not isinstance(value, Mapping):
            raise SessionReplayError("signal envelope must be an object.")
        osc = OscEnvelope.from_dict(value)
        envelope_id = _ascii_text(value.get("envelope_id"), "envelope_id")
        event_id = _ascii_text(value.get("event_id"), "event_id")
        transport = value.get("transport", "osc")
        if transport not in {"osc", "xio"}:
            raise SessionReplayError("transport must be osc or xio.")
        return cls(
            envelope_id=envelope_id,
            event_id=event_id,
            timestamp=osc.timestamp,
            sequence=osc.sequence,
            source=osc.source,
            address=osc.address,
            arguments=osc.arguments,
            transport=transport,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "SignalEnvelope",
            "schema_version": LUCIDA_SCHEMA_VERSION,
            "envelope_id": self.envelope_id,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "source": self.source,
            "address": self.address,
            "arguments": list(self.arguments),
            "transport": self.transport,
        }


@dataclass(frozen=True)
class SessionReplayRecord:
    """One immutable replay unit with normalized proposals and outcomes."""

    event: VJEvent
    signal: SignalEnvelope
    proposals: tuple[VJProposal, ...]
    results: tuple[VJResult, ...]
    state_after: LucidaState
    audit: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "SessionReplayRecord",
            "schema_version": LUCIDA_SCHEMA_VERSION,
            "event": self.event.to_dict(),
            "signal": self.signal.to_dict(),
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "results": [result.to_dict() for result in self.results],
            "state_after": self.state_after.to_dict(),
            "audit": dict(self.audit),
        }


@dataclass(frozen=True)
class SessionReplayState:
    """Persistable state for a deterministic replay stream."""

    session_id: str
    lucida_state: LucidaState
    next_sequence: int = 1
    last_timestamp: str | None = None
    seen_event_ids: tuple[str, ...] = ()
    seen_envelope_ids: tuple[str, ...] = ()
    seen_sequences: tuple[int, ...] = ()
    records: tuple[SessionReplayRecord, ...] = ()
    audit_log: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": "SessionReplayState",
            "schema_version": LUCIDA_SCHEMA_VERSION,
            "session_id": self.session_id,
            "next_sequence": self.next_sequence,
            "last_timestamp": self.last_timestamp,
            "seen_event_ids": list(self.seen_event_ids),
            "seen_envelope_ids": list(self.seen_envelope_ids),
            "seen_sequences": list(self.seen_sequences),
            "records": [record.to_dict() for record in self.records],
            "audit_log": [dict(item) for item in self.audit_log],
            "lucida_state": self.lucida_state.to_dict(),
            "metadata": dict(self.metadata),
        }


_PUBLIC_EVENT_FIELDS = ("event_id", "timestamp", "phase", "event_type", "source")
_PUBLIC_SIGNAL_FIELDS = ("envelope_id", "event_id", "timestamp", "sequence", "source", "address", "transport")
_PUBLIC_PROPOSAL_FIELDS = (
    "proposal_id",
    "event_id",
    "phase",
    "operation",
    "risk",
    "requires_explicit_approval",
    "reversible",
    "execution_mode",
)
_PUBLIC_AUDIT_FIELDS = (
    "audit_id",
    "event_id",
    "envelope_id",
    "timestamp",
    "sequence",
    "source",
    "event_source",
    "proposal_ids",
    "result_ids",
    "mode",
    "external_side_effects",
    "status",
    "execution_asserted",
)


def _public_event(event: VJEvent) -> dict[str, Any]:
    raw = event.to_dict()
    return {field: raw[field] for field in _PUBLIC_EVENT_FIELDS}


def _public_signal(signal: SignalEnvelope) -> dict[str, Any]:
    raw = signal.to_dict()
    return {field: raw[field] for field in _PUBLIC_SIGNAL_FIELDS}


def _public_proposal(proposal: VJProposal) -> dict[str, Any]:
    raw = proposal.to_dict()
    return {field: raw[field] for field in _PUBLIC_PROPOSAL_FIELDS}


def _public_result(result: VJResult) -> dict[str, Any]:
    return {
        "result_id": result.result_id,
        "proposal_id": result.proposal_id,
        "recorded_at": result.recorded_at,
        "status": result.status,
    }


def _public_audit(entry: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in _PUBLIC_AUDIT_FIELDS:
        value = entry.get(field)
        if field in {"proposal_ids", "result_ids"}:
            if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
                result[field] = list(value)
        elif field == "sequence":
            if isinstance(value, int) and not isinstance(value, bool):
                result[field] = value
        elif field == "external_side_effects":
            if isinstance(value, bool):
                result[field] = value
        elif field == "status":
            if value in {"accepted", "rejected", "unknown"}:
                result[field] = value
        elif field == "execution_asserted":
            if value is False:
                result[field] = value
        elif field == "mode":
            if value == "proposal_only":
                result[field] = value
        elif isinstance(value, str):
            result[field] = value
    return result


def _public_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicReplayReportError(f"{field_name} must be non-empty text.")
    return value


def _public_timestamp(value: Any, field_name: str) -> None:
    text = _public_text(value, field_name)
    try:
        _time_value(text)
    except (TypeError, ValueError) as exc:
        raise PublicReplayReportError(f"{field_name} must be ISO-8601.") from exc


def _public_non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PublicReplayReportError(f"{field_name} must be a non-negative integer.")
    return value


def _validate_public_event(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping) or set(value) != set(_PUBLIC_EVENT_FIELDS):
        raise PublicReplayReportError(f"{field_name} contains unsupported or missing fields.")
    _public_text(value["event_id"], f"{field_name}.event_id")
    _public_timestamp(value["timestamp"], f"{field_name}.timestamp")
    if value["phase"] not in {"preflight", "preparation", "show", "incident", "recovery", "closure"}:
        raise PublicReplayReportError(f"{field_name}.phase is invalid.")
    _public_text(value["event_type"], f"{field_name}.event_type")
    _public_text(value["source"], f"{field_name}.source")


def _validate_public_signal(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping) or set(value) != set(_PUBLIC_SIGNAL_FIELDS):
        raise PublicReplayReportError(f"{field_name} contains unsupported or missing fields.")
    for key in ("envelope_id", "event_id", "source", "address"):
        _public_text(value[key], f"{field_name}.{key}")
    _public_timestamp(value["timestamp"], f"{field_name}.timestamp")
    _public_non_negative_int(value["sequence"], f"{field_name}.sequence")
    if value["transport"] not in {"osc", "xio"}:
        raise PublicReplayReportError(f"{field_name}.transport is invalid.")


def _validate_public_proposal(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping) or set(value) != set(_PUBLIC_PROPOSAL_FIELDS):
        raise PublicReplayReportError(f"{field_name} contains unsupported or missing fields.")
    for key in ("proposal_id", "event_id", "phase", "operation", "risk"):
        _public_text(value[key], f"{field_name}.{key}")
    if value["requires_explicit_approval"] is not True:
        raise PublicReplayReportError(f"{field_name} must require explicit approval.")
    if value["reversible"] is not True:
        raise PublicReplayReportError(f"{field_name} must be reversible.")
    if value["execution_mode"] != "proposal_only":
        raise PublicReplayReportError(f"{field_name}.execution_mode is invalid.")


def _validate_public_result(value: Any, field_name: str) -> None:
    required = {"result_id", "proposal_id", "recorded_at", "status"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise PublicReplayReportError(f"{field_name} contains unsupported or missing fields.")
    _public_text(value["result_id"], f"{field_name}.result_id")
    _public_text(value["proposal_id"], f"{field_name}.proposal_id")
    _public_timestamp(value["recorded_at"], f"{field_name}.recorded_at")
    _public_text(value["status"], f"{field_name}.status")


def _validate_public_audit(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping) or not set(value).issubset(set(_PUBLIC_AUDIT_FIELDS)):
        raise PublicReplayReportError(f"{field_name} contains unsupported fields.")
    for key in ("audit_id", "event_id", "envelope_id", "source", "event_source"):
        if key in value:
            _public_text(value[key], f"{field_name}.{key}")
    if "timestamp" in value:
        _public_timestamp(value["timestamp"], f"{field_name}.timestamp")
    if "sequence" in value:
        _public_non_negative_int(value["sequence"], f"{field_name}.sequence")
    for key in ("proposal_ids", "result_ids"):
        if key in value and (
            not isinstance(value[key], list) or not all(isinstance(item, str) for item in value[key])
        ):
            raise PublicReplayReportError(f"{field_name}.{key} must be a list of strings.")
    if "mode" in value and value["mode"] != "proposal_only":
        raise PublicReplayReportError(f"{field_name}.mode is invalid.")
    if "external_side_effects" in value and value["external_side_effects"] is not False:
        raise PublicReplayReportError(f"{field_name}.external_side_effects must be false.")
    if "status" in value and value["status"] not in {"accepted", "rejected", "unknown"}:
        raise PublicReplayReportError(f"{field_name}.status is invalid.")
    if "execution_asserted" in value and value["execution_asserted"] is not False:
        raise PublicReplayReportError(f"{field_name}.execution_asserted must be false.")


def validate_public_report(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and detach a public replay report without filesystem access."""

    required = {
        "contract_type",
        "schema_version",
        "session_id",
        "status",
        "event_count",
        "signal_count",
        "proposal_count",
        "result_count",
        "phase_order",
        "records",
        "audit_log",
        "safety",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise PublicReplayReportError("public replay report contains unsupported or missing fields.")
    if value["contract_type"] != "LucidaPublicSessionReplayReport" or value["schema_version"] != LUCIDA_SCHEMA_VERSION:
        raise PublicReplayReportError("public replay report identity is invalid.")
    _public_text(value["session_id"], "session_id")
    if value["status"] not in {"PASS", "REVIEW"}:
        raise PublicReplayReportError("status is invalid.")
    event_count = _public_non_negative_int(value["event_count"], "event_count")
    signal_count = _public_non_negative_int(value["signal_count"], "signal_count")
    proposal_count = _public_non_negative_int(value["proposal_count"], "proposal_count")
    result_count = _public_non_negative_int(value["result_count"], "result_count")
    if not isinstance(value["phase_order"], list):
        raise PublicReplayReportError("phase_order must be a list.")
    if not isinstance(value["records"], list):
        raise PublicReplayReportError("records must be a list.")
    if event_count != len(value["records"]) or signal_count != len(value["records"]):
        raise PublicReplayReportError("event and signal counts must match records.")
    phase_order: list[str] = []
    counted_proposals = 0
    counted_results = 0
    known_proposal_ids: set[str] = set()
    previous_timestamp: str | None = None
    previous_sequence: int | None = None
    for index, record in enumerate(value["records"]):
        if not isinstance(record, Mapping) or set(record) != {
            "event", "signal", "proposals", "results", "state_after", "audit"
        }:
            raise PublicReplayReportError(f"records[{index}] contains unsupported or missing fields.")
        _validate_public_event(record["event"], f"records[{index}].event")
        _validate_public_signal(record["signal"], f"records[{index}].signal")
        if record["event"]["event_id"] != record["signal"]["event_id"]:
            raise PublicReplayReportError(f"records[{index}] event and signal ids differ.")
        if record["event"]["timestamp"] != record["signal"]["timestamp"]:
            raise PublicReplayReportError(f"records[{index}] event and signal timestamps differ.")
        if previous_timestamp is not None and _time_value(record["event"]["timestamp"]) < _time_value(previous_timestamp):
            raise PublicReplayReportError("public replay timestamps must be ordered.")
        if previous_sequence is not None and record["signal"]["sequence"] <= previous_sequence:
            raise PublicReplayReportError("public replay sequences must be strictly increasing.")
        if not isinstance(record["proposals"], list):
            raise PublicReplayReportError(f"records[{index}].proposals must be a list.")
        for proposal_index, proposal in enumerate(record["proposals"]):
            _validate_public_proposal(proposal, f"records[{index}].proposals[{proposal_index}]")
            if proposal["event_id"] != record["event"]["event_id"]:
                raise PublicReplayReportError(f"records[{index}] proposal event id differs.")
            known_proposal_ids.add(proposal["proposal_id"])
        if not isinstance(record["results"], list):
            raise PublicReplayReportError(f"records[{index}].results must be a list.")
        for result_index, result in enumerate(record["results"]):
            _validate_public_result(result, f"records[{index}].results[{result_index}]")
            if result["proposal_id"] not in known_proposal_ids:
                raise PublicReplayReportError(f"records[{index}] result references an unknown proposal.")
        try:
            diff_overlay_view(record["state_after"], record["state_after"])
        except ValueError as exc:
            raise PublicReplayReportError(f"records[{index}].state_after is invalid.") from exc
        if record["state_after"]["session_id"] != value["session_id"]:
            raise PublicReplayReportError(f"records[{index}] state session differs.")
        if record["state_after"]["phase"] != record["event"]["phase"]:
            raise PublicReplayReportError(f"records[{index}] state phase differs.")
        _validate_public_audit(record["audit"], f"records[{index}].audit")
        phase_order.append(record["event"]["phase"])
        counted_proposals += len(record["proposals"])
        counted_results += len(record["results"])
        previous_timestamp = record["event"]["timestamp"]
        previous_sequence = record["signal"]["sequence"]
    if value["phase_order"] != phase_order:
        raise PublicReplayReportError("phase_order does not match records.")
    if proposal_count != counted_proposals or result_count != counted_results:
        raise PublicReplayReportError("proposal and result counts do not match records.")
    if not isinstance(value["audit_log"], list):
        raise PublicReplayReportError("audit_log must be a list.")
    for index, audit in enumerate(value["audit_log"]):
        _validate_public_audit(audit, f"audit_log[{index}]")
    safety = value["safety"]
    expected_safety = {
        "replay_only": True,
        "proposal_only": True,
        "external_side_effects": False,
        "raw_payloads_included": False,
        "signal_arguments_included": False,
        "metadata_included": False,
    }
    if safety != expected_safety:
        raise PublicReplayReportError("public replay safety contract is invalid.")
    try:
        return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise PublicReplayReportError("public replay report must be JSON-safe.") from exc


class SessionReplay:
    """Append-only replay that never opens a transport or executes actions."""

    def __init__(
        self,
        session_id: str,
        *,
        first_sequence: int = 1,
        metadata: Mapping[str, Any] | None = None,
        orchestrator: LucidaOrchestrator | None = None,
    ) -> None:
        if isinstance(first_sequence, bool) or not isinstance(first_sequence, int) or first_sequence < 0:
            raise SessionReplayError("first_sequence must be a non-negative integer.")
        self._orchestrator = orchestrator or LucidaOrchestrator()
        lucida_state = self._orchestrator.initial_state(session_id, metadata=metadata)
        self._state = SessionReplayState(
            session_id=lucida_state.session_id,
            lucida_state=lucida_state,
            next_sequence=first_sequence,
            metadata=dict(metadata or {}),
        )

    @property
    def state(self) -> SessionReplayState:
        return self._state

    def append(
        self,
        event: VJEvent | Mapping[str, Any],
        signal: SignalEnvelope | Mapping[str, Any],
        results: tuple[VJResult | Mapping[str, Any], ...] | list[VJResult | Mapping[str, Any]] = (),
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> SessionReplayRecord:
        parsed_event = event if isinstance(event, VJEvent) else VJEvent.from_dict(event)
        parsed_signal = signal if isinstance(signal, SignalEnvelope) else SignalEnvelope.from_dict(signal)
        _assert_event_technical_fields(parsed_event)
        self._validate_pair(parsed_event, parsed_signal)
        self._validate_order(parsed_event, parsed_signal)

        next_lucida_state = self._orchestrator.propose(parsed_event, self._state.lucida_state)
        proposals = tuple(
            proposal for proposal in next_lucida_state.proposals if proposal.event_id == parsed_event.event_id
        )
        if any(
            not proposal.requires_explicit_approval
            or not proposal.reversible
            or proposal.execution_mode != "proposal_only"
            for proposal in proposals
        ):
            raise SessionReplayError("Replay proposals must be explicit, reversible, and proposal_only.")

        parsed_results: list[VJResult] = []
        for raw_result in results:
            result = raw_result if isinstance(raw_result, VJResult) else VJResult.from_dict(raw_result)
            if _time_value(result.recorded_at) < _time_value(parsed_signal.timestamp):
                raise OutOfOrderReplayError(
                    f"Result timestamp precedes signal: {result.result_id}."
                )
            next_lucida_state = self._orchestrator.register_result(next_lucida_state, result)
            parsed_results.append(result)

        audit = {
            "audit_id": f"audit-{parsed_signal.envelope_id}",
            "event_id": parsed_event.event_id,
            "envelope_id": parsed_signal.envelope_id,
            "timestamp": parsed_signal.timestamp,
            "sequence": parsed_signal.sequence,
            "source": parsed_signal.source,
            "event_source": parsed_event.source,
            "metadata": dict(metadata or {}),
            "proposal_ids": [proposal.proposal_id for proposal in proposals],
            "result_ids": [result.result_id for result in parsed_results],
            "mode": "proposal_only",
            "external_side_effects": False,
        }
        record = SessionReplayRecord(
            event=parsed_event,
            signal=parsed_signal,
            proposals=proposals,
            results=tuple(parsed_results),
            state_after=next_lucida_state,
            audit=audit,
        )
        self._state = replace(
            self._state,
            lucida_state=next_lucida_state,
            next_sequence=parsed_signal.sequence + 1,
            last_timestamp=parsed_signal.timestamp,
            seen_event_ids=(*self._state.seen_event_ids, parsed_event.event_id),
            seen_envelope_ids=(*self._state.seen_envelope_ids, parsed_signal.envelope_id),
            seen_sequences=(*self._state.seen_sequences, parsed_signal.sequence),
            records=(*self._state.records, record),
            audit_log=(*self._state.audit_log, audit),
        )
        return record

    def report(self) -> dict[str, Any]:
        final_state = self._state.to_dict()
        active_capabilities = sorted(
            {
                report.capability
                for record in self._state.records
                for report in record.state_after.capabilities
                if report.proposals
            }
        )
        complete = (
            final_state["lucida_state"]["vj_state"]["phase"] == "closure"
            and final_state["lucida_state"]["vj_state"]["status"] == "closed"
            and not final_state["lucida_state"]["pending_proposal_ids"]
            and active_capabilities == ["IMAGO", "INSTAR", "NAYADE"]
        )
        return {
            "contract_type": "LucidaSessionReplayReport",
            "schema_version": LUCIDA_SCHEMA_VERSION,
            "session_id": self._state.session_id,
            "status": "PASS" if complete else "REVIEW",
            "event_count": len(self._state.records),
            "signal_count": len(self._state.records),
            "proposal_count": sum(len(record.proposals) for record in self._state.records),
            "result_count": sum(len(record.results) for record in self._state.records),
            "capabilities_observed": active_capabilities,
            "records": [record.to_dict() for record in self._state.records],
            "audit_log": [dict(item) for item in self._state.audit_log],
            "final_state": final_state,
            "safety": {
                "replay_only": True,
                "proposal_only": True,
                "sockets_opened": False,
                "resolume_opened": False,
                "external_side_effects": False,
            },
        }

    def public_report(self) -> dict[str, Any]:
        """Return a shareable replay view without raw event or signal payloads."""

        internal = self.report()
        records = [
            {
                "event": _public_event(record.event),
                "signal": _public_signal(record.signal),
                "proposals": [_public_proposal(item) for item in record.proposals],
                "results": [_public_result(item) for item in record.results],
                "state_after": build_overlay_view(record.state_after),
                "audit": _public_audit(record.audit),
            }
            for record in self._state.records
        ]
        return validate_public_report(
            {
                "contract_type": "LucidaPublicSessionReplayReport",
                "schema_version": LUCIDA_SCHEMA_VERSION,
                "session_id": self._state.session_id,
                "status": internal["status"],
                "event_count": len(records),
                "signal_count": len(records),
                "proposal_count": sum(len(record.proposals) for record in self._state.records),
                "result_count": sum(len(record.results) for record in self._state.records),
                "phase_order": [record.event.phase for record in self._state.records],
                "records": records,
                "audit_log": [_public_audit(entry) for entry in self._state.audit_log],
                "safety": {
                    "replay_only": True,
                    "proposal_only": True,
                    "external_side_effects": False,
                    "raw_payloads_included": False,
                    "signal_arguments_included": False,
                    "metadata_included": False,
                },
            }
        )

    def record_audit(self, entry: Mapping[str, Any]) -> None:
        """Append an external receipt without changing replay proposals or state."""

        if not isinstance(entry, Mapping):
            raise SessionReplayError("Audit entry must be an object.")
        audit_entry = dict(entry)
        audit_entry.setdefault("mode", "proposal_only")
        audit_entry.setdefault("external_side_effects", False)
        self._state = replace(
            self._state,
            audit_log=(*self._state.audit_log, audit_entry),
        )

    def _validate_pair(self, event: VJEvent, signal: SignalEnvelope) -> None:
        if event.event_id != signal.event_id:
            raise EventSignalMismatchError(
                f"Event and signal ids differ: {event.event_id} != {signal.event_id}."
            )
        if event.timestamp != signal.timestamp:
            raise EventSignalMismatchError(
                f"Event and signal timestamps differ: {event.event_id}."
            )
        if event.event_id in self._state.seen_event_ids:
            raise DuplicateReplayIdError(f"Duplicate event_id: {event.event_id}.")
        if signal.envelope_id in self._state.seen_envelope_ids:
            raise DuplicateReplayIdError(f"Duplicate envelope_id: {signal.envelope_id}.")
        if signal.sequence in self._state.seen_sequences:
            raise DuplicateReplayIdError(f"Duplicate sequence: {signal.sequence}.")

    def _validate_order(self, event: VJEvent, signal: SignalEnvelope) -> None:
        if signal.sequence > self._state.next_sequence:
            raise SequenceGapError(
                f"Sequence gap: expected {self._state.next_sequence}, got {signal.sequence}."
            )
        if signal.sequence < self._state.next_sequence:
            raise OutOfOrderReplayError(
                f"Sequence out of order: expected {self._state.next_sequence}, got {signal.sequence}."
            )
        if self._state.last_timestamp is not None and _time_value(event.timestamp) < _time_value(
            self._state.last_timestamp
        ):
            raise OutOfOrderReplayError(f"Timestamp out of order: {event.event_id}.")


def _replay_from_fixture(fixture: Mapping[str, Any]) -> SessionReplay:
    if not isinstance(fixture, Mapping):
        raise SessionReplayError("Session replay fixture must be an object.")
    session_id = fixture.get("session_id")
    entries = fixture.get("entries")
    if not isinstance(session_id, str) or not session_id.strip():
        raise SessionReplayError("Session replay fixture needs session_id.")
    if not isinstance(entries, list) or not entries:
        raise SessionReplayError("Session replay fixture needs non-empty entries.")

    replay = SessionReplay(session_id, metadata={"fixture": True})
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise SessionReplayError("Each replay entry must be an object.")
        raw_event = entry.get("event")
        raw_signal = entry.get("signal")
        raw_results = entry.get("results", [])
        if not isinstance(raw_event, Mapping) or not isinstance(raw_signal, Mapping):
            raise SessionReplayError("Each replay entry needs event and signal.")
        if not isinstance(raw_results, list):
            raise SessionReplayError("Replay entry results must be a list.")
        replay.append(raw_event, raw_signal, tuple(raw_results))
    return replay


def replay_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Build the complete internal report for a replay fixture."""

    return _replay_from_fixture(fixture).report()


def public_replay_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Build the redacted shareable report for a replay fixture."""

    return _replay_from_fixture(fixture).public_report()

"""Small dependency-free client for the LUCIDA Adobe signal bridge."""

from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
from typing import Any, Mapping


SOURCES = frozenset({"xio", "vizz", "pupila"})
EVENT_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)+$")
METADATA_ALIASES = {
    "signal_percent": "signalPercent",
    "wifi_signal_percent": "signalPercent",
    "loss_percent": "lossPercent",
    "gateway_loss_percent": "lossPercent",
    "receive_mbps": "receiveMbps",
    "wifi_receive_mbps": "receiveMbps",
    "transmit_mbps": "transmitMbps",
    "wifi_transmit_mbps": "transmitMbps",
    "cell_rat": "radioType",
    "cell_channel": "cellChannel",
    "transport_type": "transport",
    "focus_score": "focusScore",
    "attention_score": "attentionScore",
    "participant_count": "participantCount",
    "source_version": "sourceVersion",
}
ALLOWED_METADATA = frozenset({
    "app", "host", "channel", "action", "state", "phase", "region", "mode", "status", "workflow",
    "eventClass", "intent", "kind", "target", "revision", "count", "participantCount", "confidence",
    "focusScore", "attentionScore", "latencyMs", "pointerMode", "sourceVersion", "transport", "protocol",
    "signalPercent", "lossPercent", "receiveMbps", "transmitMbps", "radioType", "cellChannel",
})
FORBIDDEN_KEYS = frozenset({
    "command", "content", "data", "executable", "file", "frame", "html", "image", "key", "keys",
    "path", "payload", "process", "raw", "script", "shell", "text", "url",
})


class SignalPublisherError(RuntimeError):
    """Raised when a signal cannot be normalized or published."""


def _ascii(value: Any, limit: int = 160) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9._:/ -]+", "", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _token(value: Any, fallback: str = "") -> str:
    text = _ascii(value, 120).lower().replace(" ", "-")
    return text or fallback


def _source(value: Any) -> str:
    source = _token(value)
    if source not in SOURCES:
        raise SignalPublisherError(f"Unsupported signal source: {source or 'missing'}")
    return source


def _event_type(value: Any) -> str:
    event_type = _token(str(value or "").lstrip("/").replace("/", "."))
    if not EVENT_PATTERN.fullmatch(event_type):
        raise SignalPublisherError("Signal event type is invalid")
    return event_type


def _bounded_number(key: str, value: Any) -> int | float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not (number == number and abs(number) != float("inf")):
        return None
    if key in {"confidence", "focusScore", "attentionScore"}:
        return round(max(0.0, min(1.0, number)), 4)
    if key in {"signalPercent", "lossPercent"}:
        return round(max(0.0, min(100.0, number)), 2)
    if key in {"count", "participantCount", "revision"}:
        return max(0, min(100000, round(number)))
    if key in {"receiveMbps", "transmitMbps"}:
        return round(max(0.0, min(100000.0, number)), 2)
    if key == "latencyMs":
        return round(max(0.0, min(600000.0, number)), 2)
    return round(number, 4)


def sanitize_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep only the shared metadata vocabulary; raw fields never enter the request."""
    result: dict[str, Any] = {}
    for raw_key, raw_value in (metadata or {}).items():
        original_key = str(raw_key)
        key = METADATA_ALIASES.get(original_key, original_key)
        if key not in ALLOWED_METADATA or key in result:
            continue
        if isinstance(raw_value, bool):
            value: Any = raw_value
        elif isinstance(raw_value, (int, float)):
            value = _bounded_number(key, raw_value)
        elif isinstance(raw_value, str):
            value = _ascii(raw_value)
        else:
            value = None
        if value is not None and value != "":
            result[key] = value
        if len(result) >= 20:
            break
    return result


def sanitize_proposal(proposal: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not proposal:
        return None
    result: dict[str, Any] = {}
    for key in ("proposalId", "kind", "title", "reason", "target", "expiresAt"):
        if key not in proposal:
            continue
        value = _token(proposal[key]) if key in {"kind", "target"} else _ascii(proposal[key], 400 if key == "reason" else 180)
        if value:
            result[key] = value
    if "reversible" in proposal:
        result["reversible"] = proposal["reversible"] is not False
    return result or None


class SignalPublisher:
    """Publish summary-only signals to a local LUCIDA Adobe bridge."""

    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 1.5):
        self.base_url = (base_url or os.getenv("LUCIDA_ADOBE_URL") or "http://127.0.0.1:47921").rstrip("/")
        self.token = token if token is not None else os.getenv("LUCIDA_ADOBE_TOKEN", "")
        self.timeout = timeout

    def publish_event(
        self,
        source: str,
        session_id: str,
        event_type: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        sequence: int | None = None,
        signal_id: str | None = None,
        timestamp: str | None = None,
        proposal: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        envelope: dict[str, Any] = {
            "schemaVersion": 1,
            "source": _source(source),
            "sessionId": _ascii(session_id, 120),
            "eventType": _event_type(event_type),
            "metadata": sanitize_metadata(metadata),
        }
        if not envelope["sessionId"]:
            raise SignalPublisherError("Signal session id is missing")
        if sequence is not None:
            envelope["sequence"] = int(sequence)
        if signal_id:
            envelope["signalId"] = _ascii(signal_id, 160)
        if timestamp:
            envelope["timestamp"] = _ascii(timestamp, 80)
        safe_proposal = sanitize_proposal(proposal)
        if safe_proposal:
            envelope["proposal"] = safe_proposal
        return self.publish(envelope)

    def publish(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        input_envelope = dict(envelope)
        safe_envelope: dict[str, Any] = {
            "schemaVersion": 1,
            "source": _source(input_envelope.get("source") or input_envelope.get("producer")),
            "sessionId": _ascii(input_envelope.get("sessionId") or input_envelope.get("session_id"), 120),
            "eventType": _event_type(
                input_envelope.get("eventType")
                or input_envelope.get("event_type")
                or input_envelope.get("event")
                or input_envelope.get("type")
            ),
            "metadata": sanitize_metadata(input_envelope.get("metadata") or input_envelope.get("meta")),
        }
        if not safe_envelope["sessionId"]:
            raise SignalPublisherError("Signal session id is missing")
        if input_envelope.get("sequence") is not None:
            safe_envelope["sequence"] = int(input_envelope["sequence"])
        signal_id = input_envelope.get("signalId") or input_envelope.get("signal_id")
        if signal_id:
            safe_envelope["signalId"] = _ascii(signal_id, 160)
        timestamp = input_envelope.get("timestamp") or input_envelope.get("timestamp_utc")
        if timestamp:
            safe_envelope["timestamp"] = _ascii(timestamp, 80)
        safe_proposal = sanitize_proposal(input_envelope.get("proposal"))
        if safe_proposal:
            safe_envelope["proposal"] = safe_proposal
        body = json.dumps(safe_envelope, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(f"{self.base_url}/signals", data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                value = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:400]
            raise SignalPublisherError(f"Signal bridge HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise SignalPublisherError(f"Signal bridge unavailable: {error.reason}") from error
        try:
            return json.loads(value) if value else {}
        except json.JSONDecodeError as error:
            raise SignalPublisherError("Signal bridge returned invalid JSON") from error


def publish_event(source: str, session_id: str, event_type: str, **kwargs: Any) -> dict[str, Any]:
    return SignalPublisher().publish_event(source, session_id, event_type, **kwargs)

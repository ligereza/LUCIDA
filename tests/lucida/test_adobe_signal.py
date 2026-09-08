import json

import pytest

from lucida.signals.adobe import (
    ADOBE_SOURCE_FIXTURES,
    DEFAULT_ADOBE_FIXTURE,
    AdobeSignalConsumer,
    AdobeSignalError,
    parse_adobe_signal,
)


FIXTURE = DEFAULT_ADOBE_FIXTURE


def _signal():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_adobe_summary_enters_lucida_replay_without_host_execution():
    consumer = AdobeSignalConsumer("fictional-adobe-session", first_sequence=0)
    result = consumer.consume(_signal())

    assert result.event.phase == "preflight"
    assert result.event.source == "adobe:vizz"
    assert result.envelope.transport == "adobe"
    assert result.record.audit["mode"] == "proposal_only"
    assert result.record.audit["external_side_effects"] is False
    assert consumer.report()["source_app"] == "ADOBE"


def test_adobe_summary_round_trips_and_preserves_redaction_boundary():
    signal = parse_adobe_signal(_signal())
    serialized = signal.to_dict()

    assert serialized["redaction"] == {"rawContentForwarded": False}
    assert serialized["metadata"]["attentionScore"] == 0.75
    assert "content" not in serialized["metadata"]


def test_adobe_signal_rejects_raw_metadata():
    signal = _signal()
    signal["metadata"]["content"] = "fictional raw content"

    with pytest.raises(AdobeSignalError, match="metadata key is not allowed"):
        parse_adobe_signal(signal)


def test_adobe_signal_requires_explicit_phase():
    signal = _signal()
    del signal["metadata"]["phase"]
    consumer = AdobeSignalConsumer("fictional-adobe-session", first_sequence=0)

    with pytest.raises(AdobeSignalError, match="metadata.phase"):
        consumer.consume(signal)


@pytest.mark.parametrize("source", sorted(ADOBE_SOURCE_FIXTURES))
def test_each_adobe_source_family_replays_as_a_safe_summary(source):
    fixture = json.loads(ADOBE_SOURCE_FIXTURES[source].read_text(encoding="utf-8"))
    consumer = AdobeSignalConsumer(fixture["sessionId"], first_sequence=fixture["sequence"])

    result = consumer.consume(fixture)

    assert result.signal.source == source
    assert result.signal.to_dict()["redaction"]["rawContentForwarded"] is False
    assert result.record.audit["external_side_effects"] is False

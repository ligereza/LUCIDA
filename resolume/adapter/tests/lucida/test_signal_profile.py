import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from lucida import LucidaOrchestrator
from lucida.replay.session import SessionReplay
from lucida.signals import (
    SignalFact,
    SignalProfileError,
    compare_signal_profiles,
    validate_signal_profile,
)


def _fact(value, origin="observed", confidence=0.9):
    return {"value": value, "origin": origin, "confidence": confidence, "source": "test"}


def _profile():
    return {
        "schema_version": "0.1",
        "profile_id": "profile-001",
        "stage": "NAYADE",
        "generated_at": "2026-01-10T20:00:00Z",
        "source": {
            "resolution": _fact("1920x1080"),
            "fps": _fact(60),
            "color_model": _fact("RGB"),
            "range": _fact("full", "declared", 1.0),
            "transfer": _fact("sRGB"),
            "primaries": _fact("BT.709"),
            "bit_depth": _fact(8),
        },
        "capture": {
            "resolution": _fact("1920x1080"),
            "refresh_hz": _fact(60),
            "format": _fact("RGB8"),
            "lock": _fact(True),
        },
        "house": {
            "input": _fact("HDMI-1", "declared", 0.7),
            "bus": _fact("main"),
            "destinations": _fact(["LED-A"]),
            "outputs": _fact(["screen-1"]),
        },
        "processor": {
            "vendor": _fact("unknown", "unknown", 0.0),
            "model": _fact("unknown", "unknown", 0.0),
            "read_only": True,
            "capabilities": {"supports_read_only_query": "unknown"},
        },
        "recommendation": {
            "range_transform": "identity",
            "gamma_transform": "identity",
            "deband": False,
            "deflicker": False,
        },
        "evidence": [{"kind": "capture-lock", "status": "PASS", "detail": "Signal locked."}],
    }


def test_signal_profile_roundtrip_is_canonical_and_detached():
    profile = _profile()

    validated = validate_signal_profile(profile)

    assert validated == profile
    assert validated is not profile
    assert validated["source"] is not profile["source"]
    profile["source"]["fps"]["value"] = 30
    assert validated["source"]["fps"]["value"] == 60


def test_signal_profile_omits_optional_empty_evidence_and_sorts_capabilities():
    profile = _profile()
    profile.pop("evidence")
    profile["processor"]["capabilities"] = {"zeta": "no", "alpha": "yes"}

    validated = validate_signal_profile(profile)

    assert "evidence" not in validated
    assert list(validated["processor"]["capabilities"]) == ["alpha", "zeta"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("source", "fps", "confidence"), 1.1),
        (("source", "fps", "origin"), "guessed"),
        (("processor", "capabilities", "query"), "maybe"),
        (("recommendation", "deflicker"), "no"),
    ],
)
def test_signal_profile_rejects_invalid_facts_and_recommendations(path, value):
    profile = copy.deepcopy(_profile())
    target = profile
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(SignalProfileError):
        validate_signal_profile(profile)


def test_signal_profile_rejects_unknown_fields_and_timezone_free_timestamp():
    profile = _profile()
    profile["unexpected"] = True
    with pytest.raises(SignalProfileError, match="unsupported or missing"):
        validate_signal_profile(profile)

    profile = _profile()
    profile["generated_at"] = "2026-01-10T20:00:00"
    with pytest.raises(SignalProfileError, match="timezone"):
        validate_signal_profile(profile)


def test_signal_fact_requires_canonical_unknown_semantics_but_keeps_inferred_source_optional():
    canonical = {
        "value": "unknown",
        "origin": "unknown",
        "confidence": 0,
    }
    assert SignalFact.from_dict(canonical).to_dict() == canonical

    for malformed in (
        {"value": "HDMI-1", "origin": "unknown", "confidence": 0},
        {"value": "unknown", "origin": "unknown", "confidence": 0.2},
    ):
        with pytest.raises(SignalProfileError, match="unknown origin"):
            SignalFact.from_dict(malformed)

    inferred = SignalFact.from_dict(
        {"value": "RGB", "origin": "inferred", "confidence": 0.6}
    )
    assert inferred.source is None


def test_signal_profile_matches_public_schema():
    schema_path = Path(__file__).parents[2] / "schemas" / "signal-profile.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    instance = validate_signal_profile(_profile())

    errors = list(Draft202012Validator(schema).iter_errors(instance))

    assert errors == []


def test_nayade_projects_only_safe_signal_profile_metrics():
    state = LucidaOrchestrator().initial_state("session-001")
    state = LucidaOrchestrator().propose(
        {
            "event_id": "evt-soundcheck",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preparation",
            "event_type": "soundcheck.profile",
            "payload": {
                "signal_status": "stable",
                "processor_status": "observed",
                "signal_profile": _profile(),
            },
        },
        state,
    )

    overlay = LucidaOrchestrator().read_overlay(state)
    nayade = next(item for item in overlay["capabilities"] if item["capability"] == "NAYADE")

    assert nayade["state"]["profile_status"] == "valid"
    assert nayade["state"]["profile_stage"] == "NAYADE"
    assert nayade["state"]["profile_unknown_count"] == 2
    assert nayade["state"]["profile_inferred_count"] == 0
    assert nayade["state"]["profile_min_confidence"] == 0.0
    assert nayade["state"]["processor_read_only"] is True
    assert "1920x1080" not in json.dumps(overlay)


def test_nayade_marks_malformed_signal_profile_without_failing_the_event():
    profile = _profile()
    del profile["source"]["fps"]
    state = LucidaOrchestrator().initial_state("session-001")
    state = LucidaOrchestrator().propose(
        {
            "event_id": "evt-invalid-profile",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preparation",
            "event_type": "soundcheck.profile",
            "payload": {"signal_profile": profile},
        },
        state,
    )

    overlay = LucidaOrchestrator().read_overlay(state)
    nayade = next(item for item in overlay["capabilities"] if item["capability"] == "NAYADE")

    assert nayade["state"]["profile_status"] == "invalid"


def test_compare_signal_profiles_reports_drift_without_raw_values():
    expected = _profile()
    observed = copy.deepcopy(expected)
    observed["source"]["range"]["value"] = "limited"
    observed["source"]["range"]["confidence"] = 0.4
    observed["house"]["input"]["origin"] = "unknown"
    observed["house"]["input"]["value"] = "unknown"
    observed["house"]["input"]["confidence"] = 0

    comparison = compare_signal_profiles(expected, observed)

    assert comparison["status"] == "changed"
    assert comparison["changed_fields"] == ["source.range", "house.input"]
    assert comparison["confidence_drops"] == ["source.range", "house.input"]
    assert comparison["origin_changes"] == ["house.input"]
    assert comparison["source_changes"] == []
    assert comparison["processor_capability_changes"] == []
    assert comparison["unknown_delta"] == 1
    assert "limited" not in json.dumps(comparison)


def test_compare_signal_profiles_detects_provenance_and_processor_capability_changes():
    expected = _profile()
    observed = copy.deepcopy(expected)
    observed["source"]["range"]["source"] = "capture-output"
    observed["processor"]["capabilities"]["supports_read_only_query"] = "yes"
    observed["processor"]["capabilities"]["new_capability"] = "unknown"

    comparison = compare_signal_profiles(expected, observed)

    assert comparison["status"] == "changed"
    assert comparison["changed_fields"] == []
    assert comparison["source_changes"] == ["source.range"]
    assert comparison["processor_capability_changes"] == [
        "processor.capabilities.new_capability",
        "processor.capabilities.supports_read_only_query",
    ]
    assert "capture-output" not in json.dumps(comparison)


def test_profile_drift_count_includes_non_value_changes():
    expected = _profile()
    observed = copy.deepcopy(expected)
    observed["stage"] = "IMAGO"
    observed["recommendation"]["deflicker"] = True
    observed["processor"]["read_only"] = False

    state = LucidaOrchestrator().initial_state("session-001")
    state = LucidaOrchestrator().propose(
        {
            "event_id": "evt-profile-flags",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preparation",
            "event_type": "soundcheck.profile.compare",
            "payload": {
                "signal_profile": observed,
                "baseline_signal_profile": expected,
            },
        },
        state,
    )

    overlay = LucidaOrchestrator().read_overlay(state)
    nayade = next(item for item in overlay["capabilities"] if item["capability"] == "NAYADE")
    proposal = next(item for item in state.proposals if item.proposal_id == "lucida-nayade-evt-profile-flags")

    assert nayade["state"]["profile_comparison_status"] == "changed"
    assert nayade["state"]["profile_changed_count"] == 3
    assert nayade["state"]["profile_stage_changed"] is True
    assert "3 bounded field(s)" in proposal.reason
    assert "limited" not in json.dumps(overlay)


def test_imago_inherits_bounded_soundcheck_context_without_raw_profile_values():
    expected = _profile()
    observed = copy.deepcopy(expected)
    observed["source"]["range"]["value"] = "limited"
    orchestrator = LucidaOrchestrator()
    state = orchestrator.initial_state("session-001")
    state = orchestrator.propose(
        {
            "event_id": "evt-soundcheck-context",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preparation",
            "event_type": "soundcheck.profile.compare",
            "payload": {
                "signal_profile": observed,
                "baseline_signal_profile": expected,
            },
        },
        state,
    )
    state = orchestrator.propose(
        {
            "event_id": "evt-show-context",
            "timestamp": "2026-01-10T22:00:00Z",
            "phase": "show",
            "event_type": "show.started",
            "payload": {"mode": "improvised"},
        },
        state,
    )

    overlay = orchestrator.read_overlay(state)
    imago = next(item for item in overlay["capabilities"] if item["capability"] == "IMAGO")
    serialized_state = json.dumps(state.to_dict(), sort_keys=True)

    assert imago["state"]["profile_context_status"] == "inherited"
    assert imago["state"]["profile_comparison_status"] == "changed"
    assert imago["state"]["profile_changed_count"] == 1
    proposal = next(item for item in state.proposals if item.proposal_id == "lucida-imago-evt-show-context")
    assert "last soundcheck profile" in proposal.reason
    assert "no new profile measurement" in proposal.reason
    assert "profile-context-inherited" in proposal.evidence
    assert "limited" not in serialized_state
    assert "limited" not in json.dumps(overlay)


def test_invalid_persisted_profile_context_is_removed_before_projection():
    orchestrator = LucidaOrchestrator()
    state = orchestrator.initial_state("session-001").to_dict()
    state["vj_state"]["metadata"]["_lucida_profile_context"] = {
        "profile_status": "valid",
        "profile_stage": "limited",
        "profile_changed_count": "raw-value",
        "unexpected": "must-drop",
    }

    state = orchestrator.propose(
        {
            "event_id": "evt-invalid-context",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preparation",
            "event_type": "soundcheck.started",
            "payload": {},
        },
        state,
    )

    serialized_state = json.dumps(state.to_dict(), sort_keys=True)
    overlay = orchestrator.read_overlay(state)

    assert "limited" not in serialized_state
    assert "raw-value" not in serialized_state
    assert "must-drop" not in serialized_state
    assert "limited" not in json.dumps(overlay)
    assert all(item["state"]["profile_context_status"] is None for item in overlay["capabilities"])


def test_replay_preserves_inherited_profile_context_across_show_boundary():
    expected = _profile()
    observed = copy.deepcopy(expected)
    observed["source"]["range"]["value"] = "limited"
    replay = SessionReplay("session-001")

    replay.append(
        {
            "event_id": "evt-replay-soundcheck",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preparation",
            "event_type": "soundcheck.profile.compare",
            "payload": {
                "signal_profile": observed,
                "baseline_signal_profile": expected,
            },
        },
        {
            "envelope_id": "sig-replay-soundcheck",
            "event_id": "evt-replay-soundcheck",
            "timestamp": "2026-01-10T20:00:00Z",
            "sequence": 1,
            "source": "test",
            "address": "/lucida/nayade/soundcheck",
            "arguments": ["changed"],
            "transport": "osc",
        },
    )
    record = replay.append(
        {
            "event_id": "evt-replay-show",
            "timestamp": "2026-01-10T22:00:00Z",
            "phase": "show",
            "event_type": "show.started",
            "payload": {"mode": "improvised"},
        },
        {
            "envelope_id": "sig-replay-show",
            "event_id": "evt-replay-show",
            "timestamp": "2026-01-10T22:00:00Z",
            "sequence": 2,
            "source": "test",
            "address": "/lucida/imago/show",
            "arguments": ["started"],
            "transport": "osc",
        },
    )

    imago = next(item for item in record.state_after.capabilities if item.capability == "IMAGO")
    serialized_state = json.dumps(record.state_after.to_dict(), sort_keys=True)

    assert imago.state["profile_context_status"] == "inherited"
    assert imago.state["profile_comparison_status"] == "changed"
    assert "limited" not in serialized_state
    assert "limited" in json.dumps(replay.state.records[0].event.to_dict(), sort_keys=True)


def test_nayade_projects_profile_drift_metrics():
    expected = _profile()
    observed = copy.deepcopy(expected)
    observed["capture"]["refresh_hz"]["value"] = 50
    state = LucidaOrchestrator().initial_state("session-001")
    state = LucidaOrchestrator().propose(
        {
            "event_id": "evt-profile-drift",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preparation",
            "event_type": "soundcheck.profile.compare",
            "payload": {
                "signal_profile": observed,
                "baseline_signal_profile": expected,
            },
        },
        state,
    )

    overlay = LucidaOrchestrator().read_overlay(state)
    nayade = next(item for item in overlay["capabilities"] if item["capability"] == "NAYADE")

    assert nayade["state"]["profile_comparison_status"] == "changed"
    assert nayade["state"]["profile_changed_count"] == 1
    assert nayade["state"]["profile_confidence_drop_count"] == 0
    assert nayade["state"]["profile_unknown_delta"] == 0
    proposal = next(item for item in state.proposals if item.proposal_id == "lucida-nayade-evt-profile-drift")
    assert "1 bounded field(s)" in proposal.reason
    assert "profile-drift" in proposal.evidence
    assert "limited" not in json.dumps(proposal.to_dict())


def test_imago_preserves_profile_drift_metrics_for_show():
    expected = _profile()
    observed = copy.deepcopy(expected)
    observed["source"]["range"]["value"] = "limited"
    state = LucidaOrchestrator().initial_state("session-001")
    state = LucidaOrchestrator().propose(
        {
            "event_id": "evt-preparation",
            "timestamp": "2026-01-10T21:00:00Z",
            "phase": "preparation",
            "event_type": "phase.completed",
            "payload": {"status": "pass"},
        },
        state,
    )
    state = LucidaOrchestrator().propose(
        {
            "event_id": "evt-show-profile-drift",
            "timestamp": "2026-01-10T22:00:00Z",
            "phase": "show",
            "event_type": "show.profile.observe",
            "payload": {
                "mode": "improvised",
                "signal_profile": observed,
                "baseline_signal_profile": expected,
            },
        },
        state,
    )

    overlay = LucidaOrchestrator().read_overlay(state)
    imago = next(item for item in overlay["capabilities"] if item["capability"] == "IMAGO")

    assert imago["state"]["profile_status"] == "valid"
    assert imago["state"]["profile_comparison_status"] == "changed"
    assert imago["state"]["profile_changed_count"] == 1
    assert "limited" not in json.dumps(overlay)
    proposal = next(item for item in state.proposals if item.proposal_id == "lucida-imago-evt-show-profile-drift")
    assert "1 bounded field(s)" in proposal.reason
    assert "profile-drift" in proposal.evidence
    assert "limited" not in json.dumps(proposal.to_dict())

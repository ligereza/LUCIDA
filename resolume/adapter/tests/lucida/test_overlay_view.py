import json
from dataclasses import replace
from pathlib import Path

import pytest

from adapters.vj.contracts import VJState
from lucida import (
    LucidaOrchestrator,
    OverlayConsumer,
    OverlayConsumerConflictError,
    OverlayConsumerGapError,
    OverlayConsumerNotInitializedError,
    OverlayConsumerStaleError,
    OverlayReplayError,
    OverlayReplayRecorder,
    OverlayUpdateError,
    build_overlay_cursor,
    build_overlay_update,
    replay_overlay_json,
    replay_overlay_path,
    overlay_view_digest,
    validate_overlay_replay,
)
from lucida.contracts import LucidaContractError, LucidaState
from lucida.overlay import (
    MAX_DIFF_CHANGES,
    OverlayCursorError,
    OverlayDiffError,
    build_overlay_view,
    diff_overlay_view,
    validate_overlay_cursor,
)


def _state():
    orchestrator = LucidaOrchestrator()
    state = orchestrator.initial_state("session-overlay")
    return orchestrator, orchestrator.propose(
        {
            "event_id": "evt-overlay",
            "timestamp": "2026-01-10T20:00:00Z",
            "phase": "preflight",
            "event_type": "phase.completed",
            "payload": {
                "status": "pass",
                "secret_raw_payload": "must-not-leak",
            },
        },
        state,
    )


def test_overlay_view_is_bounded_redacted_and_proposal_only():
    orchestrator, state = _state()
    view = orchestrator.read_overlay_view(state)
    serialized = json.dumps(view, ensure_ascii=False, sort_keys=True)

    assert view["contract_type"] == "LucidaOverlayView"
    assert view["surface"] == "LUCIDA"
    assert view["mode"] == "read_only"
    assert view["pending_proposals"]
    assert view["next_attention"]["kind"] == "proposal"
    assert view["safety"]["proposal_only"] is True
    assert "secret_raw_payload" not in serialized
    assert "metadata" not in view
    assert all("payload" not in proposal for proposal in view["pending_proposals"])


def test_overlay_view_has_deterministic_capability_and_proposal_order():
    _, state = _state()
    first = build_overlay_view(state)
    second = build_overlay_view(state.to_dict())

    assert first == second
    assert [item["capability"] for item in first["capabilities"]] == [
        "INSTAR",
        "NAYADE",
        "IMAGO",
    ]
    proposal_ids = [item["proposal_id"] for item in first["pending_proposals"]]
    assert len(proposal_ids) == len(set(proposal_ids))
    assert [item["risk"] for item in first["pending_proposals"]] == sorted(
        item["risk"] for item in first["pending_proposals"]
    )


def test_overlay_view_limits_are_explicit_and_empty_state_is_safe():
    orchestrator = LucidaOrchestrator()
    state = orchestrator.initial_state("session-empty")
    view = build_overlay_view(state, max_capabilities=1, max_proposals=0, max_unknowns=1)

    assert len(view["capabilities"]) == 1
    assert view["pending_proposals"] == []
    assert len(view["unknowns"]) == 1
    assert view["next_attention"]["kind"] == "unknown"

    with pytest.raises(ValueError, match="non-negative integer"):
        build_overlay_view(state, max_proposals=-1)


def test_overlay_view_empty_state_has_one_deterministic_phase_attention_item():
    state = LucidaState(
        session_id="session-empty",
        vj_state=VJState(session_id="session-empty"),
    )

    view = build_overlay_view(state)

    assert view["capabilities"] == []
    assert view["pending_proposals"] == []
    assert view["unknowns"] == []
    assert view["next_attention"] == {
        "kind": "phase",
        "id": "phase-preflight",
        "reason": "Awaiting the next event.",
    }


def test_overlay_diff_is_stable_and_reports_proposal_and_attention_changes():
    _, state = _state()
    previous = build_overlay_view(state)
    current = json.loads(json.dumps(previous, sort_keys=True))
    current["pending_proposals"][0]["reason"] = "Review the updated proposal."
    current["next_attention"] = {
        "kind": "unknown",
        "id": "unknown-001",
        "reason": "A safe operator review is still required.",
    }

    first = diff_overlay_view(previous, current)
    second = diff_overlay_view(previous, current)

    assert first == second
    assert [item["field"] for item in first] == ["pending_proposals", "next_attention"]
    assert first[0]["after"][0]["reason"] == "Review the updated proposal."
    assert first[1]["after"]["kind"] == "unknown"
    assert diff_overlay_view(previous, previous) == []


def test_overlay_diff_compares_only_safe_fields_and_enforces_bounds():
    _, state = _state()
    previous = build_overlay_view(state)
    current = json.loads(json.dumps(previous, sort_keys=True))
    current["session_id"] = "other-session"
    current["phase"] = "show"
    current["status"] = "changed"
    current["overlay_status"] = "changed"
    current["unknowns"] = ["Unknown change."]
    current["next_attention"] = {
        "kind": "unknown",
        "id": "unknown-001",
        "reason": "Unknown change.",
    }
    current["safety"] = dict(current["safety"])

    changes = diff_overlay_view(previous, current, max_changes=1)

    assert len(changes) == 1
    assert len(diff_overlay_view(previous, current)) <= MAX_DIFF_CHANGES
    assert changes[0]["field"] == "status"


def test_overlay_diff_rejects_non_projected_or_unsafe_inputs():
    _, state = _state()
    view = build_overlay_view(state)

    with pytest.raises(OverlayDiffError, match="mapping"):
        diff_overlay_view([], view)

    invalid_contract = dict(view)
    invalid_contract["contract_type"] = "RawState"
    with pytest.raises(OverlayDiffError, match="contract_type"):
        diff_overlay_view(view, invalid_contract)

    invalid_schema = dict(view)
    invalid_schema["schema_version"] = "9.9"
    with pytest.raises(OverlayDiffError, match="schema_version"):
        diff_overlay_view(view, invalid_schema)

    unsafe = dict(view)
    unsafe["payload"] = {"secret": "must-not-display"}
    with pytest.raises(OverlayDiffError, match="unsupported fields"):
        diff_overlay_view(view, unsafe)

    nested_unsafe = json.loads(json.dumps(view, sort_keys=True))
    nested_unsafe["pending_proposals"][0]["payload"] = {"secret": "must-not-display"}
    with pytest.raises(OverlayDiffError, match="pending_proposals"):
        diff_overlay_view(view, nested_unsafe)

    unsafe_safety = json.loads(json.dumps(view, sort_keys=True))
    unsafe_safety["safety"]["execute"] = "must-not-run"
    with pytest.raises(OverlayDiffError, match="safety"):
        diff_overlay_view(view, unsafe_safety)


def test_orchestrator_diff_projects_states_and_returns_bounded_changes():
    orchestrator, state = _state()
    equivalent = LucidaState.from_dict(state.to_dict())
    assert orchestrator.diff_overlay_view(state, equivalent) == []

    changed_proposal = replace(state.proposals[0], reason="Review the changed proposal.")
    changed = replace(state, proposals=(changed_proposal, *state.proposals[1:]))
    changes = orchestrator.diff_overlay_view(state, changed, max_changes=1)

    assert len(changes) == 1
    assert changes[0]["field"] == "pending_proposals"
    assert changes[0]["after"][0]["reason"] == "Review the changed proposal."


def test_orchestrator_diff_redacts_internal_metadata_and_payload_state():
    orchestrator, state = _state()
    private_report = replace(
        state.capabilities[0],
        state={
            **state.capabilities[0].state,
            "payload": {"secret": "must-not-leak"},
        },
    )
    private_state = replace(
        state,
        capabilities=(private_report, *state.capabilities[1:]),
        metadata={"private_path": "C:\\private", "credential": "secret"},
    )

    changes = orchestrator.diff_overlay_view(state, private_state)
    serialized = json.dumps(changes, ensure_ascii=False, sort_keys=True)

    assert changes == []
    assert "must-not-leak" not in serialized
    assert "private_path" not in serialized
    assert "credential" not in serialized


def test_orchestrator_diff_rejects_invalid_state_through_existing_contracts():
    orchestrator, state = _state()

    with pytest.raises(LucidaContractError, match="campos no soportados o faltantes"):
        orchestrator.diff_overlay_view({}, state)

    invalid_current = state.to_dict()
    invalid_current["vj_state"]["phase"] = "not-a-phase"
    with pytest.raises(ValueError, match="phase"):
        orchestrator.diff_overlay_view(state, invalid_current)


def test_overlay_contract_schemas_match_the_safe_runtime_surface():
    contracts_dir = Path(__file__).parents[2] / "lucida" / "overlay" / "contracts"
    view_schema = json.loads(
        (contracts_dir / "overlay-view.schema.json").read_text(encoding="utf-8")
    )
    diff_schema = json.loads(
        (contracts_dir / "overlay-diff.schema.json").read_text(encoding="utf-8")
    )
    _, state = _state()
    view = build_overlay_view(state)
    diff = diff_overlay_view(view, {**view, "status": "changed"})

    assert view_schema["additionalProperties"] is False
    assert set(view_schema["required"]) == set(view)
    assert diff_schema["maxItems"] == MAX_DIFF_CHANGES
    assert set(diff_schema["items"]["required"]) == {"field", "before", "after"}
    assert all(item["field"] in diff_schema["items"]["properties"]["field"]["enum"] for item in diff)


def test_overlay_contract_schemas_represent_proposal_only_safety():
    contracts_dir = Path(__file__).parents[2] / "lucida" / "overlay" / "contracts"
    view_schema = json.loads(
        (contracts_dir / "overlay-view.schema.json").read_text(encoding="utf-8")
    )
    safety = view_schema["properties"]["safety"]["properties"]
    proposal = view_schema["properties"]["pending_proposals"]["items"]["properties"]

    assert safety["proposal_only"]["const"] is True
    assert safety["automatic_actions"]["const"] is False
    assert safety["external_side_effects"]["const"] is False
    assert proposal["requires_explicit_approval"]["const"] is True
    assert proposal["reversible"]["const"] is True
    assert proposal["execution_mode"]["const"] == "proposal_only"


def test_overlay_cursor_exposes_safe_revision_fields_for_incremental_consumers():
    orchestrator, state = _state()
    cursor = orchestrator.read_overlay_cursor(state)
    equivalent = build_overlay_cursor(LucidaState.from_dict(state.to_dict()))

    assert cursor == equivalent
    assert cursor["contract_type"] == "LucidaOverlayCursor"
    assert cursor["sequence"] == state.vj_state.sequence
    assert cursor["last_event_id"] == state.vj_state.last_event_id
    assert cursor["last_timestamp"] == state.vj_state.last_timestamp
    assert cursor["checkpoint_id"] == state.vj_state.checkpoint_id
    assert cursor["safety"] == {
        "proposal_only": True,
        "automatic_actions": False,
        "external_side_effects": False,
    }
    assert "metadata" not in cursor


def test_overlay_cursor_schema_and_validation_reject_unsafe_revision_values():
    contracts_dir = Path(__file__).parents[2] / "lucida" / "overlay" / "contracts"
    schema = json.loads(
        (contracts_dir / "overlay-cursor.schema.json").read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    assert schema["properties"]["sequence"]["minimum"] == 0
    assert schema["properties"]["safety"]["properties"]["proposal_only"]["const"] is True

    orchestrator, state = _state()
    invalid_state = replace(state, vj_state=replace(state.vj_state, sequence=-1))
    with pytest.raises(OverlayCursorError, match="non-negative integer"):
        orchestrator.read_overlay_cursor(invalid_state)

    invalid_cursor = dict(orchestrator.read_overlay_cursor(state))
    invalid_cursor["last_timestamp"] = "not-a-timestamp"
    invalid_timestamp_state = replace(
        state,
        vj_state=replace(state.vj_state, last_timestamp="not-a-timestamp"),
    )
    with pytest.raises(OverlayCursorError, match="ISO-8601"):
        build_overlay_cursor(invalid_timestamp_state)
    with pytest.raises(OverlayCursorError, match="ISO-8601"):
        validate_overlay_cursor(invalid_cursor)


def test_overlay_consumer_applies_deterministic_delta_and_restores_checkpoint():
    orchestrator, state = _state()
    view = orchestrator.read_overlay_view(state)
    cursor = orchestrator.read_overlay_cursor(state)
    consumer = OverlayConsumer()
    consumer.accept_snapshot(view, cursor)

    next_view = json.loads(json.dumps(view, sort_keys=True))
    next_view["overlay_status"] = "result_recorded"
    changes = diff_overlay_view(view, next_view)
    next_cursor = dict(cursor)
    consumer.apply_delta(changes, next_cursor)

    checkpoint = consumer.checkpoint()
    restored = OverlayConsumer()
    restored.restore_checkpoint(checkpoint)

    assert restored.view == next_view
    assert restored.cursor == cursor
    assert restored.state.applied_delta_count == 1
    assert checkpoint["view_digest"] == overlay_view_digest(next_view)
    restored.state.view["status"] = "local mutation"
    assert restored.view["status"] == view["status"]
    assert restored.view["overlay_status"] == "result_recorded"
    assert checkpoint["safety"]["external_side_effects"] is False
    assert "metadata" not in json.dumps(checkpoint, sort_keys=True)


def test_overlay_consumer_rejects_uninitialized_stale_gap_and_before_conflicts():
    orchestrator, state = _state()
    view = orchestrator.read_overlay_view(state)
    cursor = orchestrator.read_overlay_cursor(state)
    consumer = OverlayConsumer()
    with pytest.raises(OverlayConsumerNotInitializedError):
        consumer.apply_delta([], cursor)
    consumer.accept_snapshot(view, cursor)

    stale_cursor = dict(cursor)
    stale_cursor["sequence"] = 0
    with pytest.raises(OverlayConsumerStaleError):
        consumer.apply_delta([], stale_cursor)

    gap_cursor = dict(cursor)
    gap_cursor["sequence"] = cursor["sequence"] + 2
    with pytest.raises(OverlayConsumerGapError):
        consumer.apply_delta([], gap_cursor)

    bad_change = [{"field": "status", "before": "wrong", "after": "changed"}]
    with pytest.raises(OverlayConsumerConflictError, match="before"):
        consumer.apply_delta(bad_change, cursor)


def test_overlay_consumer_requires_explicit_recovery_and_rejects_unsafe_changes():
    orchestrator, state = _state()
    view = orchestrator.read_overlay_view(state)
    cursor = orchestrator.read_overlay_cursor(state)
    consumer = OverlayConsumer()
    consumer.accept_snapshot(view, cursor)

    with pytest.raises(OverlayConsumerConflictError, match="recovery=True"):
        consumer.accept_snapshot(view, cursor)

    unsafe_change = [{
        "field": "status",
        "before": view["status"],
        "after": {"execute": "must-not-run"},
    }]
    unsafe_cursor = dict(cursor)
    unsafe_cursor["sequence"] = cursor["sequence"] + 1
    unsafe_cursor["last_event_id"] = "evt-next"
    unsafe_cursor["last_timestamp"] = "2026-01-10T20:01:00Z"
    with pytest.raises(OverlayConsumerConflictError):
        consumer.apply_delta(unsafe_change, unsafe_cursor)

    consumer.accept_snapshot(view, cursor, recovery=True)
    assert consumer.state.last_operation == "recovery_snapshot"


def test_overlay_consumer_rejects_mismatched_snapshot_and_checkpoint_contracts():
    orchestrator, state = _state()
    view = orchestrator.read_overlay_view(state)
    cursor = orchestrator.read_overlay_cursor(state)
    consumer = OverlayConsumer()
    mismatched_cursor = dict(cursor)
    mismatched_cursor["session_id"] = "other-session"

    with pytest.raises(OverlayConsumerConflictError, match="sessions differ"):
        consumer.accept_snapshot(view, mismatched_cursor)

    checkpoint = consumer.checkpoint()
    checkpoint["status"] = "ready"
    checkpoint["last_operation"] = "empty"
    checkpoint["view"] = view
    checkpoint["cursor"] = cursor
    with pytest.raises(ValueError, match="non-empty last_operation"):
        consumer.restore_checkpoint(checkpoint)


def test_overlay_consumer_rejects_altered_checkpoint_view_before_mutation():
    orchestrator, state = _state()
    consumer = OverlayConsumer()
    consumer.accept_snapshot(
        orchestrator.read_overlay_view(state),
        orchestrator.read_overlay_cursor(state),
    )
    checkpoint = consumer.checkpoint()
    before = consumer.state
    checkpoint["view"]["status"] = "tampered"

    with pytest.raises(ValueError, match="view_digest"):
        consumer.restore_checkpoint(checkpoint)

    assert consumer.state == before


def test_overlay_json_replay_is_deterministic_and_recoverable():
    fixture_path = Path(__file__).parents[2] / "lucida" / "overlay" / "fixtures" / "overlay-session-fictional.json"
    first = replay_overlay_path(fixture_path)
    second = replay_overlay_json(fixture_path.read_text(encoding="utf-8"))

    assert first == second
    assert first["status"] == "PASS"
    assert first["record_count"] == 5
    assert first["snapshot_count"] == 2
    assert first["delta_count"] == 3
    assert first["final_view"]["status"] == "showing"
    assert first["final_view"]["overlay_status"] == "recovered"
    assert first["final_cursor"]["sequence"] == 2
    assert first["checkpoint"]["safety"]["proposal_only"] is True
    assert "metadata" not in json.dumps(first, sort_keys=True)


def test_overlay_replay_validation_preflights_without_applying_records():
    fixture_path = (
        Path(__file__).parents[2]
        / "lucida"
        / "overlay"
        / "fixtures"
        / "overlay-atomic-update-fictional.json"
    )
    envelope = json.loads(fixture_path.read_text(encoding="utf-8"))

    validated = validate_overlay_replay(envelope)

    assert validated == envelope
    assert validated is not envelope
    assert validated["records"] is not envelope["records"]

    invalid_recovery = json.loads(json.dumps(envelope, sort_keys=True))
    invalid_recovery["records"].append(
        json.loads(json.dumps(invalid_recovery["records"][0], sort_keys=True))
    )
    with pytest.raises(OverlayReplayError, match="recovery=true"):
        validate_overlay_replay(invalid_recovery)

    invalid_view = json.loads(json.dumps(envelope, sort_keys=True))
    invalid_view["records"][0]["view"]["payload"] = {"execute": "must-not-run"}
    with pytest.raises(OverlayReplayError, match="unsupported fields"):
        validate_overlay_replay(invalid_view)


def test_overlay_json_replay_rejects_malformed_or_unsafe_streams():
    fixture_path = Path(__file__).parents[2] / "lucida" / "overlay" / "fixtures" / "overlay-session-fictional.json"
    envelope = json.loads(fixture_path.read_text(encoding="utf-8"))

    no_snapshot = json.loads(json.dumps(envelope, sort_keys=True))
    no_snapshot["records"] = no_snapshot["records"][1:]
    with pytest.raises(ValueError, match="first replay record"):
        replay_overlay_json(no_snapshot)

    gap = json.loads(json.dumps(envelope, sort_keys=True))
    gap["records"][1]["cursor"]["sequence"] = 2
    with pytest.raises(ValueError, match="skips"):
        replay_overlay_json(gap)

    unsafe = json.loads(json.dumps(envelope, sort_keys=True))
    unsafe["records"][1]["changes"][0]["after"] = {"execute": "must-not-run"}
    with pytest.raises(ValueError):
        replay_overlay_json(unsafe)


def test_overlay_json_replay_consumes_atomic_update_fixture_and_cursor_revision():
    fixture_path = (
        Path(__file__).parents[2]
        / "lucida"
        / "overlay"
        / "fixtures"
        / "overlay-atomic-update-fictional.json"
    )
    first = replay_overlay_path(fixture_path)
    second = replay_overlay_json(fixture_path.read_text(encoding="utf-8"))

    assert first == second
    assert first["record_count"] == 2
    assert first["snapshot_count"] == 1
    assert first["delta_count"] == 0
    assert first["update_count"] == 1
    assert first["applied_delta_count"] == 1
    assert first["operations"][-1]["kind"] == "update"
    assert first["final_view"]["status"] == "ready"
    assert first["final_view"]["overlay_status"] == "observing"
    assert first["final_cursor"]["sequence"] == 1
    assert first["safety"]["automatic_actions"] is False


def test_overlay_json_replay_rejects_altered_atomic_payload_without_partial_report():
    fixture_path = (
        Path(__file__).parents[2]
        / "lucida"
        / "overlay"
        / "fixtures"
        / "overlay-atomic-update-fictional.json"
    )
    envelope = json.loads(fixture_path.read_text(encoding="utf-8"))

    altered_view = json.loads(json.dumps(envelope, sort_keys=True))
    altered_view["records"][1]["update"]["view"]["payload"] = {
        "execute": "must-not-run"
    }
    with pytest.raises(OverlayReplayError, match="unsupported fields"):
        replay_overlay_json(altered_view)

    altered_changes = json.loads(json.dumps(envelope, sort_keys=True))
    altered_changes["records"][1]["update"]["changes"][0]["after"] = "tampered"
    with pytest.raises(OverlayReplayError, match="does not match"):
        replay_overlay_json(altered_changes)

    altered_cursor = json.loads(json.dumps(envelope, sort_keys=True))
    altered_cursor["records"][1]["update"]["cursor"]["sequence"] = 2
    with pytest.raises(OverlayReplayError, match="skips"):
        replay_overlay_json(altered_cursor)


def test_overlay_replay_recorder_roundtrips_updates_and_recovery_snapshots():
    orchestrator, state = _state()
    next_state = replace(state, overlay_status="result_recorded")
    recovered_state = replace(next_state, overlay_status="recovered")
    recorder = OverlayReplayRecorder("session-overlay")

    initial = recorder.start(state)
    update = recorder.record(next_state)
    recovery = recorder.record(recovered_state, recovery=True)
    envelope = recorder.envelope()

    assert initial["kind"] == "snapshot"
    assert update["kind"] == "update"
    assert update["update"]["view_digest"]
    assert recovery["kind"] == "snapshot"
    assert recovery["recovery"] is True
    assert recorder.record_count == 3
    assert recorder.to_json() == recorder.to_json()

    report = replay_overlay_json(recorder.to_json())
    assert report["record_count"] == 3
    assert report["update_count"] == 1
    assert report["snapshot_count"] == 2
    assert report["final_view"]["overlay_status"] == "recovered"
    assert replay_overlay_json(envelope) == report


def test_overlay_replay_recorder_rejects_invalid_next_revision_without_appending():
    orchestrator, state = _state()
    recorder = OverlayReplayRecorder()
    recorder.start(state)
    invalid_state = replace(
        state,
        vj_state=replace(state.vj_state, sequence=state.vj_state.sequence + 2),
    )

    with pytest.raises(OverlayReplayError, match="skips"):
        recorder.record(invalid_state)

    assert recorder.record_count == 1
    assert len(recorder.envelope()["records"]) == 1


def test_overlay_replay_schema_is_strict_and_references_safe_contracts():
    contracts_dir = Path(__file__).parents[2] / "lucida" / "overlay" / "contracts"
    schema = json.loads(
        (contracts_dir / "overlay-replay.schema.json").read_text(encoding="utf-8")
    )

    assert schema["additionalProperties"] is False
    assert schema["properties"]["records"]["minItems"] == 1
    variants = schema["properties"]["records"]["items"]["anyOf"]
    assert variants[0]["properties"]["view"]["$ref"] == "urn:resolume_adapter:lucida:overlay-view"
    assert variants[0]["properties"]["cursor"]["$ref"] == "urn:resolume_adapter:lucida:overlay-cursor"
    assert variants[1]["properties"]["cursor"]["$ref"] == "urn:resolume_adapter:lucida:overlay-cursor"
    assert variants[2]["properties"]["update"]["$ref"] == "urn:resolume_adapter:lucida:overlay-update"


def test_overlay_replay_report_schema_matches_the_deterministic_output():
    contracts_dir = Path(__file__).parents[2] / "lucida" / "overlay" / "contracts"
    schema = json.loads(
        (contracts_dir / "overlay-replay-report.schema.json").read_text(encoding="utf-8")
    )
    fixture_path = Path(__file__).parents[2] / "lucida" / "overlay" / "fixtures" / "overlay-session-fictional.json"
    report = replay_overlay_path(fixture_path)

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(report)
    assert schema["properties"]["final_view"]["$ref"] == "urn:resolume_adapter:lucida:overlay-view"
    assert schema["properties"]["final_cursor"]["$ref"] == "urn:resolume_adapter:lucida:overlay-cursor"
    assert schema["properties"]["checkpoint"]["$ref"] == "urn:resolume_adapter:lucida:overlay-consumer-checkpoint"
    assert report["safety"]["replay_only"] is True
    assert report["update_count"] == 0


def test_atomic_overlay_update_binds_view_changes_and_cursor_for_consumers():
    orchestrator, state = _state()
    current = replace(state, overlay_status="result_recorded")
    update = orchestrator.build_overlay_update(state, current)

    assert update == build_overlay_update(state.to_dict(), current.to_dict())
    assert update["contract_type"] == "LucidaOverlayUpdate"
    assert update["view_digest"] == overlay_view_digest(update["view"])
    assert update["changes"][0]["field"] == "overlay_status"
    assert update["view"] == orchestrator.read_overlay_view(current)
    assert update["cursor"] == orchestrator.read_overlay_cursor(current)
    assert update["safety"] == {
        "proposal_only": True,
        "automatic_actions": False,
        "external_side_effects": False,
    }

    consumer = OverlayConsumer()
    consumer.accept_snapshot(
        orchestrator.read_overlay_view(state),
        orchestrator.read_overlay_cursor(state),
    )
    consumer.apply_update(update)

    assert consumer.view == update["view"]
    assert consumer.cursor == update["cursor"]
    assert consumer.state.applied_delta_count == 1


def test_atomic_overlay_update_failure_does_not_mutate_consumer_state():
    orchestrator, state = _state()
    current = replace(state, overlay_status="result_recorded")
    update = orchestrator.build_overlay_update(state, current)
    consumer = OverlayConsumer()
    consumer.accept_snapshot(
        orchestrator.read_overlay_view(state),
        orchestrator.read_overlay_cursor(state),
    )
    before = consumer.state
    tampered = json.loads(json.dumps(update, sort_keys=True))
    tampered["view"]["overlay_status"] = "tampered"

    with pytest.raises(OverlayConsumerConflictError, match="does not match"):
        consumer.apply_update(tampered)

    assert consumer.state == before


def test_atomic_overlay_update_rejects_truncated_diffs_and_has_a_schema():
    orchestrator, state = _state()
    current = replace(state, overlay_status="observing", proposals=())

    with pytest.raises(OverlayUpdateError, match="truncate"):
        orchestrator.build_overlay_update(state, current, max_changes=1)

    contracts_dir = Path(__file__).parents[2] / "lucida" / "overlay" / "contracts"
    schema = json.loads(
        (contracts_dir / "overlay-update.schema.json").read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "contract_type",
        "schema_version",
        "surface",
        "mode",
        "view",
        "view_digest",
        "changes",
        "cursor",
        "safety",
    }
    assert schema["properties"]["view"]["$ref"] == "urn:resolume_adapter:lucida:overlay-view"
    assert schema["properties"]["cursor"]["$ref"] == "urn:resolume_adapter:lucida:overlay-cursor"
    assert schema["properties"]["safety"]["properties"]["automatic_actions"]["const"] is False

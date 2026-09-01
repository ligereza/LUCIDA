"""Small stdlib-only bridge exposing the integrated GDKB 0.6.1 runtime.

The original GDKB slices remain under integrations/gdkb/v0.6.1.  This bridge
assembles their compatible runtime modules behind one JSON-in/JSON-out process
so the Node toolkit can call them without adding a Python package dependency.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent / "runtime"
sys.path.insert(0, str(RUNTIME))

from gdkb.events import Event
from gdkb.import_engine import ImportRecord, import_records
from gdkb.lifecycle import MergePlan, merge_event
from gdkb.normalize import normalize_name
from gdkb.resolver import Candidate, resolve, similarity
from gdkb.snapshot import diff, snapshot
from gdkb.state import build_state


def _candidate(query: str, raw: dict) -> Candidate:
    matched = str(raw.get("matched_value") or raw.get("label") or raw.get("name") or "")
    exact = bool(raw["exact"]) if "exact" in raw else normalize_name(query) == normalize_name(matched)
    score = float(raw["similarity"]) if raw.get("similarity") is not None else similarity(query, matched)
    return Candidate(
        entity_id=str(raw.get("entity_id") or raw.get("id") or ""),
        matched_value=matched,
        source=str(raw.get("source") or raw.get("provider") or "unknown"),
        exact=exact,
        similarity=score,
        identifier_match=bool(raw.get("identifier_match", False)),
    )


def _import_records(payload: dict):
    raw_records = payload.get("records") or []
    if payload.get("input_path"):
        raw_records = []
        with open(payload["input_path"], encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    raw_records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{payload['input_path']}:{line_no}: invalid JSON") from exc
    records = [
        ImportRecord(
            source_name=str(item["source_name"]),
            external_id=str(item["external_id"]),
            record_type=str(item.get("record_type", "entity")),
            payload=item["payload"],
        )
        for item in raw_records
    ]
    return import_records(records)


def run(operation: str, payload: dict):
    if operation == "health":
        return {
            "name": "GDKB",
            "version": "0.6.1",
            "runtime": str(RUNTIME),
            "operations": ["normalize", "resolve", "import", "replay", "merge-event", "health"],
        }

    if operation == "normalize":
        value = str(payload.get("value", ""))
        return {"value": value, "normalized": normalize_name(value)}

    if operation == "resolve":
        query = str(payload.get("query", ""))
        candidates = [_candidate(query, item) for item in payload.get("candidates", [])]
        result = resolve(query, candidates)
        return {
            "entity_id": result.entity_id,
            "decision": result.decision,
            "score": result.score,
            "reason": result.reason,
            "candidates": [
                {
                    "entity_id": item.entity_id,
                    "matched_value": item.matched_value,
                    "source": item.source,
                    "exact": item.exact,
                    "similarity": item.similarity,
                    "identifier_match": item.identifier_match,
                }
                for item in result.candidates
            ],
        }

    if operation == "import":
        rows = _import_records(payload)
        return {"count": len(rows), "records": rows}

    if operation == "merge-event":
        plan = MergePlan(
            source_entity_id=str(payload["source_entity_id"]),
            target_entity_id=str(payload["target_entity_id"]),
            reason=str(payload["reason"]),
            evidence_ids=tuple(str(item) for item in payload.get("evidence_ids", [])),
        )
        return merge_event(plan)

    if operation == "replay":
        events = [
            Event(
                id=str(item["id"]),
                event_type=str(item["event_type"]),
                entity_id=item.get("entity_id"),
                target_entity_id=item.get("target_entity_id"),
                payload=item.get("payload") or {},
                sequence=int(item["sequence"]),
            )
            for item in payload.get("events", [])
        ]
        state = build_state(events)
        result = {"event_count": len(events), "state": state}
        if payload.get("snapshot_id"):
            result["snapshot"] = snapshot(state, str(payload["snapshot_id"]), max((event.sequence for event in events), default=0))
        if payload.get("compare_state") is not None:
            result["diff"] = diff(payload["compare_state"], state)
        return result

    raise ValueError(f"Unsupported GDKB operation: {operation}")


def main():
    operation = "health"
    if "--operation" in sys.argv:
        index = sys.argv.index("--operation")
        operation = sys.argv[index + 1]
    payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    try:
        print(json.dumps(run(operation, payload), ensure_ascii=False, sort_keys=True))
    except Exception as exc:  # keep the subprocess contract machine-readable
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False))
        raise


if __name__ == "__main__":
    main()

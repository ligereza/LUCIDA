"""Sesiones reproducibles de experimentación para el soundcheck de NAYADE."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .contracts import utc_now
from .media import ResolumeAdapterError


SESSION_SCHEMA_VERSION = "0.1"
SESSION_TYPE = "NayadeSoundcheckSession"
VALID_RESULTS = frozenset({"planned", "running", "approved", "rejected", "review"})


def _load_json(path: str | Path) -> tuple[Path, dict[str, Any]]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise ResolumeAdapterError(f"No se encontró el informe JSON: {resolved}")
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolumeAdapterError(f"No se pudo leer el informe JSON: {resolved}") from exc
    if not isinstance(document, dict):
        raise ResolumeAdapterError("El informe JSON debe contener un objeto en su raíz.")
    return resolved, document


def _load_adaptation_plan(path: str | Path) -> tuple[Path, dict[str, Any]]:
    resolved, document = _load_json(path)
    if document.get("plan_type") != "InstarTargetSpecificAdaptationPlan":
        raise ResolumeAdapterError("El archivo no es un plan INSTAR de adaptación target-specific.")
    return resolved, document


def _source_slices(document: dict[str, Any]) -> list[dict[str, Any]]:
    raw_slices = document.get("slices_detail") or document.get("slices")
    if not isinstance(raw_slices, list):
        raise ResolumeAdapterError("El informe no contiene slices utilizables para iniciar una sesión NAYADE.")
    slices: list[dict[str, Any]] = []
    for index, item in enumerate(raw_slices, start=1):
        if not isinstance(item, dict):
            continue
        slice_id = item.get("slice_id") or item.get("id") or f"slice-{index:03d}"
        group_id = item.get("input_group_id") or slice_id
        bounds = item.get("bounds") or ((item.get("input") or {}).get("bounds"))
        dimensions = item.get("input_dimensions") or item.get("target") or {}
        width = float(dimensions.get("width") or (bounds or {}).get("width") or 0)
        height = float(dimensions.get("height") or (bounds or {}).get("height") or 0)
        aspect = width / height if width > 0 and height > 0 else None
        orientation = (
            "vertical" if aspect is not None and aspect < 0.8
            else "horizontal" if aspect is not None and aspect > 1.25
            else "square" if aspect is not None
            else "unknown"
        )
        slices.append({
            "slice_id": str(slice_id),
            "slice_name": item.get("slice_name") or item.get("name") or str(slice_id),
            "input_group_id": str(group_id),
            "orientation": orientation,
            "aspect_ratio": round(aspect, 6) if aspect is not None else None,
            "geometry": item.get("geometry") or {},
        })
    if not slices:
        raise ResolumeAdapterError("El informe no contiene slices habilitadas para iniciar una sesión NAYADE.")
    return slices


def _mapping_hash(document: dict[str, Any], slices: list[dict[str, Any]]) -> str:
    source = {
        "source_map": document.get("source_map") or document.get("source"),
        "composition": document.get("composition"),
        "slices": slices,
    }
    payload = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _group_order(slices: list[dict[str, Any]]) -> list[str]:
    groups: list[str] = []
    for item in slices:
        group_id = item["input_group_id"]
        if group_id not in groups:
            groups.append(group_id)
    return groups


def _behavior_candidates(assets: list[dict[str, Any]], axis: str, operation: str) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for asset in assets:
        behavior = asset.get("behavior") or {}
        signal = (behavior.get(operation) or {}).get(axis) or {}
        score = signal.get("score")
        if score is None:
            continue
        ranked.append({
            "asset_id": asset.get("asset_id"),
            "filename": asset.get("filename"),
            "score": round(float(score), 6),
            "status": signal.get("status") or "unknown",
            "requires_preview": signal.get("requires_preview", True),
        })
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:6]


def build_experiment_matrix(
    slices: list[dict[str, Any]],
    assets: list[dict[str, Any]] | None = None,
    adaptations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Crea una matriz corta y determinista, agrupada por InputRect."""

    groups = _group_order(slices)
    assets = assets or []
    steps: list[dict[str, Any]] = []

    def add(operation: str, scope: str, targets: list[str], parameters: dict[str, Any], checks: list[str]) -> None:
        steps.append({
            "step_id": f"step-{len(steps) + 1:03d}",
            "operation": operation,
            "scope": scope,
            "targets": targets,
            "parameters": parameters,
            "expected_checks": checks,
            "result": "planned",
        })

    add("baseline", "input_group", groups, {}, ["boundaries", "geometry", "orientation"])
    add("flip_horizontal", "input_group", groups, {"axis": "x"}, ["orientation", "boundaries"])
    add("flip_vertical", "input_group", groups, {"axis": "y"}, ["orientation", "boundaries"])
    add("rotate", "input_group", groups, {"degrees": 180}, ["geometry", "orientation", "boundaries"])

    for group_id in groups:
        group_slices = [item for item in slices if item["input_group_id"] == group_id]
        orientation = group_slices[0]["orientation"] if group_slices else "unknown"
        axis = "vertical" if orientation == "vertical" else "horizontal"
        pattern_candidates = _behavior_candidates(assets, axis, "pattern")
        marquee_candidates = _behavior_candidates(assets, axis, "marquee")
        add(
            "pattern",
            "input_group",
            [group_id],
            {"mode": "tile", "axis": axis, "candidate_assets": pattern_candidates},
            ["seam", "continuity", "geometry"],
        )
        add(
            "marquee",
            "input_group",
            [group_id],
            {"axis": axis, "speed": 0.18, "wrap": True, "candidate_assets": marquee_candidates},
            ["continuity", "seam", "orientation"],
        )
    for adaptation in adaptations or []:
        target = adaptation.get("target") or {}
        group_id = str(target.get("input_group_id") or target.get("slice_id") or "unknown")
        add(
            "instar_adaptation",
            "input_group",
            [group_id],
            {
                "task_id": adaptation.get("task_id"),
                "strategy": adaptation.get("strategy"),
                "axis": adaptation.get("axis"),
                "preview": adaptation.get("output"),
                "dxv": (adaptation.get("dxv") or {}).get("output"),
                "source_asset_id": adaptation.get("source_asset_id"),
            },
            ["geometry", "continuity", "readability", "seam"],
        )
    return steps


def create_session(
    source_path: str | Path,
    output_path: str | Path,
    *,
    name: str | None = None,
    seed: int | None = None,
    catalog_path: str | Path | None = None,
    adaptation_plan_path: str | Path | None = None,
    protocol_path: str | Path | None = None,
) -> dict[str, Any]:
    """Crea una sesión NAYADE sin alterar el informe fuente."""

    source, document = _load_json(source_path)
    slices = _source_slices(document)
    assets: list[dict[str, Any]] = []
    catalog = None
    if catalog_path is not None:
        from .resolume import load_catalog_assets

        catalog_file = Path(catalog_path).expanduser().resolve()
        assets = load_catalog_assets(catalog_file)
        catalog = {"path": str(catalog_file), "assets": len(assets)}
    adaptation = None
    adaptations: list[dict[str, Any]] = []
    if adaptation_plan_path is not None:
        adaptation_file, adaptation_document = _load_adaptation_plan(adaptation_plan_path)
        adaptations = [item for item in adaptation_document.get("tasks") or [] if isinstance(item, dict)]
        adaptation = {
            "path": str(adaptation_file),
            "strategy_filter": adaptation_document.get("strategy_filter"),
            "output_dir": adaptation_document.get("output_dir"),
            "dxv_output_dir": adaptation_document.get("dxv_output_dir"),
            "tasks": [
                {
                    "task_id": item.get("task_id"),
                    "strategy": item.get("strategy"),
                    "axis": item.get("axis"),
                    "target": item.get("target"),
                    "output": item.get("output"),
                    "dxv": item.get("dxv"),
                    "status": item.get("status"),
                }
                for item in adaptations
            ],
        }
    protocol = None
    protocol_steps: list[dict[str, Any]] = []
    if protocol_path is not None:
        from .protocol import protocol_session_steps

        protocol_file, protocol_document = _load_json(protocol_path)
        protocol_steps = protocol_session_steps(protocol_document, targets=_group_order(slices))
        protocol = {
            "path": str(protocol_file),
            "status": protocol_document.get("status"),
            "evidence_ids": list(protocol_document.get("evidence_ids") or []),
            "source_documents": list(protocol_document.get("source_documents") or []),
            "step_count": len(protocol_steps),
        }
    mapping_hash = _mapping_hash(document, slices)
    session_seed = seed if seed is not None else int(mapping_hash[:8], 16)
    output = Path(output_path).expanduser().resolve()
    if output.exists():
        raise ResolumeAdapterError(f"La sesión ya existe; no se sobrescribirá: {output}")
    session = {
        "schema_version": SESSION_SCHEMA_VERSION,
        "session_type": SESSION_TYPE,
        "session_id": f"nayade-{mapping_hash}",
        "name": name or f"Soundcheck {mapping_hash}",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "read_only_source": True,
        "source": {
            "path": str(source),
            "type": document.get("plan_type") or document.get("testcard_type") or "unknown",
            "mapping_hash": mapping_hash,
        },
        "composition": document.get("composition"),
        "seed": session_seed,
        "catalog": catalog,
        "adaptation": adaptation,
        "protocol": protocol,
        "assets": [
            {
                "asset_id": asset.get("asset_id"),
                "filename": asset.get("filename"),
                "path": asset.get("path"),
                "width": asset.get("width"),
                "height": asset.get("height"),
            }
            for asset in assets
        ],
        "targets": {
            "slices": slices,
            "input_groups": _group_order(slices),
        },
        "planned_steps": protocol_steps + build_experiment_matrix(slices, assets, adaptations),
        "events": [],
        "limitations": [
            "La sesión registra decisiones y parámetros, pero todavía no envía órdenes a Resolume.",
            "El resultado físico de un procesador LED debe ser confirmado durante el soundcheck.",
            "El alcance input_group evita tratar como independientes slices que comparten InputRect.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    return session


def get_next_step(session_path: str | Path) -> dict[str, Any] | None:
    """Devuelve el primer paso aún no resuelto de una sesión NAYADE."""

    _, session = _load_json(session_path)
    if session.get("session_type") != SESSION_TYPE:
        raise ResolumeAdapterError("El archivo no es una sesión NAYADE válida.")
    return next(
        (step for step in session.get("planned_steps") or [] if step.get("result") == "planned"),
        None,
    )


def _step_matches(
    step: dict[str, Any],
    *,
    operation: str,
    scope: str,
    targets: list[str],
    parameters: dict[str, Any],
) -> bool:
    if step.get("operation") != operation or step.get("scope") != scope:
        return False
    step_targets = set(step.get("targets") or [])
    if targets and not set(targets).issubset(step_targets):
        return False
    step_parameters = step.get("parameters") or {}
    task_id = parameters.get("task_id")
    if task_id is not None and step_parameters.get("task_id") != task_id:
        return False
    return True


def record_event(
    session_path: str | Path,
    *,
    operation: str,
    result: str,
    scope: str = "input_group",
    targets: list[str] | None = None,
    parameters: dict[str, Any] | None = None,
    notes: str = "",
    step_id: str | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Agrega una observación al archivo de sesión elegido por el VJ."""

    path, session = _load_json(session_path)
    if session.get("session_type") != SESSION_TYPE:
        raise ResolumeAdapterError("El archivo no es una sesión NAYADE válida.")
    if result not in VALID_RESULTS:
        raise ResolumeAdapterError(f"Resultado inválido: {result}. Use uno de: {', '.join(sorted(VALID_RESULTS))}.")
    event = {
        "event_id": f"event-{len(session.get('events') or []) + 1:03d}",
        "created_at": utc_now(),
        "operation": operation,
        "scope": scope,
        "targets": targets or session.get("targets", {}).get("input_groups", []),
        "parameters": parameters or {},
        "result": result,
        "notes": notes,
    }
    chosen_step = None
    if step_id:
        chosen_step = next(
            (step for step in session.get("planned_steps") or [] if step.get("step_id") == step_id),
            None,
        )
        if chosen_step is None:
            raise ResolumeAdapterError(f"No existe el paso planificado: {step_id}")
    else:
        chosen_step = next(
            (
                step
                for step in session.get("planned_steps") or []
                if step.get("result") == "planned"
                and _step_matches(
                    step,
                    operation=operation,
                    scope=scope,
                    targets=targets or [],
                    parameters=parameters or {},
                )
            ),
            None,
        )
    if chosen_step is not None:
        chosen_step["result"] = result
        event["planned_step_id"] = chosen_step.get("step_id")
    session.setdefault("events", []).append(event)
    session["updated_at"] = utc_now()
    target = path if output_path is None else Path(output_path).expanduser().resolve()
    if target == path and output_path is not None:
        raise ResolumeAdapterError("--output debe ser distinto al archivo de sesión de origen.")
    if output_path is not None and target.exists():
        raise ResolumeAdapterError(f"El archivo de salida ya existe; no se sobrescribirá: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        temporary_path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return event


def write_session(session: dict[str, Any], path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def build_session_report(session_path: str | Path) -> dict[str, Any]:
    """Create a bounded readiness summary from a NAYADE session."""

    _, session = _load_json(session_path)
    if session.get("session_type") != SESSION_TYPE:
        raise ResolumeAdapterError("El archivo no es una sesión NAYADE válida.")
    steps = [item for item in session.get("planned_steps") or [] if isinstance(item, dict)]
    events = [item for item in session.get("events") or [] if isinstance(item, dict)]
    valid_results = VALID_RESULTS | {"unknown"}
    counts = {result: 0 for result in sorted(valid_results)}
    for step in steps:
        result = step.get("result", "unknown")
        if result not in counts:
            result = "unknown"
        counts[result] += 1
    pending = [step for step in steps if step.get("result") == "planned"]
    pending_required = [
        step for step in pending
        if (step.get("parameters") or {}).get("priority") == "required"
    ]
    risks: list[dict[str, Any]] = []
    for step in steps:
        result = step.get("result")
        if result not in {"rejected", "review", "running"}:
            continue
        risks.append({
            "risk_id": f"{step.get('step_id', 'unknown')}-{result}",
            "severity": "high" if result == "rejected" else "review",
            "step_id": step.get("step_id"),
            "operation": step.get("operation"),
            "status": result,
            "detail": (
                "El operador rechazó este paso; no se debe tratar la cadena como estable."
                if result == "rejected"
                else "Este paso necesita confirmación explícita antes de cerrar el soundcheck."
            ),
        })

    if any(item.get("result") == "rejected" for item in steps):
        status = "BLOCKED"
    elif risks or pending_required:
        status = "REVIEW"
    elif pending:
        status = "INCOMPLETE"
    else:
        status = "READY"

    next_step = None
    actionable = [
        step for step in steps
        if step.get("result") in {"planned", "running", "review", "rejected"}
    ]
    if actionable:
        candidate = actionable[0]
        parameters = candidate.get("parameters") or {}
        next_step = {
            "step_id": candidate.get("step_id"),
            "operation": candidate.get("operation"),
            "scope": candidate.get("scope"),
            "targets": list(candidate.get("targets") or []),
            "pattern": parameters.get("pattern"),
            "title": parameters.get("title"),
            "priority": parameters.get("priority", "unclassified"),
            "expected_checks": list(candidate.get("expected_checks") or []),
        }
    return {
        "schema_version": "0.1",
        "report_type": "NayadeSoundcheckSessionReport",
        "status": status,
        "session_id": session.get("session_id"),
        "session_name": session.get("name"),
        "updated_at": session.get("updated_at"),
        "summary": {
            "step_count": len(steps),
            "event_count": len(events),
            "step_results": {key: value for key, value in counts.items() if value},
            "pending_count": len(pending),
            "pending_required_count": len(pending_required),
            "risk_count": len(risks),
        },
        "next_step": next_step,
        "risks": risks,
        "safety": {
            "read_only": True,
            "commands_sent": False,
            "writes_attempted": False,
            "external_side_effects": False,
            "source_paths_exposed": False,
        },
    }


def session_report_text(report: dict[str, Any]) -> str:
    """Render the bounded session report for an operator."""

    summary = report.get("summary") or {}
    lines = [
        "RESOLUME_ADAPTER NAYADE - ESTADO DE SOUNDCHECK",
        "====================================",
        f"Sesión: {report.get('session_id')}",
        f"Estado: {report.get('status')}",
        f"Pasos: {summary.get('step_count', 0)} | pendientes: {summary.get('pending_count', 0)} | riesgos: {summary.get('risk_count', 0)}",
    ]
    next_step = report.get("next_step")
    if next_step:
        lines.extend([
            "PRÓXIMO PASO",
            f"- {next_step.get('step_id')}: {next_step.get('operation')} ({next_step.get('priority')})",
            f"- Comprobar: {', '.join(next_step.get('expected_checks') or []) or 'registrar observación'}",
        ])
    for risk in report.get("risks") or []:
        lines.append(f"- {str(risk.get('severity')).upper()} {risk.get('step_id')}: {risk.get('detail')}")
    lines.append("Modo: SOLO LECTURA; el reporte no ejecuta acciones.")
    return "\n".join(lines)


def text_report(session: dict[str, Any], *, event: dict[str, Any] | None = None) -> str:
    targets = session.get("targets") or {}
    lines = [
        "RESOLUME_ADAPTER NAYADE SOUNDCHECK",
        "========================",
        f"Sesión: {session.get('session_id')}",
        f"Mapping: {session.get('source', {}).get('mapping_hash')}",
        f"Seed: {session.get('seed')}",
        f"Catálogo: {(session.get('catalog') or {}).get('assets', 0) if session.get('catalog') else 'no cargado'}",
        f"Input groups: {len(targets.get('input_groups') or [])}",
        f"Pasos planificados: {len(session.get('planned_steps') or [])}",
        f"Pasos pendientes: {sum(step.get('result') == 'planned' for step in session.get('planned_steps') or [])}",
        f"Eventos registrados: {len(session.get('events') or [])}",
    ]
    if event:
        lines.extend([
            "",
            f"Evento: {event['event_id']} — {event['operation']} — {event['result']}",
            f"Objetivos: {', '.join(event['targets']) or 'todos'}",
        ])
        if event.get("planned_step_id"):
            lines.append(f"Paso actualizado: {event['planned_step_id']}")
    return "\n".join(lines)

"""Generador de protocolos de soundcheck para NAYADE.

El módulo convierte evidencia ya registrada en una lista ordenada de pruebas
para el operador. No genera patrones, no abre conexiones y no escribe en
procesadores; la ejecución permanece explícita y fuera de este componente.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .media import ResolumeAdapterError


PROTOCOL_SCHEMA_VERSION = "0.1"
PROTOCOL_TYPE = "NayadeSoundcheckProtocol"
PROTOCOL_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "nayade-soundcheck-protocol.schema.json"


_STEP_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "pattern": "blackout",
        "title": "Negro de referencia",
        "scope": "chain",
        "why": "Establece la referencia visual antes de juzgar rango, gamma o brillo.",
        "operator_action": "Mostrar negro absoluto y confirmar si la superficie queda en blackout o conserva gris visible.",
        "expected_observation": "Blackout uniforme; cualquier gris debe registrarse como observación, no corregirse todavía.",
        "record_fields": ["blackout_status", "uniformity", "notes"],
        "default_priority": "required",
        "triggers": [],
    },
    {
        "pattern": "pluge_near_black",
        "title": "PLUGE / near-black",
        "scope": "signal_and_processor",
        "why": "Separa negro, near-black y clipping para comprobar rango y nivel de negro.",
        "operator_action": "Mostrar barras PLUGE o near-black con la corrección creativa neutra y anotar qué barras son visibles.",
        "expected_observation": "El negro de referencia no se levanta y los niveles cercanos se distinguen sin clipping prematuro.",
        "record_fields": ["black_bar_visible", "near_black_bars", "range_mode", "notes"],
        "default_priority": "required",
        "triggers": ["range_mismatch", "possible_double_range_conversion", "raised_black_level", "processor_range_state_not_recorded"],
    },
    {
        "pattern": "gray_ramp",
        "title": "Escala de grises",
        "scope": "signal_and_processor",
        "why": "Permite distinguir gamma, contraste, banding y compensaciones de niveles.",
        "operator_action": "Mostrar una rampa y parches de gris bajo, medio y alto con Resolume en neutral.",
        "expected_observation": "Transición continua, sin saltos visibles, posterización ni medios tonos excesivamente comprimidos.",
        "record_fields": ["ramp_continuity", "banding_status", "gamma_observation", "notes"],
        "default_priority": "conditional",
        "triggers": ["extreme_gamma_low_brightness", "multi_stage_level_compensation", "banding"],
    },
    {
        "pattern": "primaries",
        "title": "Primarios y blanco",
        "scope": "signal_and_processor",
        "why": "Comprueba que RGB y blanco lleguen con identidad de canal antes de evaluar color del contenido.",
        "operator_action": "Mostrar rojo, verde, azul, blanco y gris neutro; registrar dominante, clipping o canal ausente.",
        "expected_observation": "Cada primario ocupa su canal sin contaminación evidente y el blanco no presenta dominante inesperada.",
        "record_fields": ["red_status", "green_status", "blue_status", "white_status", "neutral_gray_status", "notes"],
        "default_priority": "required",
        "triggers": ["color_range_unknown", "color_space_unknown"],
    },
    {
        "pattern": "geometry_grid",
        "title": "Geometría, círculo y límites",
        "scope": "mapping_and_surface",
        "why": "Detecta deformación, crop incorrecto, inversión, solapamiento y desliz entre slices.",
        "operator_action": "Mostrar cuadrícula, círculo, cuadrado y bordes identificables por slice; revisar cada módulo y transición.",
        "expected_observation": "El círculo permanece circular, los bordes coinciden y no hay contenido de un slice invadiendo otro.",
        "record_fields": ["circle_status", "grid_status", "slice_boundaries", "overlap_status", "orientation", "notes"],
        "default_priority": "required",
        "triggers": ["mapping_distortion_risk", "mapping_validation_failed", "resolution_mismatch"],
    },
    {
        "pattern": "resolution_scaling",
        "title": "Resolución y escalado",
        "scope": "signal_processor_mapping",
        "why": "Aísla escalado intencional, crop y proporción cuando entrada, salida o composición no coinciden.",
        "operator_action": "Mostrar una cuadrícula con resolución conocida y comparar input, output y superficie visible.",
        "expected_observation": "El escalado declarado coincide con lo observado y no introduce estiramiento o pérdida de bordes no documentada.",
        "record_fields": ["input_resolution", "output_resolution", "scaling_mode", "crop_status", "aspect_status", "notes"],
        "default_priority": "conditional",
        "triggers": ["processor_scaling", "resolution_mismatch", "mapping_distortion_risk"],
    },
    {
        "pattern": "motion_stability",
        "title": "Movimiento y estabilidad",
        "scope": "chain_and_output",
        "why": "Distingue flicker, tearing, judder y cortes de enlace de un problema del archivo visual.",
        "operator_action": "Mostrar una línea o barra en movimiento y un patrón con cambios controlados; observar a la frecuencia real de salida.",
        "expected_observation": "Movimiento continuo, sin tearing, parpadeo repetitivo ni pérdida de sincronía; registrar si el defecto depende de la salida.",
        "record_fields": ["flicker_status", "tearing_status", "judder_status", "link_stability", "refresh_observed", "notes"],
        "default_priority": "required",
        "triggers": ["flicker", "tearing", "fps_mismatch", "refresh", "stability"],
    },
)


def _require_document(name: str, document: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    if not isinstance(document, Mapping):
        raise ResolumeAdapterError(f"El documento {name} debe ser un objeto.")
    return dict(document)


def _evidence_ids(
    case_report: Mapping[str, Any] | None,
    reconciliation: Mapping[str, Any] | None,
    mapping: Mapping[str, Any] | None,
) -> set[str]:
    ids: set[str] = set()
    for finding in (case_report or {}).get("findings") or []:
        if isinstance(finding, Mapping) and isinstance(finding.get("id"), str):
            ids.add(finding["id"])
    for conflict in (reconciliation or {}).get("conflicts") or []:
        if isinstance(conflict, Mapping) and isinstance(conflict.get("id"), str):
            ids.add(conflict["id"])
    if mapping:
        validation = mapping.get("validation") or {}
        if isinstance(validation, Mapping) and validation.get("status") == "FAIL":
            ids.add("mapping_validation_failed")
        if mapping.get("mapping_distortion_risk") is True:
            ids.add("mapping_distortion_risk")
    return ids


def _trigger_matches(trigger: str, evidence_ids: set[str]) -> list[str]:
    if trigger in evidence_ids:
        return [trigger]
    if trigger == "resolution_mismatch":
        return sorted(item for item in evidence_ids if item.startswith("resolution_mismatch_"))
    if trigger == "processor_scaling" and "processor_scaling" in evidence_ids:
        return [trigger]
    if trigger == "fps_mismatch":
        return sorted(item for item in evidence_ids if item.startswith("fps_mismatch_"))
    if trigger == "color_range_unknown":
        return [trigger] if trigger in evidence_ids else []
    if trigger == "color_space_unknown":
        return [trigger] if trigger in evidence_ids else []
    return []


def _derived_evidence_ids(reconciliation: Mapping[str, Any] | None) -> set[str]:
    ids: set[str] = set()
    for calculation in (reconciliation or {}).get("calculations") or []:
        if not isinstance(calculation, Mapping):
            continue
        if calculation.get("id") == "processor_scaling" and calculation.get("value") is True:
            ids.add("processor_scaling")
    for fact in (reconciliation or {}).get("facts") or []:
        if not isinstance(fact, Mapping):
            continue
        if fact.get("subject") == "gpu.output" and fact.get("property") in {"color_range", "color_space"} and fact.get("value") == "unknown":
            ids.add(f"{fact['property']}_unknown")
    return ids


def build_soundcheck_protocol(
    case_report: Mapping[str, Any] | None = None,
    reconciliation: Mapping[str, Any] | None = None,
    mapping: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, read-only operator protocol from evidence."""

    case = _require_document("case_report", case_report)
    chain = _require_document("reconciliation", reconciliation)
    output_map = _require_document("mapping", mapping)
    if case is None and chain is None and output_map is None:
        source_documents: list[str] = []
    else:
        source_documents = [
            name for name, document in (("case", case), ("reconciliation", chain), ("mapping", output_map))
            if document is not None
        ]

    evidence_ids = _evidence_ids(case, chain, output_map) | _derived_evidence_ids(chain)
    steps: list[dict[str, Any]] = []
    for definition in _STEP_DEFINITIONS:
        matched = sorted({match for trigger in definition["triggers"] for match in _trigger_matches(trigger, evidence_ids)})
        priority = definition["default_priority"]
        if matched and priority == "conditional":
            priority = "required"
        elif not matched and priority == "conditional":
            priority = "optional"
        steps.append({
            "step_id": f"check-{len(steps) + 1:03d}",
            "order": len(steps) + 1,
            "pattern": definition["pattern"],
            "title": definition["title"],
            "priority": priority,
            "scope": definition["scope"],
            "triggered_by": matched,
            "why": definition["why"],
            "operator_action": definition["operator_action"],
            "expected_observation": definition["expected_observation"],
            "record_fields": list(definition["record_fields"]),
            "status": "planned",
            "execution_mode": "plan_only",
            "requires_operator_confirmation": True,
            "reversible": True,
        })

    severe = False
    if chain and any(isinstance(item, Mapping) and item.get("severity") == "high" for item in chain.get("conflicts") or []):
        severe = True
    if case and any(isinstance(item, Mapping) and item.get("status") in {"WARN", "REVIEW"} for item in case.get("findings") or []):
        severe = True
    return {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "protocol_type": PROTOCOL_TYPE,
        "status": "REVIEW" if severe else "READY",
        "source_documents": source_documents,
        "evidence_ids": sorted(evidence_ids),
        "steps": steps,
        "summary": {
            "step_count": len(steps),
            "required_count": sum(item["priority"] == "required" for item in steps),
            "optional_count": sum(item["priority"] == "optional" for item in steps),
            "trigger_count": len(evidence_ids),
        },
        "safety": {
            "read_only": True,
            "commands_sent": False,
            "writes_attempted": False,
            "external_side_effects": False,
            "patterns_emitted": False,
            "hardware_changed": False,
            "source_paths_exposed": False,
        },
        "limitations": [
            "El protocolo propone observaciones; no mide la pantalla ni modifica el procesador.",
            "La frecuencia de salida, el tipo de módulo y la calibración física deben registrarse durante la prueba.",
            "Un patrón aprobado no demuestra por sí solo que todos los clips del show estén libres de defectos.",
        ],
    }


def validate_soundcheck_protocol_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a protocol before it is attached to a mutable session."""

    if not isinstance(document, Mapping):
        raise ResolumeAdapterError("El protocolo NAYADE debe ser un objeto.")
    try:
        schema = json.loads(PROTOCOL_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResolumeAdapterError("No se pudo leer el schema del protocolo NAYADE.") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(item) for item in errors[0].path) or "root"
        raise ResolumeAdapterError(f"Protocolo NAYADE inválido en {location}: {errors[0].message}")
    return dict(document)


def protocol_text_report(report: Mapping[str, Any]) -> str:
    """Render a compact operator-facing protocol without paths."""

    lines = [
        "RESOLUME_ADAPTER NAYADE - PROTOCOLO DE SOUNDCHECK",
        "========================================",
        f"Estado: {report.get('status')}",
        f"Evidencia: {', '.join(report.get('evidence_ids') or []) or 'línea base sin hallazgos'}",
        f"Pasos: {(report.get('summary') or {}).get('step_count', 0)} | requeridos: {(report.get('summary') or {}).get('required_count', 0)}",
    ]
    for step in report.get("steps") or []:
        trigger = f" [{', '.join(step.get('triggered_by') or [])}]" if step.get("triggered_by") else ""
        lines.append(f"{step.get('order')}. {str(step.get('priority')).upper()} {step.get('title')}{trigger}")
        lines.append(f"   - {step.get('operator_action')}")
    lines.append("Modo: SOLO PLAN; no se enviaron patrones, comandos ni escrituras.")
    return "\n".join(lines)


def protocol_session_steps(
    report: Mapping[str, Any],
    *,
    targets: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Adapt a protocol into NAYADE session steps without executing it."""

    report = validate_soundcheck_protocol_document(report)
    session_targets = list(targets or ["all-input-groups"])
    steps: list[dict[str, Any]] = []
    for index, protocol_step in enumerate(report.get("steps") or [], start=1):
        if not isinstance(protocol_step, Mapping):
            raise ResolumeAdapterError("Cada paso del protocolo NAYADE debe ser un objeto.")
        step_id = str(protocol_step.get("step_id") or f"check-{index:03d}")
        steps.append({
            "step_id": f"processor-{step_id}",
            "operation": "processor_check",
            "scope": str(protocol_step.get("scope") or "chain"),
            "targets": session_targets,
            "parameters": {
                "protocol_step_id": step_id,
                "pattern": protocol_step.get("pattern"),
                "title": protocol_step.get("title"),
                "priority": protocol_step.get("priority"),
                "triggered_by": list(protocol_step.get("triggered_by") or []),
                "execution_mode": "plan_only",
            },
            "expected_checks": list(protocol_step.get("record_fields") or []),
            "result": "planned",
        })
    return steps


__all__ = [
    "build_soundcheck_protocol",
    "protocol_session_steps",
    "protocol_text_report",
    "validate_soundcheck_protocol_document",
]

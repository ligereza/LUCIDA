"""Reconcile VJ signal-chain evidence without changing external systems."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from .media import ResolumeAdapterError


RECONCILIATION_SCHEMA_VERSION = "0.1"
_RESOLUTION = re.compile(r"^\s*(\d+)\s*[xX]\s*(\d+)\s*$")
_DOCUMENT_NAMES = frozenset(
    {"signal_profile", "processor_observation", "processor_snapshot", "module_profile", "mapping", "output_probe"}
)


def load_reconciliation_document(path: str | Path) -> dict[str, Any]:
    """Load one JSON evidence document without returning its path."""

    document_path = Path(path).expanduser().resolve()
    if not document_path.is_file():
        raise ResolumeAdapterError(f"No se encontró el documento de reconciliación: {document_path}")
    try:
        value = json.loads(document_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResolumeAdapterError(f"No se pudo leer el documento de reconciliación: {document_path}") from exc
    if not isinstance(value, dict):
        raise ResolumeAdapterError("Cada documento de reconciliación debe ser un objeto JSON.")
    return value


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _fact_value(value: Any) -> tuple[Any, str, float, str | None]:
    if isinstance(value, Mapping) and "value" in value:
        origin = value.get("origin", "observed")
        confidence = value.get("confidence", 0.8)
        source = value.get("source")
        if isinstance(origin, str) and isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
            return value["value"], origin, max(0.0, min(1.0, float(confidence))), source if isinstance(source, str) else None
    return value, "observed", 0.8, None


def _resolution(value: Any) -> tuple[int, int] | None:
    if isinstance(value, Mapping):
        width, height = value.get("width"), value.get("height")
        if isinstance(width, int) and not isinstance(width, bool) and isinstance(height, int) and not isinstance(height, bool):
            if width > 0 and height > 0:
                return width, height
    if isinstance(value, str):
        match = _RESOLUTION.match(value)
        if match:
            return int(match.group(1)), int(match.group(2))
    return None


def _resolution_text(value: tuple[int, int]) -> str:
    return f"{value[0]}x{value[1]}"


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _path(document: Mapping[str, Any], *keys: str) -> Any:
    current: Any = document
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _fact(
    facts: list[dict[str, Any]],
    seen: set[str],
    *,
    subject: str,
    property_name: str,
    value: Any,
    origin: str,
    confidence: float,
    source: str,
) -> None:
    if not _scalar(value) or value is None:
        return
    key = f"{subject}.{property_name}"
    if key in seen:
        return
    seen.add(key)
    facts.append(
        {
            "subject": subject,
            "property": property_name,
            "value": value,
            "origin": origin,
            "confidence": round(max(0.0, min(1.0, confidence)), 6),
            "source": source,
        }
    )


def _resolution_fact(
    facts: list[dict[str, Any]],
    seen: set[str],
    resolutions: dict[str, tuple[int, int]],
    *,
    label: str,
    subject: str,
    value: Any,
    origin: str,
    confidence: float,
    source: str,
) -> None:
    parsed = _resolution(value)
    if parsed is None:
        return
    resolutions[label] = parsed
    _fact(
        facts,
        seen,
        subject=subject,
        property_name="resolution",
        value=_resolution_text(parsed),
        origin=origin,
        confidence=confidence,
        source=source,
    )


def _conflict(
    conflicts: list[dict[str, Any]],
    *,
    conflict_id: str,
    severity: str,
    fields: list[str],
    detail: str,
    action: str,
) -> None:
    conflicts.append(
        {
            "id": conflict_id,
            "severity": severity,
            "fields": fields,
            "detail": detail,
            "action": action,
        }
    )


def _recommendation(
    recommendations: list[dict[str, Any]],
    *,
    operation: str,
    reason: str,
    evidence: list[str],
    risk: str = "low",
) -> None:
    recommendations.append(
        {
            "operation": operation,
            "reason": reason,
            "risk": risk,
            "evidence": evidence,
            "requires_explicit_approval": True,
            "reversible": True,
            "execution_mode": "proposal_only",
        }
    )


def reconcile_signal_chain(documents: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Produce facts, calculations, conflicts, and proposals from evidence."""

    if not isinstance(documents, Mapping) or not documents:
        raise ResolumeAdapterError("La reconciliación necesita al menos un documento.")
    unknown_documents = set(documents) - _DOCUMENT_NAMES
    if unknown_documents:
        raise ResolumeAdapterError(f"Documentos de reconciliación no soportados: {sorted(unknown_documents)}")
    if any(not isinstance(value, Mapping) for value in documents.values()):
        raise ResolumeAdapterError("Los documentos de reconciliación deben ser objetos.")

    facts: list[dict[str, Any]] = []
    seen_facts: set[str] = set()
    resolutions: dict[str, tuple[int, int]] = {}
    fps_values: dict[str, float] = {}
    range_values: dict[str, str] = {}
    calculations: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []

    signal = documents.get("signal_profile")
    if signal:
        source = "signal_profile"
        for field_name in ("resolution", "fps", "range", "transfer", "primaries", "bit_depth"):
            raw = _path(signal, "source", field_name)
            value, origin, confidence, _ = _fact_value(raw)
            if field_name == "resolution":
                _resolution_fact(
                    facts,
                    seen_facts,
                    resolutions,
                    label="signal.source",
                    subject="signal.source",
                    value=value,
                    origin=origin,
                    confidence=confidence,
                    source=source,
                )
            else:
                _fact(
                    facts,
                    seen_facts,
                    subject="signal.source",
                    property_name=field_name,
                    value=value,
                    origin=origin,
                    confidence=confidence,
                    source=source,
                )
                if field_name == "fps" and _number(value) is not None:
                    fps_values["signal.source"] = _number(value) or 0.0
                if field_name == "range" and isinstance(value, str):
                    range_values["signal.source"] = value.casefold()
        capture_resolution = _fact_value(_path(signal, "capture", "resolution"))
        _resolution_fact(
            facts,
            seen_facts,
            resolutions,
            label="signal.capture",
            subject="signal.capture",
            value=capture_resolution[0],
            origin=capture_resolution[1],
            confidence=capture_resolution[2],
            source=source,
        )
        _fact(
            facts,
            seen_facts,
            subject="processor",
            property_name="model",
            value=_fact_value(_path(signal, "processor", "model"))[0],
            origin=_fact_value(_path(signal, "processor", "model"))[1],
            confidence=_fact_value(_path(signal, "processor", "model"))[2],
            source=source,
        )

    observation = documents.get("processor_observation")
    if observation:
        source = "processor_observation"
        for direction in ("input", "output"):
            signal_section = _path(observation, f"{direction}_signal") or {}
            resolution_raw = signal_section.get("resolution") if isinstance(signal_section, Mapping) else None
            _resolution_fact(
                facts,
                seen_facts,
                resolutions,
                label=f"processor.{direction}",
                subject=f"processor.{direction}",
                value=resolution_raw,
                origin="observed",
                confidence=0.8,
                source=source,
            )
            fps = _number(signal_section.get("fps")) if isinstance(signal_section, Mapping) else None
            if fps is not None:
                fps_values[f"processor.{direction}"] = fps
                _fact(
                    facts,
                    seen_facts,
                    subject=f"processor.{direction}",
                    property_name="fps",
                    value=int(fps) if fps.is_integer() else fps,
                    origin="observed",
                    confidence=0.8,
                    source=source,
                )
            signal_range = signal_section.get("range") if isinstance(signal_section, Mapping) else None
            if isinstance(signal_range, str):
                range_values[f"processor.{direction}"] = signal_range.casefold()
                _fact(
                    facts,
                    seen_facts,
                    subject=f"processor.{direction}",
                    property_name="range",
                    value=signal_range,
                    origin="observed",
                    confidence=0.8,
                    source=source,
                )
        for field_name in ("model", "firmware", "transport", "confidence"):
            value = observation.get(field_name)
            _fact(
                facts,
                seen_facts,
                subject="processor",
                property_name=field_name,
                value=value,
                origin="observed",
                confidence=0.8,
                source=source,
            )

    snapshot = documents.get("processor_snapshot")
    if snapshot:
        identification = snapshot.get("identification") or {}
        for field_name in ("manufacturer", "family", "model"):
            raw = identification.get(field_name) if isinstance(identification, Mapping) else None
            value, origin, confidence, _ = _fact_value(raw)
            _fact(
                facts,
                seen_facts,
                subject="processor",
                property_name=field_name,
                value=value,
                origin=origin,
                confidence=confidence,
                source="processor_snapshot",
            )
        _fact(
            facts,
            seen_facts,
            subject="processor",
            property_name="read_only",
            value=snapshot.get("read_only"),
            origin="observed",
            confidence=1.0,
            source="processor_snapshot",
        )

    mapping = documents.get("mapping")
    if mapping:
        composition = mapping.get("composition") or {}
        composition_resolution = _resolution(composition)
        if composition_resolution:
            resolutions["mapping.composition"] = composition_resolution
            _fact(
                facts,
                seen_facts,
                subject="mapping.composition",
                property_name="resolution",
                value=_resolution_text(composition_resolution),
                origin="observed",
                confidence=0.9,
                source="mapping",
            )
        validation = mapping.get("validation") or {}
        if isinstance(validation, Mapping):
            status = validation.get("status")
            _fact(
                facts,
                seen_facts,
                subject="mapping",
                property_name="validation_status",
                value=status,
                origin="observed",
                confidence=0.9,
                source="mapping",
            )
            if status == "FAIL":
                _conflict(
                    conflicts,
                    conflict_id="mapping_validation_failed",
                    severity="high",
                    fields=["mapping.validation"],
                    detail="El Advanced Output contiene errores de validación.",
                    action="Revisar el preset y confirmar la salida antes de usar el show.",
                )
        if mapping.get("mapping_distortion_risk") is True:
            _conflict(
                conflicts,
                conflict_id="mapping_distortion_risk",
                severity="review",
                fields=["mapping.output_transformation"],
                detail="El mapping declara riesgo de deformación no uniforme.",
                action="Probar un círculo y comparar InputRect con OutputRect durante NAYADE.",
            )

    output_probe = documents.get("output_probe")
    if output_probe:
        output_signal = output_probe.get("output_signal") or {}
        if isinstance(output_signal, Mapping):
            _resolution_fact(
                facts,
                seen_facts,
                resolutions,
                label="gpu.output",
                subject="gpu.output",
                value=output_signal.get("resolution"),
                origin="observed",
                confidence=0.75,
                source="output_probe",
            )
            refresh_hz = _number(output_signal.get("refresh_hz"))
            if refresh_hz is not None:
                fps_values["gpu.output"] = refresh_hz
                _fact(
                    facts,
                    seen_facts,
                    subject="gpu.output",
                    property_name="refresh_hz",
                    value=int(refresh_hz) if refresh_hz.is_integer() else refresh_hz,
                    origin="observed",
                    confidence=0.75,
                    source="output_probe",
                )
            for field_name in ("color_range", "color_space"):
                _fact(
                    facts,
                    seen_facts,
                    subject="gpu.output",
                    property_name=field_name,
                    value=output_signal.get(field_name),
                    origin="observed",
                    confidence=0.4 if output_signal.get(field_name) == "unknown" else 0.75,
                    source="output_probe",
                )

    module = documents.get("module_profile")
    if module:
        value, origin, confidence, _ = _fact_value(module.get("environment"))
        _fact(
            facts,
            seen_facts,
            subject="module",
            property_name="environment",
            value=value,
            origin=origin,
            confidence=confidence,
            source="module_profile",
        )
        fixtures = module.get("fixtures") or []
        if isinstance(fixtures, list):
            for index, fixture in enumerate(fixtures):
                if not isinstance(fixture, Mapping):
                    continue
                fixture_id = str(fixture.get("fixture_id") or f"fixture-{index + 1:03d}")
                pixel = fixture.get("pixel_resolution") or {}
                physical = fixture.get("physical_size_mm") or {}
                width_px = _number(pixel.get("width")) if isinstance(pixel, Mapping) else None
                height_px = _number(pixel.get("height")) if isinstance(pixel, Mapping) else None
                width_mm = _number(physical.get("width")) if isinstance(physical, Mapping) else None
                height_mm = _number(physical.get("height")) if isinstance(physical, Mapping) else None
                if width_px and height_px and width_mm and height_mm:
                    pitch_x = width_mm / width_px
                    pitch_y = height_mm / height_px
                    calculations.append(
                        {
                            "id": f"pixel_pitch_{fixture_id}",
                            "kind": "pixel_pitch",
                            "fixture_id": fixture_id,
                            "pitch_x_mm": round(pitch_x, 6),
                            "pitch_y_mm": round(pitch_y, 6),
                            "uniform": abs(pitch_x - pitch_y) <= max(pitch_x, pitch_y) * 0.01,
                            "origin": "inferred",
                            "confidence": 0.9,
                        }
                    )
                    if abs(pitch_x - pitch_y) > max(pitch_x, pitch_y) * 0.01:
                        _conflict(
                            conflicts,
                            conflict_id=f"module_pitch_inconsistent_{fixture_id}",
                            severity="review",
                            fields=[f"module.fixtures.{fixture_id}.pixel_resolution", f"module.fixtures.{fixture_id}.physical_size_mm"],
                            detail="El pixel pitch calculado en los ejes X e Y no coincide.",
                            action="Confirmar medidas físicas y si la ficha corresponde al mismo gabinete.",
                        )
                    declared_pitch = _fact_value(fixture.get("pixel_pitch_mm"))[0]
                    declared_number = _number(declared_pitch)
                    calculated_pitch = (pitch_x + pitch_y) / 2
                    if declared_number is not None and abs(declared_number - calculated_pitch) > calculated_pitch * 0.05:
                        _conflict(
                            conflicts,
                            conflict_id=f"module_pitch_declared_mismatch_{fixture_id}",
                            severity="review",
                            fields=[f"module.fixtures.{fixture_id}.pixel_pitch_mm", f"module.fixtures.{fixture_id}.physical_size_mm"],
                            detail="El pixel pitch declarado difiere más de 5% del cálculo físico.",
                            action="Revisar unidad, redondeo o identidad del módulo antes de inferir capacidad.",
                        )

    def compare_resolution(left: str, right: str) -> None:
        if left not in resolutions or right not in resolutions or resolutions[left] == resolutions[right]:
            return
        _conflict(
            conflicts,
            conflict_id=f"resolution_mismatch_{left.replace('.', '_')}_{right.replace('.', '_')}",
            severity="review",
            fields=[left, right],
            detail=f"Las resoluciones declaradas no coinciden: {_resolution_text(resolutions[left])} frente a {_resolution_text(resolutions[right])}.",
            action="Confirmar si existe escalado intencional o si se capturó una ruta de señal distinta.",
        )

    compare_resolution("signal.source", "processor.input")
    compare_resolution("processor.input", "mapping.composition")
    compare_resolution("signal.source", "mapping.composition")
    compare_resolution("signal.source", "gpu.output")
    compare_resolution("processor.input", "gpu.output")
    if "processor.input" in resolutions and "processor.output" in resolutions:
        scaling = resolutions["processor.input"] != resolutions["processor.output"]
        calculations.append(
            {
                "id": "processor_scaling",
                "kind": "scaling_detected",
                "value": scaling,
                "origin": "inferred",
                "confidence": 0.9,
            }
        )
        if scaling:
            _recommendation(
                recommendations,
                operation="review_processor_scaling",
                reason="La entrada y salida del procesador tienen resoluciones distintas.",
                evidence=["processor.input", "processor.output"],
                risk="medium",
            )

    for left, right in (("signal.source", "processor.input"), ("signal.source", "processor.output"), ("signal.source", "gpu.output")):
        if left in fps_values and right in fps_values and not math.isclose(fps_values[left], fps_values[right], rel_tol=0.0, abs_tol=0.01):
            _conflict(
                conflicts,
                conflict_id=f"fps_mismatch_{left.replace('.', '_')}_{right.replace('.', '_')}",
                severity="review",
                fields=[left, right],
                detail=f"Los FPS observados no coinciden: {fps_values[left]:g} frente a {fps_values[right]:g}.",
                action="Confirmar el modo de salida y evitar interpolación no registrada.",
            )
    if "signal.source" in range_values and "processor.input" in range_values and range_values["signal.source"] != range_values["processor.input"]:
        _conflict(
            conflicts,
            conflict_id="range_mismatch",
            severity="high",
            fields=["signal.source.range", "processor.input.range"],
            detail="La fuente y la entrada del procesador declaran rangos de señal diferentes.",
            action="Probar PLUGE/near-black y confirmar una sola transformación de rango antes de tocar gamma.",
        )
        _recommendation(
            recommendations,
            operation="review_signal_range",
            reason="Existe una discrepancia de rango en la cadena de señal.",
            evidence=["signal.source.range", "processor.input.range"],
            risk="medium",
        )

    if module and not (module.get("fixtures") or []):
        _recommendation(
            recommendations,
            operation="capture_module_profile",
            reason="La cadena no tiene un fixture físico vinculado; indoor/outdoor, pitch y brillo siguen desconocidos.",
            evidence=["module_profile"],
        )
    if not module:
        _recommendation(
            recommendations,
            operation="capture_module_profile",
            reason="No se recibió un perfil físico del módulo; no se debe inferir brillo o pitch desde HDMI.",
            evidence=["missing:module_profile"],
        )

    unknown_count = sum(1 for name in ("signal_profile", "processor_observation", "processor_snapshot", "module_profile", "mapping", "output_probe") if name not in documents)
    status = "FAIL" if any(item["severity"] == "high" for item in conflicts) else ("REVIEW" if conflicts or unknown_count else "PASS")
    known_confidences = [item["confidence"] for item in facts]
    return {
        "schema_version": RECONCILIATION_SCHEMA_VERSION,
        "report_type": "NayadeSignalChainReconciliation",
        "status": status,
        "source_documents": sorted(documents),
        "facts": facts,
        "calculations": calculations,
        "conflicts": conflicts,
        "recommendations": recommendations,
        "summary": {
            "fact_count": len(facts),
            "calculation_count": len(calculations),
            "conflict_count": len(conflicts),
            "unknown_document_count": unknown_count,
            "min_confidence": round(min(known_confidences), 6) if known_confidences else 0.0,
        },
        "safety": {
            "read_only": True,
            "commands_sent": False,
            "writes_attempted": False,
            "external_side_effects": False,
            "raw_documents_included": False,
            "source_paths_exposed": False,
        },
    }


def reconciliation_text_report(report: Mapping[str, Any]) -> str:
    """Render a compact operator report without exposing source paths."""

    lines = [
        "RESOLUME_ADAPTER NAYADE - RECONCILIACION DE CADENA",
        "=========================================",
        f"Estado: {report.get('status')}",
        f"Documentos: {', '.join(report.get('source_documents') or [])}",
        f"Hechos: {(report.get('summary') or {}).get('fact_count', 0)}",
        f"Calculos: {(report.get('summary') or {}).get('calculation_count', 0)}",
        f"Conflictos: {(report.get('summary') or {}).get('conflict_count', 0)}",
    ]
    for conflict in report.get("conflicts") or []:
        lines.append(f"- {conflict.get('severity')} {conflict.get('id')}: {conflict.get('detail')}")
    for recommendation in report.get("recommendations") or []:
        lines.append(f"- PROPOSAL {recommendation.get('operation')}: {recommendation.get('reason')}")
    lines.append("Modo: SOLO LECTURA; no se enviaron comandos ni se modifico hardware.")
    return "\n".join(lines)


__all__ = [
    "RECONCILIATION_SCHEMA_VERSION",
    "load_reconciliation_document",
    "reconcile_signal_chain",
    "reconciliation_text_report",
]

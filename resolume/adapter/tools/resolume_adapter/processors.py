"""Descubrimiento y diagnóstico seguro de procesadores LED para NAYADE.

El módulo separa tres cosas que suelen mezclarse en un soundcheck:

* identidad/capacidades del procesador;
* datos físicos del sistema LED y sus módulos;
* observaciones visuales y reglas de diagnóstico.

El transporte implementado aquí es deliberadamente de solo lectura a nivel de
descubrimiento: enumera puertos USB/COM y no transmite comandos al hardware.
Los protocolos de cada fabricante se incorporarán como adaptadores explícitos
después de probar el modelo exacto.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .contracts import utc_now
from .media import ResolumeAdapterError


CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "processors" / "catalog.json"
UNKNOWN_PROFILE_ID = "unknown-led-processor"
CASE_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "nayade-processor-case.schema.json"


def _load_json(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise ResolumeAdapterError(f"No se encontró el JSON: {resolved}")
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolumeAdapterError(f"No se pudo leer el JSON: {resolved}") from exc
    if not isinstance(document, dict):
        raise ResolumeAdapterError(f"El JSON debe contener un objeto en su raíz: {resolved}")
    return document


def load_processor_catalog(path: str | Path | None = None) -> dict[str, Any]:
    """Carga el catálogo local de perfiles de procesadores."""

    catalog = _load_json(path or CATALOG_PATH)
    if catalog.get("catalog_type") != "ResolumeAdapterProcessorCatalog":
        raise ResolumeAdapterError("El archivo no es un catálogo de procesadores RESOLUME_ADAPTER válido.")
    processors = catalog.get("processors")
    if not isinstance(processors, list) or not processors:
        raise ResolumeAdapterError("El catálogo de procesadores no contiene perfiles.")
    return catalog


def validate_processor_case_document(case: dict[str, Any]) -> dict[str, Any]:
    """Validate one public NAYADE case before applying diagnosis rules."""

    if not isinstance(case, dict):
        raise ResolumeAdapterError("El caso NAYADE debe ser un objeto JSON.")
    try:
        schema = json.loads(CASE_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolumeAdapterError(f"No se pudo leer el schema de casos NAYADE: {CASE_SCHEMA_PATH}") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(case), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(item) for item in errors[0].path) or "root"
        raise ResolumeAdapterError(f"Caso NAYADE inválido en {location}: {errors[0].message}")
    return dict(case)


def validate_processor_case(path: str | Path) -> dict[str, Any]:
    """Return a shareable validation summary without exposing the source path."""

    case = validate_processor_case_document(_load_json(path))
    return {
        "schema_version": "0.1",
        "report_type": "NayadeProcessorCaseValidation",
        "case_id": case["case_id"],
        "valid": True,
        "observation_count": len(case["observations"]),
        "hypothesis_count": len(case["diagnostic_hypotheses"]),
        "event_count": len(case["event_sequence"]),
        "safety": {
            "commands_sent": False,
            "writes_attempted": False,
            "source_path_exposed": False,
        },
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()


def _vid_pid(vid: Any, pid: Any) -> str | None:
    if vid is None or pid is None:
        return None
    try:
        return f"{int(vid):04x}:{int(pid):04x}"
    except (TypeError, ValueError):
        return f"{vid}:{pid}".casefold()


def match_processor_profiles(
    device: dict[str, Any],
    catalog: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Devuelve perfiles ordenados por coincidencia, sin abrir el dispositivo."""

    catalog = catalog or load_processor_catalog()
    haystack = " ".join(
        _text(device.get(key))
        for key in ("device", "description", "manufacturer", "product", "interface", "hwid", "location")
    )
    observed_vid_pid = _vid_pid(device.get("vid"), device.get("pid")) or _text(device.get("vid_pid"))
    matches: list[dict[str, Any]] = []
    for profile in catalog.get("processors") or []:
        if profile.get("profile_id") == UNKNOWN_PROFILE_ID:
            continue
        identifiers = profile.get("identifiers") or {}
        score = 0
        reasons: list[str] = []
        for keyword in identifiers.get("keywords") or []:
            normalized = _text(keyword)
            if normalized and normalized in haystack:
                score += 2
                reasons.append(f"keyword:{keyword}")
        for candidate in identifiers.get("vid_pid") or []:
            if observed_vid_pid and _text(candidate) == observed_vid_pid:
                score += 5
                reasons.append(f"vid_pid:{candidate}")
        if score:
            matches.append({"profile_id": profile.get("profile_id"), "score": score, "reasons": reasons})
    matches.sort(key=lambda item: (-int(item["score"]), str(item["profile_id"])))
    return matches


def _port_to_record(port: Any) -> dict[str, Any]:
    return {
        "transport": "usb_serial",
        "device": getattr(port, "device", None),
        "description": getattr(port, "description", None),
        "manufacturer": getattr(port, "manufacturer", None),
        "product": getattr(port, "product", None),
        "serial_number": getattr(port, "serial_number", None),
        "interface": getattr(port, "interface", None),
        "location": getattr(port, "location", None),
        "hwid": getattr(port, "hwid", None),
        "vid": getattr(port, "vid", None),
        "pid": getattr(port, "pid", None),
        "vid_pid": _vid_pid(getattr(port, "vid", None), getattr(port, "pid", None)),
    }


def discover_serial_devices(catalog_path: str | Path | None = None) -> dict[str, Any]:
    """Enumera dispositivos seriales/USB visibles para Windows.

    PySerial consulta el inventario del sistema. No se abre ningún puerto y no
    se envían bytes al procesador.
    """

    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise ResolumeAdapterError("Falta pyserial; instálalo con `python -m pip install pyserial`.") from exc

    catalog = load_processor_catalog(catalog_path)
    devices: list[dict[str, Any]] = []
    for port in sorted(list_ports.comports(), key=lambda item: str(getattr(item, "device", ""))):
        record = _port_to_record(port)
        record["matches"] = match_processor_profiles(record, catalog)
        record["best_match"] = (record["matches"] or [{"profile_id": UNKNOWN_PROFILE_ID}])[0]
        devices.append(record)
    return {
        "schema_version": "0.1",
        "report_type": "NayadeProcessorDiscovery",
        "captured_at": utc_now(),
        "read_only": True,
        "transport_scope": ["usb_serial"],
        "devices": devices,
        "safety": {
            "ports_opened": False,
            "commands_sent": False,
            "writes_attempted": False,
        },
        "limitations": [
            "Un puerto COM puede pertenecer a un adaptador sin ser un procesador LED.",
            "La ausencia de un dispositivo USB no descarta control por Ethernet o software propietario.",
            "VID/PID y descriptores no prueban por sí solos el modelo ni la configuración física del LED.",
        ],
    }


def _profile_by_id(catalog: dict[str, Any], profile_id: str) -> dict[str, Any]:
    for profile in catalog.get("processors") or []:
        if profile.get("profile_id") == profile_id:
            return profile
    raise ResolumeAdapterError(f"No existe el perfil de procesador: {profile_id}")


def _unknown_connection(device: str) -> dict[str, Any]:
    return {
        "transport": "usb_serial",
        "device": device,
        "description": "provided_by_operator",
        "manufacturer": None,
        "product": None,
        "serial_number": None,
        "interface": None,
        "location": None,
        "hwid": None,
        "vid": None,
        "pid": None,
        "vid_pid": None,
    }


def _fact(value: Any, origin: str = "unknown", confidence: float = 0.0, source: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"value": value, "origin": origin, "confidence": confidence}
    if source:
        result["source"] = source
    return result


def build_processor_snapshot(
    connection: dict[str, Any],
    *,
    model: str | None = None,
    catalog_path: str | Path | None = None,
) -> dict[str, Any]:
    """Construye un snapshot sin consultar ni modificar el hardware."""

    catalog = load_processor_catalog(catalog_path)
    matches = match_processor_profiles(connection, catalog)
    selected_id = model or (matches[0]["profile_id"] if matches else UNKNOWN_PROFILE_ID)
    profile = _profile_by_id(catalog, selected_id)
    model_origin = "operator_selected" if model else ("matched" if matches else "unknown")
    model_confidence = 1.0 if model else (0.65 if matches else 0.0)
    return {
        "schema_version": "0.1",
        "snapshot_type": "NayadeProcessorSnapshot",
        "captured_at": utc_now(),
        "read_only": True,
        "connection": connection,
        "identification": {
            "manufacturer": _fact(profile.get("manufacturer"), model_origin, model_confidence, "resolume_adapter_catalog"),
            "family": _fact(profile.get("family"), model_origin, model_confidence, "resolume_adapter_catalog"),
            "model": _fact(selected_id, model_origin, model_confidence, "resolume_adapter_catalog"),
            "transport_matches": matches,
        },
        "catalog_profile": profile,
        "screen": {
            "environment": _fact(None),
            "pixel_pitch_mm": _fact(None),
            "fixture_model": _fact(None),
            "receiving_card": _fact(None),
            "physical_dimensions_mm": _fact(None),
            "note": "Debe vincularse un ModuleProfile; no se infiere desde HDMI.",
        },
        "observations": [
            {
                "kind": "usb_descriptor",
                "status": "observed" if connection.get("device") else "unknown",
                "detail": "Se registró metadata del puerto; todavía no se abrió ni interrogó el protocolo del dispositivo.",
            }
        ],
        "diagnostics": [],
        "module_profile_id": None,
        "safety": {
            "commands_sent": False,
            "writes_attempted": False,
            "unknown_device_write_blocked": True,
        },
    }


def snapshot_from_serial_device(
    device: str,
    *,
    model: str | None = None,
    catalog_path: str | Path | None = None,
) -> dict[str, Any]:
    """Crea snapshot de un COM; si no está enumerado, conserva identidad desconocida."""

    discovery = discover_serial_devices(catalog_path)
    connection = next(
        (item for item in discovery["devices"] if _text(item.get("device")) == _text(device)),
        _unknown_connection(device),
    )
    return build_processor_snapshot(connection, model=model, catalog_path=catalog_path)


def diagnose_signal_observations(observations: dict[str, Any]) -> list[dict[str, Any]]:
    """Aplica reglas conservadoras a observaciones declaradas por el operador.

    Las reglas no miden la pantalla y no escriben en el procesador. Solo
    priorizan hipótesis que luego deben verificarse con patrones.
    """

    findings: list[dict[str, Any]] = []
    gpu_range = _text(observations.get("gpu_range"))
    processor_conversion = _text(observations.get("processor_limited_to_full"))
    if gpu_range == "full" and processor_conversion in {"on", "true", "1"}:
        findings.append({
            "id": "possible_double_range_conversion",
            "status": "WARN",
            "detail": "La GPU declara RGB Full y el procesador convierte Limited-to-Full; revisar antes de dejar ambos activos.",
            "action": "Comparar patrón PLUGE/near-black con una sola conversión activa.",
        })

    try:
        gamma = float(observations.get("processor_gamma"))
    except (TypeError, ValueError):
        gamma = None
    try:
        brightness = float(observations.get("processor_brightness"))
    except (TypeError, ValueError):
        brightness = None
    if gamma is not None and gamma >= 3.5 and brightness is not None and brightness <= 10:
        findings.append({
            "id": "extreme_gamma_low_brightness",
            "status": "WARN",
            "detail": "Gamma extremo y brillo muy bajo sugieren compensaciones acumuladas; gamma afecta medios tonos, no demuestra por sí solo un negro levantado.",
            "action": "Restaurar snapshot y probar gamma/brightness por separado.",
        })

    if _text(observations.get("resolume_levels")) in {"modified", "brightness_and_contrast_modified"}:
        findings.append({
            "id": "multi_stage_level_compensation",
            "status": "WARN",
            "detail": "Resolume también modifica niveles; comparar con brillo/contraste neutros antes de juzgar el procesador.",
            "action": "Registrar un patrón sin correcciones creativas en Resolume.",
        })

    black = _text(observations.get("black_level"))
    if black in {"gray_above_blackout", "raised", "lifted"}:
        findings.append({
            "id": "raised_black_level",
            "status": "REVIEW",
            "detail": "Un negro visible por encima de blackout apunta primero a rango/offset/black level o doble conversión; gamma sola no basta para explicarlo.",
            "action": "Medir RGB(0,0,0), near-black y PLUGE en la cadena completa.",
        })
    return findings


def diagnose_case(path: str | Path) -> dict[str, Any]:
    case = validate_processor_case_document(_load_json(path))
    observations: dict[str, Any] = {}
    before_observations: dict[str, Any] = {}
    after_observations: dict[str, Any] = {}
    for item in case.get("observations") or []:
        if not isinstance(item, dict) or not item.get("key"):
            continue
        key = item["key"]
        if "value" in item:
            observations[key] = item["value"]
        if "before" in item:
            before_observations[key] = item["before"]
        if "after" in item:
            after_observations[key] = item["after"]
            observations[key] = item["after"]

    findings = diagnose_signal_observations(observations)
    findings.extend(diagnose_signal_observations(before_observations))
    if "black_level" in before_observations:
        findings = [
            finding for finding in findings
            if not (finding.get("id") == "raised_black_level" and finding.get("status") == "REVIEW")
        ] + diagnose_signal_observations({"black_level": before_observations["black_level"]})
    range_state = _text(observations.get("processor_limited_to_full"))
    if range_state not in {"on", "off", "true", "false", "1", "0"}:
        findings.append({
            "id": "processor_range_state_not_recorded",
            "status": "INFO",
            "detail": "El caso no registra si el procesador tenía activa la conversión Limited-to-Full; no se puede confirmar doble conversión.",
            "action": "En el próximo soundcheck registrar explícitamente el estado de rango del procesador antes de tocarlo.",
        })
    unique_findings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for finding in findings:
        if finding.get("id") not in seen_ids:
            unique_findings.append(finding)
            seen_ids.add(str(finding.get("id")))
    return {
        "schema_version": "0.1",
        "report_type": "NayadeProcessorCaseDiagnosis",
        "case_id": case.get("case_id"),
        "captured_at": utc_now(),
        "read_only": True,
        "findings": unique_findings,
        "source_case": case["case_id"],
        "safety": {
            "commands_sent": False,
            "writes_attempted": False,
            "source_path_exposed": False,
        },
    }


def write_json(document: dict[str, Any], path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def catalog_text_report(catalog: dict[str, Any]) -> str:
    lines = ["RESOLUME_ADAPTER NAYADE — PROCESADORES", "============================"]
    for profile in catalog.get("processors") or []:
        capabilities = profile.get("capabilities") or {}
        lines.append(
            f"- {profile.get('profile_id')}: {profile.get('manufacturer')} {profile.get('family')} | "
            f"{profile.get('device_class')} | transport={','.join(profile.get('transports') or [])} | "
            f"test_patterns={capabilities.get('test_patterns')}"
        )
    return "\n".join(lines)


def discovery_text_report(report: dict[str, Any]) -> str:
    devices = report.get("devices") or []
    lines = [
        "RESOLUME_ADAPTER NAYADE — DESCUBRIMIENTO DE PROCESADORES",
        "===============================================",
        f"Dispositivos USB/COM: {len(devices)}",
        "Modo: SOLO LECTURA; no se abrieron puertos ni se enviaron comandos.",
    ]
    for device in devices:
        best = device.get("best_match") or {}
        lines.append(
            f"- {device.get('device')}: {device.get('description') or 'sin descripción'} "
            f"VID:PID={device.get('vid_pid') or 'desconocido'} -> {best.get('profile_id', UNKNOWN_PROFILE_ID)}"
        )
    if not devices:
        lines.append("- No hay puertos seriales visibles en este equipo.")
    return "\n".join(lines)


def snapshot_text_report(snapshot: dict[str, Any]) -> str:
    identification = snapshot.get("identification") or {}
    model = (identification.get("model") or {}).get("value", UNKNOWN_PROFILE_ID)
    manufacturer = (identification.get("manufacturer") or {}).get("value", "Unknown")
    connection = snapshot.get("connection") or {}
    return "\n".join([
        "RESOLUME_ADAPTER NAYADE — SNAPSHOT DE PROCESADOR",
        "=======================================",
        f"Dispositivo: {connection.get('device')}",
        f"Identificación: {manufacturer} / {model}",
        "Modo: SOLO LECTURA",
        "Comandos enviados: no",
        "Escrituras intentadas: no",
        "Pixel pitch/módulo: pendiente de ModuleProfile",
    ])


def case_text_report(report: dict[str, Any]) -> str:
    lines = [
        "RESOLUME_ADAPTER NAYADE — DIAGNÓSTICO DE CASO",
        "===================================",
        f"Caso: {report.get('case_id')}",
    ]
    for finding in report.get("findings") or []:
        lines.append(f"- {finding.get('status')} {finding.get('id')}: {finding.get('detail')}")
    return "\n".join(lines)

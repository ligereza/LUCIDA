"""Importación conservadora de routing desde Pixel Peeker para INSTAR.

Pixel Peeker ya calcula la parte que una imagen o un PDF no puede contener:
procesadores, puertos, orden de cadena y posición de cada gabinete. Este módulo
solo normaliza ese intercambio y, cuando se entrega un reporte de layout INSTAR,
compara geometrías. Nunca convierte una coincidencia geométrica en una afirmación
de patch físico.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .media import ResolumeAdapterError


INTERCHANGE_FORMAT = "pixel-peeker.interchange/1"


def _read_json(source: str | Path | Mapping[str, Any]) -> tuple[dict[str, Any], str | None]:
    if isinstance(source, Mapping):
        return dict(source), None
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise ResolumeAdapterError(f"No se encontró el intercambio Pixel Peeker: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResolumeAdapterError(f"No se pudo leer el intercambio Pixel Peeker: {path}") from exc
    if not isinstance(value, dict):
        raise ResolumeAdapterError("El intercambio Pixel Peeker debe ser un objeto JSON.")
    return value, str(path)


def _number(value: Any, label: str, *, integer: bool = False) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResolumeAdapterError(f"Campo inválido {label}: se esperaba un número.")
    if integer and int(value) != value:
        raise ResolumeAdapterError(f"Campo inválido {label}: se esperaba un entero.")
    return int(value) if integer else float(value)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResolumeAdapterError(f"Campo inválido {label}: se esperaba texto no vacío.")
    return value.strip()


def _rect_from_cabinets(cabinets: list[dict[str, Any]]) -> dict[str, int] | None:
    if not cabinets:
        return None
    x0 = min(c["x"] for c in cabinets)
    y0 = min(c["y"] for c in cabinets)
    x1 = max(c["x"] + c["width"] for c in cabinets)
    y1 = max(c["y"] + c["height"] for c in cabinets)
    return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}


def _area(rect: Mapping[str, int | float]) -> float:
    return max(0.0, float(rect["width"])) * max(0.0, float(rect["height"]))


def _intersection(a: Mapping[str, int | float], b: Mapping[str, int | float]) -> float:
    x0 = max(float(a["x"]), float(b["x"]))
    y0 = max(float(a["y"]), float(b["y"]))
    x1 = min(float(a["x"]) + float(a["width"]), float(b["x"]) + float(b["width"]))
    y1 = min(float(a["y"]) + float(a["height"]), float(b["y"]) + float(b["height"]))
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _same_rect(a: Mapping[str, int | float], b: Mapping[str, int | float], tolerance: float = 1.0) -> bool:
    return all(abs(float(a[key]) - float(b[key])) <= tolerance for key in ("x", "y", "width", "height"))


def _rect_from_points(points: Any, label: str) -> dict[str, float]:
    if not isinstance(points, list) or len(points) < 3:
        raise ResolumeAdapterError(f"{label} debe contener al menos tres puntos.")
    parsed: list[tuple[float, float]] = []
    for index, point in enumerate(points, 1):
        if not isinstance(point, list) or len(point) < 2:
            raise ResolumeAdapterError(f"{label}[{index}] no es un punto [x, y].")
        parsed.append((float(_number(point[0], f"{label}[{index}][0]")), float(_number(point[1], f"{label}[{index}][1]"))))
    x0 = min(point[0] for point in parsed)
    y0 = min(point[1] for point in parsed)
    x1 = max(point[0] for point in parsed)
    y1 = max(point[1] for point in parsed)
    return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}


def _layout_regions(source: str | Path | Mapping[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    raw, path = _read_json(source)
    regions = raw.get("regions")
    source_key = "regions"
    if not isinstance(regions, list):
        regions = raw.get("slices")
        source_key = "slices"
    if not isinstance(regions, list):
        raise ResolumeAdapterError("El reporte INSTAR no contiene regions ni slices.")
    result: list[dict[str, Any]] = []
    for index, region in enumerate(regions, 1):
        if not isinstance(region, dict):
            raise ResolumeAdapterError(f"La entrada INSTAR {source_key}[{index}] no es un objeto JSON.")
        name = _text(region.get("name"), f"{source_key}[{index}].name")
        bounds = region.get("bounds")
        if isinstance(bounds, dict):
            rect = {key: _number(bounds.get(key), f"{source_key}[{index}].bounds.{key}") for key in ("x", "y", "width", "height")}
        elif source_key == "slices":
            rect = _rect_from_points(region.get("input_points"), f"slices[{index}].input_points")
        else:
            raise ResolumeAdapterError(f"La región INSTAR {name!r} no contiene bounds.")
        if rect["width"] <= 0 or rect["height"] <= 0:
            raise ResolumeAdapterError(f"La región INSTAR {name!r} tiene dimensiones no positivas.")
        result.append({"name": name, "bounds": rect})
    return result, path


def import_pixel_peeker_routing(
    interchange: str | Path | Mapping[str, Any],
    *,
    layout_report: str | Path | Mapping[str, Any] | None = None,
    tolerance: float = 1.0,
) -> dict[str, Any]:
    """Normaliza un intercambio y opcionalmente lo cruza con regiones INSTAR.

    El resultado tiene tres niveles deliberadamente separados:

    * ``import_status``: el JSON fue leído y validado;
    * ``geometry_status``: puertos y superficies tienen una correspondencia
      geométrica inequívoca;
    * ``physical_status``: siempre ``UNVERIFIED`` hasta contrastar el hardware.
    """

    if tolerance < 0:
        raise ResolumeAdapterError("La tolerancia geométrica no puede ser negativa.")
    raw, interchange_path = _read_json(interchange)
    if raw.get("format") != INTERCHANGE_FORMAT:
        raise ResolumeAdapterError(
            f"Formato no soportado: {raw.get('format')!r}; se esperaba {INTERCHANGE_FORMAT!r}."
        )
    wall = raw.get("wall")
    processors = raw.get("processors")
    if not isinstance(wall, dict) or not isinstance(processors, list):
        raise ResolumeAdapterError("El intercambio debe contener wall y processors.")
    canvas = {
        "width": int(_number(wall.get("widthPx"), "wall.widthPx", integer=True)),
        "height": int(_number(wall.get("heightPx"), "wall.heightPx", integer=True)),
    }
    if canvas["width"] <= 0 or canvas["height"] <= 0:
        raise ResolumeAdapterError("El canvas del intercambio debe tener dimensiones positivas.")

    normalized_processors: list[dict[str, Any]] = []
    port_entries: list[dict[str, Any]] = []
    for p_index, processor in enumerate(processors, 1):
        if not isinstance(processor, dict):
            raise ResolumeAdapterError(f"processors[{p_index}] no es un objeto JSON.")
        p_name = _text(processor.get("name"), f"processors[{p_index}].name")
        p_ports = processor.get("ports")
        if not isinstance(p_ports, list):
            raise ResolumeAdapterError(f"El procesador {p_name!r} no contiene ports.")
        normalized_ports: list[dict[str, Any]] = []
        for port_index, port in enumerate(p_ports, 1):
            if not isinstance(port, dict):
                raise ResolumeAdapterError(f"{p_name}.ports[{port_index}] no es un objeto JSON.")
            label = _text(port.get("label"), f"{p_name}.ports[{port_index}].label")
            cabinets_value = port.get("cabinets", [])
            if not isinstance(cabinets_value, list):
                raise ResolumeAdapterError(f"El puerto {p_name}/{label} no contiene cabinets como lista.")
            cabinets: list[dict[str, Any]] = []
            for cabinet_index, cabinet in enumerate(cabinets_value, 1):
                if not isinstance(cabinet, dict):
                    raise ResolumeAdapterError(f"{p_name}/{label}.cabinets[{cabinet_index}] no es un objeto JSON.")
                cabinets.append({
                    "order": int(_number(cabinet.get("order"), f"{p_name}/{label}.cabinets[{cabinet_index}].order", integer=True)),
                    "id": _text(cabinet.get("id"), f"{p_name}/{label}.cabinets[{cabinet_index}].id"),
                    "model": _text(cabinet.get("model"), f"{p_name}/{label}.cabinets[{cabinet_index}].model"),
                    "x": int(_number(cabinet.get("xPx"), f"{p_name}/{label}.cabinets[{cabinet_index}].xPx", integer=True)),
                    "y": int(_number(cabinet.get("yPx"), f"{p_name}/{label}.cabinets[{cabinet_index}].yPx", integer=True)),
                    "width": int(_number(cabinet.get("widthPx"), f"{p_name}/{label}.cabinets[{cabinet_index}].widthPx", integer=True)),
                    "height": int(_number(cabinet.get("heightPx"), f"{p_name}/{label}.cabinets[{cabinet_index}].heightPx", integer=True)),
                })
            bounds = _rect_from_cabinets(cabinets)
            normalized_port = {
                "label": label,
                "link_speed_gbps": _number(port.get("linkSpeedGbps"), f"{p_name}/{label}.linkSpeedGbps"),
                "capacity_px": int(_number(port.get("capacityPx"), f"{p_name}/{label}.capacityPx", integer=True)),
                "used_px": int(_number(port.get("usedPx"), f"{p_name}/{label}.usedPx", integer=True)),
                "utilisation_pct": int(_number(port.get("utilisationPct"), f"{p_name}/{label}.utilisationPct", integer=True)),
                "cabinets": cabinets,
                "bounds": bounds,
            }
            normalized_ports.append(normalized_port)
            if bounds is not None:
                port_entries.append({"processor": p_name, "port": normalized_port})
        normalized_processors.append({
            "name": p_name,
            "model": _text(processor.get("model"), f"processors[{p_index}].model"),
            "manufacturer": _text(processor.get("manufacturer"), f"processors[{p_index}].manufacturer"),
            "device_capacity_px": int(_number(processor.get("deviceCapacityPx"), f"processors[{p_index}].deviceCapacityPx", integer=True)),
            "used_px": int(_number(processor.get("usedPx"), f"processors[{p_index}].usedPx", integer=True)),
            "ports": normalized_ports,
        })

    matches: list[dict[str, Any]] = []
    unmatched_ports: list[str] = []
    ambiguous_ports: list[str] = []
    unmatched_regions: list[str] = []
    conflicting_regions: dict[str, list[str]] = {}
    regions: list[dict[str, Any]] = []
    layout_path: str | None = None
    if layout_report is not None:
        regions, layout_path = _layout_regions(layout_report)
        used_region_names: set[str] = set()
        for entry in port_entries:
            processor = entry["processor"]
            port = entry["port"]
            port_id = f"{processor}/{port['label']}"
            candidates: list[tuple[dict[str, Any], str, float]] = []
            for region in regions:
                overlap = _intersection(port["bounds"], region["bounds"])
                minimum_area = min(_area(port["bounds"]), _area(region["bounds"]))
                if _same_rect(port["bounds"], region["bounds"], tolerance):
                    candidates.append((region, "exact_geometry", 1.0))
                elif minimum_area and overlap / minimum_area >= 0.99:
                    candidates.append((region, "contained_geometry", round(overlap / minimum_area, 6)))
            if len(candidates) == 1:
                region, method, score = candidates[0]
                if region["name"] in used_region_names:
                    conflicting_regions.setdefault(region["name"], []).append(port_id)
                    ambiguous_ports.append(port_id)
                    continue
                used_region_names.add(region["name"])
                matches.append({
                    "processor": processor,
                    "port": port["label"],
                    "surface": region["name"],
                    "method": method,
                    "score": score,
                    "bounds": port["bounds"],
                    "cabinet_count": len(port["cabinets"]),
                })
            elif len(candidates) > 1:
                ambiguous_ports.append(port_id)
            else:
                unmatched_ports.append(port_id)
        unmatched_regions = [region["name"] for region in regions if region["name"] not in used_region_names]
        geometry_status = "GEOMETRIC_MATCH" if not unmatched_ports and not ambiguous_ports and not unmatched_regions and not conflicting_regions and bool(matches) else "PARTIAL_MATCH"
        validation_status = "PASS" if geometry_status == "GEOMETRIC_MATCH" else "REVIEW"
    else:
        geometry_status = "NOT_COMPARED"
        validation_status = "REVIEW"

    return {
        "schema_version": "0.1",
        "map_type": "InstarProcessorRoutingImport",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"interchange": interchange_path, "layout_report": layout_path},
        "input_format": raw["format"],
        "project": raw.get("project", {}),
        "canvas": canvas,
        "processors": normalized_processors,
        "comparison": {
            "geometry_status": geometry_status,
            "matches": matches,
            "unmatched_ports": unmatched_ports,
            "ambiguous_ports": ambiguous_ports,
            "unmatched_regions": unmatched_regions,
            "conflicting_regions": conflicting_regions,
            "tolerance_px": tolerance,
        },
        "status": {
            "import_status": "IMPORTED",
            "geometry_status": geometry_status,
            "physical_status": "UNVERIFIED",
        },
        "validation": {
            "status": validation_status,
            "errors": [],
            "warnings": [
                "La coincidencia de geometría no demuestra el patch físico ni el orden del cableado en el venue.",
            ],
        },
        "limitations": [
            "El intercambio no sustituye una configuración .scr/.vmp ni un snapshot del procesador.",
            "Los bounds por puerto se derivan de sus gabinetes; no se inventan cuando el puerto está vacío.",
            "La imagen/PDF sigue describiendo layout, no routing; ambos datos deben mantenerse separados.",
        ],
    }


def write_processor_routing_report(report: dict[str, Any], path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def processor_routing_text_report(report: Mapping[str, Any]) -> str:
    comparison = report.get("comparison") or {}
    status = report.get("status") or {}
    processors = report.get("processors") or []
    ports = [port for processor in processors for port in processor.get("ports", []) if port.get("bounds")]
    return "\n".join([
        "RESOLUME_ADAPTER INSTAR PROCESSOR ROUTING",
        "===========================================",
        f"Intercambio: {report.get('source', {}).get('interchange')}",
        f"Procesadores: {len(processors)}",
        f"Puertos con geometría: {len(ports)}",
        f"Importación: {status.get('import_status', 'UNKNOWN')}",
        f"Geometría: {status.get('geometry_status', comparison.get('geometry_status', 'UNKNOWN'))}",
        f"Hardware: {status.get('physical_status', 'UNVERIFIED')}",
        f"Validación: {report.get('validation', {}).get('status', 'REVIEW')}",
        f"Coincidencias: {len(comparison.get('matches') or [])}",
        f"Puertos sin coincidencia: {len(comparison.get('unmatched_ports') or [])}",
        f"Regiones sin coincidencia: {len(comparison.get('unmatched_regions') or [])}",
        f"Conflictos de región: {len(comparison.get('conflicting_regions') or {})}",
    ])

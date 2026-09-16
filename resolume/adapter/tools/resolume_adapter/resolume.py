"""Auditor de composiciones Resolume en modo lectura."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .diagnose import diagnose_file
from .media import ResolumeAdapterError


def _int_attribute(element: ElementTree.Element | None, name: str) -> int | None:
    if element is None:
        return None
    try:
        return int(element.attrib[name])
    except (KeyError, TypeError, ValueError):
        return None


def _float_attribute(element: ElementTree.Element | None, name: str) -> float | None:
    if element is None:
        return None
    try:
        return float(element.attrib[name])
    except (KeyError, TypeError, ValueError):
        return None


def _path_key(value: str) -> str:
    return value.replace("/", "\\").casefold()


def _clip_media(clip: ElementTree.Element) -> list[tuple[str, str]]:
    """Devuelve (tipo, ruta) de las fuentes de archivo de un clip."""

    sources: list[tuple[str, str]] = []
    for source in clip.iter("VideoFormatReaderSource"):
        value = source.attrib.get("fileName")
        if value:
            sources.append(("video", value))

    if not sources:
        for video_file in clip.iter("VideoFile"):
            value = video_file.attrib.get("value")
            if value:
                sources.append(("video", value))

    for source in clip.iter("AudioFileSource"):
        value = source.attrib.get("FileName") or source.attrib.get("filename")
        if value:
            sources.append(("audio", value))

    return sources


def _clip_name(clip: ElementTree.Element, index: int) -> str:
    name_param = clip.find("./Params/Param[@name='Name']")
    if name_param is not None:
        value = name_param.attrib.get("value") or name_param.attrib.get("default")
        if value:
            return value
    return clip.attrib.get("name") or f"Clip {index}"


def _clip_duration_ms(clip: ElementTree.Element) -> float | None:
    position = clip.find("./Transport/Params/ParamRange[@name='Position']")
    if position is None:
        return None

    value_range = position.find("./ValueRange[@name='minMax']")
    duration_ms = _float_attribute(value_range, "max")
    if duration_ms is not None and duration_ms > 0:
        return duration_ms

    timeline = position.find("./PhaseSourceTransportTimeline")
    duration_ms = _float_attribute(timeline, "defaultMillisecondsDuration")
    if duration_ms is not None and duration_ms > 0:
        return duration_ms

    duration_source = position.find("./DurationSource")
    raw_duration = duration_source.attrib.get("defaultDuration") if duration_source is not None else None
    if raw_duration:
        match = re.fullmatch(r"\s*([0-9.+-eE]+)s\s*", raw_duration)
        if match:
            try:
                duration_ms = float(match.group(1)) * 1000.0
            except ValueError:
                duration_ms = None
            if duration_ms is not None and duration_ms > 0:
                return duration_ms
    return None


def _clip_transport(clip: ElementTree.Element) -> dict[str, Any]:
    position = clip.find("./Transport/Params/ParamRange[@name='Position']")
    timeline = position.find("./PhaseSourceTransportTimeline") if position is not None else None
    beats = timeline.find("./Beats_double") if timeline is not None else None
    duration_ms = _clip_duration_ms(clip)
    result: dict[str, Any] = {
        "duration_ms": round(duration_ms, 6) if duration_ms is not None else None,
        "current_position_ms": _float_attribute(position, "value"),
        "transport_type": (
            clip.find("./Params/Param[@name='TransportType']").attrib.get("value")
            if clip.find("./Params/Param[@name='TransportType']") is not None
            else None
        ),
        "default_beats_duration": _float_attribute(timeline, "defaultBeatsDuration"),
        "detected_tempo": _float_attribute(beats, "detectedTempo"),
        "manual_tempo": _float_attribute(beats, "manualTempo"),
        "detected_beats": _int_attribute(beats, "numDetectedBeats"),
        "manual_beats": _int_attribute(beats, "numManualBeats"),
    }
    for key in ("current_position_ms", "default_beats_duration", "detected_tempo", "manual_tempo"):
        if result[key] is not None:
            result[key] = round(float(result[key]), 6)
    return result


def _clip_cues(clip: ElementTree.Element, duration_ms: float | None) -> dict[str, Any]:
    points = clip.find("./Transport/Params/ParamPoints6[@name='CuePoints']")
    cues: list[dict[str, Any]] = []
    empty_slots: list[int] = []
    selected_position_ms = _float_attribute(points, "value")
    if points is None:
        return {
            "selected_position_ms": None,
            "cues": cues,
            "empty_slots": empty_slots,
        }

    for param in points.findall("./Param"):
        match = re.fullmatch(r"Position(\d+)", param.attrib.get("name", ""))
        if not match:
            continue
        slot = int(match.group(1))
        position_ms = _float_attribute(param, "value")
        if position_ms is None or position_ms < 0:
            empty_slots.append(slot)
            continue
        cue: dict[str, Any] = {
            "slot": slot,
            "position_ms": round(position_ms, 6),
            "position_s": round(position_ms / 1000.0, 6),
        }
        if duration_ms and duration_ms > 0:
            cue["normalized"] = round(position_ms / duration_ms, 6)
            cue["out_of_range"] = position_ms > duration_ms
        else:
            cue["normalized"] = None
            cue["out_of_range"] = None
        cues.append(cue)

    if selected_position_ms is not None:
        selected_position_ms = round(selected_position_ms, 6)
    return {
        "selected_position_ms": selected_position_ms,
        "cues": sorted(cues, key=lambda cue: cue["slot"]),
        "empty_slots": sorted(empty_slots),
    }


def _layer_transition_durations(root: ElementTree.Element) -> dict[int, float]:
    durations: dict[int, float] = {}
    for layer in root.iter("Layer"):
        layer_index = _int_attribute(layer, "layerIndex")
        transition = layer.find("./ClipTransition/Params/ParamRange[@name='Duration']")
        duration_s = _float_attribute(transition, "value")
        if layer_index is not None and duration_s is not None and duration_s >= 0:
            durations[layer_index] = round(duration_s * 1000.0, 6)
    return durations


def build_cue_map(root: ElementTree.Element, composition_path: str | Path) -> dict[str, Any]:
    """Extrae cues y transporte de una composición Resolume sin modificarla."""

    layer_transitions = _layer_transition_durations(root)
    clips: list[dict[str, Any]] = []
    cue_count = 0
    clips_with_cues = 0
    for index, clip in enumerate(root.iter("Clip"), start=1):
        layer = _int_attribute(clip, "layerIndex")
        column = _int_attribute(clip, "columnIndex")
        transport = _clip_transport(clip)
        duration_ms = transport.get("duration_ms")
        cue_data = _clip_cues(clip, duration_ms)
        cue_count += len(cue_data["cues"])
        if cue_data["cues"]:
            clips_with_cues += 1
        item: dict[str, Any] = {
            "clip_index": index,
            "unique_id": clip.attrib.get("uniqueId"),
            "name": _clip_name(clip, index),
            "layer": layer,
            "column": column,
            "media": [
                {"type": media_type, "path": raw_path}
                for media_type, raw_path in _clip_media(clip)
            ],
            "transport": transport,
            "cues": cue_data["cues"],
            "empty_cue_slots": cue_data["empty_slots"],
            "selected_cue_position_ms": cue_data["selected_position_ms"],
        }
        if layer in layer_transitions:
            item["layer_transition_ms"] = layer_transitions[layer]
        clips.append(item)

    return {
        "schema_version": "0.1",
        "map_type": "ResolumeCueMap",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(Path(composition_path).expanduser().resolve()),
        "read_only": True,
        "composition": _composition_metadata(root),
        "statistics": {
            "clips": len(clips),
            "clips_with_cues": clips_with_cues,
            "cue_points": cue_count,
            "layers_with_transition": len(layer_transitions),
        },
        "clips": clips,
        "limitations": [
            "Los nombres semánticos de los cues (inicio, build, drop, salida) aún deben ser asignados por una persona o por NAYADE.",
            "Los cues se extraen del .avc; esta primera versión no modifica la composición ni crea nuevos cues.",
        ],
    }


def extract_cue_map(composition_path: str | Path) -> dict[str, Any]:
    """Lee una composición Resolume y devuelve su mapa de cues."""

    path = Path(composition_path).expanduser().resolve()
    if not path.is_file():
        raise ResolumeAdapterError(f"No se encontró la composición Resolume: {path}")
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise ResolumeAdapterError(f"La composición no es XML válido: {path}") from exc
    if root.tag != "Composition":
        raise ResolumeAdapterError(f"El archivo no parece una composición Resolume (.avc): raíz {root.tag!r}")
    return build_cue_map(root, path)


def cue_text_report(cue_map: dict[str, Any]) -> str:
    """Genera una salida breve del mapa de cues para PowerShell."""

    lines = [
        "RESOLUME_ADAPTER RESOLUME CUES",
        "====================",
        f"Composición: {cue_map['input']}",
        f"Nombre: {cue_map['composition'].get('name') or 'desconocido'}",
        f"Clips: {cue_map['statistics']['clips']}",
        f"Clips con cues: {cue_map['statistics']['clips_with_cues']}",
        f"Cues encontrados: {cue_map['statistics']['cue_points']}",
        "",
        "Cues:",
    ]
    for clip in cue_map["clips"]:
        if not clip["cues"]:
            continue
        location = f"L{clip.get('layer')} C{clip.get('column')}"
        cues = ", ".join(
            f"{cue['slot']}={cue['position_s']:.3f}s"
            for cue in clip["cues"]
        )
        transition = clip.get("layer_transition_ms")
        transition_label = f", transición capa={transition:.0f}ms" if transition is not None else ""
        lines.append(f"  [{location}] {clip['name']}: {cues}{transition_label}")
    return "\n".join(lines)


def write_cue_map(cue_map: dict[str, Any], path: str | Path) -> Path:
    """Guarda un mapa de cues en JSON, sin tocar la composición de origen."""

    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(cue_map, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def _composition_metadata(root: ElementTree.Element) -> dict[str, Any]:
    info = root.find("CompositionInfo")
    version = root.find("versionInfo")
    return {
        "name": (info.attrib.get("name") if info is not None else None) or root.attrib.get("name"),
        "description": info.attrib.get("description") if info is not None else None,
        "width": _int_attribute(info, "width"),
        "height": _int_attribute(info, "height"),
        "version": {
            "product": version.attrib.get("name") if version is not None else None,
            "major": _int_attribute(version, "majorVersion"),
            "minor": _int_attribute(version, "minorVersion"),
            "micro": _int_attribute(version, "microVersion"),
            "revision": _int_attribute(version, "revision"),
        },
        "declared": {
            "decks": _int_attribute(root, "numDecks"),
            "layers": _int_attribute(root, "numLayers"),
            "columns": _int_attribute(root, "numColumns"),
            "current_deck_index": _int_attribute(root, "currentDeckIndex"),
        },
    }


def _extract_media(root: ElementTree.Element) -> tuple[list[dict[str, Any]], int]:
    by_key: dict[str, dict[str, Any]] = {}
    capture_sources = 0
    for clip in root.iter("Clip"):
        layer = _int_attribute(clip, "layerIndex")
        column = _int_attribute(clip, "columnIndex")
        for media_type, raw_path in _clip_media(clip):
            key = _path_key(raw_path)
            item = by_key.setdefault(
                key,
                {
                    "path": raw_path,
                    "media_type": media_type,
                    "occurrences": 0,
                    "locations": [],
                },
            )
            item["occurrences"] += 1
            item["locations"].append({"layer": layer, "column": column})

        for source in clip.iter("VideoSource"):
            if source.attrib.get("type") == "CaptureDeviceVideoSource":
                capture_sources += 1

    return list(by_key.values()), capture_sources


def _action_plan(media: list[dict[str, Any]], capture_sources: int) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for index, item in enumerate(media, start=1):
        diagnosis = item.get("diagnosis") or {}
        if not item["exists"]:
            actions.append(
                {
                    "action_id": f"missing-media-{index:03d}",
                    "risk": "REVIEW",
                    "operation": "relocate_or_restore_media",
                    "target": item["path"],
                    "reason": "La composición referencia un archivo que no está disponible en su ruta guardada.",
                    "requires_confirmation": True,
                    "reversible": True,
                }
            )
            continue

        video = diagnosis.get("video", {})
        if str(video.get("codec") or "").lower() != "dxv":
            actions.append(
                {
                    "action_id": f"prepare-dxv-{index:03d}",
                    "risk": "SAFE",
                    "operation": "create_derived_media",
                    "target": item["path"],
                    "reason": "El host objetivo es Resolume y el medio no está en DXV.",
                    "parameters": {"codec_profile": "resolume-dxv3-normal"},
                    "requires_confirmation": False,
                    "reversible": True,
                }
            )

        if diagnosis.get("overall_status") == "WARN":
            actions.append(
                {
                    "action_id": f"review-media-{index:03d}",
                    "risk": "REVIEW",
                    "operation": "review_media_warnings",
                    "target": item["path"],
                    "reason": "El diagnóstico de media contiene advertencias que pueden afectar la reproducción.",
                    "requires_confirmation": True,
                    "reversible": True,
                }
            )

    if capture_sources:
        actions.append(
            {
                "action_id": "live-inputs-001",
                "risk": "BLOCKED",
                "operation": "offline_media_preparation",
                "target": "capture-devices",
                "reason": "Las entradas de captura no pueden diagnosticarse como archivos ni pre-renderizarse offline.",
                "requires_confirmation": False,
                "reversible": False,
            }
        )
    return actions


def run_resolume_audit(
    composition_path: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    target_fps: float | None = None,
    target_width: int | None = None,
    target_height: int | None = None,
    max_samples: int = 300,
    skip_media: bool = False,
) -> dict[str, Any]:
    """Audita un .avc sin modificarlo ni modificar Resolume."""

    path = Path(composition_path).expanduser().resolve()
    if not path.is_file():
        raise ResolumeAdapterError(f"No se encontró la composición Resolume: {path}")

    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise ResolumeAdapterError(f"La composición no es XML válido: {path}") from exc

    if root.tag != "Composition":
        raise ResolumeAdapterError(f"El archivo no parece una composición Resolume (.avc): raíz {root.tag!r}")

    media, capture_sources = _extract_media(root)
    statuses: Counter[str] = Counter()
    for item in media:
        item_path = Path(item["path"]).expanduser()
        item["exists"] = item_path.is_file()
        if not item["exists"]:
            item["status"] = "FAIL"
            item["error"] = "Archivo no encontrado en la ruta guardada."
            statuses["FAIL"] += 1
            continue
        if skip_media:
            item["status"] = "NOT_ANALYZED"
            statuses["NOT_ANALYZED"] += 1
            continue

        try:
            diagnosis = diagnose_file(
                item_path,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                target_fps=target_fps,
                target_width=target_width,
                target_height=target_height,
                max_samples=max_samples,
            )
        except ResolumeAdapterError as exc:
            item["status"] = "FAIL"
            item["error"] = str(exc)
            statuses["FAIL"] += 1
            continue

        item["status"] = diagnosis.get("overall_status", "WARN")
        item["diagnosis"] = diagnosis
        statuses[item["status"]] += 1

    if statuses["FAIL"]:
        overall_status = "FAIL"
    elif statuses["WARN"]:
        overall_status = "WARN"
    elif statuses["NOT_ANALYZED"]:
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    return {
        "schema_version": "0.1",
        "tool": "RESOLUME_ADAPTER Resolume Audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(path),
        "read_only": True,
        "composition": _composition_metadata(root),
        "statistics": {
            "clips": sum(1 for _ in root.iter("Clip")),
            "media_files": len(media),
            "capture_sources": capture_sources,
            "status_counts": dict(statuses),
        },
        "target": {
            "fps": target_fps,
            "width": target_width,
            "height": target_height,
        },
        "overall_status": overall_status,
        "media": media,
        "action_plan": _action_plan(media, capture_sources),
        "limitations": [
            "El auditor lee el archivo .avc; no observa por sí solo Advanced Output ni el procesador LED.",
            "La ruta guardada puede ser válida sólo en el equipo donde se creó la composición.",
            "El diagnóstico de media no confirma problemas de PWM, cableado, tearing o frecuencia de pantalla.",
        ],
    }


def text_report(report: dict[str, Any]) -> str:
    """Convierte el informe a una salida breve para PowerShell."""

    composition = report["composition"]
    lines = [
        "RESOLUME_ADAPTER RESOLUME AUDIT",
        "=====================",
        f"Composición: {report['input']}",
        f"Nombre: {composition.get('name') or 'desconocido'}",
        f"Canvas: {composition.get('width')} × {composition.get('height')}",
        f"Estado: {report['overall_status']}",
        f"Clips: {report['statistics']['clips']}",
        f"Archivos únicos: {report['statistics']['media_files']}",
        f"Capturas: {report['statistics']['capture_sources']}",
        "",
        "Media:",
    ]
    for item in report["media"]:
        detail = item.get("error") or (item.get("diagnosis", {}).get("video", {}).get("codec") if item.get("diagnosis") else "no analizado")
        lines.append(f"  [{item['status']}] {Path(item['path']).name}: {detail} ({item['occurrences']} uso(s))")
    lines.extend(["", "Plan:"])
    for action in report["action_plan"]:
        lines.append(f"  [{action['risk']}] {action['operation']}: {action['target']}")
    return "\n".join(lines)


def write_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# Advanced Output / INSTAR mapping
# ---------------------------------------------------------------------------

ADVANCED_OUTPUT_MAP_VERSION = "0.1"
MAPPING_PLAN_VERSION = "0.1"


def _param_value(parent: ElementTree.Element | None, name: str) -> str | None:
    """Lee tanto Param como ParamChoice sin asumir el tipo de parámetro."""

    if parent is None:
        return None
    for tag in ("Param", "ParamChoice", "ParamRange"):
        item = parent.find(f"./{tag}[@name='{name}']")
        if item is not None:
            return item.attrib.get("value") or item.attrib.get("default")
    return None


def _bool_value(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rounded(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None else None


def _rect_data(rect: ElementTree.Element | None) -> dict[str, Any] | None:
    """Normaliza un rectángulo Resolume y conserva sus cuatro puntos."""

    if rect is None:
        return None
    points: list[dict[str, float]] = []
    for point in rect.findall("./v"):
        x = _number(point.attrib.get("x"))
        y = _number(point.attrib.get("y"))
        if x is None or y is None:
            continue
        points.append({"x": _rounded(x) or 0.0, "y": _rounded(y) or 0.0})
    if not points:
        return None

    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    width = max(0.0, x_max - x_min)
    height = max(0.0, y_max - y_min)
    axis_aligned = len(points) == 4 and all(
        point["x"] in {x_min, x_max} and point["y"] in {y_min, y_max}
        for point in points
    )
    return {
        "orientation": int(_number(rect.attrib.get("orientation")) or 0),
        "points": points,
        "bounds": {
            "x": _rounded(x_min),
            "y": _rounded(y_min),
            "width": _rounded(width),
            "height": _rounded(height),
        },
        "axis_aligned": axis_aligned,
    }


def _bounds(rect: dict[str, Any] | None) -> dict[str, float] | None:
    if not rect:
        return None
    return rect.get("bounds")


def _warper_data(slice_element: ElementTree.Element) -> dict[str, Any]:
    warper = slice_element.find("./Warper")
    params = warper.find("./Params") if warper is not None else None
    bezier = warper.find("./BezierWarper") if warper is not None else None
    homography = warper.find("./Homography") if warper is not None else None
    src = _rect_data(homography.find("./src") if homography is not None else None)
    dst = _rect_data(homography.find("./dst") if homography is not None else None)
    has_non_identity_homography = False
    if src and dst and len(src["points"]) == len(dst["points"]):
        has_non_identity_homography = any(
            abs(a[axis] - b[axis]) > 0.01
            for a, b in zip(src["points"], dst["points"])
            for axis in ("x", "y")
        )

    point_mode = _param_value(params, "Point Mode")
    has_active_warp = has_non_identity_homography or point_mode not in {None, "PM_LINEAR"}
    return {
        "point_mode": point_mode,
        "flip": _number(_param_value(params, "Flip")),
        "bezier_control_width": int(_number(bezier.attrib.get("controlWidth")) or 0) if bezier is not None else None,
        "bezier_control_height": int(_number(bezier.attrib.get("controlHeight")) or 0) if bezier is not None else None,
        "has_bezier": bezier is not None,
        "has_active_warp": has_active_warp,
        "has_non_identity_homography": has_non_identity_homography,
        "homography_source": src,
        "homography_destination": dst,
    }


def _output_device_data(screen: ElementTree.Element) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    for wrapper in screen.findall("./OutputDevice"):
        device_element = next(iter(wrapper), None)
        if device_element is None:
            continue
        params = device_element.find("./Params")
        device: dict[str, Any] = {
            "type": device_element.tag.removeprefix("OutputDevice").casefold() or "unknown",
            "name": device_element.attrib.get("name"),
            "device_id": device_element.attrib.get("deviceId"),
            "id_hash": device_element.attrib.get("idHash"),
            "fullscreen": _bool_value(device_element.attrib.get("fullscreen")),
            "width": int(_number(device_element.attrib.get("width")) or 0) or None,
            "height": int(_number(device_element.attrib.get("height")) or 0) or None,
            "delay_s": _rounded(_number(_param_value(params, "Delay"))),
        }
        if device["width"] is None:
            device["width"] = int(_number(_param_value(params, "Width")) or 0) or None
        if device["height"] is None:
            device["height"] = int(_number(_param_value(params, "Height")) or 0) or None
        devices.append(device)
    return devices


def _normalise_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", _normalise_text(value)))


def _surface_hints(name: str, input_rect: dict[str, Any] | None) -> list[str]:
    hints: list[str] = []
    tokens = _tokens(name)
    if tokens & {"central", "centro", "main", "principal", "front", "frontal"}:
        hints.append("central")
    if tokens & {"totem", "pilar", "pillar", "vertical", "izq", "izquierda", "der", "derecha", "left", "right"}:
        hints.append("vertical")
    if tokens & {"arriba", "abajo", "top", "bottom", "banner", "techo", "ceiling"}:
        hints.append("horizontal")

    rect = _bounds(input_rect)
    if rect and rect.get("height", 0) > 0:
        aspect = rect["width"] / rect["height"]
        if aspect < 0.8 and "vertical" not in hints:
            hints.append("vertical")
        elif aspect > 3.2 and "horizontal" not in hints:
            hints.append("ultrawide")
        elif aspect > 1.35 and "horizontal" not in hints:
            hints.append("landscape")
        elif 0.8 <= aspect <= 1.25:
            hints.append("square")
    return list(dict.fromkeys(hints))


def _geometry_profile(slice_item: dict[str, Any]) -> dict[str, Any]:
    """Calcula el riesgo teórico de deformar una figura geométrica.

    La métrica compara el escalado horizontal y vertical entre InputRect y
    OutputRect. No sustituye una comprobación física de la pantalla: un
    procesador LED puede volver a escalar la señal después de Resolume.
    """

    input_dimensions = slice_item.get("input_dimensions") or {}
    output_dimensions = slice_item.get("output_dimensions") or {}
    input_width = float(input_dimensions.get("width") or 0)
    input_height = float(input_dimensions.get("height") or 0)
    output_width = float(output_dimensions.get("width") or 0)
    output_height = float(output_dimensions.get("height") or 0)
    if min(input_width, input_height, output_width, output_height) <= 0:
        return {
            "status": "UNKNOWN",
            "risk": "high",
            "assumes_square_pixels": True,
            "requires_geometry_test": True,
            "reason": "faltan dimensiones completas de InputRect u OutputRect",
        }

    scale_x = output_width / input_width
    scale_y = output_height / input_height
    scale_ratio = scale_x / scale_y if scale_y else 0.0
    deformation_percent = abs(scale_ratio - 1.0) * 100.0
    input_aspect = input_width / input_height
    output_aspect = output_width / output_height
    warper = slice_item.get("warper") or {}
    non_rectangular = not (slice_item.get("input") or {}).get("axis_aligned", True) or not (
        slice_item.get("output") or {}
    ).get("axis_aligned", True)
    has_warp = bool(warper.get("has_active_warp"))

    if non_rectangular or has_warp:
        status = "REVIEW"
        risk = "high"
        reason = "la geometría o el warper pueden deformar localmente la figura"
    elif deformation_percent <= 2.0:
        status = "PASS"
        risk = "low"
        reason = "InputRect y OutputRect conservan un escalado prácticamente uniforme"
    elif deformation_percent <= 5.0:
        status = "WARN"
        risk = "medium"
        reason = "hay una diferencia moderada entre el escalado horizontal y vertical"
    else:
        status = "FAIL"
        risk = "high"
        reason = "el escalado horizontal y vertical deformará círculos y cuadrados"

    return {
        "status": status,
        "risk": risk,
        "assumes_square_pixels": True,
        "requires_geometry_test": status != "PASS",
        "input_aspect_ratio": _rounded(input_aspect),
        "output_aspect_ratio": _rounded(output_aspect),
        "scale_x": _rounded(scale_x),
        "scale_y": _rounded(scale_y),
        "circle_output_aspect_ratio": _rounded(scale_ratio),
        "deformation_percent": _rounded(deformation_percent, 3),
        "has_active_warp": has_warp,
        "non_rectangular_geometry": non_rectangular,
        "reason": reason,
    }


def _rect_signature(rect: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    bounds = _bounds(rect)
    if not bounds:
        return None
    return tuple(round(float(bounds.get(key, 0.0)), 2) for key in ("x", "y", "width", "height"))


def _intersection_area(first: dict[str, Any] | None, second: dict[str, Any] | None) -> float:
    first_bounds = _bounds(first)
    second_bounds = _bounds(second)
    if not first_bounds or not second_bounds:
        return 0.0
    left = max(first_bounds["x"], second_bounds["x"])
    top = max(first_bounds["y"], second_bounds["y"])
    right = min(first_bounds["x"] + first_bounds["width"], second_bounds["x"] + second_bounds["width"])
    bottom = min(first_bounds["y"] + first_bounds["height"], second_bounds["y"] + second_bounds["height"])
    return max(0.0, right - left) * max(0.0, bottom - top)


def _advanced_output_version(root: ElementTree.Element) -> dict[str, Any]:
    version = root.find("./ScreenSetup/versionInfo")
    if version is None:
        version = root.find("./versionInfo")
    return {
        "product": version.attrib.get("name") if version is not None else None,
        "major": int(_number(version.attrib.get("majorVersion")) or 0) if version is not None else None,
        "minor": int(_number(version.attrib.get("minorVersion")) or 0) if version is not None else None,
        "micro": int(_number(version.attrib.get("microVersion")) or 0) if version is not None else None,
        "revision": int(_number(version.attrib.get("revision")) or 0) if version is not None else None,
    }


def _validate_advanced_output_map(output_map: dict[str, Any]) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    composition = output_map.get("composition") or {}
    comp_width = composition.get("width")
    comp_height = composition.get("height")
    seen_names: dict[str, list[str]] = {}
    input_signatures: dict[tuple[float, float, float, float], list[str]] = {}

    for screen in output_map.get("screens", []):
        if not screen.get("devices"):
            warnings.append({
                "code": "screen_without_output_device",
                "screen_id": screen.get("id"),
                "message": "La pantalla no declara un dispositivo físico, virtual o de salida.",
            })
        device_dimensions = [
            (device.get("width"), device.get("height"))
            for device in screen.get("devices", [])
            if device.get("width") and device.get("height")
        ]
        if device_dimensions:
            device_width, device_height = device_dimensions[0]
            for slice_item in screen.get("slices", []):
                output_bounds = _bounds(slice_item.get("output"))
                if not output_bounds:
                    continue
                if (
                    output_bounds["x"] < -0.01
                    or output_bounds["y"] < -0.01
                    or output_bounds["x"] + output_bounds["width"] > device_width + 0.01
                    or output_bounds["y"] + output_bounds["height"] > device_height + 0.01
                ):
                    warnings.append({
                        "code": "output_outside_declared_device",
                        "slice_id": slice_item.get("id"),
                        "message": "El OutputRect sale del tamaño declarado del dispositivo; puede ser crop intencional, preset antiguo o desajuste de salida.",
                    })
        for slice_item in screen.get("slices", []):
            name_key = _normalise_text(slice_item.get("name") or "")
            seen_names.setdefault(name_key, []).append(slice_item["id"])
            input_rect = slice_item.get("input")
            output_rect = slice_item.get("output")
            if not input_rect or not output_rect:
                errors.append({
                    "code": "slice_missing_geometry",
                    "slice_id": slice_item.get("id"),
                    "message": "La slice no contiene InputRect y OutputRect completos.",
                })
                continue
            signature = _rect_signature(input_rect)
            if signature:
                input_signatures.setdefault(signature, []).append(slice_item["id"])
            input_bounds = _bounds(input_rect)
            if comp_width and comp_height and input_bounds:
                if (
                    input_bounds["x"] < -0.01
                    or input_bounds["y"] < -0.01
                    or input_bounds["x"] + input_bounds["width"] > comp_width + 0.01
                    or input_bounds["y"] + input_bounds["height"] > comp_height + 0.01
                ):
                    warnings.append({
                        "code": "input_outside_composition",
                        "slice_id": slice_item.get("id"),
                        "message": "El InputRect sale del canvas de composición declarado; revisar recorte.",
                    })
            if not input_rect.get("axis_aligned") or not output_rect.get("axis_aligned"):
                warnings.append({
                    "code": "non_axis_aligned_geometry",
                    "slice_id": slice_item.get("id"),
                    "message": "La slice usa geometría no rectangular; la asignación por dimensión es aproximada.",
                })
            warper = slice_item.get("warper") or {}
            if warper.get("has_active_warp"):
                warnings.append({
                    "code": "warped_slice",
                    "slice_id": slice_item.get("id"),
                    "message": "La slice tiene warp; el tamaño calculado no describe toda la transformación física.",
                })
            geometry = slice_item.get("geometry") or {}
            if geometry.get("status") in {"WARN", "FAIL", "REVIEW", "UNKNOWN"}:
                warnings.append({
                    "code": "geometry_test_required",
                    "slice_id": slice_item.get("id"),
                    "deformation_percent": geometry.get("deformation_percent"),
                    "message": "Probar círculos y cuadrados en esta slice; el XML no garantiza geometría uniforme en la salida física.",
                })
        screen_slices = screen.get("slices", [])
        for index, first in enumerate(screen_slices):
            for second in screen_slices[index + 1:]:
                overlap_area = _intersection_area(first.get("output"), second.get("output"))
                if overlap_area > 0.5:
                    warnings.append({
                        "code": "output_overlap",
                        "slice_ids": [first.get("id"), second.get("id")],
                        "overlap_area_px": round(overlap_area, 3),
                        "message": "Dos OutputRect se superponen; puede ser intencional, pero no debe tratarse como asignación uno-a-uno.",
                    })

    for name, ids in seen_names.items():
        if name and len(ids) > 1:
            warnings.append({
                "code": "duplicate_slice_name",
                "slice_ids": ids,
                "message": "Hay varias slices con el mismo nombre; no usar el nombre como identificador único.",
            })
    for signature, ids in input_signatures.items():
        if len(ids) > 1:
            warnings.append({
                "code": "shared_input_rect",
                "slice_ids": ids,
                "message": "Varias slices consumen la misma zona del canvas; pueden ser copias o salidas paralelas.",
            })

    if errors:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"
    return {"status": status, "errors": errors, "warnings": warnings}


def build_advanced_output_map(root: ElementTree.Element, source_path: str | Path) -> dict[str, Any]:
    """Construye un modelo legible del preset Advanced Output sin modificarlo."""

    setup = root.find("./ScreenSetup")
    if setup is None:
        setup = root
    texture = setup.find("./CurrentCompositionTextureSize")
    comp_width = int(_number(texture.attrib.get("width")) or 0) if texture is not None else None
    comp_height = int(_number(texture.attrib.get("height")) or 0) if texture is not None else None
    screens: list[dict[str, Any]] = []
    flat_slices: list[dict[str, Any]] = []

    for screen_index, screen in enumerate(setup.findall("./screens/Screen"), start=1):
        screen_params = screen.find("./Params[@name='Params']")
        screen_name = _param_value(screen_params, "Name") or screen.attrib.get("name") or f"Screen {screen_index}"
        screen_item: dict[str, Any] = {
            "id": screen.attrib.get("uniqueId") or f"screen-{screen_index:03d}",
            "name": screen_name,
            "enabled": _bool_value(_param_value(screen_params, "Enabled"), True),
            "hidden": _bool_value(_param_value(screen_params, "Hidden")),
            "devices": _output_device_data(screen),
            "slices": [],
        }
        layers = screen.find("./layers")
        layer_elements = (
            [element for element in list(layers) if element.tag in {"Slice", "Polygon"}]
            if layers is not None
            else []
        )
        for slice_index, slice_element in enumerate(layer_elements, start=1):
            common = slice_element.find("./Params[@name='Common']")
            input_params = slice_element.find("./Params[@name='Input']")
            output_params = slice_element.find("./Params[@name='Output']")
            input_rect = _rect_data(slice_element.find("./InputRect"))
            output_rect = _rect_data(slice_element.find("./OutputRect"))
            slice_id = slice_element.attrib.get("uniqueId") or f"{screen_item['id']}:slice-{slice_index:03d}"
            slice_item: dict[str, Any] = {
                "id": slice_id,
                "screen_id": screen_item["id"],
                "screen_name": screen_name,
                "name": _param_value(common, "Name") or f"Slice {slice_index}",
                "enabled": _bool_value(_param_value(common, "Enabled"), True),
                "input_source": _param_value(input_params, "Input Source"),
                "input": input_rect,
                "output": output_rect,
                "warper": _warper_data(slice_element),
                "output_controls": {
                    "flip": _number(_param_value(output_params, "Flip")),
                    "is_key": _bool_value(_param_value(output_params, "Is Key")),
                    "black_background": _bool_value(_param_value(output_params, "Black BG")),
                    "soft_edge": _bool_value(_param_value(input_params, "SoftEdgeEnable")),
                },
                "hints": _surface_hints(_param_value(common, "Name") or "", input_rect),
            }
            if input_rect and _bounds(input_rect):
                dimensions = _bounds(input_rect)
                slice_item["input_dimensions"] = {
                    "width": dimensions["width"],
                    "height": dimensions["height"],
                    "aspect_ratio": _rounded(dimensions["width"] / dimensions["height"]) if dimensions["height"] else None,
                }
            if output_rect and _bounds(output_rect):
                dimensions = _bounds(output_rect)
                slice_item["output_dimensions"] = {
                    "width": dimensions["width"],
                    "height": dimensions["height"],
                    "aspect_ratio": _rounded(dimensions["width"] / dimensions["height"]) if dimensions["height"] else None,
                }
            slice_item["geometry"] = _geometry_profile(slice_item)
            screen_item["slices"].append(slice_item)
            flat_slices.append(slice_item)
        screens.append(screen_item)

    output_map: dict[str, Any] = {
        "schema_version": ADVANCED_OUTPUT_MAP_VERSION,
        "map_type": "ResolumeAdvancedOutputMap",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "source": {"path": str(Path(source_path).expanduser().resolve()), "preset_name": root.attrib.get("name")},
        "resolume": {"version": _advanced_output_version(root)},
        "composition": {"width": comp_width, "height": comp_height},
        "screens": screens,
        "slices": flat_slices,
        "statistics": {
            "screens": len(screens),
            "slices": len(flat_slices),
            "enabled_slices": sum(1 for item in flat_slices if item["enabled"]),
            "physical_outputs": sum(1 for screen in screens for device in screen["devices"] if device["type"] == "display"),
            "virtual_outputs": sum(1 for screen in screens for device in screen["devices"] if device["type"] == "virtual"),
            "warped_slices": sum(1 for item in flat_slices if (item.get("warper") or {}).get("has_active_warp")),
        },
        "limitations": [
            "El preset describe Advanced Output; no identifica por sí solo el modelo, pixel pitch, puertos o configuración interna del procesador LED.",
            "Input y Output se conservan por separado: Input es la región de composición y Output es la transformación final hacia la salida.",
            "La asignación de una visual a una slice es una sugerencia de INSTAR; este informe no edita .avc ni activa rutas en Resolume.",
        ],
    }
    input_groups: dict[tuple[float, float, float, float], str] = {}
    for slice_index, slice_item in enumerate(flat_slices, start=1):
        signature = _rect_signature(slice_item.get("input"))
        if signature is None:
            group_id = f"input-group-{slice_index:03d}"
        else:
            group_id = input_groups.setdefault(signature, f"input-group-{len(input_groups) + 1:03d}")
        slice_item["input_group_id"] = group_id
    output_map["statistics"]["input_groups"] = len({item["input_group_id"] for item in flat_slices})
    output_map["validation"] = _validate_advanced_output_map(output_map)
    return output_map


def extract_advanced_output_map(preset_path: str | Path) -> dict[str, Any]:
    """Lee un preset Advanced Output de Resolume en modo lectura."""

    path = Path(preset_path).expanduser().resolve()
    if not path.is_file():
        raise ResolumeAdapterError(f"No se encontró el preset Advanced Output: {path}")
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise ResolumeAdapterError(f"El preset Advanced Output no es XML válido: {path}") from exc
    if root.tag not in {"XmlState", "ScreenSetup"}:
        raise ResolumeAdapterError(f"El archivo no parece un preset Advanced Output: raíz {root.tag!r}")
    return build_advanced_output_map(root, path)


def _asset_path(item: dict[str, Any], catalog_root: str | None) -> Path | None:
    profile = item.get("profile") or item.get("clip_profile") or {}
    report = item.get("report") or {}
    source = profile.get("source") or {}
    raw = item.get("absolute_path") or source.get("path") or report.get("input") or item.get("path")
    if not raw:
        return None
    path = Path(str(raw)).expanduser()
    if not path.is_absolute() and catalog_root:
        path = Path(catalog_root).expanduser() / path
    return path.resolve()


def load_catalog_assets(catalog_path: str | Path) -> list[dict[str, Any]]:
    path = Path(catalog_path).expanduser().resolve()
    if not path.is_file():
        raise ResolumeAdapterError(f"No se encontró el catálogo INSTAR: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolumeAdapterError(f"No se pudo leer el catálogo INSTAR: {path}") from exc

    catalog_root = document.get("root") or document.get("media_root")
    raw_items = document.get("assets") if document.get("manifest_type") == "AssetManifest" else document.get("items")
    if not isinstance(raw_items, list):
        raise ResolumeAdapterError("El catálogo debe ser un informe INSTAR o un AssetManifest.")

    assets: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        report = item.get("report") or {}
        profile = item.get("profile") or item.get("clip_profile") or report.get("clip_profile") or {}
        technical = profile.get("technical") or report
        video = technical.get("video") or report.get("video") or {}
        width = _number(str(video.get("width")))
        height = _number(str(video.get("height")))
        source_path = _asset_path(item, catalog_root)
        if width is None or height is None or width <= 0 or height <= 0 or source_path is None:
            continue
        filename_text = " ".join(
            part for part in (
                str(source_path),
                str(profile.get("source", {}).get("filename", "")),
            ) if part
        )
        alpha = technical.get("alpha") or report.get("alpha") or {}
        alpha_encoded = alpha.get("encoded") if isinstance(alpha, dict) else None
        behavior = (profile.get("visual") or {}).get("behavior") or {}
        asset = {
            "asset_id": profile.get("profile_id") or item.get("profile_id") or f"asset-{index:04d}",
            "path": str(source_path),
            "filename": source_path.name,
            "status": item.get("status") or report.get("overall_status") or "UNKNOWN",
            "width": int(width),
            "height": int(height),
            "aspect_ratio": _rounded(width / height),
            "orientation": "portrait" if height > width else "landscape" if width > height else "square",
            "alpha": alpha_encoded,
            "tokens": sorted(_tokens(filename_text)),
            "behavior": behavior,
            "profile": profile,
        }
        assets.append(asset)
    return assets


def _asset_role_score(asset: dict[str, Any], hints: list[str], slice_name: str) -> tuple[float, list[str]]:
    asset_tokens = set(asset.get("tokens") or [])
    slice_tokens = _tokens(slice_name)
    reasons: list[str] = []
    score = 0.0
    semantic_tokens = asset_tokens & slice_tokens
    if semantic_tokens:
        score += 1.0
        reasons.append(f"coincide nombre: {', '.join(sorted(semantic_tokens))}")
    if "vertical" in hints and asset.get("orientation") == "portrait":
        score += 0.65
        reasons.append("orientación vertical")
    if "horizontal" in hints or "ultrawide" in hints:
        if asset.get("orientation") == "landscape":
            score += 0.25
            reasons.append("orientación horizontal")
    if "central" in hints and asset_tokens & {"central", "centro", "main", "full", "completo"}:
        score += 0.7
        reasons.append("indicio central/completo")
    return score, reasons


def _asset_behavior_score(asset: dict[str, Any], slice_item: dict[str, Any]) -> tuple[float, list[str]]:
    """Prioriza material repetible para superficies extremas sin ocultar la revisión."""

    behavior = asset.get("behavior") or {}
    hints = set(slice_item.get("hints") or [])
    if "vertical" in hints:
        axis = "vertical"
    elif "horizontal" in hints or "ultrawide" in hints:
        axis = "horizontal"
    else:
        return 0.0, []

    signals = [
        (behavior.get("pattern") or {}).get(axis) or {},
        (behavior.get("marquee") or {}).get(axis) or {},
    ]
    usable = [item for item in signals if item.get("score") is not None]
    if not usable:
        return 0.0, []
    selected = max(usable, key=lambda item: float(item.get("score") or 0.0))
    status = selected.get("status")
    status_factor = {
        "candidate": 1.0,
        "inferred": 0.72,
        "review": 0.5,
        "weak": 0.2,
    }.get(status, 0.0)
    score = float(selected.get("score") or 0.0) * status_factor
    if score <= 0:
        return 0.0, []
    operation = "pattern" if selected is signals[0] else "marquee"
    reason = f"comportamiento {operation} {axis}: {status} ({score:.2f})"
    return min(1.0, score), [reason]


def _recommend_scaling(asset: dict[str, Any], slice_item: dict[str, Any]) -> dict[str, Any]:
    """Sugiere Fill/Fit sin deformar la visual y cuantifica el coste del recorte."""

    input_target = slice_item.get("input_dimensions") or {}
    output_target = slice_item.get("output_dimensions") or {}
    target = input_target or output_target
    source_width = float(asset.get("width") or 0)
    source_height = float(asset.get("height") or 0)
    target_width = float(target.get("width") or 0)
    target_height = float(target.get("height") or 0)
    source_aspect = source_width / source_height if source_width > 0 and source_height > 0 else 0.0
    target_aspect = target_width / target_height if target_width > 0 and target_height > 0 else 0.0
    output_aspect = float(output_target.get("aspect_ratio") or 0)
    mapping_aspect_delta = (
        abs(math.log(target_aspect / output_aspect))
        if target_aspect > 0 and output_aspect > 0
        else None
    )
    mapping_distortion_risk = mapping_aspect_delta is not None and mapping_aspect_delta > 0.02
    if not source_aspect or not target_aspect:
        return {
            "mode": "review",
            "control": "Slice Transform",
            "resolume_scaling": None,
            "source_aspect_ratio": round(source_aspect, 6) if source_aspect else None,
            "target_aspect_ratio": round(target_aspect, 6) if target_aspect else None,
            "fill_crop_fraction": None,
            "fit_empty_fraction": None,
            "mapping_output_aspect_ratio": round(output_aspect, 6) if output_aspect else None,
            "mapping_aspect_delta_log": round(mapping_aspect_delta, 6) if mapping_aspect_delta is not None else None,
            "mapping_distortion_risk": mapping_distortion_risk,
            "requires_review": True,
            "reason": "faltan dimensiones de la visual o de la slice",
        }

    fill_scale = max(target_width / source_width, target_height / source_height)
    fill_width = source_width * fill_scale
    fill_height = source_height * fill_scale
    fill_crop_x = max(0.0, 1.0 - target_width / fill_width)
    fill_crop_y = max(0.0, 1.0 - target_height / fill_height)
    fill_crop_fraction = max(fill_crop_x, fill_crop_y)

    fit_scale = min(target_width / source_width, target_height / source_height)
    fit_width = source_width * fit_scale
    fit_height = source_height * fit_scale
    fit_empty_x = max(0.0, 1.0 - fit_width / target_width)
    fit_empty_y = max(0.0, 1.0 - fit_height / target_height)
    fit_empty_fraction = max(fit_empty_x, fit_empty_y)

    protected_tokens = set(asset.get("tokens") or []) & {
        "logo", "logos", "text", "texto", "letras", "titulo", "title",
        "nombre", "name", "sponsor", "sponsors", "marca", "brand",
    }
    alpha_protected = asset.get("alpha") is True
    if fill_crop_fraction <= 0.08:
        mode = "fill"
        reason = "la proporción casi coincide; Fill no recorta de forma relevante"
        requires_review = False
    elif alpha_protected or protected_tokens:
        mode = "fit"
        reason = "se prioriza conservar alpha, texto, logo o nombre completo"
        requires_review = fit_empty_fraction > 0.55
    elif fill_crop_fraction <= 0.30:
        mode = "fill"
        reason = "el recorte conserva la mayor parte del cuadro y evita deformación"
        requires_review = False
    else:
        mode = "fit"
        reason = "Fill recortaría demasiado contenido; Fit conserva la visual para revisión"
        requires_review = True
    if mapping_distortion_risk:
        requires_review = True
        reason += "; InputRect y OutputRect no conservan exactamente la proporción"

    crop_axis = []
    if fill_crop_x > 0.01:
        crop_axis.append("horizontal")
    if fill_crop_y > 0.01:
        crop_axis.append("vertical")
    empty_axis = []
    if fit_empty_x > 0.01:
        empty_axis.append("horizontal")
    if fit_empty_y > 0.01:
        empty_axis.append("vertical")
    return {
        "mode": mode,
        "control": "Slice Transform",
        "resolume_scaling": mode.title() if mode in {"fill", "fit"} else None,
        "source_aspect_ratio": round(source_aspect, 6),
        "target_aspect_ratio": round(target_aspect, 6),
        "mapping_output_aspect_ratio": round(output_aspect, 6) if output_aspect else None,
        "mapping_aspect_delta_log": round(mapping_aspect_delta, 6) if mapping_aspect_delta is not None else None,
        "mapping_distortion_risk": mapping_distortion_risk,
        "fill_crop_fraction": round(fill_crop_fraction, 6),
        "fill_crop_axes": crop_axis,
        "fit_empty_fraction": round(fit_empty_fraction, 6),
        "fit_empty_axes": empty_axis,
        "protected_tokens": sorted(protected_tokens),
        "stretch_allowed": False,
        "requires_review": requires_review,
        "reason": reason,
    }


def _score_asset_to_slice(asset: dict[str, Any], slice_item: dict[str, Any]) -> dict[str, Any]:
    target = slice_item.get("input_dimensions") or slice_item.get("output_dimensions") or {}
    target_width = float(target.get("width") or 0)
    target_height = float(target.get("height") or 0)
    target_aspect = float(target.get("aspect_ratio") or 0)
    asset_aspect = float(asset.get("aspect_ratio") or 0)
    if target_aspect > 0 and asset_aspect > 0:
        aspect_delta = abs(math.log(asset_aspect / target_aspect))
        aspect_score = math.exp(-1.15 * aspect_delta)
    else:
        aspect_delta = None
        aspect_score = 0.0
    if target_width > 0 and target_height > 0:
        resolution_score = min(1.0, asset["width"] / target_width, asset["height"] / target_height)
    else:
        resolution_score = 0.0
    semantic_raw, semantic_reasons = _asset_role_score(asset, slice_item.get("hints") or [], slice_item.get("name") or "")
    semantic_score = min(1.0, semantic_raw / 1.7)
    behavior_score, behavior_reasons = _asset_behavior_score(asset, slice_item)
    is_key = (slice_item.get("output_controls") or {}).get("is_key")
    alpha_score = 1.0 if not is_key else 1.0 if asset.get("alpha") is True else 0.0
    score = (
        (aspect_score * 0.55)
        + (resolution_score * 0.20)
        + (semantic_score * 0.10)
        + (behavior_score * 0.10)
        + (alpha_score * 0.05)
    )
    reasons = [
        f"aspect ratio {asset_aspect:.3f} frente a {target_aspect:.3f}" if target_aspect else "slice sin dimensiones utilizables",
        f"cobertura de resolución {resolution_score:.0%}",
    ]
    reasons.extend(semantic_reasons)
    reasons.extend(behavior_reasons)
    if is_key:
        reasons.append("la slice está marcada como key")
        if asset.get("alpha") is not True:
            reasons.append("la visual no declara alpha real")
    return {
        "score": round(max(0.0, min(1.0, score)), 6),
        "aspect_delta_log": round(aspect_delta, 6) if aspect_delta is not None else None,
        "aspect_score": round(aspect_score, 6),
        "resolution_score": round(resolution_score, 6),
        "semantic_score": round(semantic_score, 6),
        "behavior_score": round(behavior_score, 6),
        "alpha_score": round(alpha_score, 6),
        "reasons": reasons,
    }


def _match_quality(score: float) -> str:
    if score >= 0.72:
        return "GOOD"
    if score >= 0.55:
        return "POSSIBLE"
    return "NO_GOOD_MATCH"


def _fallback_strategies(
    slice_item: dict[str, Any],
    assets: list[dict[str, Any]],
    candidate_status: str,
    *,
    max_candidates: int,
) -> list[dict[str, Any]]:
    """Propone un handoff conservador a NAYADE para superficies sin match fuerte."""

    if candidate_status not in {"NO_GOOD_MATCH", "NO_CANDIDATES"}:
        return []
    dimensions = slice_item.get("input_dimensions") or slice_item.get("output_dimensions") or {}
    aspect = float(dimensions.get("aspect_ratio") or 0.0)
    if aspect > 1.25:
        axes = ["horizontal"]
    elif 0.0 < aspect < 0.8:
        axes = ["vertical"]
    else:
        axes = ["horizontal", "vertical"]

    strategies: list[dict[str, Any]] = []
    for operation in ("pattern", "marquee"):
        for axis in axes:
            ranked: list[dict[str, Any]] = []
            for asset in assets:
                signal = ((asset.get("behavior") or {}).get(operation) or {}).get(axis) or {}
                score = signal.get("score")
                if score is None:
                    continue
                ranked.append({
                    "asset_id": asset.get("asset_id"),
                    "asset_path": asset.get("path"),
                    "filename": asset.get("filename"),
                    "score": round(float(score), 6),
                    "status": signal.get("status") or "unknown",
                    "requires_preview": signal.get("requires_preview", True),
                    "basis": signal.get("basis") or [],
                })
            ranked.sort(key=lambda item: item["score"], reverse=True)
            strategies.append({
                "operation": operation,
                "scope": "input_group",
                "input_group_id": slice_item.get("input_group_id"),
                "axis": axis,
                "status": (
                    "CANDIDATE"
                    if any(item["status"] == "candidate" for item in ranked[:max_candidates])
                    else "REVIEW" if ranked else "NO_BEHAVIOR_DATA"
                ),
                "requires_preview": True,
                "reason": (
                    "No hay una visual con aspecto suficiente; probar repetición o desplazamiento "
                    "sin deformar la imagen."
                ),
                "candidate_assets": ranked[:max_candidates],
            })
    return strategies


def build_mapping_plan(
    output_map: dict[str, Any],
    assets: list[dict[str, Any]] | None = None,
    *,
    max_candidates: int = 6,
) -> dict[str, Any]:
    """Cruza perfiles INSTAR con slices y genera sugerencias, nunca cambios."""

    assets = assets or []
    slices: list[dict[str, Any]] = []
    for slice_index, original in enumerate(output_map.get("slices", []), start=1):
        if not original.get("enabled", True):
            continue
        slice_item = dict(original)
        slice_item["input_group_id"] = original.get("input_group_id") or f"input-group-auto-{slice_index:03d}"
        slice_item["geometry"] = original.get("geometry") or _geometry_profile(slice_item)
        slices.append(slice_item)
    assignments: list[dict[str, Any]] = []
    by_slice: dict[str, list[dict[str, Any]]] = {slice_item["id"]: [] for slice_item in slices}
    for asset in assets:
        ranked: list[dict[str, Any]] = []
        for slice_item in slices:
            match = _score_asset_to_slice(asset, slice_item)
            ranked.append({"slice": slice_item, "match": match})
        ranked.sort(key=lambda item: item["match"]["score"], reverse=True)
        if not ranked:
            continue
        top = ranked[0]
        second_score = ranked[1]["match"]["score"] if len(ranked) > 1 else 0.0
        margin = top["match"]["score"] - second_score
        confidence = min(1.0, top["match"]["score"] * 0.75 + min(1.0, margin * 4.0) * 0.25)
        scaling = _recommend_scaling(asset, top["slice"])
        requires_review = (
            top["match"]["score"] < 0.72
            or margin < 0.08
            or bool((top["slice"].get("warper") or {}).get("has_active_warp"))
            or scaling["requires_review"]
        )
        match_quality = _match_quality(top["match"]["score"])
        if match_quality == "NO_GOOD_MATCH":
            requires_review = True
        assignment = {
            "asset_id": asset["asset_id"],
            "asset_path": asset["path"],
            "asset_dimensions": {
                "width": asset["width"],
                "height": asset["height"],
                "aspect_ratio": asset["aspect_ratio"],
                "orientation": asset["orientation"],
                "alpha": asset["alpha"],
            },
            "scaling": scaling,
            "slice_id": top["slice"]["id"],
            "slice_name": top["slice"]["name"],
            "screen_name": top["slice"]["screen_name"],
            "input_group_id": top["slice"].get("input_group_id"),
            "target_slice_ids": [
                slice_item["id"]
                for slice_item in slices
                if slice_item.get("input_group_id") == top["slice"].get("input_group_id")
            ],
            "score": top["match"]["score"],
            "match_quality": match_quality,
            "confidence": round(confidence, 6),
            "requires_review": requires_review,
            "eligible_for_auto_apply": not requires_review and match_quality == "GOOD",
            "match": top["match"],
            "alternatives": [
                {
                    "slice_id": item["slice"]["id"],
                    "slice_name": item["slice"]["name"],
                    "score": item["match"]["score"],
                }
                for item in ranked[1:max_candidates]
            ],
            "operation": "suggest_assignment_to_input_group",
        }
        if len(assignment["target_slice_ids"]) > 1:
            requires_review = True
            assignment["requires_review"] = True
            assignment["match"]["reasons"].append(
                f"fan-out de entrada: {len(assignment['target_slice_ids'])} slices comparten InputRect"
            )
        assignments.append(assignment)
        for item in ranked:
            by_slice[item["slice"]["id"]].append({
                "asset_id": asset["asset_id"],
                "asset_path": asset["path"],
                "score": item["match"]["score"],
                "match_quality": _match_quality(item["match"]["score"]),
                "requires_review": requires_review if item is top else True,
            })

    slice_candidates = []
    for slice_item in slices:
        candidates = sorted(by_slice[slice_item["id"]], key=lambda item: item["score"], reverse=True)
        best_score = candidates[0]["score"] if candidates else 0.0
        candidate_status = _match_quality(best_score) if candidates else "NO_CANDIDATES"
        slice_candidates.append({
            "slice_id": slice_item["id"],
            "slice_name": slice_item["name"],
            "screen_name": slice_item["screen_name"],
            "input_group_id": slice_item.get("input_group_id"),
            "target": slice_item.get("input_dimensions") or slice_item.get("output_dimensions"),
            "candidate_status": candidate_status,
            "candidates": candidates[:max_candidates],
            "fallback_strategies": _fallback_strategies(
                slice_item,
                assets,
                candidate_status,
                max_candidates=max_candidates,
            ),
        })

    status = output_map.get("validation", {}).get("status", "WARN")
    if any(item["requires_review"] for item in assignments):
        status = "WARN" if status == "PASS" else status
    if assets and not assignments:
        status = "WARN"
    return {
        "schema_version": MAPPING_PLAN_VERSION,
        "plan_type": "InstarResolumeMappingPlan",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "status": status,
        "source_map": output_map.get("source"),
        "catalog": {
            "assets": len(assets),
            "assets_with_assignment": len(assignments),
            "assets_requiring_review": sum(1 for item in assignments if item["requires_review"]),
            "assets_without_strong_match": sum(1 for item in assignments if item["match_quality"] == "NO_GOOD_MATCH"),
        },
        "composition": output_map.get("composition"),
        "validation": output_map.get("validation"),
        "screens": output_map.get("screens"),
        "slices": slices,
        "assignments": assignments,
        "slice_candidates": slice_candidates,
        "limitations": [
            "Las dimensiones reducen el espacio de búsqueda, pero no conocen la intención artística ni garantizan que una visual sea adecuada para una superficie.",
            "Si dos slices comparten InputRect o tienen el mismo aspecto, el resultado queda deliberadamente en revisión.",
            "El plan no carga clips, no cambia rutas, no edita .avc y no transmite órdenes al procesador LED.",
        ],
    }


def advanced_output_text_report(report: dict[str, Any]) -> str:
    """Resumen breve del mapa o plan para la terminal."""

    is_plan = report.get("plan_type") == "InstarResolumeMappingPlan"
    validation = report.get("validation") or {}
    status = report.get("status") if is_plan else validation.get("status")
    lines = [
        "RESOLUME_ADAPTER INSTAR MAP",
        "=================",
        f"Preset: {(report.get('source_map') or report.get('source') or {}).get('path')}",
        f"Estado: {status or 'UNKNOWN'}",
        f"Canvas de composición: {report.get('composition', {}).get('width')} × {report.get('composition', {}).get('height')}",
        f"Pantallas: {len(report.get('screens') or [])}",
        f"Slices: {len(report.get('slices') or [])}",
    ]
    geometry_slices = [item for item in report.get("slices") or [] if item.get("geometry")]
    geometry_review = [
        item for item in geometry_slices
        if (item.get("geometry") or {}).get("requires_geometry_test")
    ]
    lines.append(
        f"Prueba geométrica: {len(geometry_review)}/{len(geometry_slices)} slices requieren círculos/cuadrados"
    )
    if is_plan:
        catalog = report.get("catalog") or {}
        lines.extend([
            f"Visuales del catálogo: {catalog.get('assets')}",
            f"Asignaciones sugeridas: {catalog.get('assets_with_assignment')}",
            f"Revisión requerida: {catalog.get('assets_requiring_review')}",
            f"Sin candidato fuerte: {catalog.get('assets_without_strong_match', 0)}",
            f"Alertas del mapa: {len((report.get('validation') or {}).get('warnings') or [])}",
            f"Fallbacks NAYADE: {sum(bool(item.get('fallback_strategies')) for item in report.get('slice_candidates') or [])}",
            "",
            "Asignaciones:",
        ])
        for assignment in report.get("assignments", []):
            review = "REVISAR" if assignment["requires_review"] else "OK"
            scaling = (assignment.get("scaling") or {}).get("resolume_scaling") or "REVISAR"
            lines.append(
                f"  [{review}] {Path(assignment['asset_path']).name} -> "
                f"{assignment['slice_name']} [{scaling}] ({assignment['score']:.2f})"
            )
    else:
        lines.extend(["", "Validación:"])
        for issue in (validation.get("errors") or []) + (validation.get("warnings") or []):
            lines.append(f"  [{issue.get('code')}] {issue.get('message')}")
    return "\n".join(lines)


def write_advanced_output_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path

"""Detección geométrica de superficies en mapas raster de INSTAR."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .instar_svg import build_svg_mapping
from .media import ResolumeAdapterError

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - exercised only on environments without the optional backend
    cv2 = None
    np = None


_HUE_BANDS = (
    ("red", ((0, 10), (170, 180))),
    ("orange", ((10, 22),)),
    ("yellow", ((22, 42),)),
    ("green", ((42, 90),)),
    ("blue", ((90, 135),)),
    ("magenta", ((135, 170),)),
)
_OCR_LINE = re.compile(r"^OCR_LINE\s+x=([-+]?\d+(?:\.\d+)?)\s+y=([-+]?\d+(?:\.\d+)?)\s+w=([-+]?\d+(?:\.\d+)?)\s+h=([-+]?\d+(?:\.\d+)?)\s+text=(.*)$")
_PIXEL_DIMENSIONS = re.compile(r"\bW\s*(\d+)\s*(?:[x×]\s*)?H\s*(\d+)\b", re.IGNORECASE)


def _require_backend() -> None:
    if cv2 is None or np is None:
        raise ResolumeAdapterError("El detector raster requiere OpenCV y NumPy disponibles en el entorno Python.")


def _overlap(first: dict[str, Any], second: dict[str, Any]) -> float:
    left = max(first["x"], second["x"])
    top = max(first["y"], second["y"])
    right = min(first["x"] + first["width"], second["x"] + second["width"])
    bottom = min(first["y"] + first["height"], second["y"] + second["height"])
    area = max(0, right - left) * max(0, bottom - top)
    first_area = first["width"] * first["height"]
    second_area = second["width"] * second["height"]
    return area / max(1, min(first_area, second_area))


def _detect_components(hsv: Any, image_width: int, image_height: int, min_area_ratio: float) -> list[dict[str, Any]]:
    kernel = np.ones((9, 9), dtype=np.uint8)
    min_area = max(1000, int(image_width * image_height * min_area_ratio))
    candidates: list[dict[str, Any]] = []
    for color_name, bands in _HUE_BANDS:
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for low, high in bands:
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv, (low, 55, 45), (high - 1, 255, 255)))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
        for row in stats[1:count]:
            x, y, width, height, area = [int(value) for value in row]
            if area < min_area or width < 16 or height < 16:
                continue
            rectangularity = area / max(1, width * height)
            if rectangularity < 0.20:
                continue
            candidates.append(
                {
                    "color_family": color_name,
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "area": area,
                    "rectangularity": round(rectangularity, 4),
                }
            )

    candidates.sort(key=lambda item: item["area"], reverse=True)
    regions: list[dict[str, Any]] = []
    for candidate in candidates:
        if any(_overlap(candidate, existing) >= 0.80 for existing in regions):
            continue
        regions.append(candidate)
    regions.sort(key=lambda item: (item["y"], item["x"]))
    return regions


def _normalise_regions(regions: list[dict[str, Any]], canvas_size: tuple[int, int]) -> list[dict[str, Any]]:
    if not regions:
        raise ResolumeAdapterError("No se encontraron superficies coloreadas suficientemente grandes en la imagen.")
    canvas_width, canvas_height = canvas_size
    min_x = min(item["x"] for item in regions)
    min_y = min(item["y"] for item in regions)
    max_x = max(item["x"] + item["width"] for item in regions)
    max_y = max(item["y"] + item["height"] for item in regions)
    source_width = max_x - min_x
    source_height = max_y - min_y
    if source_width <= 0 or source_height <= 0:
        raise ResolumeAdapterError("Las superficies detectadas no forman un área válida.")

    normalised: list[dict[str, Any]] = []
    for index, item in enumerate(regions, start=1):
        x = (item["x"] - min_x) * canvas_width / source_width
        y = (item["y"] - min_y) * canvas_height / source_height
        width = item["width"] * canvas_width / source_width
        height = item["height"] * canvas_height / source_height
        name = f"surface-{index:03d}"
        orientation = "vertical" if height > width * 1.25 else "horizontal" if width > height * 1.25 else "rectangular"
        if orientation == "horizontal" and height < canvas_height * 0.25 and y < canvas_height * 0.25:
            inferred_role = "BANNER_FRONTAL"
        elif orientation == "horizontal" and height < canvas_height * 0.25 and y > canvas_height * 0.65:
            inferred_role = "BANNER_PISO"
        elif orientation == "vertical":
            inferred_role = "VERTICAL_SURFACE"
        else:
            inferred_role = "MAIN_SURFACE"
        normalised.append(
            {
                "id": name,
                "name": name,
                "source_color_family": item["color_family"],
                "source_bounds": {key: item[key] for key in ("x", "y", "width", "height")},
                "bounds": {
                    "x": round(x, 3),
                    "y": round(y, 3),
                    "width": round(width, 3),
                    "height": round(height, 3),
                },
                "orientation": orientation,
                "inferred_role": inferred_role,
                "detection": {"area": item["area"], "rectangularity": item["rectangularity"]},
            }
        )
    return normalised


def _normalise_ocr_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.upper())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _parse_ocr_output(stdout: str) -> dict[str, Any]:
    language_match = re.search(r"^OCR_LANGUAGE\s+(.+)$", stdout, re.MULTILINE)
    lines: list[dict[str, Any]] = []
    for raw_line in stdout.splitlines():
        match = _OCR_LINE.match(raw_line.strip())
        if not match:
            continue
        x, y, width, height = (float(match.group(index)) for index in range(1, 5))
        text = match.group(5).strip()
        if text:
            lines.append({"x": x, "y": y, "width": width, "height": height, "text": text})
    return {"language": language_match.group(1).strip() if language_match else None, "lines": lines}


def _run_ocr_once(binary: Path, source: Path, timeout_seconds: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [str(binary), str(source)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"available": False, "reason": "ocr_timeout", "lines": []}
    except OSError as exc:
        return {"available": False, "reason": f"ocr_launch_failed:{exc}", "lines": []}
    parsed = _parse_ocr_output(result.stdout)
    parsed.update({
        "available": result.returncode == 0 and bool(parsed["lines"]),
        "returncode": result.returncode,
        "stderr": result.stderr.strip()[:500],
    })
    if not parsed["available"]:
        parsed["reason"] = "ocr_returned_no_lines"
    return parsed


def run_ocr_command(
    image_path: str | Path,
    executable: str | Path | None,
    *,
    region_boxes: list[dict[str, int]] | None = None,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Ejecuta un OCR externo que emita el protocolo OCR_LINE de INSTAR."""

    if executable is None:
        return {"available": False, "reason": "ocr_not_requested", "lines": []}
    source = Path(image_path).expanduser().resolve()
    binary = Path(executable).expanduser().resolve()
    if not binary.is_file():
        return {"available": False, "reason": f"ocr_executable_not_found:{binary}", "lines": []}
    full_pass = _run_ocr_once(binary, source, timeout_seconds)
    all_lines = list(full_pass.get("lines") or [])
    languages = [full_pass.get("language")] if full_pass.get("language") else []
    passes = 1
    if region_boxes and cv2 is not None:
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
        if image is not None:
            image_height, image_width = image.shape[:2]
            with tempfile.TemporaryDirectory(prefix="instar-ocr-crops-") as directory:
                for index, bounds in enumerate(region_boxes, start=1):
                    left = max(0, int(bounds["x"]) - 24)
                    top = max(0, int(bounds["y"]) - 24)
                    right = min(image_width, int(bounds["x"] + bounds["width"]) + 24)
                    bottom = min(image_height, int(bounds["y"] + bounds["height"]) + 24)
                    crop = image[top:bottom, left:right]
                    if crop.size == 0:
                        continue
                    crop_path = Path(directory) / f"region-{index:03d}.png"
                    if not cv2.imwrite(str(crop_path), crop):
                        continue
                    crop_pass = _run_ocr_once(binary, crop_path, timeout_seconds)
                    passes += 1
                    if crop_pass.get("language"):
                        languages.append(crop_pass["language"])
                    for line in crop_pass.get("lines") or []:
                        all_lines.append({
                            **line,
                            "x": line["x"] + left,
                            "y": line["y"] + top,
                            "pass": f"region-{index:03d}",
                        })
    deduplicated: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for line in all_lines:
        key = (line["text"], round(line["x"]), round(line["y"]))
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(line)
    available = bool(deduplicated) and full_pass.get("returncode", 1) == 0
    return {
        "available": available,
        "language": next((language for language in languages if language), None),
        "lines": deduplicated,
        "passes": passes,
        "returncode": full_pass.get("returncode"),
        "stderr": full_pass.get("stderr", ""),
        **({} if available else {"reason": full_pass.get("reason", "ocr_returned_no_lines")}),
    }


def _line_inside_region(line: dict[str, Any], region: dict[str, Any]) -> bool:
    bounds = region["source_bounds"]
    center_x = line["x"] + line["width"] / 2.0
    center_y = line["y"] + line["height"] / 2.0
    margin_x = max(24.0, bounds["width"] * 0.04)
    margin_y = max(24.0, bounds["height"] * 0.04)
    return (
        bounds["x"] - margin_x <= center_x <= bounds["x"] + bounds["width"] + margin_x
        and bounds["y"] - margin_y <= center_y <= bounds["y"] + bounds["height"] + margin_y
    )


def _semantic_name(text: str) -> str | None:
    normalised = _normalise_ocr_text(text)
    for needle, name in (
        ("BANNER FRONTAL", "BANNER_FRONTAL"),
        ("BANNER PISO", "BANNER_PISO"),
        ("CENTRAL", "CENTRAL"),
        ("CCTV R", "CCTV_R"),
        ("CCTV L", "CCTV_L"),
    ):
        if needle in normalised:
            return name
    return None


def _declared_dimensions(text: str) -> tuple[int, int] | None:
    match = _PIXEL_DIMENSIONS.search(_normalise_ocr_text(text))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _annotate_regions(report: dict[str, Any]) -> int:
    ocr = report.get("ocr") or {}
    lines = ocr.get("lines") or []
    resolved_names = 0
    for region in report.get("regions") or []:
        matches = [line for line in lines if _line_inside_region(line, region)]
        semantic_name = next((_semantic_name(line["text"]) for line in matches if _semantic_name(line["text"])), None)
        dimensions = next((_declared_dimensions(line["text"]) for line in matches if _declared_dimensions(line["text"])), None)
        if semantic_name:
            region["name"] = semantic_name
            region["name_source"] = "ocr"
            region["name_confidence"] = "high"
            resolved_names += 1
        else:
            region["name"] = region["inferred_role"]
            region["name_source"] = "geometry_inference"
            region["name_confidence"] = "medium"
        if dimensions:
            region["declared_resolution"] = {"width": dimensions[0], "height": dimensions[1], "source": "ocr"}
            bounds = region["bounds"]
            center_x = bounds["x"] + bounds["width"] / 2.0
            center_y = bounds["y"] + bounds["height"] / 2.0
            bounds["width"] = float(dimensions[0])
            bounds["height"] = float(dimensions[1])
            bounds["x"] = round(center_x - bounds["width"] / 2.0, 3)
            bounds["y"] = round(center_y - bounds["height"] / 2.0, 3)
            region["geometry_source"] = "raster_detection_plus_ocr_dimensions"
        else:
            region["geometry_source"] = "raster_detection"
        region["ocr_matches"] = [line["text"] for line in matches if _semantic_name(line["text"]) or _declared_dimensions(line["text"])]
    return resolved_names


def _infer_paired_banner_dimensions(report: dict[str, Any]) -> None:
    banners = [
        region for region in report.get("regions") or []
        if region.get("inferred_role") in {"BANNER_FRONTAL", "BANNER_PISO"}
    ]
    known = next((region for region in banners if region.get("declared_resolution")), None)
    if not known:
        return
    resolution = known["declared_resolution"]
    for region in banners:
        if region is known or region.get("declared_resolution"):
            continue
        region["declared_resolution"] = {
            "width": resolution["width"],
            "height": resolution["height"],
            "source": "paired_banner_inference",
        }
        bounds = region["bounds"]
        center_x = bounds["x"] + bounds["width"] / 2.0
        center_y = bounds["y"] + bounds["height"] / 2.0
        bounds["width"] = float(resolution["width"])
        bounds["height"] = float(resolution["height"])
        bounds["x"] = round(center_x - bounds["width"] / 2.0, 3)
        bounds["y"] = round(center_y - bounds["height"] / 2.0, 3)
        region["geometry_source"] = "raster_detection_plus_paired_banner_inference"


def _reconcile_detected_layout(report: dict[str, Any]) -> bool:
    """Alinea bordes evidentes de una captura sin inventar routing físico."""

    changed = False
    for region in report.get("regions") or []:
        bounds = region["bounds"]
        for axis in ("x", "y", "width", "height"):
            rounded = float(round(bounds[axis]))
            if abs(bounds[axis] - rounded) <= 0.5:
                if bounds[axis] != rounded:
                    changed = True
                bounds[axis] = rounded
        if abs(bounds["x"]) <= 12:
            changed = changed or bounds["x"] != 0.0
            bounds["x"] = 0.0
        if abs(bounds["y"]) <= 12:
            changed = changed or bounds["y"] != 0.0
            bounds["y"] = 0.0

    by_name = {region.get("name"): region for region in report.get("regions") or []}
    top = by_name.get("BANNER_FRONTAL")
    central = by_name.get("CENTRAL")
    bottom = by_name.get("BANNER_PISO")
    if top and central and bottom:
        aligned_x = max(abs(top["bounds"]["x"] - central["bounds"]["x"]), abs(bottom["bounds"]["x"] - central["bounds"]["x"])) <= 16
        if aligned_x and top.get("declared_resolution") and central.get("declared_resolution") and bottom.get("declared_resolution"):
            previous = [(top["bounds"]["x"], top["bounds"]["y"]), (central["bounds"]["x"], central["bounds"]["y"]), (bottom["bounds"]["x"], bottom["bounds"]["y"])]
            top["bounds"]["x"] = 0.0
            top["bounds"]["y"] = 0.0
            central["bounds"]["x"] = 0.0
            central["bounds"]["y"] = top["bounds"]["height"]
            bottom["bounds"]["x"] = 0.0
            bottom["bounds"]["y"] = central["bounds"]["y"] + central["bounds"]["height"]
            changed = changed or previous != [(top["bounds"]["x"], top["bounds"]["y"]), (central["bounds"]["x"], central["bounds"]["y"]), (bottom["bounds"]["x"], bottom["bounds"]["y"])]
            for region in (top, central, bottom):
                region["geometry_source"] = f"{region.get('geometry_source', 'raster_detection')}_layout_snap"
    for region in report.get("regions") or []:
        if region.get("orientation") == "vertical" and abs(region["bounds"]["y"]) <= 12:
            region["bounds"]["y"] = 0.0
    if changed:
        report["validation"]["warnings"].append({
            "code": "layout_edges_snapped",
            "message": "Se alinearon bordes cercanos y superficies apiladas usando dimensiones declaradas; confirmar con el documento original.",
        })
    return changed


def detect_raster_surfaces(image_path: str | Path, *, canvas_size: tuple[int, int], min_area_ratio: float = 0.005) -> dict[str, Any]:
    """Detecta superficies grandes y las normaliza al canvas declarado.

    La normalización usa el bounding box de las regiones detectadas. Por eso el
    resultado sirve como candidato geométrico, pero no afirma que los bordes de
    una captura coincidan con coordenadas exactas del procesador.
    """

    _require_backend()
    source = Path(image_path).expanduser().resolve()
    if not source.is_file():
        raise ResolumeAdapterError(f"No se encontró la imagen de mapping: {source}")
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise ResolumeAdapterError(f"No se pudo decodificar la imagen de mapping: {source}")
    image_height, image_width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    detected = _detect_components(hsv, image_width, image_height, min_area_ratio)
    regions = _normalise_regions(detected, canvas_size)
    return {
        "schema_version": "0.1",
        "map_type": "InstarRasterMappingCandidate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"image": str(source), "width": image_width, "height": image_height},
        "canvas": {"width": canvas_size[0], "height": canvas_size[1]},
        "regions": regions,
        "validation": {
            "status": "REVIEW",
            "errors": [],
            "warnings": [
                {
                    "code": "coordinates_scaled_from_raster",
                    "message": "Las coordenadas se normalizaron desde el bounding box de la captura; confirmar contra el documento original o un XML de Resolume.",
                },
                {
                    "code": "labels_not_read",
                    "message": "La detección geométrica todavía no asigna nombres semánticos ni resoluciones leídas desde texto.",
                },
            ],
        },
        "limitations": [
            "No interpreta todavía OCR, números de panel, orden de puertos ni asignación de procesadores.",
            "La detección por color depende de que las superficies tengan rellenos diferenciables y suficientemente grandes.",
        ],
    }


def _candidate_svg(report: dict[str, Any], path: str | Path) -> Path:
    canvas = report["canvas"]
    root = ElementTree.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"0 0 {canvas['width']} {canvas['height']}",
            "width": str(canvas["width"]),
            "height": str(canvas["height"]),
        },
    )
    for region in report["regions"]:
        bounds = region["bounds"]
        ElementTree.SubElement(
            root,
            "rect",
            {
                "id": region["name"],
                "x": str(bounds["x"]),
                "y": str(bounds["y"]),
                "width": str(bounds["width"]),
                "height": str(bounds["height"]),
            },
        )
    ElementTree.indent(root, space="\t")
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)
    return target


def build_raster_mapping(
    image_path: str | Path,
    xml_output: str | Path,
    *,
    canvas_size: tuple[int, int],
    output_size: tuple[int, int] | None = None,
    svg_output: str | Path | None = None,
    screen_name: str = "INSTAR Raster Map",
    min_area_ratio: float = 0.005,
    ocr_executable: str | Path | None = None,
) -> dict[str, Any]:
    report = detect_raster_surfaces(image_path, canvas_size=canvas_size, min_area_ratio=min_area_ratio)
    report["ocr"] = run_ocr_command(
        image_path,
        ocr_executable,
        region_boxes=[region["source_bounds"] for region in report.get("regions") or []],
    )
    resolved_names = _annotate_regions(report)
    _infer_paired_banner_dimensions(report)
    _reconcile_detected_layout(report)
    if report["ocr"].get("available"):
        report["validation"]["warnings"] = [
            warning for warning in report["validation"]["warnings"] if warning.get("code") != "labels_not_read"
        ]
        if resolved_names == 0:
            report["validation"]["warnings"].append(
                {"code": "ocr_no_semantic_names", "message": "El OCR devolvió líneas, pero no resolvió nombres de superficies conocidos."}
            )
    elif ocr_executable is not None:
        report["validation"]["warnings"].append(
            {"code": "ocr_unavailable", "message": report["ocr"].get("reason", "No se pudo ejecutar el OCR externo.")}
        )
    with tempfile.TemporaryDirectory(prefix="instar-raster-") as directory:
        svg_path = _candidate_svg(report, Path(directory) / "candidate.svg")
        if svg_output:
            _candidate_svg(report, svg_output)
        xml_report = build_svg_mapping(
            svg_path,
            xml_output,
            composition_size=canvas_size,
            output_size=output_size or canvas_size,
            screen_name=screen_name,
        )
    report["artifacts"] = {
        "advanced_output_xml": str(Path(xml_output).expanduser().resolve()),
        "candidate_svg": str(Path(svg_output).expanduser().resolve()) if svg_output else None,
    }
    report["xml_mapping"] = xml_report
    return report


def raster_mapping_text_report(report: dict[str, Any]) -> str:
    validation = report.get("validation") or {}
    canvas = report.get("canvas") or {}
    lines = [
        "RESOLUME_ADAPTER INSTAR IMAGE MAP",
        "=================================",
        f"Entrada: {report.get('source', {}).get('image')}",
        f"Canvas declarado: {canvas.get('width')} × {canvas.get('height')}",
        f"Superficies detectadas: {len(report.get('regions') or [])}",
        f"XML candidato: {report.get('artifacts', {}).get('advanced_output_xml')}",
        f"Estado: {validation.get('status', 'UNKNOWN')}",
    ]
    for region in report.get("regions") or []:
        bounds = region["bounds"]
        lines.append(
            f"  {region['name']} [{region['source_color_family']}] "
            f"x={bounds['x']} y={bounds['y']} w={bounds['width']} h={bounds['height']}"
        )
    for warning in validation.get("warnings") or []:
        lines.append(f"  [REVIEW] {warning.get('message')}")
    return "\n".join(lines)


def write_raster_mapping_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path

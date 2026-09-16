"""Detección geométrica de superficies en mapas raster de INSTAR."""

from __future__ import annotations

import json
import tempfile
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
                "detection": {"area": item["area"], "rectangularity": item["rectangularity"]},
            }
        )
    return normalised


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
                    "message": "La detección geométrica no asigna nombres semánticos ni resoluciones leídas desde texto.",
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
                "id": region["id"],
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
) -> dict[str, Any]:
    report = detect_raster_surfaces(image_path, canvas_size=canvas_size, min_area_ratio=min_area_ratio)
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
            f"  {region['id']} [{region['source_color_family']}] "
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

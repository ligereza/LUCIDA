"""Generación de candidatos Advanced Output desde SVG vectorial."""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .media import ResolumeAdapterError


_NUMBER = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
_TOKEN_RE = re.compile(rf"[AaCcHhLlMmQqSsTtVvZz]|{_NUMBER}")
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _normalise_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char)).upper()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _numbers(value: str | None) -> list[float]:
    if not value:
        return []
    return [float(item) for item in re.findall(_NUMBER, value)]


def _length(value: str | None) -> float | None:
    values = _numbers(value)
    return values[0] if values else None


def _compose(first: tuple[float, ...], second: tuple[float, ...]) -> tuple[float, ...]:
    """Compose two SVG 2D affine matrices in SVG's six-value form."""

    a, b, c, d, e, f = first
    g, h, i, j, k, l = second
    return (
        a * g + c * h,
        b * g + d * h,
        a * i + c * j,
        b * i + d * j,
        a * k + c * l + e,
        b * k + d * l + f,
    )


def _apply(matrix: tuple[float, ...], point: tuple[float, float]) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    x, y = point
    return (a * x + c * y + e, b * x + d * y + f)


def _transform_matrix(value: str | None) -> tuple[float, ...]:
    matrix = _IDENTITY
    if not value:
        return matrix
    for match in re.finditer(r"(matrix|translate|rotate|scale|skewX|skewY)\s*\(([^)]+)\)", value):
        operation = match.group(1)
        args = _numbers(match.group(2))
        if operation == "matrix" and len(args) >= 6:
            current = tuple(args[:6])
        elif operation == "translate":
            current = (1.0, 0.0, 0.0, 1.0, args[0] if args else 0.0, args[1] if len(args) > 1 else 0.0)
        elif operation == "scale":
            sx = args[0] if args else 1.0
            sy = args[1] if len(args) > 1 else sx
            current = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif operation == "rotate" and args:
            angle = math.radians(args[0])
            cosine, sine = math.cos(angle), math.sin(angle)
            rotation = (cosine, sine, -sine, cosine, 0.0, 0.0)
            if len(args) >= 3:
                cx, cy = args[1], args[2]
                current = _compose(
                    _compose((1.0, 0.0, 0.0, 1.0, cx, cy), rotation),
                    (1.0, 0.0, 0.0, 1.0, -cx, -cy),
                )
            else:
                current = rotation
        elif operation == "skewX" and args:
            current = (1.0, 0.0, math.tan(math.radians(args[0])), 1.0, 0.0, 0.0)
        elif operation == "skewY" and args:
            current = (1.0, math.tan(math.radians(args[0])), 0.0, 1.0, 0.0, 0.0)
        else:
            continue
        matrix = _compose(matrix, current)
    return matrix


def _bezier_cubic(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    samples: int = 16,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(samples + 1):
        t = index / samples
        inverse = 1.0 - t
        points.append(
            (
                inverse**3 * p0[0] + 3 * inverse**2 * t * p1[0] + 3 * inverse * t**2 * p2[0] + t**3 * p3[0],
                inverse**3 * p0[1] + 3 * inverse**2 * t * p1[1] + 3 * inverse * t**2 * p2[1] + t**3 * p3[1],
            )
        )
    return points


def _parse_path(value: str) -> tuple[list[tuple[float, float]], bool]:
    tokens = _TOKEN_RE.findall(value)
    points: list[tuple[float, float]] = []
    index = 0
    command: str | None = None
    current = (0.0, 0.0)
    start = (0.0, 0.0)
    last_cubic: tuple[float, float] | None = None
    last_quadratic: tuple[float, float] | None = None
    closed = False

    def is_command(token: str) -> bool:
        return len(token) == 1 and token.isalpha()

    def next_numbers(count: int) -> list[float]:
        nonlocal index
        if index + count > len(tokens) or any(is_command(token) for token in tokens[index:index + count]):
            raise ResolumeAdapterError("El path SVG tiene una cantidad de coordenadas incompleta.")
        values = [float(token) for token in tokens[index:index + count]]
        index += count
        return values

    while index < len(tokens):
        if is_command(tokens[index]):
            command = tokens[index]
            index += 1
            if command in {"Z", "z"}:
                current = start
                closed = True
                last_cubic = None
                last_quadratic = None
                command = None
            continue
        if command is None:
            raise ResolumeAdapterError("El path SVG comienza sin un comando.")

        relative = command.islower()
        operation = command.upper()
        if operation == "M":
            x, y = next_numbers(2)
            point = (x + current[0], y + current[1]) if relative else (x, y)
            current = point
            start = point
            points.append(point)
            command = "l" if relative else "L"
            last_cubic = None
            last_quadratic = None
        elif operation == "L":
            x, y = next_numbers(2)
            point = (x + current[0], y + current[1]) if relative else (x, y)
            points.append(point)
            current = point
            last_cubic = None
            last_quadratic = None
        elif operation == "H":
            x = next_numbers(1)[0]
            point = (x + current[0], current[1]) if relative else (x, current[1])
            points.append(point)
            current = point
            last_cubic = None
            last_quadratic = None
        elif operation == "V":
            y = next_numbers(1)[0]
            point = (current[0], y + current[1]) if relative else (current[0], y)
            points.append(point)
            current = point
            last_cubic = None
            last_quadratic = None
        elif operation == "C":
            x1, y1, x2, y2, x, y = next_numbers(6)
            if relative:
                control1 = (x1 + current[0], y1 + current[1])
                control2 = (x2 + current[0], y2 + current[1])
                point = (x + current[0], y + current[1])
            else:
                control1, control2, point = (x1, y1), (x2, y2), (x, y)
            points.extend(_bezier_cubic(current, control1, control2, point)[1:])
            current = point
            last_cubic = control2
            last_quadratic = None
        elif operation == "S":
            x2, y2, x, y = next_numbers(4)
            control1 = (
                (2 * current[0] - last_cubic[0], 2 * current[1] - last_cubic[1])
                if last_cubic is not None else current
            )
            control2 = (x2 + current[0], y2 + current[1]) if relative else (x2, y2)
            point = (x + current[0], y + current[1]) if relative else (x, y)
            points.extend(_bezier_cubic(current, control1, control2, point)[1:])
            current = point
            last_cubic = control2
            last_quadratic = None
        elif operation in {"Q", "T"}:
            if operation == "Q":
                x1, y1, x, y = next_numbers(4)
                control = (x1 + current[0], y1 + current[1]) if relative else (x1, y1)
                point = (x + current[0], y + current[1]) if relative else (x, y)
            else:
                x, y = next_numbers(2)
                control = (
                    (2 * current[0] - last_quadratic[0], 2 * current[1] - last_quadratic[1])
                    if last_quadratic is not None else current
                )
                point = (x + current[0], y + current[1]) if relative else (x, y)
            control1 = (
                current[0] + (2.0 / 3.0) * (control[0] - current[0]),
                current[1] + (2.0 / 3.0) * (control[1] - current[1]),
            )
            control2 = (
                point[0] + (2.0 / 3.0) * (control[0] - point[0]),
                point[1] + (2.0 / 3.0) * (control[1] - point[1]),
            )
            points.extend(_bezier_cubic(current, control1, control2, point)[1:])
            current = point
            last_quadratic = control
            last_cubic = None
        elif operation == "A":
            raise ResolumeAdapterError("Los arcos SVG (A) aún no están soportados; conviértelos a paths Bézier.")
        else:
            raise ResolumeAdapterError(f"Comando SVG no soportado: {command}")

    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(points) < 3:
        raise ResolumeAdapterError("El path SVG no forma una superficie con al menos tres puntos.")
    return points, closed


def _points_attribute(value: str | None) -> list[tuple[float, float]]:
    values = _numbers(value)
    if len(values) < 6 or len(values) % 2:
        raise ResolumeAdapterError("El polígono SVG no contiene pares de coordenadas válidos.")
    return list(zip(values[::2], values[1::2]))


def _view_box(root: ElementTree.Element) -> tuple[float, float, float, float]:
    values = _numbers(root.attrib.get("viewBox"))
    if len(values) == 4 and values[2] > 0 and values[3] > 0:
        return tuple(values)  # type: ignore[return-value]
    width = _length(root.attrib.get("width"))
    height = _length(root.attrib.get("height"))
    if width and height:
        return (0.0, 0.0, width, height)
    raise ResolumeAdapterError("El SVG necesita viewBox o width/height para conocer su canvas.")


def _element_name(element: ElementTree.Element, index: int) -> str:
    for key in ("id", "data-name", "aria-label"):
        if element.attrib.get(key):
            return str(element.attrib[key])
    for key, value in element.attrib.items():
        if key.casefold().endswith("}label") and value:
            return str(value)
    return f"Slice_{index:03d}"


def _has_explicit_surface_name(element: ElementTree.Element) -> bool:
    return bool(
        element.attrib.get("id")
        or element.attrib.get("data-name")
        or element.attrib.get("data-slice")
        or element.attrib.get("aria-label")
        or any(key.casefold().endswith("}label") and value for key, value in element.attrib.items())
    )


def _has_map_fill(element: ElementTree.Element) -> bool:
    raw_opacity = element.attrib.get("fill-opacity")
    try:
        return float(raw_opacity) >= 0.5
    except (TypeError, ValueError):
        return False


def _shape_points(element: ElementTree.Element) -> tuple[list[tuple[float, float]], str] | None:
    tag = _local_name(element.tag)
    if tag == "rect":
        x = _length(element.attrib.get("x")) or 0.0
        y = _length(element.attrib.get("y")) or 0.0
        width = _length(element.attrib.get("width")) or 0.0
        height = _length(element.attrib.get("height")) or 0.0
        if width <= 0 or height <= 0:
            return None
        return ([(x, y), (x + width, y), (x + width, y + height), (x, y + height)], "rect")
    if tag in {"polygon", "polyline"}:
        return (_points_attribute(element.attrib.get("points")), "polygon")
    if tag == "ellipse":
        cx = _length(element.attrib.get("cx")) or 0.0
        cy = _length(element.attrib.get("cy")) or 0.0
        rx = _length(element.attrib.get("rx")) or 0.0
        ry = _length(element.attrib.get("ry")) or 0.0
        if rx <= 0 or ry <= 0:
            return None
        return (
            [
                (cx + rx * math.cos(2 * math.pi * index / 32), cy + ry * math.sin(2 * math.pi * index / 32))
                for index in range(32)
            ],
            "polygon",
        )
    if tag == "path" and element.attrib.get("d"):
        points, _closed = _parse_path(element.attrib["d"])
        return (points, "polygon")
    return None


def _find_canvas_view(root: ElementTree.Element, root_view: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Detecta un canvas interno cuando el SVG también contiene un reporte."""

    _root_min_x, _root_min_y, root_width, root_height = root_view
    candidates: list[tuple[float, float, float, float]] = []

    def visit(element: ElementTree.Element, parent_matrix: tuple[float, ...]) -> None:
        tag = _local_name(element.tag)
        local_matrix = _transform_matrix(element.attrib.get("transform"))
        matrix = _compose(parent_matrix, local_matrix)
        if tag == "rect":
            fill = (element.attrib.get("fill") or "").casefold()
            width = _length(element.attrib.get("width")) or 0.0
            height = _length(element.attrib.get("height")) or 0.0
            if fill in {"#000000", "black"} and width >= root_width * 0.75 and height >= root_height * 0.65:
                shape = _shape_points(element)
                if shape is not None:
                    points = [_apply(matrix, point) for point in shape[0]]
                    candidates.append((min(point[0] for point in points), min(point[1] for point in points), width, height))
        for child in list(element):
            visit(child, matrix)

    visit(root, _IDENTITY)
    if not candidates:
        return root_view
    return max(candidates, key=lambda item: item[2] * item[3])


def _surface_name_from_hints(hints: list[str], fallback: str) -> str:
    for raw_text in hints:
        text = " ".join(raw_text.split()).strip()
        if not text:
            continue
        candidate = re.split(
            r"\s+(?=(?:\d+(?:[.,]\d+)?\s*[x×]\s*\d+(?:[.,]\d+)?\s*M\b|\d+(?:[.,]\d+)?\s*M\b|\d{2,5}\s*[x×]\s*\d{2,5}\s*PX\b|POS\s*\())",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" |-")
        normalised = _normalise_text(candidate)
        if not candidate or any(token in normalised for token in ("LIENZO", "ESCALA", "NOTA:", "TOTAL:")):
            continue
        if len(candidate) <= 80 and any(char.isalpha() for char in candidate):
            return candidate
    return fallback


def _extract_svg_metadata(shapes: list[dict[str, Any]]) -> dict[str, Any]:
    text = "\n".join(
        value
        for value in [
            shapes[0].get("document_text", "") if shapes else "",
            *(hint for shape in shapes for hint in shape.get("text_hints") or []),
        ]
        if value
    )
    metadata: dict[str, Any] = {"source": "svg_text_annotations", "raw_text_available": bool(text)}
    scale = re.search(r"\b(\d+(?:[.,]\d+)?)\s*PX\s*/\s*M\b", _normalise_text(text))
    if scale:
        metadata["pixel_scale_px_per_m"] = float(scale.group(1).replace(",", "."))
    total_modules = re.search(r"\bTOTAL:\s*(\d+)\s+MOD", _normalise_text(text))
    if total_modules:
        metadata["total_modules"] = int(total_modules.group(1))
    area = re.search(r"\bTOTAL:\s*\d+\s+MOD(?:ULOS)?\s+(\d+(?:[.,]\d+)?)\s*M2\b", _normalise_text(text))
    if area:
        metadata["physical_area_m2"] = float(area.group(1).replace(",", "."))
    return metadata


def _parse_svg(path: str | Path, target_size: tuple[int, int]) -> list[dict[str, Any]]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ResolumeAdapterError(f"No se encontró el SVG: {source}")
    try:
        root = ElementTree.parse(source).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise ResolumeAdapterError(f"No se pudo leer el SVG: {source}") from exc
    if _local_name(root.tag) != "svg":
        raise ResolumeAdapterError("El archivo no tiene raíz SVG.")

    root_view = _view_box(root)
    min_x, min_y, view_width, view_height = _find_canvas_view(root, root_view)
    target_width, target_height = target_size
    view_transform = (
        target_width / view_width,
        0.0,
        0.0,
        target_height / view_height,
        -min_x * target_width / view_width,
        -min_y * target_height / view_height,
    )
    shapes: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []

    def visit(element: ElementTree.Element, parent_matrix: tuple[float, ...]) -> None:
        tag = _local_name(element.tag)
        if tag in {"defs", "clippath", "mask", "metadata", "title", "desc"}:
            return
        local_matrix = _transform_matrix(element.attrib.get("transform"))
        raw_matrix = _compose(parent_matrix, local_matrix)
        matrix = _compose(view_transform, raw_matrix)
        if tag == "text":
            text = " ".join("".join(element.itertext()).split())
            x = _length(element.attrib.get("x"))
            y = _length(element.attrib.get("y"))
            if text and x is not None and y is not None:
                annotations.append({"point": _apply(matrix, (x, y)), "text": text})
        shape = _shape_points(element)
        if shape is not None:
            points, kind = shape
            transformed = [_apply(matrix, point) for point in points]
            shapes.append(
                {
                    "name": _element_name(element, len(shapes) + 1),
                    "kind": kind,
                    "points": transformed,
                    "source_tag": tag,
                    "surface_hint": _has_explicit_surface_name(element) or _has_map_fill(element),
                }
            )
        for child in list(element):
            visit(child, raw_matrix)

    visit(root, _IDENTITY)
    if not shapes:
        raise ResolumeAdapterError(f"No se encontraron rectángulos, polígonos, elipses o paths en: {source}")
    hinted = [shape for shape in shapes if shape["surface_hint"]]
    selected = hinted or shapes
    document_text = "\n".join(annotation["text"] for annotation in annotations)
    for shape in selected:
        xs = [point[0] for point in shape["points"]]
        ys = [point[1] for point in shape["points"]]
        left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
        shape["text_hints"] = [
            annotation["text"]
            for annotation in annotations
            if left <= annotation["point"][0] <= right and top <= annotation["point"][1] <= bottom
        ]
        shape["name"] = _surface_name_from_hints(shape["text_hints"], shape["name"])
    if selected:
        selected[0]["document_text"] = document_text
    return selected


def _canonical_rect(points: list[tuple[float, float]]) -> list[tuple[float, float]] | None:
    if len(points) != 4:
        return None
    xs = sorted({round(point[0], 6) for point in points})
    ys = sorted({round(point[1], 6) for point in points})
    if len(xs) != 2 or len(ys) != 2:
        return None
    expected = {(xs[0], ys[0]), (xs[1], ys[0]), (xs[1], ys[1]), (xs[0], ys[1])}
    actual = {(round(x, 6), round(y, 6)) for x, y in points}
    if actual != expected:
        return None
    return [(xs[0], ys[0]), (xs[1], ys[0]), (xs[1], ys[1]), (xs[0], ys[1])]


def _bounds(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [(min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))]


def _fmt(value: float) -> str:
    rounded = round(float(value), 6)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.6f}".rstrip("0").rstrip(".")


def _points(parent: ElementTree.Element, values: list[tuple[float, float]]) -> None:
    for x, y in values:
        ElementTree.SubElement(parent, "v", {"x": _fmt(x), "y": _fmt(y)})


def _param_range(parent: ElementTree.Element, name: str, default: str, value: str, minimum: str, maximum: str, alt_name: str | None = None) -> None:
    attributes = {"name": name, "T": "DOUBLE", "default": default, "value": value}
    if alt_name:
        attributes["altName"] = alt_name
    parameter = ElementTree.SubElement(parent, "ParamRange", attributes)
    ElementTree.SubElement(parameter, "PhaseSourceStatic", {"name": "PhaseSourceStatic"})
    ElementTree.SubElement(parameter, "BehaviourDouble", {"name": "BehaviourDouble"})
    for range_name in ("defaultRange", "minMax", "startStop"):
        ElementTree.SubElement(parameter, "ValueRange", {"name": range_name, "min": minimum, "max": maximum})


def _screen_output_params(parent: ElementTree.Element) -> None:
    params = ElementTree.SubElement(parent, "Params", {"name": "Output"})
    for name, default, minimum, maximum in (
        ("Opacity", "1", "0", "1"),
        ("Brightness", "0", "-1", "1"),
        ("Contrast", "0", "-1", "1"),
        ("Red", "0", "-1", "1"),
        ("Green", "0", "-1", "1"),
        ("Blue", "0", "-1", "1"),
    ):
        _param_range(params, name, default, default, minimum, maximum)


def _slice_output_params(parent: ElementTree.Element) -> None:
    params = ElementTree.SubElement(parent, "Params", {"name": "Output"})
    ElementTree.SubElement(params, "Param", {"name": "Flip", "T": "UINT8", "default": "0", "value": "0"})
    for name in ("Brightness", "Contrast", "Red", "Green", "Blue"):
        _param_range(params, name, "0", "0", "-1", "1")
    ElementTree.SubElement(params, "Param", {"name": "Is Key", "T": "BOOL", "default": "0", "value": "0"})
    ElementTree.SubElement(params, "Param", {"name": "Black BG", "T": "BOOL", "default": "0", "value": "0"})


def _warper(parent: ElementTree.Element, points: list[tuple[float, float]]) -> None:
    warper = ElementTree.SubElement(parent, "Warper")
    params = ElementTree.SubElement(warper, "Params", {"name": "Warper"})
    ElementTree.SubElement(params, "ParamChoice", {"name": "Point Mode", "default": "PM_LINEAR", "value": "PM_LINEAR", "storeChoices": "0"})
    ElementTree.SubElement(params, "Param", {"name": "Flip", "T": "UINT8", "default": "0", "value": "0"})
    bezier = ElementTree.SubElement(warper, "BezierWarper", {"controlWidth": "4", "controlHeight": "4"})
    vertices = ElementTree.SubElement(bezier, "vertices")
    top_left, top_right, bottom_right, bottom_left = points
    for row in range(4):
        vertical = row / 3.0
        for column in range(4):
            horizontal = column / 3.0
            top = (top_left[0] + (top_right[0] - top_left[0]) * horizontal, top_left[1] + (top_right[1] - top_left[1]) * horizontal)
            bottom = (bottom_left[0] + (bottom_right[0] - bottom_left[0]) * horizontal, bottom_left[1] + (bottom_right[1] - bottom_left[1]) * horizontal)
            _points(vertices, [(top[0] + (bottom[0] - top[0]) * vertical, top[1] + (bottom[1] - top[1]) * vertical)])
    homography = ElementTree.SubElement(warper, "Homography")
    source = ElementTree.SubElement(homography, "src")
    _points(source, points)
    destination = ElementTree.SubElement(homography, "dst")
    _points(destination, points)


def _contour(parent: ElementTree.Element, name: str, points: list[tuple[float, float]]) -> None:
    contour = ElementTree.SubElement(parent, f"{name}Contour", {"closed": "1"})
    point_group = ElementTree.SubElement(contour, "points")
    _points(point_group, points)
    ElementTree.SubElement(contour, "segments").text = "L" * len(points)


def _output_device(parent: ElementTree.Element, width: int, height: int) -> None:
    wrapper = ElementTree.SubElement(parent, "OutputDevice")
    device = ElementTree.SubElement(
        wrapper,
        "OutputDeviceVirtual",
        {"name": "INSTAR Output", "deviceId": "VirtualScreen INSTAR", "width": str(width), "height": str(height)},
    )
    params = ElementTree.SubElement(device, "Params", {"name": "Params"})
    _param_range(params, "Width", str(width), str(width), "1", "32768")
    _param_range(params, "Height", str(height), str(height), "1", "32768")


def build_svg_mapping(
    input_svg: str | Path,
    xml_output: str | Path,
    *,
    composition_size: tuple[int, int] | None = None,
    output_svg: str | Path | None = None,
    output_size: tuple[int, int] | None = None,
    screen_name: str = "INSTAR SVG Map",
    resolume_minor: int = 27,
) -> dict[str, Any]:
    input_path = Path(input_svg).expanduser().resolve()
    if composition_size is None:
        root = ElementTree.parse(input_path).getroot()
        view = _find_canvas_view(root, _view_box(root))
        composition_size = (int(round(view[2])), int(round(view[3])))
    if output_size is None:
        if output_svg:
            output_root = ElementTree.parse(Path(output_svg).expanduser().resolve()).getroot()
            output_view = _view_box(output_root)
            output_size = (int(round(output_view[2])), int(round(output_view[3])))
        else:
            output_size = composition_size
    if min(*composition_size, *output_size) <= 0:
        raise ResolumeAdapterError("Las resoluciones de composición y salida deben ser positivas.")

    input_shapes = _parse_svg(input_path, composition_size)
    output_shapes = _parse_svg(output_svg, output_size) if output_svg else None
    warnings: list[dict[str, Any]] = []
    if output_shapes is not None and len(output_shapes) != len(input_shapes):
        raise ResolumeAdapterError("Input SVG y Output SVG deben contener la misma cantidad de superficies y en el mismo orden.")
    if output_shapes is None:
        warnings.append({"code": "output_geometry_scaled", "message": "No se entregó Output SVG; OutputRect se derivó escalando la geometría del Input SVG."})

    source_digest = hashlib.sha256(input_path.read_bytes()).hexdigest()
    if output_svg:
        source_digest = hashlib.sha256((source_digest + hashlib.sha256(Path(output_svg).read_bytes()).hexdigest()).encode()).hexdigest()
    screen_id = f"instar-{source_digest[:16]}"
    root = ElementTree.Element("XmlState", {"name": screen_name})
    ElementTree.SubElement(root, "versionInfo", {"name": "Resolume Arena", "majorVersion": "7", "minorVersion": str(resolume_minor), "microVersion": "0", "revision": "0"})
    setup = ElementTree.SubElement(root, "ScreenSetup", {"name": "ScreenSetup"})
    ElementTree.SubElement(setup, "Params", {"name": "ScreenSetupParams"})
    ElementTree.SubElement(setup, "CurrentCompositionTextureSize", {"width": str(composition_size[0]), "height": str(composition_size[1])})
    screens = ElementTree.SubElement(setup, "screens")
    screen = ElementTree.SubElement(screens, "Screen", {"name": screen_name, "uniqueId": screen_id})
    screen_params = ElementTree.SubElement(screen, "Params", {"name": "Params"})
    ElementTree.SubElement(screen_params, "Param", {"name": "Name", "T": "STRING", "default": "", "value": screen_name})
    ElementTree.SubElement(screen_params, "Param", {"name": "Enabled", "T": "BOOL", "default": "1", "value": "1"})
    ElementTree.SubElement(screen_params, "Param", {"name": "Hidden", "T": "BOOL", "default": "0", "value": "0"})
    _screen_output_params(screen)
    guides = ElementTree.SubElement(screen, "guides")
    for guide_type in ("0", "1"):
        guide = ElementTree.SubElement(guides, "ScreenGuide", {"name": "ScreenGuide", "type": guide_type})
        guide_params = ElementTree.SubElement(guide, "Params", {"name": "Params"})
        ElementTree.SubElement(guide_params, "ParamPixels", {"name": "Image"})
        _param_range(guide_params, "Opacity", "0.25", "0.25", "0", "1")
    layers = ElementTree.SubElement(screen, "layers")
    shape_records: list[dict[str, Any]] = []

    for index, input_shape in enumerate(input_shapes, start=1):
        input_points = _canonical_rect(input_shape["points"]) if input_shape["kind"] == "rect" else None
        if input_points is None:
            input_points = _canonical_rect(input_shape["points"]) or _bounds(input_shape["points"])
        if output_shapes is not None:
            output_shape = output_shapes[index - 1]
            output_points = _canonical_rect(output_shape["points"]) if output_shape["kind"] == "rect" else None
            if output_points is None:
                output_points = _canonical_rect(output_shape["points"]) or _bounds(output_shape["points"])
            output_contour_points = output_shape["points"]
        else:
            sx = output_size[0] / composition_size[0]
            sy = output_size[1] / composition_size[1]
            output_points = [(x * sx, y * sy) for x, y in input_points]
            output_contour_points = output_points

        is_rect = input_shape["kind"] == "rect" and _canonical_rect(input_shape["points"]) is not None
        tag = "Slice" if is_rect else "Polygon"
        slice_id = f"{screen_id}-slice-{index:03d}"
        attributes = {"uniqueId": slice_id}
        if not is_rect:
            attributes["IsVirgin"] = "0"
        slice_element = ElementTree.SubElement(layers, tag, attributes)
        common = ElementTree.SubElement(slice_element, "Params", {"name": "Common"})
        ElementTree.SubElement(common, "Param", {"name": "Name", "T": "STRING", "default": "Layer", "value": input_shape["name"]})
        ElementTree.SubElement(common, "Param", {"name": "Enabled", "T": "BOOL", "default": "1", "value": "1"})
        input_params = ElementTree.SubElement(slice_element, "Params", {"name": "Input"})
        ElementTree.SubElement(input_params, "ParamChoice", {"name": "Input Source", "default": "0:1", "value": "0:1", "storeChoices": "0"})
        ElementTree.SubElement(input_params, "Param", {"name": "Input Opacity", "T": "BOOL", "default": "1", "value": "1"})
        ElementTree.SubElement(input_params, "Param", {"name": "Input Bypass/Solo", "T": "BOOL", "default": "1", "value": "1"})
        ElementTree.SubElement(input_params, "Param", {"name": "SoftEdgeEnable", "T": "BOOL", "default": "0", "value": "0"})
        _slice_output_params(slice_element)
        input_rect = ElementTree.SubElement(slice_element, "InputRect", {"orientation": "0"})
        _points(input_rect, input_points)
        output_rect = ElementTree.SubElement(slice_element, "OutputRect", {"orientation": "0"})
        _points(output_rect, output_points)
        if is_rect:
            _warper(slice_element, output_points)
        else:
            _contour(slice_element, "Input", input_shape["points"])
            _contour(slice_element, "Output", output_contour_points)
        shape_records.append(
            {
                "id": slice_id,
                "name": input_shape["name"],
                "type": tag,
                "text_hints": input_shape.get("text_hints", []),
                "input_points": input_shape["points"],
                "output_points": output_contour_points,
            }
        )

    _output_device(screen, output_size[0], output_size[1])
    soft_edging = ElementTree.SubElement(setup, "SoftEdging")
    soft_params = ElementTree.SubElement(soft_edging, "Params", {"name": "Soft Edge"})
    _param_range(soft_params, "Gamma Red", "2", "2", "1", "3")
    _param_range(soft_params, "Gamma Green", "2", "2", "1", "3")
    _param_range(soft_params, "Gamma Blue", "2", "2", "1", "3")
    _param_range(soft_params, "Gamma", "1", "1", "0", "1")
    _param_range(soft_params, "Luminance", "0.5", "0.5", "0", "1")
    _param_range(soft_params, "Power", "2", "2", "0.1", "7")

    ElementTree.indent(root, space="\t")
    xml_path = Path(xml_output).expanduser().resolve()
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)
    return {
        "schema_version": "0.1",
        "map_type": "InstarSvgMappingCandidate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"input_svg": str(input_path), "output_svg": str(Path(output_svg).expanduser().resolve()) if output_svg else None},
        "composition": {"width": composition_size[0], "height": composition_size[1]},
        "output": {"width": output_size[0], "height": output_size[1]},
        "screen_name": screen_name,
        "metadata": _extract_svg_metadata(input_shapes),
        "slices": shape_records,
        "artifacts": {"advanced_output_xml": str(xml_path)},
        "validation": {"status": "WARN" if warnings else "PASS", "errors": [], "warnings": warnings},
        "limitations": [
            "La correspondencia Input/Output de SVG separado se realiza por orden, no por semántica de nombre.",
            "El candidato no confirma la conexión física, el procesador LED ni el routing del venue.",
            "Los arcos SVG deben convertirse a Bézier antes de importar.",
        ],
    }


def svg_mapping_text_report(report: dict[str, Any]) -> str:
    validation = report.get("validation") or {}
    lines = [
        "RESOLUME_ADAPTER INSTAR SVG MAP",
        "===============================",
        f"Entrada: {report.get('source', {}).get('input_svg')}",
        f"Salida XML: {report.get('artifacts', {}).get('advanced_output_xml')}",
        f"Composición: {report.get('composition', {}).get('width')} × {report.get('composition', {}).get('height')}",
        f"Output: {report.get('output', {}).get('width')} × {report.get('output', {}).get('height')}",
        f"Slices: {len(report.get('slices') or [])}",
        f"Estado: {validation.get('status', 'UNKNOWN')}",
    ]
    for warning in validation.get("warnings") or []:
        lines.append(f"  [WARN] {warning.get('message')}")
    return "\n".join(lines)


def write_svg_mapping_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path

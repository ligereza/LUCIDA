"""Aplicación de geometría INSTAR sobre un template Advanced Output existente."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .instar_svg import _canonical_rect, _find_canvas_view, _parse_svg, _view_box
from .media import ResolumeAdapterError


def _template_size(root: ElementTree.Element) -> tuple[int, int] | None:
    texture = root.find("./ScreenSetup/CurrentCompositionTextureSize")
    if texture is None:
        texture = root.find("./CurrentCompositionTextureSize")
    if texture is None:
        return None
    try:
        width, height = int(texture.attrib["width"]), int(texture.attrib["height"])
    except (KeyError, TypeError, ValueError):
        return None
    return (width, height) if width > 0 and height > 0 else None


def _slice_name(element: ElementTree.Element) -> str | None:
    common = element.find("./Params[@name='Common']")
    if common is not None:
        name = common.find("./Param[@name='Name']")
        if name is not None and name.attrib.get("value"):
            return name.attrib["value"]
    return element.attrib.get("name")


def _replace_input_rect(element: ElementTree.Element, points: list[tuple[float, float]]) -> None:
    rect = element.find("./InputRect")
    if rect is None:
        rect = ElementTree.Element("InputRect", {"orientation": "0"})
        output_rect = element.find("./OutputRect")
        children = list(element)
        if output_rect is not None:
            element.insert(children.index(output_rect), rect)
        else:
            element.append(rect)
    rect.attrib["orientation"] = "0"
    for child in list(rect):
        rect.remove(child)
    for x, y in points:
        ElementTree.SubElement(rect, "v", {"x": _format(x), "y": _format(y)})


def _format(value: float) -> str:
    rounded = round(float(value), 6)
    return str(int(rounded)) if rounded == int(rounded) else f"{rounded:.6f}".rstrip("0").rstrip(".")


def apply_input_svg_to_template(
    template_xml: str | Path,
    input_svg: str | Path,
    xml_output: str | Path,
    *,
    composition_size: tuple[int, int] | None = None,
) -> dict[str, Any]:
    template_path = Path(template_xml).expanduser().resolve()
    input_path = Path(input_svg).expanduser().resolve()
    if not template_path.is_file():
        raise ResolumeAdapterError(f"No se encontró el template Advanced Output: {template_path}")
    try:
        root = ElementTree.parse(template_path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise ResolumeAdapterError(f"No se pudo leer el template Advanced Output: {template_path}") from exc
    if root.tag not in {"XmlState", "ScreenSetup"}:
        raise ResolumeAdapterError(f"El template no parece Advanced Output: raíz {root.tag!r}")

    resolved_size = composition_size or _template_size(root)
    if resolved_size is None:
        svg_root = ElementTree.parse(input_path).getroot()
        view = _find_canvas_view(svg_root, _view_box(svg_root))
        resolved_size = (int(round(view[2])), int(round(view[3])))
    shapes = _parse_svg(input_path, resolved_size)
    by_name: dict[str, list[dict[str, Any]]] = {}
    for shape in shapes:
        by_name.setdefault(shape["name"], []).append(shape)

    setup = root.find("./ScreenSetup")
    if setup is None:
        setup = root
    template_elements = [
        element
        for screen in setup.findall("./screens/Screen")
        for layers in [screen.find("./layers")]
        if layers is not None
        for element in list(layers)
        if element.tag in {"Slice", "Polygon"}
    ]
    template_names = [_slice_name(element) for element in template_elements]
    matched: list[str] = []
    unmatched_input: list[str] = []
    unsupported_input: list[str] = []
    ambiguous_template: list[str] = []

    for element in template_elements:
        name = _slice_name(element)
        if not name or name not in by_name:
            continue
        candidates = by_name[name]
        if len(candidates) != 1:
            ambiguous_template.append(name)
            continue
        points = _canonical_rect(candidates[0]["points"])
        if points is None:
            unsupported_input.append(name)
            continue
        _replace_input_rect(element, points)
        matched.append(name)

    for name in by_name:
        if name not in template_names:
            unmatched_input.append(name)

    output_path = Path(xml_output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.indent(root, space="\t")
    ElementTree.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)
    status = "PASS" if matched and not unsupported_input and not ambiguous_template else "REVIEW"
    return {
        "schema_version": "0.1",
        "map_type": "InstarInputTemplateApplication",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"template_xml": str(template_path), "input_svg": str(input_path)},
        "composition": {"width": resolved_size[0], "height": resolved_size[1]},
        "matched_slices": matched,
        "unmatched_input": unmatched_input,
        "unsupported_input": unsupported_input,
        "ambiguous_template": ambiguous_template,
        "processor_routing": {"status": "PRESERVED_FROM_TEMPLATE"},
        "output": {"xml": str(output_path), "input_rects_changed": len(matched), "output_rects_changed": 0},
        "validation": {"status": status, "errors": [], "warnings": [] if status == "PASS" else [
            "El resultado conserva el routing del template, pero requiere revisión cuando hay slices sin coincidencia o geometría no rectangular."
        ]},
        "limitations": [
            "Solo actualiza InputRect de superficies rectangulares coincidentes por nombre.",
            "No modifica OutputRect, dispositivos, procesadores, puertos ni warpers del template.",
            "La carga y validación física en Resolume permanecen fuera de esta orden.",
        ],
    }


def input_template_text_report(report: dict[str, Any]) -> str:
    output = report.get("output") or {}
    validation = report.get("validation") or {}
    return "\n".join([
        "RESOLUME_ADAPTER INSTAR INPUT TEMPLATE",
        "=======================================",
        f"Template: {report.get('source', {}).get('template_xml')}",
        f"Input SVG: {report.get('source', {}).get('input_svg')}",
        f"Slices actualizadas: {output.get('input_rects_changed', 0)}",
        f"OutputRects modificados: {output.get('output_rects_changed', 0)}",
        f"Routing: {(report.get('processor_routing') or {}).get('status')}",
        f"Estado: {validation.get('status', 'UNKNOWN')}",
    ])


def write_input_template_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path

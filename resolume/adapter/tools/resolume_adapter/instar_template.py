"""Aplicación de geometría INSTAR sobre un template Advanced Output existente."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import unicodedata
from typing import Any, Mapping
from xml.etree import ElementTree

from .instar_image import build_raster_mapping
from .instar_routing import import_pixel_peeker_routing
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


def _name_key(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if char.isalnum())


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
    aliases: Mapping[str, str] | None = None,
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
        by_name.setdefault(_name_key(shape["name"]), []).append(shape)
    alias_targets = {_name_key(target): _name_key(source) for source, target in (aliases or {}).items()}

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
    match_methods: dict[str, str] = {}
    matched_input_names: set[str] = set()

    for element in template_elements:
        name = _slice_name(element)
        if not name:
            continue
        target_key = _name_key(name)
        source_key = alias_targets.get(target_key, target_key)
        candidates = by_name.get(source_key, [])
        if len(candidates) != 1:
            if candidates:
                ambiguous_template.append(name)
            continue
        points = _canonical_rect(candidates[0]["points"])
        if points is None:
            unsupported_input.append(name)
            continue
        _replace_input_rect(element, points)
        matched.append(name)
        matched_input_names.add(source_key)
        match_methods[name] = "alias" if target_key in alias_targets else "normalised_name"

    for shape in shapes:
        if _name_key(shape["name"]) not in matched_input_names:
            unmatched_input.append(shape["name"])
    matched_template_names = {_name_key(name) for name in matched}
    unmatched_template = [name for name in template_names if name and _name_key(name) not in matched_template_names]

    output_path = Path(xml_output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.indent(root, space="\t")
    ElementTree.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)
    status = "PASS" if (
        matched
        and not unmatched_input
        and not unmatched_template
        and not unsupported_input
        and not ambiguous_template
    ) else "REVIEW"
    return {
        "schema_version": "0.1",
        "map_type": "InstarInputTemplateApplication",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"template_xml": str(template_path), "input_svg": str(input_path)},
        "composition": {"width": resolved_size[0], "height": resolved_size[1]},
        "matched_slices": matched,
        "unmatched_input": unmatched_input,
        "unmatched_template": unmatched_template,
        "unsupported_input": unsupported_input,
        "ambiguous_template": ambiguous_template,
        "match_methods": match_methods,
        "alias_count": len(alias_targets),
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


def apply_raster_image_to_template(
    template_xml: str | Path,
    image_path: str | Path,
    xml_output: str | Path,
    *,
    canvas_size: tuple[int, int] | None = None,
    ocr_executable: str | Path | None = None,
    pdf_renderer: str | Path | None = None,
    pdf_page: int = 1,
    pdf_dpi: int = 200,
    aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Aplica un mapa raster al InputRect de un template sin tocar su output."""

    with tempfile.TemporaryDirectory(prefix="instar-template-image-") as directory:
        directory_path = Path(directory)
        raster_report = build_raster_mapping(
            image_path,
            directory_path / "detected.xml",
            canvas_size=canvas_size,
            svg_output=directory_path / "detected.svg",
            ocr_executable=ocr_executable,
            pdf_renderer=pdf_renderer,
            pdf_page=pdf_page,
            pdf_dpi=pdf_dpi,
        )
        report = apply_input_svg_to_template(
            template_xml,
            directory_path / "detected.svg",
            xml_output,
            composition_size=(raster_report["canvas"]["width"], raster_report["canvas"]["height"]),
            aliases=aliases,
        )
    report["source"]["input_image"] = str(Path(image_path).expanduser().resolve())
    report["source"]["input_svg"] = None
    report["source"]["input_kind"] = "raster"
    report["raster_detection"] = {
        "layout_role": raster_report.get("layout_role"),
        "regions": raster_report.get("regions"),
        "metadata": raster_report.get("metadata"),
        "ocr": {
            "available": (raster_report.get("ocr") or {}).get("available", False),
            "language": (raster_report.get("ocr") or {}).get("language"),
            "passes": (raster_report.get("ocr") or {}).get("passes", 0),
        },
    }
    return report


def apply_routed_layout_to_template(
    template_xml: str | Path,
    interchange: str | Path | Mapping[str, Any],
    layout_report: str | Path | Mapping[str, Any],
    xml_output: str | Path,
    *,
    tolerance: float = 1.0,
) -> dict[str, Any]:
    """Apply matched layout geometry to slices named ``processor + port``.

    Pixel Peeker supplies the processor/port identity and the INSTAR layout
    supplies the named surface geometry. Only ``InputRect`` is replaced. The
    template remains the sole authority for ``OutputRect``, devices, warpers
    and any existing processor assignment.
    """

    routing = import_pixel_peeker_routing(
        interchange,
        layout_report=layout_report,
        tolerance=tolerance,
    )
    template_path = Path(template_xml).expanduser().resolve()
    if not template_path.is_file():
        raise ResolumeAdapterError(f"No se encontró el template Advanced Output: {template_path}")
    try:
        root = ElementTree.parse(template_path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise ResolumeAdapterError(f"No se pudo leer el template Advanced Output: {template_path}") from exc
    if root.tag not in {"XmlState", "ScreenSetup"}:
        raise ResolumeAdapterError(f"El template no parece Advanced Output: raíz {root.tag!r}")

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

    route_matches = routing.get("comparison", {}).get("matches", [])
    routes_by_slice: dict[str, list[dict[str, Any]]] = {}
    all_route_ids: list[str] = []
    for processor in routing.get("processors", []):
        processor_name = processor["name"]
        for port in processor.get("ports", []):
            if port.get("bounds") is not None:
                all_route_ids.append(f"{processor_name}/{port['label']}")
    for match in route_matches:
        route_id = f"{match['processor']}/{match['port']}"
        routes_by_slice.setdefault(_name_key(f"{match['processor']} {match['port']}"), []).append({
            "route_id": route_id,
            "surface": match["surface"],
            "bounds": match["bounds"],
            "method": match["method"],
            "score": match["score"],
        })

    matched_slices: list[dict[str, Any]] = []
    ambiguous_template: list[str] = []
    unmatched_template: list[str] = []
    matched_route_ids: set[str] = set()
    for element in template_elements:
        name = _slice_name(element)
        if not name:
            continue
        candidates = routes_by_slice.get(_name_key(name), [])
        if len(candidates) != 1:
            if len(candidates) > 1:
                ambiguous_template.append(name)
            else:
                unmatched_template.append(name)
            continue
        candidate = candidates[0]
        bounds = candidate["bounds"]
        points = [
            (float(bounds["x"]), float(bounds["y"])),
            (float(bounds["x"] + bounds["width"]), float(bounds["y"])),
            (float(bounds["x"] + bounds["width"]), float(bounds["y"] + bounds["height"])),
            (float(bounds["x"]), float(bounds["y"] + bounds["height"])),
        ]
        _replace_input_rect(element, points)
        matched_route_ids.add(candidate["route_id"])
        matched_slices.append({
            "template_slice": name,
            "route": candidate["route_id"],
            "surface": candidate["surface"],
            "method": candidate["method"],
            "score": candidate["score"],
        })

    unmatched_routes = [route_id for route_id in all_route_ids if route_id not in matched_route_ids]
    output_path = Path(xml_output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.indent(root, space="\t")
    ElementTree.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)
    validation_status = "PASS" if (
        matched_slices
        and routing.get("comparison", {}).get("geometry_status") == "GEOMETRIC_MATCH"
        and not unmatched_routes
        and not unmatched_template
        and not ambiguous_template
    ) else "REVIEW"
    return {
        "schema_version": "0.1",
        "map_type": "InstarRoutedTemplateApplication",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "template_xml": str(template_path),
            "interchange": routing.get("source", {}).get("interchange"),
            "layout_report": routing.get("source", {}).get("layout_report"),
        },
        "matched_slices": matched_slices,
        "unmatched_routes": unmatched_routes,
        "unmatched_template": unmatched_template,
        "ambiguous_template": ambiguous_template,
        "processor_routing": {"status": "PRESERVED_FROM_TEMPLATE"},
        "output": {
            "xml": str(output_path),
            "input_rects_changed": len(matched_slices),
            "output_rects_changed": 0,
            "devices_changed": 0,
        },
        "validation": {
            "status": validation_status,
            "errors": [],
            "warnings": [
                "La aplicación usa coincidencias geométricas; no demuestra el patch físico ni el cableado del venue.",
            ],
        },
        "physical_status": "UNVERIFIED",
        "limitations": [
            "El nombre del slice debe corresponder a '<processor name> <port label>' normalizado.",
            "Solo se modifica InputRect; OutputRect, dispositivos, warpers y routing del template se conservan.",
            "Un intercambio parcial produce un candidato REVIEW, no una aplicación total silenciosa.",
        ],
    }


def routed_template_text_report(report: dict[str, Any]) -> str:
    output = report.get("output") or {}
    validation = report.get("validation") or {}
    return "\n".join([
        "RESOLUME_ADAPTER INSTAR ROUTED TEMPLATE",
        "=========================================",
        f"Template: {report.get('source', {}).get('template_xml')}",
        f"Slices actualizadas: {output.get('input_rects_changed', 0)}",
        f"Rutas sin coincidencia: {len(report.get('unmatched_routes') or [])}",
        f"Slices sin coincidencia: {len(report.get('unmatched_template') or [])}",
        f"OutputRects modificados: {output.get('output_rects_changed', 0)}",
        f"Dispositivos modificados: {output.get('devices_changed', 0)}",
        f"Routing: {(report.get('processor_routing') or {}).get('status')}",
        f"Hardware: {report.get('physical_status', 'UNVERIFIED')}",
        f"Estado: {validation.get('status', 'REVIEW')}",
    ])


def input_template_text_report(report: dict[str, Any]) -> str:
    output = report.get("output") or {}
    validation = report.get("validation") or {}
    return "\n".join([
        "RESOLUME_ADAPTER INSTAR INPUT TEMPLATE",
        "=======================================",
        f"Template: {report.get('source', {}).get('template_xml')}",
        f"Entrada: {report.get('source', {}).get('input_image') or report.get('source', {}).get('input_svg')}",
        f"Slices actualizadas: {output.get('input_rects_changed', 0)}",
        f"Template sin coincidencia: {len(report.get('unmatched_template') or [])}",
        f"Input sin coincidencia: {len(report.get('unmatched_input') or [])}",
        f"OutputRects modificados: {output.get('output_rects_changed', 0)}",
        f"Routing: {(report.get('processor_routing') or {}).get('status')}",
        f"Estado: {validation.get('status', 'UNKNOWN')}",
    ])


def write_input_template_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path

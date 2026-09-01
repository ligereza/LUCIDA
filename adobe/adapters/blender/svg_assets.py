"""Small, dependency-free SVG asset importer for Blender.

The native Blender SVG importer is intentionally limited to path geometry. This
module keeps the source SVG editable as 2D curves while handling the parts that
matter for editorial assets: basic shapes, paths, CSS paint, opacity, transforms
and deterministic layer order.
"""

import math
import re
import xml.etree.ElementTree as ET

import bpy


NUMBER = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
TOKEN_RE = re.compile(rf"[AaCcHhLlMmQqSsTtVvZz]|{NUMBER}")
TRANSFORM_RE = re.compile(r"([a-zA-Z]+)\s*\(([^)]*)\)")
STYLE_BLOCK_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _tag(element):
    return element.tag.rsplit("}", 1)[-1].lower()


def _number(value, fallback=0.0):
    try:
        return float(str(value).strip().replace("px", ""))
    except (TypeError, ValueError):
        return fallback


def _dimension(value, base, fallback=0.0):
    text = str(value or "").strip()
    if text.endswith("%"):
        return _number(text[:-1], fallback * 100.0) * base / 100.0
    return _number(text, fallback)


def _numbers(value):
    return [_number(item) for item in re.findall(NUMBER, str(value or ""))]


def _matrix_multiply(left, right):
    a1, b1, c1, d1, e1, f1 = left
    a2, b2, c2, d2, e2, f2 = right
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _apply_matrix(matrix, point):
    a, b, c, d, e, f = matrix
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


def _parse_transform(value):
    result = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, raw in TRANSFORM_RE.findall(value or ""):
        values = _numbers(raw)
        name = name.lower()
        if name == "matrix" and len(values) >= 6:
            current = tuple(values[:6])
        elif name == "translate":
            current = (1.0, 0.0, 0.0, 1.0, values[0] if values else 0.0, values[1] if len(values) > 1 else 0.0)
        elif name == "scale":
            sx = values[0] if values else 1.0
            sy = values[1] if len(values) > 1 else sx
            current = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif name == "rotate" and values:
            angle = math.radians(values[0])
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            current = (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
            if len(values) >= 3:
                cx, cy = values[1], values[2]
                result = _matrix_multiply(result, (1.0, 0.0, 0.0, 1.0, cx, cy))
                result = _matrix_multiply(result, current)
                result = _matrix_multiply(result, (1.0, 0.0, 0.0, 1.0, -cx, -cy))
                continue
        elif name == "skewx" and values:
            current = (1.0, 0.0, math.tan(math.radians(values[0])), 1.0, 0.0, 0.0)
        elif name == "skewy" and values:
            current = (1.0, math.tan(math.radians(values[0])), 0.0, 1.0, 0.0, 0.0)
        else:
            continue
        result = _matrix_multiply(result, current)
    return result


def _sample_cubic(p0, p1, p2, p3, steps=12):
    points = []
    for index in range(1, steps + 1):
        t = index / steps
        inv = 1.0 - t
        points.append((
            inv ** 3 * p0[0] + 3 * inv ** 2 * t * p1[0] + 3 * inv * t ** 2 * p2[0] + t ** 3 * p3[0],
            inv ** 3 * p0[1] + 3 * inv ** 2 * t * p1[1] + 3 * inv * t ** 2 * p2[1] + t ** 3 * p3[1],
        ))
    return points


def _sample_quadratic(p0, p1, p2, steps=10):
    points = []
    for index in range(1, steps + 1):
        t = index / steps
        inv = 1.0 - t
        points.append((
            inv ** 2 * p0[0] + 2 * inv * t * p1[0] + t ** 2 * p2[0],
            inv ** 2 * p0[1] + 2 * inv * t * p1[1] + t ** 2 * p2[1],
        ))
    return points


def _path_subpaths(value):
    tokens = TOKEN_RE.findall(value or "")
    index = 0
    command = None
    previous_command = None
    current = (0.0, 0.0)
    start = (0.0, 0.0)
    last_cubic_control = None
    last_quadratic_control = None
    subpaths = []
    active = None

    def take(count):
        nonlocal index
        if index + count > len(tokens):
            return None
        values = []
        for _ in range(count):
            if re.fullmatch(r"[A-Za-z]", tokens[index]):
                return None
            values.append(float(tokens[index]))
            index += 1
        return values

    while index < len(tokens):
        if re.fullmatch(r"[A-Za-z]", tokens[index]):
            command = tokens[index]
            index += 1
            if command.upper() == "Z":
                if active and active["points"]:
                    active["closed"] = True
                    current = start
                previous_command = command
                command = None
                last_cubic_control = None
                last_quadratic_control = None
                continue
        if command is None:
            break
        relative = command.islower()
        op = command.upper()
        if op == "M":
            values = take(2)
            if values is None:
                break
            point = (values[0] + current[0], values[1] + current[1]) if relative else (values[0], values[1])
            active = {"points": [point], "closed": False}
            subpaths.append(active)
            current = point
            start = point
            command = "l" if relative else "L"
            last_cubic_control = None
            last_quadratic_control = None
            previous_command = "M"
            continue
        if active is None:
            command = None
            continue
        if op == "L":
            values = take(2)
            if values is None:
                command = None
                continue
            point = (values[0] + current[0], values[1] + current[1]) if relative else (values[0], values[1])
            active["points"].append(point)
            current = point
        elif op == "H":
            values = take(1)
            if values is None:
                command = None
                continue
            point = ((values[0] + current[0]) if relative else values[0], current[1])
            active["points"].append(point)
            current = point
        elif op == "V":
            values = take(1)
            if values is None:
                command = None
                continue
            point = (current[0], (values[0] + current[1]) if relative else values[0])
            active["points"].append(point)
            current = point
        elif op == "C":
            values = take(6)
            if values is None:
                command = None
                continue
            points = [(values[i] + current[i % 2], values[i + 1] + current[(i + 1) % 2]) if relative else (values[i], values[i + 1]) for i in range(0, 6, 2)]
            active["points"].extend(_sample_cubic(current, *points))
            current = points[-1]
            last_cubic_control = points[-2]
            last_quadratic_control = None
        elif op == "S":
            values = take(4)
            if values is None:
                command = None
                continue
            control = (2 * current[0] - last_cubic_control[0], 2 * current[1] - last_cubic_control[1]) if last_cubic_control and previous_command and previous_command.upper() in {"C", "S"} else current
            points = [(values[i] + current[i % 2], values[i + 1] + current[(i + 1) % 2]) if relative else (values[i], values[i + 1]) for i in range(0, 4, 2)]
            active["points"].extend(_sample_cubic(current, control, points[0], points[1]))
            current = points[1]
            last_cubic_control = points[0]
            last_quadratic_control = None
        elif op == "Q":
            values = take(4)
            if values is None:
                command = None
                continue
            points = [(values[i] + current[i % 2], values[i + 1] + current[(i + 1) % 2]) if relative else (values[i], values[i + 1]) for i in range(0, 4, 2)]
            active["points"].extend(_sample_quadratic(current, points[0], points[1]))
            current = points[1]
            last_quadratic_control = points[0]
            last_cubic_control = None
        elif op == "T":
            values = take(2)
            if values is None:
                command = None
                continue
            control = (2 * current[0] - last_quadratic_control[0], 2 * current[1] - last_quadratic_control[1]) if last_quadratic_control and previous_command and previous_command.upper() in {"Q", "T"} else current
            point = (values[0] + current[0], values[1] + current[1]) if relative else (values[0], values[1])
            active["points"].extend(_sample_quadratic(current, control, point))
            current = point
            last_quadratic_control = control
            last_cubic_control = None
        elif op == "A":
            values = take(7)
            if values is None:
                command = None
                continue
            point = (values[5] + current[0], values[6] + current[1]) if relative else (values[5], values[6])
            active["points"].append(point)
            current = point
            last_cubic_control = None
            last_quadratic_control = None
        else:
            command = None
            continue
        previous_command = op
    return [item for item in subpaths if len(item["points"]) >= 2]


def _shape_subpaths(element, viewport_width=1.0, viewport_height=1.0):
    tag = _tag(element)
    if tag == "path":
        return _path_subpaths(element.attrib.get("d", ""))
    if tag == "rect":
        x, y = _dimension(element.attrib.get("x"), viewport_width), _dimension(element.attrib.get("y"), viewport_height)
        width, height = _dimension(element.attrib.get("width"), viewport_width), _dimension(element.attrib.get("height"), viewport_height)
        return [{"points": [(x, y), (x + width, y), (x + width, y + height), (x, y + height)], "closed": True}]
    if tag in {"polygon", "polyline"}:
        values = _numbers(element.attrib.get("points", ""))
        points = list(zip(values[::2], values[1::2]))
        return [{"points": points, "closed": tag == "polygon"}] if len(points) >= 2 else []
    if tag == "line":
        return [{"points": [(_number(element.attrib.get("x1")), _number(element.attrib.get("y1"))), (_number(element.attrib.get("x2")), _number(element.attrib.get("y2")))], "closed": False}]
    if tag in {"circle", "ellipse"}:
        cx, cy = _dimension(element.attrib.get("cx"), viewport_width), _dimension(element.attrib.get("cy"), viewport_height)
        rx = _dimension(element.attrib.get("r"), viewport_width, 0.0) if tag == "circle" else _dimension(element.attrib.get("rx"), viewport_width)
        ry = rx if tag == "circle" else _dimension(element.attrib.get("ry"), viewport_height)
        points = [(cx + rx * math.cos(index * 2 * math.pi / 48), cy + ry * math.sin(index * 2 * math.pi / 48)) for index in range(48)]
        return [{"points": points, "closed": True}]
    return []


def _style_declarations(value):
    return {key.strip().lower(): item.strip() for key, item in (chunk.split(":", 1) for chunk in str(value or "").split(";") if ":" in chunk)}


def _css_styles(root):
    styles = {}
    for element in root.iter():
        if _tag(element) != "style":
            continue
        for selector, body in STYLE_BLOCK_RE.findall("".join(element.itertext())):
            declarations = _style_declarations(body)
            for item in selector.split(","):
                styles[item.strip()] = declarations
    return styles


def _element_style(element, inherited, css):
    style = dict(inherited)
    classes = str(element.attrib.get("class", "")).split()
    if element.attrib.get("id"):
        style.update(css.get(f"#{element.attrib['id']}", {}))
    for class_name in classes:
        style.update(css.get(f".{class_name}", {}))
    for key in ("fill", "stroke", "stroke-width", "opacity", "fill-opacity", "stroke-opacity", "color"):
        if key in element.attrib:
            style[key] = element.attrib[key]
    style.update(_style_declarations(element.attrib.get("style", "")))
    return style


def _color(value, fallback=(1.0, 1.0, 1.0, 1.0), current=(1.0, 1.0, 1.0, 1.0), gradients=None):
    value = str(value or "").strip().lower()
    if not value or value == "none":
        return None
    if value == "currentcolor":
        return current
    if value.startswith("url(#") and gradients:
        gradient_id = value[5:-1]
        value = gradients.get(gradient_id, value)
    named = {"black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000", "blue": "#0000ff", "yellow": "#ffff00", "transparent": "#00000000"}
    value = named.get(value, value)
    if value.startswith("#"):
        raw = value[1:]
        if len(raw) in {3, 4}:
            raw = "".join(char * 2 for char in raw)
        if len(raw) in {6, 8}:
            try:
                values = [int(raw[index:index + 2], 16) / 255.0 for index in range(0, len(raw), 2)]
                return tuple(values[:3]) + (values[3] if len(values) == 4 else 1.0,)
            except ValueError:
                return fallback
    match = re.match(r"rgba?\(([^)]*)\)", value)
    if match:
        values = [item.strip() for item in match.group(1).split(",")]
        rgb = [(_number(item[:-1]) / 100.0 if item.endswith("%") else _number(item) / 255.0) for item in values[:3]]
        alpha = _number(values[3]) if len(values) > 3 else 1.0
        return tuple(max(0.0, min(1.0, item)) for item in rgb) + (max(0.0, min(1.0, alpha)),)
    return fallback


def _gradient_colors(root):
    gradients = {}
    for element in root.iter():
        if _tag(element) not in {"lineargradient", "radialgradient"}:
            continue
        stops = []
        for stop in element:
            if _tag(stop) == "stop":
                stop_style = _style_declarations(stop.attrib.get("style", ""))
                stops.append(stop_style.get("stop-color", stop.attrib.get("stop-color", "#ffffff")))
        if stops:
            gradients[element.attrib.get("id", "")] = stops[0]
    return gradients


def _srgb_to_linear(value):
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _linear_color(color):
    return tuple(_srgb_to_linear(value) for value in color[:3]) + (color[3],)


def emission_material(name, color):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    rgba = _linear_color(color)
    emission.inputs["Color"].default_value = rgba
    emission.inputs["Strength"].default_value = 1.0
    mix.inputs[0].default_value = rgba[3]
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs[0])
    material.diffuse_color = rgba
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = "DITHERED"
    return material


def _curve_object(name, subpaths, material, stroke=False, stroke_width=0.001, z=0.0):
    data = bpy.data.curves.new(name=name, type="CURVE")
    data.dimensions = "2D"
    data.resolution_u = 1
    data.render_resolution_u = 1
    data.fill_mode = "BOTH"
    data.use_fill_caps = True
    if stroke:
        data.bevel_depth = max(0.0001, stroke_width / 2.0)
        data.bevel_resolution = 0
    data.materials.append(material)
    for item in subpaths:
        points = item["points"]
        spline = data.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for point, coordinate in zip(spline.points, points):
            point.co = (coordinate[0], coordinate[1], z, 1.0)
        spline.use_cyclic_u = bool(item.get("closed"))
    obj = bpy.data.objects.new(name, data)
    return obj


def import_svg_asset(filepath, collection, asset_id="asset", default_color="#ffffff", z_base=0.15, layer_step=0.0001, convert_to_mesh=False):
    tree = ET.parse(filepath)
    root = tree.getroot()
    view_box = _numbers(root.attrib.get("viewBox", ""))
    if len(view_box) == 4:
        min_x, min_y, width, height = view_box
    else:
        width = _number(root.attrib.get("width"), 1.0)
        height = _number(root.attrib.get("height"), 1.0)
        min_x, min_y = 0.0, 0.0
    width = max(width, 0.001)
    height = max(height, 0.001)
    css = _css_styles(root)
    gradients = _gradient_colors(root)
    objects = []
    order = 0
    identity = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    inherited = {"fill": default_color, "stroke": "none", "stroke-width": "1", "opacity": "1", "fill-opacity": "1", "stroke-opacity": "1", "color": default_color}

    def visit(element, parent_matrix, parent_style):
        nonlocal order
        tag = _tag(element)
        matrix = _matrix_multiply(parent_matrix, _parse_transform(element.attrib.get("transform", "")))
        style = _element_style(element, parent_style, css)
        if tag in {"defs", "style", "title", "desc", "metadata", "text", "tspan"}:
            return
        if tag in {"g", "svg"}:
            for child in list(element):
                visit(child, matrix, style)
            return
        subpaths = _shape_subpaths(element, width, height)
        if not subpaths:
            return
        normalized = []
        for item in subpaths:
            points = []
            for point in item["points"]:
                transformed = _apply_matrix(matrix, point)
                points.append(((transformed[0] - min_x) / width, 1.0 - (transformed[1] - min_y) / height))
            normalized.append({"points": points, "closed": item.get("closed", False)})
        opacity = max(0.0, min(1.0, _number(style.get("opacity"), 1.0)))
        fill = _color(style.get("fill", default_color), current=_color(style.get("color", default_color), fallback=(1, 1, 1, 1)), gradients=gradients)
        stroke = _color(style.get("stroke", "none"), current=_color(style.get("color", default_color), fallback=(1, 1, 1, 1)), gradients=gradients)
        if fill:
            fill = fill[:3] + (fill[3] * opacity * _number(style.get("fill-opacity"), 1.0),)
            material = emission_material(f"{asset_id}_fill_{order:04d}", fill)
            obj = _curve_object(f"{asset_id}_fill_{order:04d}", normalized, material, z=z_base + order * layer_step)
            collection.objects.link(obj)
            objects.append(obj)
        if stroke:
            stroke = stroke[:3] + (stroke[3] * opacity * _number(style.get("stroke-opacity"), 1.0),)
            material = emission_material(f"{asset_id}_stroke_{order:04d}", stroke)
            stroke_width = _number(style.get("stroke-width"), 1.0) / max(width, height)
            obj = _curve_object(f"{asset_id}_stroke_{order:04d}", normalized, material, stroke=True, stroke_width=stroke_width, z=z_base + order * layer_step + layer_step / 2.0)
            collection.objects.link(obj)
            objects.append(obj)
        order += 1

    visit(root, identity, inherited)
    if convert_to_mesh:
        for obj in list(objects):
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.convert(target="MESH")
            obj.select_set(False)
    return {"objects": objects, "width": width, "height": height, "aspect": width / height, "mode": "mesh" if convert_to_mesh else "curve"}

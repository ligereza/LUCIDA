"""Import SVG IR manifests into editable, traceable Blender curves.

The JSON IR remains the source of truth.  This adapter creates a derived
Blender scene with full-viewBox coordinates, one animation Empty per logical
group, and Curve splines retaining path anchors and Bézier handles whenever
the source geometry provides them.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

from svg_assets import _color, emission_material


def _svg_to_blender(value, view_box):
    min_x, min_y, width, height = view_box
    width = max(float(width), 1e-9)
    height = max(float(height), 1e-9)
    x, y = float(value[0]), float(value[1])
    return ((x - min_x) / width - 0.5, 0.5 - (y - min_y) / height, 0.0)


def _number(value, fallback=0.0):
    try:
        return float(str(value).strip().replace("px", ""))
    except (TypeError, ValueError):
        return fallback


def _ensure_collection(name, parent=None):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(collection)
    return collection


def _group_objects(group_manifest, nodes_by_id, view_box, name_prefix):
    groups = group_manifest.get("grouping", {}).get("groups", [])
    source_to_group = {}
    group_objects = {}
    for ordinal, group in enumerate(groups, start=1):
        group_id = str(group.get("group_id", f"anim_auto_{ordinal:03d}"))
        empty = bpy.data.objects.new(f"AnimGroup_{name_prefix}_{group_id}", None)
        empty.empty_display_type = "PLAIN_AXES"
        empty.empty_display_size = 0.04
        empty["group_id"] = group_id
        empty["source_kind"] = group_manifest.get("source_kind", "UNKNOWN")
        empty["source_ids"] = json.dumps(group.get("source_ids", []), ensure_ascii=False)
        empty["operation"] = group.get("operation", "unknown")
        empty["confidence"] = float(group.get("confidence", 0.0))
        empty["topology_hash"] = str(group.get("topology_hash", ""))
        group_objects[group_id] = empty
        for source_id in group.get("source_ids", []):
            source_to_group[source_id] = empty
    return group_objects, source_to_group


def _line_point(value):
    return (float(value[0]), float(value[1]))


def _arc_center(start, end, rx, ry, rotation, large_arc, sweep):
    if rx <= 1e-12 or ry <= 1e-12 or (abs(start[0] - end[0]) < 1e-12 and abs(start[1] - end[1]) < 1e-12):
        return None
    phi = math.radians(rotation % 360.0)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    dx, dy = (start[0] - end[0]) / 2.0, (start[1] - end[1]) / 2.0
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy
    scale = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if scale > 1.0:
        scale = math.sqrt(scale)
        rx *= scale
        ry *= scale
    numerator = max(0.0, rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p)
    denominator = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    factor = 0.0 if denominator <= 1e-12 else math.sqrt(numerator / denominator)
    if bool(large_arc) == bool(sweep):
        factor = -factor
    cxp = factor * (rx * y1p / ry)
    cyp = factor * (-ry * x1p / rx)
    cx = cos_phi * cxp - sin_phi * cyp + (start[0] + end[0]) / 2.0
    cy = sin_phi * cxp + cos_phi * cyp + (start[1] + end[1]) / 2.0
    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    start_angle = math.atan2(uy, ux)
    delta = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    if not sweep and delta > 0:
        delta -= 2.0 * math.pi
    if sweep and delta < 0:
        delta += 2.0 * math.pi
    return cx, cy, rx, ry, phi, start_angle, delta


def _arc_point(arc_data, angle):
    cx, cy, rx, ry, phi, _, _ = arc_data
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    return (
        cx + rx * math.cos(angle) * cos_phi - ry * math.sin(angle) * sin_phi,
        cy + rx * math.cos(angle) * sin_phi + ry * math.sin(angle) * cos_phi,
    )


def _arc_derivative(arc_data, angle):
    _, _, rx, ry, phi, _, _ = arc_data
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    return (
        -rx * math.sin(angle) * cos_phi - ry * math.cos(angle) * sin_phi,
        -rx * math.sin(angle) * sin_phi + ry * math.cos(angle) * cos_phi,
    )


def _arc_to_cubic(start, end, arc):
    arc_data = _arc_center(start, end, float(arc.get("rx", 0.0)), float(arc.get("ry", 0.0)), float(arc.get("rotation", 0.0)), int(arc.get("large_arc", 0)), int(arc.get("sweep", 0)))
    if arc_data is None:
        return [(start, start, end)]
    _, _, _, _, _, start_angle, delta = arc_data
    count = max(1, int(math.ceil(abs(delta) / (math.pi / 2.0))))
    step = delta / count
    result = []
    for index in range(count):
        angle0 = start_angle + index * step
        angle1 = angle0 + step
        p0 = _arc_point(arc_data, angle0)
        p3 = _arc_point(arc_data, angle1)
        d0 = _arc_derivative(arc_data, angle0)
        d1 = _arc_derivative(arc_data, angle1)
        alpha = 4.0 / 3.0 * math.tan((angle1 - angle0) / 4.0)
        c1 = (p0[0] + alpha * d0[0], p0[1] + alpha * d0[1])
        c2 = (p3[0] - alpha * d1[0], p3[1] - alpha * d1[1])
        result.append((c1, c2, p3))
    return result


def _curve_specs_for_path(geometry, view_box):
    """Return per-subpath Bezier point specifications from IR commands."""
    commands = geometry.get("commands", [])
    specs = []
    for subpath in geometry.get("subpaths", []):
        start = _line_point(subpath.get("start", [0.0, 0.0]))
        points = [{"co": start, "left": start, "right": start}]
        current = start
        cyclic = bool(subpath.get("closed"))
        for command_index in subpath.get("segment_indices", []):
            command = commands[command_index]
            op = command.get("effective_command")
            if op == "Z":
                cyclic = True
                continue
            resolved = [_line_point(item) for item in command.get("resolved_points", [])]
            if not resolved:
                continue
            end = resolved[-1]
            right_handle = current
            left_handle = end
            if op in {"C", "S"} and len(resolved) >= 3:
                right_handle = resolved[0]
                left_handle = resolved[-2]
            elif op in {"Q", "T"} and len(resolved) >= 2:
                control = resolved[-2]
                right_handle = (current[0] + 2.0 * (control[0] - current[0]) / 3.0, current[1] + 2.0 * (control[1] - current[1]) / 3.0)
                left_handle = (end[0] + 2.0 * (control[0] - end[0]) / 3.0, end[1] + 2.0 * (control[1] - end[1]) / 3.0)
            elif op == "A":
                arc_segments = _arc_to_cubic(current, end, command.get("arc", {}))
                for control_1, control_2, arc_end in arc_segments:
                    points[-1]["right"] = control_1
                    points.append({"co": arc_end, "left": control_2, "right": arc_end})
                    current = arc_end
                continue
            points[-1]["right"] = right_handle
            points.append({"co": end, "left": left_handle, "right": end})
            current = end
        if len(points) >= 2:
            transformed = []
            for item in points:
                transformed.append({key: _svg_to_blender(value, view_box) for key, value in item.items()})
            specs.append({"points": transformed, "cyclic": cyclic})
    return specs


def _curve_object(name, drawable, view_box, material, stroke=False, stroke_width=0.0):
    geometry = drawable.get("geometry", {})
    data = bpy.data.curves.new(name=name, type="CURVE")
    data.dimensions = "2D"
    data.resolution_u = 1
    data.render_resolution_u = 1
    data.fill_mode = "BOTH"
    data.use_fill_caps = True
    if material:
        data.materials.append(material)
    if stroke:
        data.bevel_depth = max(0.0001, stroke_width / 2.0)
        data.bevel_resolution = 0
    for subpath in _curve_specs_for_path(geometry, view_box):
        points = subpath["points"]
        spline = data.splines.new("BEZIER")
        spline.bezier_points.add(len(points) - 1)
        for bezier_point, specification in zip(spline.bezier_points, points):
            bezier_point.co = specification["co"]
            bezier_point.handle_left_type = "FREE"
            bezier_point.handle_right_type = "FREE"
            bezier_point.handle_left = specification["left"]
            bezier_point.handle_right = specification["right"]
        spline.use_cyclic_u = subpath["cyclic"]
    obj = bpy.data.objects.new(name, data)
    obj["source_id"] = drawable["source_id"]
    obj["source_path"] = drawable.get("source_path", "")
    obj["source_kind"] = drawable.get("source_kind", "UNKNOWN")
    obj["geometry_hash"] = drawable.get("geometry_hash", "")
    obj["style_hash"] = drawable.get("style_hash", "")
    obj["paint_index"] = int(drawable.get("paint_index", 0))
    obj["pivot_space"] = drawable.get("pivot", {}).get("space", "svg-world")
    obj["pivot_x_svg"] = float(drawable.get("pivot", {}).get("x") or 0.0)
    obj["pivot_y_svg"] = float(drawable.get("pivot", {}).get("y") or 0.0)
    if drawable.get("source_kind") == "PNG_INFERRED_SVG":
        obj["confidence"] = json.dumps(drawable.get("confidence", {}), ensure_ascii=False)
        obj["support_evidence"] = json.dumps(drawable.get("support_evidence", {}), ensure_ascii=False)
    if any(command.get("effective_command") == "A" for command in geometry.get("commands", [])):
        obj["arc_conversion"] = "svg-endpoint-arc-to-cubic-bezier"
    return obj


def _image_texture_material(name, image_path):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    texture = nodes.new("ShaderNodeTexImage")
    texcoord = nodes.new("ShaderNodeTexCoord")
    image = bpy.data.images.get(str(Path(image_path).resolve()))
    if image is None:
        image = bpy.data.images.load(str(Path(image_path).resolve()), check_existing=True)
    if hasattr(image, "colorspace_settings"):
        try:
            image.colorspace_settings.name = "sRGB"
        except (AttributeError, TypeError):
            pass
    if hasattr(image, "alpha_mode"):
        image.alpha_mode = "STRAIGHT"
    texture.image = image
    texture.interpolation = "Linear"
    emission.inputs["Strength"].default_value = 1.0
    links.new(texcoord.outputs["UV"], texture.inputs["Vector"])
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(texture.outputs["Alpha"], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs[0])
    material.diffuse_color = (1.0, 1.0, 1.0, 1.0)
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = "DITHERED"
    material["texture_source"] = str(Path(image_path).resolve())
    material["texture_mapping"] = "svg-world-full-canvas-uv"
    return material


def _texture_mesh_from_curve(curve_object, collection, image_material):
    """Create a textured mesh derivative while retaining the hidden source curve."""
    render_object = curve_object.copy()
    render_object.data = curve_object.data.copy()
    render_object.name = f"{curve_object.name}_texture_mesh"
    render_object.hide_render = False
    collection.objects.link(render_object)
    render_object.hide_set(False)
    render_object.parent = curve_object.parent
    render_object.matrix_parent_inverse = curve_object.matrix_parent_inverse.copy()
    render_object.location = curve_object.location.copy()
    render_object.rotation_euler = curve_object.rotation_euler.copy()
    render_object.scale = curve_object.scale.copy()
    bpy.ops.object.select_all(action="DESELECT")
    render_object.select_set(True)
    bpy.context.view_layer.objects.active = render_object
    bpy.ops.object.convert(target="MESH")
    mesh = render_object.data
    mesh.materials.clear()
    mesh.materials.append(image_material)
    uv_layer = mesh.uv_layers.get("UVMap") or mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        vertex = mesh.vertices[loop.vertex_index].co
        uv_layer.data[loop.index].uv = (max(0.0, min(1.0, float(vertex.x) + 0.5)), max(0.0, min(1.0, float(vertex.y) + 0.5)))
    render_object["representation"] = "texture-mesh-derived"
    render_object["source_curve_object"] = curve_object.name
    render_object["texture_mapping"] = "full-canvas-svg-world"
    curve_object["representation"] = "editable-source-curve-hidden-by-texture-derivative"
    curve_object.hide_render = True
    curve_object.hide_set(True)
    render_object.select_set(False)
    return render_object


def import_svg_ir_manifest(ir_path, groups_path, collection_name="SVG_IR_Import", asset_id="asset"):
    ir_path = Path(ir_path)
    groups_path = Path(groups_path)
    ir_manifest = json.loads(ir_path.read_text(encoding="utf-8"))
    group_manifest = json.loads(groups_path.read_text(encoding="utf-8"))
    view_box = ir_manifest["source"]["viewBox"]
    collection = _ensure_collection(collection_name)
    root = bpy.data.objects.new(f"SVGIR_{asset_id}", None)
    root["manifest_path"] = str(ir_path.resolve())
    root["groups_manifest_path"] = str(groups_path.resolve())
    root["source_kind"] = ir_manifest.get("source_kind", "UNKNOWN")
    root["source_sha256"] = ir_manifest["source"].get("sha256", "")
    root["viewBox"] = json.dumps(view_box)
    root["style_pipeline"] = "solid-fill-stroke-opacity"
    root["texture_pipeline"] = "not-applicable-when-source-has-no-gradient-pattern-filter"
    collection.objects.link(root)

    nodes_by_id = {node["source_id"]: node for node in ir_manifest.get("nodes", [])}
    group_objects, source_to_group = _group_objects(group_manifest, nodes_by_id, view_box, asset_id)
    for empty in group_objects.values():
        collection.objects.link(empty)
        empty.parent = root

    default_group = bpy.data.objects.new(f"AnimGroup_{asset_id}_ungrouped", None)
    default_group.empty_display_type = "PLAIN_AXES"
    default_group["group_id"] = "ungrouped"
    default_group["source_kind"] = ir_manifest.get("source_kind", "UNKNOWN")
    collection.objects.link(default_group)
    default_group.parent = root

    texture_material = None
    png_reference = ir_manifest.get("source", {}).get("png_reference") or {}
    texture_path = png_reference.get("path")
    if texture_path and Path(texture_path).exists():
        texture_material = _image_texture_material(f"{asset_id}_PNG_Texture_FullCanvas", texture_path)
        root["texture_pipeline"] = "png-texture-on-svg-derived-mesh"
        root["texture_source"] = str(Path(texture_path).resolve())

    created = []
    drawable_nodes = [nodes_by_id[item] for item in ir_manifest.get("drawables", []) if item in nodes_by_id]
    for drawable in drawable_nodes:
        source_role = str(drawable.get("source_attributes", {}).get("data-role", ""))
        if source_role == "clip-mask":
            continue
        style = drawable.get("style", {})
        parent_group = source_to_group.get(drawable["source_id"], default_group)
        fill = _color(style.get("fill", "none"), fallback=(1.0, 1.0, 1.0, 1.0))
        opacity = max(0.0, min(1.0, _number(style.get("opacity", 1.0), 1.0)))
        fill_opacity = max(0.0, min(1.0, _number(style.get("fill-opacity", 1.0), 1.0)))
        stroke_opacity = max(0.0, min(1.0, _number(style.get("stroke-opacity", 1.0), 1.0)))
        if fill and fill[3] * opacity * fill_opacity > 0.0:
            fill = fill[:3] + (fill[3] * opacity * fill_opacity,)
            obj = _curve_object(f"{asset_id}_{drawable['source_id']}_fill", drawable, view_box, emission_material(f"{asset_id}_{drawable['source_id']}_fill_mat", fill), stroke=False)
            obj["fill_source"] = str(style.get("fill", "none"))
            obj["fill_opacity"] = fill_opacity
            obj["opacity"] = opacity
            obj["fill_rule_source"] = str(style.get("fill-rule", "nonzero"))
            obj.location.z = float(drawable.get("paint_index", 0)) * 0.0001
            collection.objects.link(obj)
            obj.parent = parent_group
            created.append(obj)
            if texture_material:
                created.append(_texture_mesh_from_curve(obj, collection, texture_material))
        elif texture_material and source_role == "editable-mask-path":
            # A rebuilt PNG layer can carry a geometry-only path.  Preserve
            # that curve as the editable source and derive the visible mesh
            # from the same full-canvas PNG texture.
            mask_material = emission_material(f"{asset_id}_{drawable['source_id']}_mask_source_mat", (1.0, 1.0, 1.0, 0.0))
            obj = _curve_object(f"{asset_id}_{drawable['source_id']}_mask", drawable, view_box, mask_material, stroke=False)
            obj["representation"] = "editable-mask-curve"
            obj["mask_role"] = source_role
            obj.hide_render = True
            obj.location.z = float(drawable.get("paint_index", 0)) * 0.0001
            collection.objects.link(obj)
            obj.hide_set(True)
            obj.parent = parent_group
            created.append(obj)
            created.append(_texture_mesh_from_curve(obj, collection, texture_material))
        stroke = _color(style.get("stroke", "none"), fallback=(1.0, 1.0, 1.0, 1.0))
        if stroke and stroke[3] * opacity * stroke_opacity > 0.0:
            stroke = stroke[:3] + (stroke[3] * opacity * stroke_opacity,)
            stroke_width = _number(style.get("stroke-width", 1.0), 1.0) / max(float(view_box[2]), float(view_box[3]), 1.0)
            obj = _curve_object(f"{asset_id}_{drawable['source_id']}_stroke", drawable, view_box, emission_material(f"{asset_id}_{drawable['source_id']}_stroke_mat", stroke), stroke=True, stroke_width=stroke_width)
            obj["stroke_source"] = str(style.get("stroke", "none"))
            obj["stroke_opacity"] = stroke_opacity
            obj["opacity"] = opacity
            obj["stroke_width_source"] = str(style.get("stroke-width", "1"))
            obj.location.z = float(drawable.get("paint_index", 0)) * 0.0001 + 0.00001
            collection.objects.link(obj)
            obj.parent = parent_group
            created.append(obj)
    return {"root": root, "groups": list(group_objects.values()) + [default_group], "objects": created, "source_kind": ir_manifest.get("source_kind", "UNKNOWN")}

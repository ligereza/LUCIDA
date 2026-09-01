import argparse
import json
import math
import os
import re
import sys
import subprocess

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svg_assets import emission_material, import_svg_asset


def parse_args():
    marker = sys.argv.index("--") if "--" in sys.argv else len(sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--render-output")
    return parser.parse_args(sys.argv[marker + 1:])


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def configure_cycles(scene, samples=64):
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(samples)
    if hasattr(scene.cycles, "use_denoising"):
        scene.cycles.use_denoising = True
    try:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0
    except (AttributeError, TypeError):
        pass
    scene.render.image_settings.file_format = "PNG"


def apply_material(obj, color):
    if not color:
        return
    material = bpy.data.materials.new(name=f"AgentMaterial_{obj.name}")
    material.diffuse_color = (*[float(value) for value in color[:3]], float(color[3] if len(color) > 3 else 1.0))
    obj.data.materials.append(material)


def add_object(item):
    kind = item.get("type", "cube")
    location = tuple(item.get("location", [0, 0, 0]))
    scale = tuple(item.get("scale", [1, 1, 1]))
    if kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=location)
    elif kind == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, location=location)
    else:
        bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = item.get("name", f"Agent_{kind}")
    obj.scale = scale
    apply_material(obj, item.get("color"))
    return obj


def setup_scene(spec):
    scene = bpy.context.scene
    configure_cycles(scene, spec.get("cycles_samples", 64))
    scene.render.resolution_x = int(spec.get("resolution", {}).get("width", 800))
    scene.render.resolution_y = int(spec.get("resolution", {}).get("height", 600))
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = spec.get("format", "PNG")
    objects = spec["objects"] if "objects" in spec else [{"type": "cube", "name": "AgentCube"}]
    for item in objects:
        add_object(item)
    bpy.ops.object.camera_add(location=tuple(spec.get("camera", {}).get("location", [7, -7, 5])))
    camera = bpy.context.object
    camera.rotation_euler = tuple(spec.get("camera", {}).get("rotation", [0.9, 0, 0.8]))
    scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=(4, -4, 6))
    light = bpy.context.object
    light.data.energy = 1000
    light.data.shape = "DISK"
    light.data.size = 5
    scene.world.color = tuple(spec.get("world_color", [0.03, 0.03, 0.03]))
    return scene


def import_svg_scene(spec_path):
    bpy.ops.import_curve.svg(filepath=spec_path)
    scene = bpy.context.scene
    configure_cycles(scene)
    scene.render.resolution_x = 800
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    objects = [obj for obj in scene.objects if obj.type in {"CURVE", "MESH", "FONT", "META"}]
    if not objects:
        return setup_scene({"objects": []})
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    min_x = min(point.x for point in points)
    max_x = max(point.x for point in points)
    min_y = min(point.y for point in points)
    max_y = max(point.y for point in points)
    min_z = min(point.z for point in points)
    max_z = max(point.z for point in points)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    span = max(max_x - min_x, max_y - min_y, 1.0) * 1.15
    bpy.ops.object.camera_add(location=(center_x, center_y, max_z + span * 2), rotation=(0, 0, 0))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = span
    scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=(center_x, center_y, max_z + span))
    light = bpy.context.object
    light.data.energy = 1200
    light.data.size = span
    scene.world.color = (0.02, 0.02, 0.02)
    return scene


def frame_objects(objects):
    if not objects:
        return setup_scene({"objects": []})
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    min_x = min(point.x for point in points)
    max_x = max(point.x for point in points)
    min_y = min(point.y for point in points)
    max_y = max(point.y for point in points)
    min_z = min(point.z for point in points)
    max_z = max(point.z for point in points)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    center_z = (min_z + max_z) / 2
    span = max(max_x - min_x, max_y - min_y, max_z - min_z, 1.0) * 1.6
    bpy.ops.object.camera_add(location=(center_x + span, center_y - span, center_z + span))
    camera = bpy.context.object
    camera.rotation_euler = (0.9, 0, 0.8)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = span
    bpy.context.scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=(center_x + span, center_y - span, center_z + span * 1.5))
    light = bpy.context.object
    light.data.energy = 1200
    light.data.size = span
    bpy.context.scene.world.color = (0.02, 0.02, 0.02)
    return bpy.context.scene


def import_glb_scene(spec_path):
    bpy.ops.import_scene.gltf(filepath=spec_path)
    scene = bpy.context.scene
    configure_cycles(scene)
    scene.render.resolution_x = 800
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    objects = [obj for obj in scene.objects if obj.type in {"MESH", "CURVE", "FONT", "META"}]
    return frame_objects(objects)


def export_glb(spec_path, output):
    with open(spec_path, "r", encoding="utf-8") as handle:
        spec = json.load(handle)
    scene = setup_scene(spec)
    bpy.ops.export_scene.gltf(filepath=output, export_format="GLB", use_selection=False)
    return scene


def color_from_hex(value, fallback=(0.08, 0.04, 0.12, 1.0)):
    text = str(value or "").lstrip("#")
    if len(text) != 6:
        return fallback
    try:
        return tuple(int(text[index:index + 2], 16) / 255.0 for index in (0, 2, 4)) + (1.0,)
    except ValueError:
        return fallback


def layout_material(name, color):
    return emission_material(name, color_from_hex(color))


def ensure_collection(name, scene):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
    if collection.name not in {item.name for item in scene.collection.children}:
        scene.collection.children.link(collection)
    return collection


def resolve_asset_path(value, spec_path):
    if not value:
        return None
    path = str(value)
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(os.path.abspath(spec_path)), path)
    return os.path.abspath(path)


def load_asset_specs(storyboard, spec_path):
    assets = []
    manifests = storyboard.get("assetManifests", [])
    if storyboard.get("assetManifest"):
        manifests = [storyboard.get("assetManifest"), *manifests]
    if isinstance(manifests, (str, dict)):
        manifests = [manifests]
    for manifest in manifests:
        value = manifest
        if isinstance(manifest, str):
            manifest_path = resolve_asset_path(manifest, spec_path)
            with open(manifest_path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
        if isinstance(value, dict):
            assets.extend(value.get("assets", []))
        elif isinstance(value, list):
            assets.extend(value)
    assets.extend(storyboard.get("assets", []))
    assets.extend(storyboard.get("design", {}).get("assets", []))
    for part in storyboard.get("parts", []):
        for raw in part.get("assets", []):
            item = dict(raw)
            item.setdefault("slideId", part.get("id"))
            assets.append(item)
    return assets


def asset_matches_part(asset, part, index):
    if asset.get("singleSlide") is True:
        return index == 0
    part_id = str(part.get("id", ""))
    targets = [asset.get("slideId"), asset.get("partId"), asset.get("slide_id")]
    targets = [str(value) for value in targets if value not in (None, "")]
    if targets:
        return part_id in targets or str(part.get("title", "")) in targets
    for key in ("slideIndex", "slideNumber", "slide"):
        if asset.get(key) not in (None, ""):
            try:
                return int(asset[key]) == index + 1
            except (TypeError, ValueError):
                return str(asset[key]).lower() == str(index + 1)
    filename = os.path.basename(str(asset.get("file", asset.get("path", ""))))
    match = re.search(r"(?:slide|lamina|pagina|page)[-_ ]?0*(\d+)", filename, re.IGNORECASE)
    return bool(match and int(match.group(1)) == index + 1)


def zone_from_asset(asset, part, canvas_width, canvas_height):
    layout = part.get("layout", {})
    placement = asset.get("placement")
    anchor = asset.get("anchor", asset.get("zone", "illustration"))
    if isinstance(placement, dict):
        zone = dict(placement)
    elif isinstance(anchor, dict):
        zone = dict(anchor)
    elif anchor == "full":
        zone = {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
    else:
        zone = dict(layout.get(str(anchor), layout.get("illustration", {})))
    override = asset.get("layout") if isinstance(asset.get("layout"), dict) else asset
    for key in ("x", "y", "width", "height"):
        if key in override:
            zone[key] = override[key]
    if any(abs(float(zone.get(key, 0))) > 1.001 for key in ("x", "y", "width", "height")):
        zone["x"] = float(zone.get("x", 0)) / canvas_width
        zone["width"] = float(zone.get("width", 0)) / canvas_width
        zone["y"] = float(zone.get("y", 0)) / canvas_height
        zone["height"] = float(zone.get("height", 0)) / canvas_height
    return {key: max(0.0, min(1.0, float(zone.get(key, 0)))) for key in ("x", "y", "width", "height")}


def import_raster_asset(filepath, collection, asset_id, default_color="#ffffff", pack=False):
    image = bpy.data.images.load(filepath, check_existing=False)
    if hasattr(image, "colorspace_settings"):
        try:
            image.colorspace_settings.name = "sRGB"
        except (AttributeError, TypeError):
            pass
    if hasattr(image, "alpha_mode"):
        image.alpha_mode = "STRAIGHT"
    width, height = image.size
    width = max(1, int(width))
    height = max(1, int(height))
    mesh = bpy.data.meshes.new(f"{asset_id}_ImageMesh")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    uv_coordinates = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    for loop in mesh.loops:
        uv_layer.data[loop.index].uv = uv_coordinates[loop.vertex_index]
    obj = bpy.data.objects.new(asset_id, mesh)
    collection.objects.link(obj)
    material = bpy.data.materials.new(f"{asset_id}_ImageMaterial")
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
    texture.image = image
    texture.interpolation = "Linear"
    emission.inputs["Strength"].default_value = 1.0
    links.new(texcoord.outputs["UV"], texture.inputs["Vector"])
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(texture.outputs["Alpha"], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs[0])
    material.diffuse_color = color_from_hex(default_color)
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = "DITHERED"
    obj.data.materials.append(material)
    if pack:
        image.pack()
    return {"objects": [obj], "width": width, "height": height, "aspect": width / height, "mode": "image"}


def rasterize_svg_asset(filepath, spec_path, asset, asset_id):
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "image", "rasterize_svg.py"))
    output_dir = os.path.join(os.path.dirname(os.path.abspath(spec_path)), "rasterized-assets")
    os.makedirs(output_dir, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", asset_id).strip("-.") or "asset"
    output = os.path.join(output_dir, f"{safe_id}.png")
    command = [
        os.environ.get("PYTHON_EXE", "python"),
        script,
        "--input", filepath,
        "--output", output,
        "--width", str(int(asset.get("rasterWidth", 2048))),
    ]
    if asset.get("background"):
        command.extend(["--background", str(asset["background"])])
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    if not os.path.exists(output):
        raise RuntimeError(f"CairoSVG did not create the fallback image: {result.stdout}")
    return output


def asset_geometry_node_group():
    """Reusable GN pass-through that exposes 2D asset transform controls."""
    name = "GN_Asset_2D_Transform"
    existing = bpy.data.node_groups.get(name)
    if existing:
        return existing
    node_group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")
    group_socket(node_group, "INPUT")
    group_socket(node_group, "OUTPUT")
    group_float_socket(node_group, "Scale X", 1.0, 0.001, 100.0)
    group_float_socket(node_group, "Scale Y", 1.0, 0.001, 100.0)
    group_float_socket(node_group, "Offset X", 0.0, -100.0, 100.0)
    group_float_socket(node_group, "Offset Y", 0.0, -100.0, 100.0)
    group_float_socket(node_group, "Rotation", 0.0, -math.pi * 4.0, math.pi * 4.0)
    group_float_socket(node_group, "Pulse", 0.0, -1.0, 1.0)
    group_float_socket(node_group, "Pivot X", 0.5, -1.0, 2.0)
    group_float_socket(node_group, "Pivot Y", 0.5, -1.0, 2.0)

    nodes = node_group.nodes
    links = node_group.links
    group_input = nodes.new("NodeGroupInput")
    group_output = nodes.new("NodeGroupOutput")
    transform = nodes.new("GeometryNodeTransform")
    pre_pivot = nodes.new("GeometryNodeTransform")
    post_pivot = nodes.new("GeometryNodeTransform")
    scale = nodes.new("ShaderNodeCombineXYZ")
    translation = nodes.new("ShaderNodeCombineXYZ")
    rotation = nodes.new("ShaderNodeCombineXYZ")
    pivot = nodes.new("ShaderNodeCombineXYZ")
    pivot_scale_x = nodes.new("ShaderNodeMath")
    pivot_scale_x.operation = "MULTIPLY"
    pivot_scale_y = nodes.new("ShaderNodeMath")
    pivot_scale_y.operation = "MULTIPLY"
    negate_pivot = nodes.new("ShaderNodeVectorMath")
    negate_pivot.operation = "SCALE"
    negate_pivot.inputs["Scale"].default_value = -1.0
    pulse_add = nodes.new("ShaderNodeMath")
    pulse_add.operation = "ADD"
    pulse_add.inputs[0].default_value = 1.0
    pulse_add.label = "1 + Pulse"
    pulse_x = nodes.new("ShaderNodeMath")
    pulse_x.operation = "MULTIPLY"
    pulse_y = nodes.new("ShaderNodeMath")
    pulse_y.operation = "MULTIPLY"
    for node, location in (
        (group_input, (-600, 0)),
        (pulse_add, (-350, -240)),
        (pulse_x, (-100, 160)),
        (pulse_y, (-100, 60)),
        (scale, (120, 160)),
        (translation, (120, -40)),
        (rotation, (120, -220)),
        (pivot_scale_x, (-100, -460)),
        (pivot_scale_y, (120, -460)),
        (pivot, (-100, -360)),
        (negate_pivot, (120, -360)),
        (pre_pivot, (360, 120)),
        (transform, (560, 0)),
        (post_pivot, (760, 120)),
        (group_output, (960, 0)),
    ):
        node.location = location
    links.new(group_input.outputs["Geometry"], pre_pivot.inputs["Geometry"])
    links.new(pre_pivot.outputs["Geometry"], transform.inputs["Geometry"])
    links.new(transform.outputs["Geometry"], post_pivot.inputs["Geometry"])
    links.new(post_pivot.outputs["Geometry"], group_output.inputs["Geometry"])
    links.new(group_input.outputs["Pulse"], pulse_add.inputs[1])
    links.new(group_input.outputs["Scale X"], pulse_x.inputs[0])
    links.new(pulse_add.outputs[0], pulse_x.inputs[1])
    links.new(group_input.outputs["Scale Y"], pulse_y.inputs[0])
    links.new(pulse_add.outputs[0], pulse_y.inputs[1])
    links.new(pulse_x.outputs[0], scale.inputs["X"])
    links.new(pulse_y.outputs[0], scale.inputs["Y"])
    scale.inputs["Z"].default_value = 1.0
    links.new(group_input.outputs["Offset X"], translation.inputs["X"])
    links.new(group_input.outputs["Offset Y"], translation.inputs["Y"])
    translation.inputs["Z"].default_value = 0.0
    links.new(group_input.outputs["Rotation"], rotation.inputs["Z"])
    rotation.inputs["X"].default_value = 0.0
    rotation.inputs["Y"].default_value = 0.0
    links.new(group_input.outputs["Pivot X"], pivot_scale_x.inputs[0])
    links.new(pulse_x.outputs[0], pivot_scale_x.inputs[1])
    links.new(group_input.outputs["Pivot Y"], pivot_scale_y.inputs[0])
    links.new(pulse_y.outputs[0], pivot_scale_y.inputs[1])
    links.new(pivot_scale_x.outputs[0], pivot.inputs["X"])
    links.new(pivot_scale_y.outputs[0], pivot.inputs["Y"])
    pivot.inputs["Z"].default_value = 0.0
    links.new(pivot.outputs["Vector"], negate_pivot.inputs["Vector"])
    links.new(negate_pivot.outputs["Vector"], pre_pivot.inputs["Translation"])
    links.new(pivot.outputs["Vector"], post_pivot.inputs["Translation"])
    links.new(scale.outputs["Vector"], transform.inputs["Scale"])
    links.new(translation.outputs["Vector"], transform.inputs["Translation"])
    links.new(rotation.outputs["Vector"], transform.inputs["Rotation"])
    return node_group


def modifier_socket_id(node_group, name):
    if hasattr(node_group, "interface"):
        for item in node_group.interface.items_tree:
            if getattr(item, "item_type", None) == "SOCKET" and item.name == name and item.in_out == "INPUT":
                return item.identifier
    return None


def set_modifier_input(modifier, node_group, name, value):
    identifier = modifier_socket_id(node_group, name)
    if identifier:
        modifier[identifier] = float(value)
    return identifier


def attach_asset_geometry_nodes(objects, root, fit_width, fit_height, asset):
    """Apply the same editable GN transform to every primitive in an asset."""
    node_group = asset_geometry_node_group()
    controls = {
        "Scale X": fit_width,
        "Scale Y": fit_height,
        "Offset X": float(asset.get("offsetX", 0.0)),
        "Offset Y": float(asset.get("offsetY", 0.0)),
        "Rotation": math.radians(float(asset.get("rotation", 0.0))),
        "Pulse": float(asset.get("pulse", 0.0)),
    }
    pivot = asset.get("pivot", [0.5, 0.5])
    if not isinstance(pivot, (list, tuple)) or len(pivot) < 2:
        pivot = [0.5, 0.5]
    controls["Pivot X"] = float(asset.get("pivotX", pivot[0]))
    controls["Pivot Y"] = float(asset.get("pivotY", pivot[1]))
    identifiers = {}
    for obj in objects:
        modifier = obj.modifiers.new(name="GN Asset Transform", type="NODES")
        modifier.node_group = node_group
        for name, value in controls.items():
            identifier = set_modifier_input(modifier, node_group, name, value)
            if identifier:
                identifiers[name] = identifier
        obj["geometry_nodes_group"] = node_group.name
        obj["geometry_nodes_controls"] = json.dumps(identifiers, ensure_ascii=False)
    root["geometry_nodes_group"] = node_group.name
    root["geometry_nodes_controls"] = json.dumps(identifiers, ensure_ascii=False)


def place_asset(imported, asset, part, slide_offset, slide_width, slide_height, canvas_width, canvas_height, collection):
    objects = imported["objects"]
    if not objects:
        return None
    asset_id = str(asset.get("id") or asset.get("name") or os.path.splitext(os.path.basename(str(asset.get("file", "asset"))))[0])
    root = bpy.data.objects.new(f"Asset_{asset_id}", None)
    collection.objects.link(root)
    zone = zone_from_asset(asset, part, canvas_width, canvas_height)
    zone_width = max(0.001, zone["width"] * slide_width)
    zone_height = max(0.001, zone["height"] * slide_height)
    aspect = max(0.0001, float(imported.get("aspect", 1.0)))
    fit = str(asset.get("fit", "contain")).lower()
    if fit == "stretch":
        fit_width, fit_height = zone_width, zone_height
    elif fit == "cover":
        fit_width = max(zone_width, zone_height * aspect)
        fit_height = fit_width / aspect
        if fit_height < zone_height:
            fit_height = zone_height
            fit_width = fit_height * aspect
    else:
        fit_width = min(zone_width, zone_height * aspect)
        fit_height = fit_width / aspect
    scale = float(asset.get("scale", 1.0))
    fit_width *= scale
    fit_height *= scale
    zone_left = slide_offset[0] - slide_width / 2 + zone["x"] * slide_width
    zone_bottom = slide_offset[1] + slide_height / 2 - (zone["y"] + zone["height"]) * slide_height
    root.location = (zone_left + (zone_width - fit_width) / 2, zone_bottom + (zone_height - fit_height) / 2, 0.14 + float(asset.get("zIndex", 0)) * 0.0001)
    root.scale = (1.0, 1.0, 1.0)
    pivot = asset.get("pivot", [0.5, 0.5])
    if not isinstance(pivot, (list, tuple)) or len(pivot) < 2:
        pivot = [0.5, 0.5]
    controls = {
        "Pivot X": float(asset.get("pivotX", pivot[0])),
        "Pivot Y": float(asset.get("pivotY", pivot[1])),
    }
    root["gn_scale_x"] = fit_width
    root["gn_scale_y"] = fit_height
    root["gn_offset_x"] = float(asset.get("offsetX", 0.0))
    root["gn_offset_y"] = float(asset.get("offsetY", 0.0))
    root["gn_rotation"] = math.radians(float(asset.get("rotation", 0.0)))
    root["gn_pulse"] = float(asset.get("pulse", 0.0))
    root["gn_pivot_x"] = controls["Pivot X"]
    root["gn_pivot_y"] = controls["Pivot Y"]
    for obj in objects:
        obj.parent = root
        obj["asset_id"] = asset_id
        obj["slide_id"] = part.get("id", "")
        obj["asset_role"] = asset.get("role", "illustration")
    attach_asset_geometry_nodes(objects, root, fit_width, fit_height, asset)
    root["asset_id"] = asset_id
    root["slide_id"] = part.get("id", "")
    root["asset_role"] = asset.get("role", "illustration")
    root["asset_file"] = str(asset.get("file", asset.get("path", "")))
    root["asset_fit"] = fit
    root["asset_mode"] = imported.get("mode", "curve")
    return root


def ensure_animation_group(group_id, collection):
    """Create one editable Empty for a coarse animation unit."""
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(group_id)).strip("-.") or "group"
    name = f"AnimGroup_{safe_id}"
    group = bpy.data.objects.get(name)
    if group is None:
        group = bpy.data.objects.new(name, None)
        collection.objects.link(group)
        group.empty_display_type = "PLAIN_AXES"
        group.empty_display_size = 0.08
        group.location = (0.0, 0.0, 0.0)
        group.rotation_euler = (0.0, 0.0, 0.0)
        group.scale = (1.0, 1.0, 1.0)
    group["animation_group"] = str(group_id)
    group["animation_role"] = "auto-spatial-animation-unit"
    return group


def import_assets_for_part(assets, part, index, spec_path, slide_offset, slide_width, slide_height, canvas_width, canvas_height, scene):
    collection = ensure_collection(f"Slide_{index + 1:02d}_Assets", scene)
    imported_roots = []
    errors = []
    animation_groups = {}
    for asset in assets:
        if not asset_matches_part(asset, part, index):
            continue
        filepath = resolve_asset_path(asset.get("file", asset.get("path")), spec_path)
        if not filepath or not os.path.exists(filepath):
            errors.append({"asset": asset.get("id", asset.get("file")), "error": f"Missing asset: {filepath}"})
            continue
        asset_id = str(asset.get("id") or asset.get("name") or os.path.splitext(os.path.basename(filepath))[0])
        try:
            extension = os.path.splitext(filepath)[1].lower()
            if extension == ".svg":
                import_mode = str(asset.get("importMode", "curves")).lower()
                if import_mode == "raster":
                    raster_path = rasterize_svg_asset(filepath, spec_path, asset, asset_id)
                    imported = import_raster_asset(raster_path, collection, asset_id, pack=bool(asset.get("pack", False)))
                    imported["mode"] = "raster"
                else:
                    imported = import_svg_asset(filepath, collection, asset_id=asset_id, default_color=asset.get("defaultColor", "#ffffff"), z_base=0.0, convert_to_mesh=import_mode == "mesh" or bool(asset.get("convertToMesh", False)))
            elif extension in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".exr"}:
                imported = import_raster_asset(filepath, collection, asset_id, default_color=asset.get("defaultColor", "#ffffff"), pack=bool(asset.get("pack", False)))
            else:
                errors.append({"asset": asset_id, "error": f"Unsupported asset type: {extension}"})
                continue
            root = place_asset(imported, asset, part, slide_offset, slide_width, slide_height, canvas_width, canvas_height, collection)
            if root:
                group_id = asset.get("animationGroup") or asset.get("animation_group")
                if group_id:
                    group = animation_groups.setdefault(str(group_id), ensure_animation_group(group_id, collection))
                    root.parent = group
                    root["animation_group"] = str(group_id)
                    group["member_count"] = int(group.get("member_count", 0)) + 1
                imported_roots.append(root)
        except Exception as error:
            errors.append({"asset": asset_id, "error": str(error)})
    return imported_roots, errors


def group_socket(node_group, in_out):
    if hasattr(node_group, "interface"):
        node_group.interface.new_socket(name="Geometry", in_out=in_out, socket_type="NodeSocketGeometry")
    elif in_out == "INPUT":
        node_group.inputs.new("NodeSocketGeometry", "Geometry")
    else:
        node_group.outputs.new("NodeSocketGeometry", "Geometry")


def group_float_socket(node_group, name, default, minimum=0.001, maximum=100.0):
    if hasattr(node_group, "interface"):
        socket = node_group.interface.new_socket(name=name, in_out="INPUT", socket_type="NodeSocketFloat")
    else:
        socket = node_group.inputs.new("NodeSocketFloat", name)
    socket.default_value = float(default)
    socket.min_value = float(minimum)
    socket.max_value = float(maximum)
    return socket


def make_layout_node_group(name, text_box, art_box, canvas_width, canvas_height, text_material, art_material):
    node_group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")
    group_socket(node_group, "INPUT")
    group_socket(node_group, "OUTPUT")
    group_float_socket(node_group, "Text Width", max(0.001, text_box.get("width", 0.1) * canvas_width / 1000.0))
    group_float_socket(node_group, "Text Height", max(0.001, text_box.get("height", 0.1) * canvas_height / 1000.0))
    group_float_socket(node_group, "Text X", (text_box.get("x", 0) + text_box.get("width", 0) / 2 - 0.5) * canvas_width / 1000.0, -100.0, 100.0)
    group_float_socket(node_group, "Text Y", (0.5 - text_box.get("y", 0) - text_box.get("height", 0) / 2) * canvas_height / 1000.0, -100.0, 100.0)
    group_float_socket(node_group, "Art Width", max(0.001, art_box.get("width", 0.1) * canvas_width / 1000.0))
    group_float_socket(node_group, "Art Height", max(0.001, art_box.get("height", 0.1) * canvas_height / 1000.0))
    group_float_socket(node_group, "Art X", (art_box.get("x", 0) + art_box.get("width", 0) / 2 - 0.5) * canvas_width / 1000.0, -100.0, 100.0)
    group_float_socket(node_group, "Art Y", (0.5 - art_box.get("y", 0) - art_box.get("height", 0) / 2) * canvas_height / 1000.0, -100.0, 100.0)
    group_float_socket(node_group, "Depth", 0.035, 0.001, 10.0)
    nodes = node_group.nodes
    links = node_group.links
    group_input = nodes.new("NodeGroupInput")
    group_output = nodes.new("NodeGroupOutput")
    group_input.location = (-700, 0)
    group_output.location = (500, 0)
    join = nodes.new("GeometryNodeJoinGeometry")
    join.location = (250, 0)

    def add_zone(label, zone, material, y, prefix):
        cube = nodes.new("GeometryNodeMeshCube")
        size = nodes.new("ShaderNodeCombineXYZ")
        position = nodes.new("ShaderNodeCombineXYZ")
        transform = nodes.new("GeometryNodeTransform")
        set_material = nodes.new("GeometryNodeSetMaterial")
        cube.label = label
        size.label = f"{label} dimensions"
        position.label = f"{label} coordinates"
        transform.label = f"{label} position"
        set_material.label = f"{label} material"
        cube.location = (-500, y)
        size.location = (-500, y - 100)
        position.location = (-500, y - 200)
        transform.location = (-250, y)
        set_material.location = (0, y)
        width = max(0.001, zone.get("width", 0.1) * canvas_width / 1000.0)
        height = max(0.001, zone.get("height", 0.1) * canvas_height / 1000.0)
        center_x = (zone.get("x", 0) + zone.get("width", 0) / 2 - 0.5) * canvas_width / 1000.0
        center_y = (0.5 - zone.get("y", 0) - zone.get("height", 0) / 2) * canvas_height / 1000.0
        size.inputs["Z"].default_value = 0.035
        position.inputs["Z"].default_value = 0.0
        set_material.inputs["Material"].default_value = material
        links.new(group_input.outputs[f"{prefix} Width"], size.inputs["X"])
        links.new(group_input.outputs[f"{prefix} Height"], size.inputs["Y"])
        links.new(group_input.outputs[f"{prefix} X"], position.inputs["X"])
        links.new(group_input.outputs[f"{prefix} Y"], position.inputs["Y"])
        links.new(group_input.outputs["Depth"], size.inputs["Z"])
        links.new(size.outputs["Vector"], cube.inputs["Size"])
        links.new(position.outputs["Vector"], transform.inputs["Translation"])
        links.new(cube.outputs["Mesh"], transform.inputs["Geometry"])
        links.new(transform.outputs["Geometry"], set_material.inputs["Geometry"])
        links.new(set_material.outputs["Geometry"], join.inputs["Geometry"])

    add_zone("TEXT", text_box, text_material, 160, "Text")
    add_zone("ILLUSTRATION", art_box, art_material, -160, "Art")
    links.new(join.outputs["Geometry"], group_output.inputs["Geometry"])
    return node_group


def add_label(text, location, size, material, name):
    curve = bpy.data.curves.new(name=name, type="FONT")
    curve.body = str(text or "")[:80]
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = 0.002
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    return obj


def layout_scene(spec_path):
    with open(spec_path, "r", encoding="utf-8") as handle:
        storyboard = json.load(handle)
    design = storyboard.get("design", {})
    canvas = design.get("canvas", {}) or storyboard.get("canvas", {})
    # Chemsex project default: 1080x1440 portrait. Keep the canvas explicit in
    # the storyboard; these fallbacks only protect older/incomplete manifests.
    canvas_width = float(canvas.get("width", 1080))
    canvas_height = float(canvas.get("height", 1440))
    parts = storyboard.get("parts", [])
    asset_specs = load_asset_specs(storyboard, spec_path)
    asset_errors = []
    scene = bpy.context.scene
    configure_cycles(scene, design.get("cyclesSamples", 64))
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    background = layout_material("Chemsex Background", design.get("colors", {}).get("background", "#090712"))
    text_material = layout_material("Chemsex Text Zone", design.get("colors", {}).get("highlight", "#f0abfc"))
    art_material = layout_material("Chemsex Illustration Zone", design.get("colors", {}).get("accent", "#7c3aed"))
    cols = min(4, max(1, len(parts)))
    rows = max(1, (len(parts) + cols - 1) // cols)
    slide_width = canvas_width / 1000.0
    slide_height = canvas_height / 1000.0
    gap_x = 0.24
    gap_y = 0.32
    total_width = cols * slide_width + (cols - 1) * gap_x
    total_height = rows * slide_height + (rows - 1) * gap_y

    render_spec = storyboard.get("render", {})
    if not isinstance(render_spec, dict):
        render_spec = {}
    render_mode = str(render_spec.get("mode", "sheet")).lower()
    show_guides = bool(render_spec.get("showGuides", render_mode not in {"slide", "single"}))

    for index, part in enumerate(parts):
        col = index % cols
        row = index // cols
        offset_x = -total_width / 2 + slide_width / 2 + col * (slide_width + gap_x)
        offset_y = total_height / 2 - slide_height / 2 - row * (slide_height + gap_y)
        bpy.ops.mesh.primitive_plane_add(size=2, location=(offset_x, offset_y, -0.08))
        plane = bpy.context.object
        plane.name = f"Slide_{index + 1:02d}_Background"
        plane.scale = (slide_width / 2, slide_height / 2, 1)
        plane.data.materials.append(background)
        layout = part.get("layout", {})
        text_box = layout.get("text", {}) or part.get("textBox", {})
        art_box = layout.get("illustration", {}) or part.get("artBox", {})
        group_name = f"GN_Slide_{index + 1:02d}_{part.get('theme', 'general')}"
        node_group = make_layout_node_group(group_name, text_box, art_box, canvas_width, canvas_height, text_material, art_material)
        mesh = bpy.data.meshes.new(f"LayoutMesh_{index + 1:02d}")
        controller = bpy.data.objects.new(f"Slide_{index + 1:02d}_GeometryNodes", mesh)
        bpy.context.collection.objects.link(controller)
        modifier = controller.modifiers.new(name="Chemsex Layout Geometry", type="NODES")
        modifier.node_group = node_group
        controller.location = (offset_x, offset_y, 0)
        controller["theme"] = part.get("theme", "general")
        controller["layout_variant"] = layout.get("variant", "")
        controller["layout_score"] = float(part.get("layoutScore", part.get("layout", {}).get("layoutScore", 0)))
        controller["text_density"] = float(part.get("textMetrics", {}).get("density", 0))
        imported_roots, errors = import_assets_for_part(
            asset_specs,
            part,
            index,
            spec_path,
            (offset_x, offset_y),
            slide_width,
            slide_height,
            canvas_width,
            canvas_height,
            scene,
        )
        asset_errors.extend(errors)
        controller["asset_count"] = len(imported_roots)
        label = add_label(f"{index + 1:02d} · {part.get('title', '')}", (offset_x, offset_y - slide_height / 2 - 0.08, 0.045), 0.045, text_material, f"Slide_{index + 1:02d}_Label")
        theme_label = add_label(part.get("theme", "general"), (offset_x, offset_y + slide_height / 2 + 0.08, 0.035), 0.035, art_material, f"Slide_{index + 1:02d}_Theme")
        if not show_guides:
            controller.hide_render = True
            label.hide_render = True
            theme_label.hide_render = True

    render_slide = render_spec.get("slide", render_spec.get("slideIndex", 1))
    try:
        render_slide = max(1, min(len(parts), int(render_slide)))
    except (TypeError, ValueError):
        render_slide = 1
    render_col = (render_slide - 1) % cols
    render_row = (render_slide - 1) // cols
    render_offset_x = -total_width / 2 + slide_width / 2 + render_col * (slide_width + gap_x)
    render_offset_y = total_height / 2 - slide_height / 2 - render_row * (slide_height + gap_y)
    camera_z = max(total_width, total_height) * 2
    bpy.ops.object.camera_add(location=(render_offset_x if render_mode in {"slide", "single"} else 0, render_offset_y if render_mode in {"slide", "single"} else 0, camera_z))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    if render_mode in {"slide", "single"}:
        camera.data.ortho_scale = slide_height
        scene.render.resolution_x = int(canvas_width)
        scene.render.resolution_y = int(canvas_height)
        scene["render_mode"] = "slide"
        scene["render_slide"] = render_slide
    else:
        camera.data.ortho_scale = max(total_height * 1.18, total_width * 0.72)
        scene["render_mode"] = "sheet"
    scene.camera = camera
    scene.world.color = (0.015, 0.01, 0.02)
    scene["asset_count"] = sum(1 for asset in asset_specs if any(asset_matches_part(asset, part, index) for index, part in enumerate(parts)))
    scene["asset_errors"] = json.dumps(asset_errors, ensure_ascii=False)
    return scene


def main():
    args = parse_args()
    clear_scene()
    if args.operation == "import-svg":
        spec = {"objects": []}
        scene = import_svg_scene(args.spec)
    elif args.operation == "layout-scene":
        scene = layout_scene(args.spec)
    elif args.operation == "import-glb":
        spec = {"objects": []}
        scene = import_glb_scene(args.spec)
    elif args.operation == "export-glb":
        output = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output), exist_ok=True)
        scene = export_glb(args.spec, output)
        if args.render_output:
            scene.render.filepath = os.path.abspath(args.render_output)
            bpy.ops.render.render(write_still=True)
        print(json.dumps({"glb": output}))
        return
    else:
        with open(args.spec, "r", encoding="utf-8") as handle:
            spec = json.load(handle)
        scene = setup_scene(spec)
    output = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    if args.operation == "render":
        scene.render.filepath = output
        bpy.ops.render.render(write_still=True)
        print(json.dumps({"render": output}))
    else:
        if not output.lower().endswith(".blend"):
            output = f"{output}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=output)
        if args.render_output:
            scene.render.filepath = os.path.abspath(args.render_output)
            bpy.ops.render.render(write_still=True)
        print(json.dumps({"blend": output}))


if __name__ == "__main__":
    main()

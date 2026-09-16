"""Generador de tarjetas de prueba para validar un mapping de Resolume."""

from __future__ import annotations

import colorsys
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .media import ResolumeAdapterError


_PALETTE = (
    (230, 57, 70),
    (29, 161, 242),
    (46, 204, 113),
    (241, 196, 15),
    (155, 89, 182),
    (230, 126, 34),
    (26, 188, 156),
    (236, 112, 20),
)


def _group_color(index: int) -> tuple[int, int, int]:
    if index < len(_PALETTE):
        return _PALETTE[index]
    hue = (index * 0.61803398875) % 1.0
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.72, 0.9)
    return round(red * 255), round(green * 255), round(blue * 255)


def _bounds(item: dict[str, Any]) -> dict[str, float] | None:
    rect = item.get("input") or {}
    bounds = rect.get("bounds") if isinstance(rect, dict) else None
    if not bounds:
        bounds = (item.get("input_dimensions") or {}).get("bounds")
    return bounds if isinstance(bounds, dict) else None


def build_testcard_spec(
    output_map: dict[str, Any],
    *,
    duration_seconds: float = 12.0,
    fps: float = 30.0,
    suite: str = "geometry",
) -> dict[str, Any]:
    """Genera una especificación reproducible sin renderizar ni modificar Resolume."""

    composition = output_map.get("composition") or {}
    width = int(composition.get("width") or 0)
    height = int(composition.get("height") or 0)
    if width <= 0 or height <= 0:
        raise ResolumeAdapterError("El mapping no declara un tamaño de composición válido.")
    if duration_seconds <= 0 or fps <= 0:
        raise ResolumeAdapterError("La duración y los FPS del test card deben ser positivos.")
    if suite not in {"geometry", "soundcheck"}:
        raise ResolumeAdapterError("La suite del test card debe ser geometry o soundcheck.")

    group_order: list[str] = []
    for item in output_map.get("slices", []):
        if not item.get("enabled", True):
            continue
        group_id = item.get("input_group_id") or item.get("id")
        if group_id not in group_order:
            group_order.append(group_id)

    slices: list[dict[str, Any]] = []
    for item in output_map.get("slices", []):
        if not item.get("enabled", True):
            continue
        bounds = _bounds(item)
        if not bounds or bounds.get("width", 0) <= 0 or bounds.get("height", 0) <= 0:
            continue
        group_id = item.get("input_group_id") or item.get("id")
        slices.append({
            "slice_id": item.get("id"),
            "slice_name": item.get("name"),
            "screen_name": item.get("screen_name"),
            "input_group_id": group_id,
            "color": _group_color(group_order.index(group_id)),
            "bounds": {
                "x": round(float(bounds.get("x", 0)), 3),
                "y": round(float(bounds.get("y", 0)), 3),
                "width": round(float(bounds.get("width", 0)), 3),
                "height": round(float(bounds.get("height", 0)), 3),
            },
            "geometry": item.get("geometry") or {},
        })

    total_frames = max(1, round(float(duration_seconds) * float(fps)))
    patterns = (
        ("blackout", "Negro de referencia", ["blackout_status", "uniformity", "notes"]),
        ("pluge_near_black", "PLUGE / near-black", ["black_bar_visible", "near_black_bars", "range_mode", "notes"]),
        ("gray_ramp", "Escala de grises", ["ramp_continuity", "banding_status", "gamma_observation", "notes"]),
        ("primaries", "Primarios y blanco", ["red_status", "green_status", "blue_status", "white_status", "neutral_gray_status", "notes"]),
        ("geometry_grid", "Geometría, círculo y límites", ["circle_status", "grid_status", "slice_boundaries", "overlap_status", "orientation", "notes"]),
        ("resolution_scaling", "Resolución y escalado", ["input_resolution", "output_resolution", "scaling_mode", "crop_status", "aspect_status", "notes"]),
        ("motion_stability", "Movimiento y estabilidad", ["flicker_status", "tearing_status", "judder_status", "link_stability", "refresh_observed", "notes"]),
    )
    selected_patterns = patterns if suite == "soundcheck" else (patterns[4],)
    sections = []
    section_frames = max(1, total_frames // len(selected_patterns))
    for index, (pattern, title, record_fields) in enumerate(selected_patterns):
        start_frame = index * section_frames
        end_frame = total_frames if index == len(selected_patterns) - 1 else min(total_frames, (index + 1) * section_frames)
        sections.append({
            "pattern": pattern,
            "title": title,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "record_fields": record_fields,
        })

    return {
        "schema_version": "0.1",
        "testcard_type": "InstarResolumeGeometryTestCard",
        "read_only_source": True,
        "suite": suite,
        "source_map": output_map.get("source"),
        "composition": {"width": width, "height": height},
        "duration_seconds": round(float(duration_seconds), 3),
        "fps": round(float(fps), 3),
        "input_groups": len(group_order),
        "slices": len(slices),
        "test_modes": (
            [section["pattern"] for section in sections]
            if suite == "soundcheck"
            else [
                "solid_group_colors",
                "slice_labels",
                "inner_grid",
                "moving_diagonal",
                "circle_and_square_geometry",
                "safe_area_border",
            ]
        ),
        "sections": sections,
        "slices_detail": slices,
        "limitations": [
            "La tarjeta valida la geometría que sale de Resolume; no puede confirmar por sí sola un reescalado posterior del procesador LED.",
            "Slices que comparten InputRect reciben deliberadamente el mismo color y geometría de input.",
            "El render se crea sobre el canvas de composición; Advanced Output conserva el warping y la salida física.",
        ],
    }


def _font() -> ImageFont.ImageFont:
    return ImageFont.load_default()


def _draw_header(draw: ImageDraw.ImageDraw, text: str, width: int, height: int, font: ImageFont.ImageFont) -> None:
    draw.rectangle((0, 0, width - 1, min(height - 1, 30)), fill=(0, 0, 0))
    draw.text((10, 8), text, fill=(255, 255, 255), font=font)


def _render_geometry_frame(spec: dict[str, Any], image: Image.Image, frame_index: int) -> None:
    """Render the geometry section over the composition canvas."""

    width = int(spec["composition"]["width"])
    height = int(spec["composition"]["height"])
    total_frames = max(1, round(float(spec["duration_seconds"]) * float(spec["fps"])))
    phase = (frame_index % total_frames) / total_frames
    draw = ImageDraw.Draw(image)
    font = _font()

    for index, item in enumerate(spec.get("slices_detail", [])):
        bounds = item["bounds"]
        left = max(0, round(bounds["x"]))
        top = max(0, round(bounds["y"]))
        right = min(width - 1, round(bounds["x"] + bounds["width"]) - 1)
        bottom = min(height - 1, round(bounds["y"] + bounds["height"]) - 1)
        if right <= left or bottom <= top:
            continue
        color = tuple(item["color"])
        draw.rectangle((left, top, right, bottom), fill=color)

        inner_left, inner_top = left + 2, top + 2
        inner_right, inner_bottom = right - 2, bottom - 2
        inner_width = max(1, inner_right - inner_left)
        inner_height = max(1, inner_bottom - inner_top)
        grid_x = max(8, round(inner_width / 8))
        grid_y = max(8, round(inner_height / 4))
        grid_color = tuple(max(0, channel - 85) for channel in color)
        for x in range(inner_left, inner_right + 1, grid_x):
            draw.line((x, inner_top, x, inner_bottom), fill=grid_color, width=1)
        for y in range(inner_top, inner_bottom + 1, grid_y):
            draw.line((inner_left, y, inner_right, y), fill=grid_color, width=1)

        diameter = max(4, min(inner_width, inner_height) * 2 // 3)
        cx = inner_left + inner_width // 2
        cy = inner_top + inner_height // 2
        circle_box = (cx - diameter // 2, cy - diameter // 2, cx + diameter // 2, cy + diameter // 2)
        square_box = (cx - diameter // 3, cy - diameter // 3, cx + diameter // 3, cy + diameter // 3)
        line_color = (245, 245, 245)
        draw.ellipse(circle_box, outline=line_color, width=max(1, min(3, inner_height // 24)))
        draw.rectangle(square_box, outline=line_color, width=max(1, min(3, inner_height // 24)))

        travel = max(1, inner_width - 1)
        moving_x = inner_left + round((phase * travel + index * travel / max(1, len(spec["slices_detail"]))) % travel)
        draw.line((moving_x, inner_top, moving_x, inner_bottom), fill=(255, 255, 255), width=max(1, min(4, inner_height // 18)))
        draw.rectangle((left, top, right, bottom), outline=(255, 255, 255), width=max(1, min(4, inner_height // 20)))

        label = f"{index + 1} {item.get('slice_name') or item.get('slice_id') or ''}".strip()
        if inner_height >= 18:
            draw.rectangle((inner_left, inner_top, min(inner_right, inner_left + max(20, len(label) * 7)), inner_top + 12), fill=(0, 0, 0))
            draw.text((inner_left + 2, inner_top + 1), label, fill=(255, 255, 255), font=font)


def _render_soundcheck_frame(spec: dict[str, Any], image: Image.Image, frame_index: int) -> None:
    width = int(spec["composition"]["width"])
    height = int(spec["composition"]["height"])
    draw = ImageDraw.Draw(image)
    font = _font()
    section = next(
        (item for item in spec.get("sections", []) if item["start_frame"] <= frame_index < item["end_frame"]),
        spec.get("sections", [{"pattern": "blackout", "title": "Blackout"}])[-1],
    )
    pattern = section["pattern"]
    _draw_header(draw, f"NAYADE SOUNDCHECK — {section['title']}", width, height, font)
    if pattern == "blackout":
        image.paste((0, 0, 0), (0, 0, width, height))
        return
    if pattern == "pluge_near_black":
        image.paste((0, 0, 0), (0, 0, width, height))
        levels = (0, 4, 8, 16, 24, 32)
        bar_width = max(1, width // len(levels))
        for index, level in enumerate(levels):
            left = index * bar_width
            right = width if index == len(levels) - 1 else (index + 1) * bar_width
            draw.rectangle((left, 80, right - 1, height - 80), fill=(level, level, level))
            draw.text((left + 8, 45), str(level), fill=(255, 255, 255), font=font)
        return
    if pattern == "gray_ramp":
        for x in range(width):
            value = round(255 * x / max(1, width - 1))
            draw.line((x, 0, x, height), fill=(value, value, value))
        draw.rectangle((0, 0, min(width - 1, 240), 30), fill=(0, 0, 0))
        draw.text((10, 8), "NAYADE SOUNDCHECK — ESCALA DE GRISES", fill=(255, 255, 255), font=font)
        for index, value in enumerate((16, 32, 64, 128, 192, 235, 255)):
            x = round((value / 255) * max(0, width - 1))
            draw.line((x, 40, x, height - 40), fill=(255 - value, 255 - value, 255 - value), width=max(1, width // 1000))
            draw.text((max(0, x - 12), height - 35), str(value), fill=(255 - value, 255 - value, 255 - value), font=font)
        return
    if pattern == "primaries":
        colours = ((255, 0, 0, "RED"), (0, 255, 0, "GREEN"), (0, 0, 255, "BLUE"), (255, 255, 255, "WHITE"), (128, 128, 128, "GRAY"), (0, 0, 0, "BLACK"))
        band_width = max(1, width // len(colours))
        for index, (red, green, blue, label) in enumerate(colours):
            left = index * band_width
            right = width if index == len(colours) - 1 else (index + 1) * band_width
            draw.rectangle((left, 0, right - 1, height - 1), fill=(red, green, blue))
            draw.text((left + 10, height // 2), label, fill=(255, 255, 255) if (red + green + blue) < 500 else (0, 0, 0), font=font)
        return
    if pattern == "resolution_scaling":
        image.paste((8, 8, 12), (0, 0, width, height))
        grid = max(4, min(64, round(min(width, height) / 32)))
        for x in range(0, width, grid):
            draw.line((x, 0, x, height - 1), fill=(220, 220, 220), width=1)
        for y in range(0, height, grid):
            draw.line((0, y, width - 1, y), fill=(220, 220, 220), width=1)
        draw.line((0, 0, width - 1, height - 1), fill=(255, 255, 255), width=max(1, grid // 4))
        draw.line((width - 1, 0, 0, height - 1), fill=(255, 255, 255), width=max(1, grid // 4))
        draw.ellipse((width // 2 - min(width, height) // 5, height // 2 - min(width, height) // 5, width // 2 + min(width, height) // 5, height // 2 + min(width, height) // 5), outline=(255, 255, 0), width=max(1, grid // 4))
        return
    if pattern == "motion_stability":
        image.paste((8, 8, 12), (0, 0, width, height))
        total_frames = max(1, round(float(spec["duration_seconds"]) * float(spec["fps"])))
        phase = (frame_index % total_frames) / total_frames
        x = round(phase * max(1, width - 1))
        y = round((0.5 + 0.45 * math.sin(phase * 6.28318530718)) * max(1, height - 1))
        draw.line((x, 0, x, height - 1), fill=(255, 255, 255), width=max(2, width // 500))
        draw.line((0, y, width - 1, y), fill=(0, 255, 255), width=max(2, height // 300))
        return
    _render_geometry_frame(spec, image, frame_index)


def render_testcard_frame(spec: dict[str, Any], frame_index: int = 0) -> Image.Image:
    """Renderiza un frame RGB determinista de la tarjeta."""

    width = int(spec["composition"]["width"])
    height = int(spec["composition"]["height"])
    image = Image.new("RGB", (width, height), (10, 10, 14))
    if spec.get("suite", "geometry") == "soundcheck":
        _render_soundcheck_frame(spec, image, frame_index)
    else:
        _render_geometry_frame(spec, image, frame_index)

    return image


def render_testcard(
    output_map: dict[str, Any],
    output_path: str | Path,
    *,
    duration_seconds: float = 12.0,
    fps: float = 30.0,
    ffmpeg: str = "ffmpeg",
    suite: str = "geometry",
) -> dict[str, Any]:
    """Renderiza PNG o MP4 según la extensión de salida."""

    spec = build_testcard_spec(output_map, duration_seconds=duration_seconds, fps=fps, suite=suite)
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.casefold()
    if suffix == ".png":
        render_testcard_frame(spec).save(path)
        result = {"output": str(path), "format": "png", "frames_rendered": 1}
    elif suffix in {".mp4", ".mov", ".mkv"}:
        import subprocess

        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{spec['composition']['width']}x{spec['composition']['height']}",
            "-r",
            str(spec["fps"]),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(path),
        ]
        process = None
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert process.stdin is not None
            frame_count = max(1, round(spec["duration_seconds"] * spec["fps"]))
            for frame_index in range(frame_count):
                frame = render_testcard_frame(spec, frame_index)
                process.stdin.write(np.asarray(frame, dtype=np.uint8).tobytes())
            process.stdin.close()
            stdout, stderr = process.communicate()
        except FileNotFoundError as exc:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            raise ResolumeAdapterError(f"No se encontró FFmpeg para renderizar el test card: {ffmpeg}") from exc
        except Exception:
            if process is not None and process.poll() is None:
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                process.kill()
                process.wait()
            raise
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise ResolumeAdapterError(f"FFmpeg no pudo renderizar el test card: {detail or 'error desconocido'}")
        result = {"output": str(path), "format": suffix.removeprefix("."), "frames_rendered": frame_count}
    else:
        raise ResolumeAdapterError("La salida del test card debe terminar en .png, .mp4, .mov o .mkv.")

    report = dict(spec)
    report["render"] = result
    return report


def write_testcard_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def text_report(report: dict[str, Any]) -> str:
    render = report.get("render") or {}
    lines = [
        "RESOLUME_ADAPTER NAYADE TEST CARD",
        "=======================",
        f"Salida: {render.get('output')}",
        f"Canvas: {report.get('composition', {}).get('width')} × {report.get('composition', {}).get('height')}",
        f"Slices: {report.get('slices')}",
        f"Input groups: {report.get('input_groups')}",
        f"Frames renderizados: {render.get('frames_rendered')}",
        "",
        f"Suite: {report.get('suite', 'geometry')}. Secciones: {', '.join(item.get('pattern', '') for item in report.get('sections', []))}.",
        "El render no modifica el XML ni el showfile de Resolume.",
    ]
    return "\n".join(lines)

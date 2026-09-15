"""Generación de derivados target-specific para superficies de Resolume."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dxv import convert_to_dxv
from .media import ResolumeAdapterError, _run, ensure_file, probe_media, resolve_binary, summarize_video


ADAPTATION_SCHEMA_VERSION = "0.1"
STATIC_EXTENSIONS = frozenset({".bmp", ".jpeg", ".jpg", ".png", ".webp"})
STRATEGIES = frozenset({"crop", "fit_background", "pattern", "marquee"})


def _load_mapping_plan(path: str | Path) -> tuple[Path, dict[str, Any]]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise ResolumeAdapterError(f"No se encontró el plan de mapping: {resolved}")
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolumeAdapterError(f"No se pudo leer el plan de mapping: {resolved}") from exc
    if not isinstance(document, dict) or document.get("plan_type") != "InstarResolumeMappingPlan":
        raise ResolumeAdapterError("El archivo no es un plan INSTAR de Advanced Output.")
    return resolved, document


def _even(value: int) -> int:
    return max(2, value - (value % 2))


def _target_dimensions(candidate: dict[str, Any]) -> tuple[int, int]:
    target = candidate.get("target") or {}
    try:
        width = int(round(float(target.get("width") or 0)))
        height = int(round(float(target.get("height") or 0)))
    except (TypeError, ValueError) as exc:
        raise ResolumeAdapterError(f"El slice no tiene dimensiones válidas: {candidate.get('slice_name')}") from exc
    if width <= 0 or height <= 0:
        raise ResolumeAdapterError(f"El slice no tiene dimensiones válidas: {candidate.get('slice_name')}")
    return _even(width), _even(height)


def _safe_name(value: str, *, fallback: str = "asset") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return text.strip("._-") or fallback


def _candidate_tasks(
    mapping_plan: dict[str, Any],
    output_dir: Path,
    *,
    strategy: str = "auto",
    max_variants: int = 1,
) -> list[dict[str, Any]]:
    if strategy != "auto" and strategy not in STRATEGIES:
        raise ResolumeAdapterError(f"Estrategia inválida: {strategy}. Use auto o: {', '.join(sorted(STRATEGIES))}.")
    if max_variants <= 0:
        raise ResolumeAdapterError("max_variants debe ser mayor que cero.")

    tasks: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for candidate in mapping_plan.get("slice_candidates") or []:
        fallback_strategies = candidate.get("fallback_strategies") or []
        for fallback in fallback_strategies:
            operation = str(fallback.get("operation") or "")
            if operation not in STRATEGIES or (strategy != "auto" and operation != strategy):
                continue
            axis = str(fallback.get("axis") or "horizontal")
            group_id = str(fallback.get("input_group_id") or candidate.get("slice_id") or "group")
            target_width, target_height = _target_dimensions(candidate)
            candidates = fallback.get("candidate_assets") or []
            for ranked in candidates[:max_variants]:
                source = ranked.get("asset_path")
                asset_id = str(ranked.get("asset_id") or ranked.get("filename") or "asset")
                if not source:
                    continue
                key = (group_id, operation, axis, asset_id)
                if key in seen:
                    continue
                seen.add(key)
                source_path = Path(str(source)).expanduser().resolve()
                output_name = "__".join(
                    (
                        _safe_name(group_id, fallback="group"),
                        _safe_name(operation),
                        _safe_name(axis),
                        _safe_name(Path(str(ranked.get("filename") or source_path.name)).stem),
                    )
                ) + ".mp4"
                tasks.append({
                    "task_id": f"adapt-{len(tasks) + 1:03d}",
                    "source": str(source_path),
                    "source_asset_id": asset_id,
                    "source_filename": ranked.get("filename") or source_path.name,
                    "target": {
                        "width": target_width,
                        "height": target_height,
                        "slice_name": candidate.get("slice_name"),
                        "slice_id": candidate.get("slice_id"),
                        "input_group_id": group_id,
                    },
                    "strategy": operation,
                    "axis": axis,
                    "score": ranked.get("score"),
                    "evidence_status": ranked.get("status") or "unknown",
                    "requires_preview": True,
                    "output": str(output_dir / output_name),
                    "status": "planned",
                })
    return tasks


def build_adaptation_plan(
    mapping_plan: dict[str, Any],
    output_dir: str | Path,
    *,
    strategy: str = "auto",
    max_variants: int = 1,
    duration_seconds: float = 6.0,
    speed_pixels: float = 120.0,
    dxv_output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Construye recetas de derivados sin leer ni modificar los archivos fuente."""

    if duration_seconds <= 0:
        raise ResolumeAdapterError("duration_seconds debe ser mayor que cero.")
    if speed_pixels <= 0:
        raise ResolumeAdapterError("speed_pixels debe ser mayor que cero.")
    output = Path(output_dir).expanduser().resolve()
    dxv_output = Path(dxv_output_dir).expanduser().resolve() if dxv_output_dir else None
    tasks = _candidate_tasks(mapping_plan, output, strategy=strategy, max_variants=max_variants)
    return {
        "schema_version": ADAPTATION_SCHEMA_VERSION,
        "plan_type": "InstarTargetSpecificAdaptationPlan",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only_source": True,
        "source_mapping_plan": mapping_plan.get("source_map"),
        "mapping_plan_path": mapping_plan.get("generated_from"),
        "output_dir": str(output),
        "dxv_output_dir": str(dxv_output) if dxv_output else None,
        "dxv_export_requested": dxv_output is not None,
        "strategy_filter": strategy,
        "duration_seconds": duration_seconds,
        "speed_pixels": speed_pixels,
        "tasks": tasks,
        "limitations": [
            "Los derivados son previews y siempre requieren revisión en el LED real.",
            "La adaptación no modifica XML, showfiles, rutas de Resolume ni procesadores LED.",
            "El encoder GPU puede acelerar la salida, pero algunos filtros de composición siguen ejecutándose en CPU.",
            "El análisis de comportamiento no garantiza que un patrón sea estéticamente adecuado.",
        ],
    }


def _scaled_unit(source: dict[str, Any], target_width: int, target_height: int, axis: str) -> tuple[int, int]:
    video = source.get("video") or {}
    width = float(video.get("width") or 0)
    height = float(video.get("height") or 0)
    if width <= 0 or height <= 0:
        raise ResolumeAdapterError("No se pudieron obtener las dimensiones del video fuente.")
    if axis == "vertical":
        unit_width = target_width
        unit_height = _even(int(round(target_width * height / width)))
    else:
        unit_height = target_height
        unit_width = _even(int(round(target_height * width / height)))
    return max(2, unit_width), max(2, unit_height)


def _pattern_graph(
    source: dict[str, Any],
    target_width: int,
    target_height: int,
    *,
    axis: str,
    mirror_alternate: bool,
    marquee: bool,
    speed_pixels: float,
) -> str:
    unit_width, unit_height = _scaled_unit(source, target_width, target_height, axis)
    if axis == "vertical":
        count = max(2, math.ceil(target_height / unit_height) + 1)
    else:
        count = max(2, math.ceil(target_width / unit_width) + 1)
    labels = [f"p{index}" for index in range(count)]
    split_labels = "".join(f"[{label}]" for label in labels)
    graph = [
        f"[0:v]scale={unit_width}:{unit_height}:flags=lanczos,setsar=1,split={count}{split_labels}"
    ]
    stack_labels: list[str] = []
    for index, label in enumerate(labels):
        if mirror_alternate and index % 2 == 1:
            flipped = f"{label}f"
            graph.append(f"[{label}]hflip[{flipped}]")
            stack_labels.append(f"[{flipped}]")
        else:
            stack_labels.append(f"[{label}]")
    stack = "".join(stack_labels)
    if axis == "vertical":
        graph.append(f"{stack}vstack=inputs={count}[wide]")
        if marquee:
            y = f"mod(t*{speed_pixels:g}\\,in_h-out_h)"
            graph.append(f"[wide]crop={target_width}:{target_height}:0:{y},setsar=1")
        else:
            graph.append(f"[wide]crop={target_width}:{target_height}:0:0,setsar=1")
    else:
        graph.append(f"{stack}hstack=inputs={count}[wide]")
        if marquee:
            x = f"mod(t*{speed_pixels:g}\\,in_w-out_w)"
            graph.append(f"[wide]crop={target_width}:{target_height}:{x}:0,setsar=1")
        else:
            graph.append(f"[wide]crop={target_width}:{target_height}:0:0,setsar=1")
    return ";".join(graph)


def build_filter_graph(
    strategy: str,
    source: dict[str, Any],
    target_width: int,
    target_height: int,
    *,
    axis: str = "horizontal",
    mirror_alternate: bool = True,
    speed_pixels: float = 120.0,
) -> str:
    """Devuelve un filtergraph FFmpeg determinista para una estrategia."""

    if strategy not in STRATEGIES:
        raise ResolumeAdapterError(f"Estrategia inválida: {strategy}.")
    target_width, target_height = _even(target_width), _even(target_height)
    if strategy == "crop":
        return (
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={target_width}:{target_height}:(in_w-out_w)/2:(in_h-out_h)/2,setsar=1"
        )
    if strategy == "fit_background":
        return (
            f"split=2[bg][fg];"
            f"[bg]scale={target_width}:{target_height}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={target_width}:{target_height},boxblur=10:1[bg];"
            f"[fg]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease:flags=lanczos[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"
        )
    if strategy == "pattern":
        return _pattern_graph(
            source,
            target_width,
            target_height,
            axis=axis,
            mirror_alternate=mirror_alternate,
            marquee=False,
            speed_pixels=speed_pixels,
        )
    return _pattern_graph(
        source,
        target_width,
        target_height,
        axis=axis,
        mirror_alternate=mirror_alternate,
        marquee=True,
        speed_pixels=speed_pixels,
    )


def _available_encoder(ffmpeg: str, requested: str) -> tuple[str, str]:
    if requested not in {"auto", "h264_nvenc", "libx264"}:
        raise ResolumeAdapterError("El encoder debe ser auto, h264_nvenc o libx264.")
    if requested == "libx264":
        return "libx264", "cpu"
    executable = resolve_binary(ffmpeg, "FFmpeg")
    result = _run([executable, "-hide_banner", "-encoders"], check=False)
    has_nvenc = bool(re.search(r"\bh264_nvenc\b", f"{result.stdout}\n{result.stderr}"))
    if requested == "h264_nvenc" and not has_nvenc:
        raise ResolumeAdapterError("La build de FFmpeg no expone h264_nvenc.")
    return ("h264_nvenc", "nvidia_nvenc") if has_nvenc else ("libx264", "cpu")


def render_task(
    task: dict[str, Any],
    *,
    duration_seconds: float = 6.0,
    speed_pixels: float = 120.0,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    encoder: str = "auto",
    mirror_alternate: bool = True,
    dxv_output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Renderiza un preview y, opcionalmente, un DXV candidato sin sobrescribir."""

    source_path = ensure_file(task["source"], "fuente de adaptación")
    destination = Path(task["output"]).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = task.get("target") or {}
    target_width = int(target["width"])
    target_height = int(target["height"])
    if destination.exists():
        output_probe = probe_media(destination, ffprobe)
        output_video = summarize_video(output_probe)
        result_task: dict[str, Any] = {**task, "output": str(destination), "status": "EXISTS"}
    else:
        source_probe = probe_media(source_path, ffprobe)
        source_video = summarize_video(source_probe)
        filter_graph = build_filter_graph(
            task["strategy"],
            {"video": source_probe["video"]},
            target_width,
            target_height,
            axis=task.get("axis") or "horizontal",
            mirror_alternate=mirror_alternate,
            speed_pixels=speed_pixels,
        )
        selected_encoder, encoder_backend = _available_encoder(ffmpeg, encoder)
        input_args = ["-loop", "1"] if source_path.suffix.lower() in STATIC_EXTENSIONS else []
        input_args.extend(["-i", str(source_path)])
        command = [
            resolve_binary(ffmpeg, "FFmpeg"),
            "-hide_banner",
            "-nostdin",
            "-n",
            *input_args,
            "-an",
            "-vf",
            filter_graph,
            "-t",
            f"{duration_seconds:g}",
            "-c:v",
            selected_encoder,
            "-pix_fmt",
            "yuv420p",
        ]
        if selected_encoder == "h264_nvenc":
            command.extend(["-preset", "p4", "-cq", "19"])
        else:
            command.extend(["-preset", "medium", "-crf", "18"])
        command.extend(["-movflags", "+faststart", str(destination)])
        result = _run(command, check=False)
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip()
            if len(details) > 1800:
                details = details[-1800:]
            raise ResolumeAdapterError(f"Falló el render de adaptación ({task['task_id']}).\n{details}")
        output_probe = probe_media(destination, ffprobe)
        output_video = summarize_video(output_probe)
        result_task = {
            **task,
            "output": str(destination),
            "status": "PASS",
            "encoder": selected_encoder,
            "encoder_backend": encoder_backend,
            "filter_graph": filter_graph,
            "source_video": source_video,
        }
    if int(output_video.get("width") or 0) != target_width or int(output_video.get("height") or 0) != target_height:
        raise ResolumeAdapterError(
            f"El derivado no respetó el target: {output_video.get('width')}x{output_video.get('height')} "
            f"frente a {target_width}x{target_height}."
        )
    result_task["output_video"] = output_video

    if dxv_output_dir:
        dxv_directory = Path(dxv_output_dir).expanduser().resolve()
        dxv_directory.mkdir(parents=True, exist_ok=True)
        dxv_destination = dxv_directory / f"{destination.stem}_DXV.mov"
        if dxv_destination.exists():
            dxv_probe = probe_media(dxv_destination, ffprobe)
            dxv_video = summarize_video(dxv_probe)
            if str(dxv_video.get("codec") or "").lower() != "dxv":
                raise ResolumeAdapterError(f"La salida DXV existente no es DXV: {dxv_destination}")
            dxv_result = {
                "status": "EXISTS",
                "output": str(dxv_destination),
                "video": dxv_video,
            }
        else:
            dxv_result = convert_to_dxv(
                destination,
                dxv_destination,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                width=target_width,
                height=target_height,
                alpha=False,
                overwrite=False,
            )
        result_task["dxv"] = dxv_result
    return result_task


def run_adaptation(
    mapping_plan_path: str | Path,
    output_dir: str | Path,
    *,
    strategy: str = "auto",
    max_variants: int = 1,
    duration_seconds: float = 6.0,
    speed_pixels: float = 120.0,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    encoder: str = "auto",
    mirror_alternate: bool = True,
    dxv_output_dir: str | Path | None = None,
) -> dict[str, Any]:
    mapping_path, mapping_plan = _load_mapping_plan(mapping_plan_path)
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    plan = build_adaptation_plan(
        mapping_plan,
        output,
        strategy=strategy,
        max_variants=max_variants,
        duration_seconds=duration_seconds,
        speed_pixels=speed_pixels,
        dxv_output_dir=dxv_output_dir,
    )
    plan["mapping_plan_path"] = str(mapping_path)
    results: list[dict[str, Any]] = []
    for task in plan["tasks"]:
        results.append(
            render_task(
                task,
                duration_seconds=duration_seconds,
                speed_pixels=speed_pixels,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                encoder=encoder,
                mirror_alternate=mirror_alternate,
                dxv_output_dir=dxv_output_dir,
            )
        )
    plan["tasks"] = results
    plan["summary"] = {
        "planned": len(results),
        "passed": sum(item.get("status") == "PASS" for item in results),
        "existing": sum(item.get("status") == "EXISTS" for item in results),
    }
    return plan


def write_adaptation_plan(plan: dict[str, Any], path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def text_report(plan: dict[str, Any]) -> str:
    summary = plan.get("summary") or {}
    lines = [
        "RESOLUME_ADAPTER INSTAR ADAPT",
        "===================",
        f"Mapping: {(plan.get('source_mapping_plan') or {}).get('path') or plan.get('mapping_plan_path')}",
        f"Estrategia: {plan.get('strategy_filter')}",
        f"Target previews: {plan.get('duration_seconds')} s",
        f"Tareas: {summary.get('planned', len(plan.get('tasks') or []))}",
        f"Render PASS: {summary.get('passed', 0)}",
        f"Ya existentes: {summary.get('existing', 0)}",
        f"Exportación DXV: {'sí' if plan.get('dxv_export_requested') else 'no'}",
    ]
    for task in plan.get("tasks") or []:
        target = task.get("target") or {}
        lines.append(
            f"  [{task.get('status')}] {task.get('strategy')} {task.get('axis')} -> "
            f"{task.get('source_filename')} -> {target.get('slice_name')} "
            f"({target.get('width')}x{target.get('height')})"
        )
        if task.get("dxv"):
            lines.append(f"    DXV [{task['dxv'].get('status')}] -> {task['dxv'].get('output')}")
    return "\n".join(lines)

"""Preparación y conversión DXV para RESOLUME_ADAPTER."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from .media import ResolumeAdapterError, _run, ensure_file, probe_media, resolve_binary, summarize_video


def encoder_capabilities(ffmpeg: str = "ffmpeg") -> dict[str, Any]:
    executable = resolve_binary(ffmpeg, "FFmpeg")
    result = _run([executable, "-hide_banner", "-h", "encoder=dxv"], check=False)
    output = f"{result.stdout}\n{result.stderr}"
    available = result.returncode == 0 and re.search(r"Encoder\s+dxv\b", output, re.IGNORECASE) is not None
    formats = sorted(set(re.findall(r"^\s+(dxt1|dxt5|ycg6|yg10)\s+", output, re.IGNORECASE | re.MULTILINE)))
    return {
        "available": available,
        "formats": [item.lower() for item in formats],
        "raw_help": output,
    }


def default_output_path(input_path: str | Path) -> Path:
    source = ensure_file(input_path)
    return source.with_name(f"{source.stem}_DXV.mov")


def build_command(
    input_path: str | Path,
    output_path: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
    fps: float | None = None,
    width: int | None = None,
    height: int | None = None,
    alpha: bool = False,
    overwrite: bool = False,
) -> list[str]:
    input_file = ensure_file(input_path)
    output_file = Path(output_path).expanduser().resolve()
    capabilities = encoder_capabilities(ffmpeg)
    if not capabilities["available"]:
        raise ResolumeAdapterError(
            "El FFmpeg seleccionado no expone el encoder DXV. "
            "Instala una build que lo incluya o usa Resolume Alley."
        )

    format_name = "dxt5" if alpha else "dxt1"
    if format_name not in capabilities["formats"]:
        if alpha:
            raise ResolumeAdapterError(
                "Este encoder DXV no expone un formato con alpha. "
                "La primera versión soporta Normal Quality / No Alpha."
            )
        raise ResolumeAdapterError("El encoder DXV no expone el formato dxt1 esperado.")

    filters: list[str] = []
    if width is not None or height is not None:
        if width is None or height is None or width <= 0 or height <= 0:
            raise ResolumeAdapterError("Para cambiar la resolución debes indicar --width y --height positivos.")
        filters.append(
            f"scale={width}:{height}:force_original_aspect_ratio=decrease"
        )
        filters.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black")
        filters.append("setsar=1")
    if fps is not None:
        if fps <= 0:
            raise ResolumeAdapterError("El FPS debe ser mayor que cero.")
        filters.append(f"fps={fps:g}")
    filters.append("format=rgba")

    command = [
        resolve_binary(ffmpeg, "FFmpeg"),
        "-hide_banner",
        "-nostdin",
        "-y" if overwrite else "-n",
        "-i",
        str(input_file),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-map_metadata",
        "0",
        "-map_chapters",
        "0",
        "-vf",
        ",".join(filters),
        "-c:v",
        "dxv",
        "-format",
        format_name,
        "-pix_fmt",
        "rgba",
        "-c:a",
        "pcm_s16le",
        str(output_file),
    ]
    return command


def convert_to_dxv(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    fps: float | None = None,
    width: int | None = None,
    height: int | None = None,
    alpha: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    input_file = ensure_file(input_path)
    destination = (Path(output_path) if output_path else default_output_path(input_file)).expanduser().resolve()
    if destination.exists() and not overwrite and not dry_run:
        raise ResolumeAdapterError(f"La salida ya existe; usa --overwrite para reemplazarla: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = build_command(
        input_file,
        destination,
        ffmpeg=ffmpeg,
        fps=fps,
        width=width,
        height=height,
        alpha=alpha,
        overwrite=overwrite,
    )
    if dry_run:
        return {"input": str(input_file), "output": str(destination), "command": command, "dry_run": True}

    _run(command)
    validation = probe_media(destination, ffprobe)
    video = summarize_video(validation)
    if str(video.get("codec") or "").lower() != "dxv":
        raise ResolumeAdapterError("La conversión terminó, pero la salida no fue identificada como DXV.")
    return {
        "input": str(input_file),
        "output": str(destination),
        "dry_run": False,
        "video": video,
        "status": "PASS",
    }

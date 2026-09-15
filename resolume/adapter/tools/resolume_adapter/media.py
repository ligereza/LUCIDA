"""Utilidades comunes para inspeccionar y analizar archivos de video."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import statistics
import subprocess
from pathlib import Path
from typing import Any, Iterable


class ResolumeAdapterError(RuntimeError):
    """Error esperado que puede mostrarse directamente a una persona usuaria."""


def resolve_binary(name_or_path: str, label: str) -> str:
    """Resuelve un ejecutable por nombre o ruta absoluta."""

    candidate = Path(name_or_path)
    if candidate.parent != Path(".") or candidate.is_absolute():
        if candidate.exists():
            return str(candidate)
        raise ResolumeAdapterError(f"No se encontró {label} en: {name_or_path}")

    resolved = shutil.which(name_or_path)
    if resolved:
        return resolved
    raise ResolumeAdapterError(
        f"No se encontró {label} ({name_or_path}). "
        "Instálalo o indica su ruta con la opción correspondiente."
    )


def ensure_file(path_value: str | Path, label: str = "archivo") -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise ResolumeAdapterError(f"No se encontró el {label}: {path}")
    return path


def parse_fraction(value: Any) -> float | None:
    """Convierte valores como 30000/1001 a un número, sin inventar datos."""

    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"0/0", "N/A", "nan"}:
        return None
    try:
        if "/" in text:
            numerator, denominator = text.split("/", 1)
            denominator_value = float(denominator)
            if denominator_value == 0:
                return None
            return float(numerator) / denominator_value
        return float(text)
    except ValueError:
        return None


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        if len(details) > 1800:
            details = details[-1800:]
        raise ResolumeAdapterError(
            f"Falló una operación externa ({Path(command[0]).name}, código "
            f"{result.returncode}).\n{details}"
        )
    return result


def probe_media(path: str | Path, ffprobe: str = "ffprobe") -> dict[str, Any]:
    """Obtiene metadata estructurada sin decodificar todo el video."""

    media_path = ensure_file(path)
    executable = resolve_binary(ffprobe, "FFprobe")
    result = _run(
        [
            executable,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(media_path),
        ]
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ResolumeAdapterError("FFprobe devolvió una respuesta que no es JSON válido.") from exc

    streams = data.get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if video is None:
        raise ResolumeAdapterError(f"No se encontró una pista de video en: {media_path}")

    return {
        "path": str(media_path),
        "format": data.get("format") or {},
        "streams": streams,
        "video": video,
        "audio": audio,
    }


def inspect_frame_timing(
    path: str | Path,
    ffprobe: str = "ffprobe",
    seconds: int = 30,
) -> dict[str, Any]:
    """Mide la estabilidad temporal de una ventana inicial del video."""

    media_path = ensure_file(path)
    executable = resolve_binary(ffprobe, "FFprobe")
    result = _run(
        [
            executable,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-read_intervals",
            f"%+{seconds}",
            "-show_frames",
            "-show_entries",
            "frame=best_effort_timestamp_time,pkt_duration_time",
            "-of",
            "csv=p=0",
            str(media_path),
        ],
        check=False,
    )

    timestamps: list[float] = []
    for line in result.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if not fields:
            continue
        timestamp = parse_fraction(fields[0])
        if timestamp is not None:
            timestamps.append(timestamp)

    intervals = [right - left for left, right in zip(timestamps, timestamps[1:])]
    intervals = [value for value in intervals if value > 0 and math.isfinite(value)]
    if len(intervals) < 3:
        return {
            "sampled_seconds": seconds,
            "frames_with_timestamps": len(timestamps),
            "intervals": len(intervals),
            "status": "unknown",
            "reason": "No hubo suficientes timestamps válidos para evaluar estabilidad.",
        }

    median_interval = statistics.median(intervals)
    deviations = [abs(value - median_interval) / median_interval for value in intervals]
    median_absolute_deviation = statistics.median(deviations)
    max_deviation = max(deviations)
    likely_vfr = median_absolute_deviation > 0.02 or max_deviation > 0.08

    return {
        "sampled_seconds": seconds,
        "frames_with_timestamps": len(timestamps),
        "intervals": len(intervals),
        "median_interval_seconds": round(median_interval, 8),
        "estimated_fps": round(1.0 / median_interval, 4),
        "median_relative_deviation": round(median_absolute_deviation, 6),
        "max_relative_deviation": round(max_deviation, 6),
        "status": "warning" if likely_vfr else "pass",
        "likely_variable_frame_rate": likely_vfr,
    }


def analyze_luminance(
    path: str | Path,
    ffmpeg: str = "ffmpeg",
    max_samples: int = 300,
    sample_fps: int = 10,
) -> dict[str, Any]:
    """Calcula una señal de luminancia global como cribado de posible flicker.

    La métrica es una señal de alerta, no una prueba definitiva: movimiento,
    cortes y flashes intencionales también pueden producir alternancia.
    """

    media_path = ensure_file(path)
    executable = resolve_binary(ffmpeg, "FFmpeg")
    command = [
        executable,
        "-hide_banner",
        "-nostats",
        "-i",
        str(media_path),
        "-an",
        "-vf",
        # Normalizamos solo la señal de análisis a 8 bits. El archivo original
        # no se modifica y así YAVG queda comparable entre H.264, CineForm y DXV.
        f"fps={sample_fps},format=yuv444p,signalstats,metadata=print:file=-",
        "-frames:v",
        str(max_samples),
        "-f",
        "null",
        os.devnull,
    ]
    result = _run(command, check=False)
    output = f"{result.stdout}\n{result.stderr}"
    values = [
        float(match.group(1))
        for match in re.finditer(
            r"lavfi\.signalstats\.YAVG=([+-]?(?:\d+(?:\.\d*)?|\.\d+))",
            output,
        )
    ]
    if len(values) < 3:
        return {
            "sampled_frames": len(values),
            "status": "unknown",
            "reason": "No hubo suficientes frames con señal de luminancia.",
        }

    deltas = [right - left for left, right in zip(values, values[1:])]
    active_deltas = [value for value in deltas if abs(value) >= 0.5]
    sign_changes = sum(
        1
        for left, right in zip(active_deltas, active_deltas[1:])
        if left * right < 0
    )
    alternation_ratio = sign_changes / max(1, len(active_deltas) - 1)
    mean_absolute_delta = statistics.fmean(abs(value) for value in deltas)
    mean_luminance = statistics.fmean(values)
    relative_change = mean_absolute_delta / max(1.0, mean_luminance)
    intensity_component = min(1.0, relative_change / 0.06)
    score = min(1.0, 0.55 * alternation_ratio + 0.45 * intensity_component)
    possible = score >= 0.55 and mean_absolute_delta >= 2.0

    return {
        "sampled_frames": len(values),
        "sample_fps": sample_fps,
        "mean_luminance": round(mean_luminance, 4),
        "luminance_min": round(min(values), 4),
        "luminance_max": round(max(values), 4),
        "mean_absolute_delta": round(mean_absolute_delta, 4),
        "alternation_ratio": round(alternation_ratio, 4),
        "screening_score": round(score, 4),
        "possible_luminance_flicker": possible,
        "status": "warning" if possible else "pass",
        "interpretation": (
            "Señal compatible con variaciones temporales; revisar el archivo y la cadena de salida."
            if possible
            else "No se observó una señal fuerte de flicker global en la ventana analizada."
        ),
    }


def format_fps(value: Any) -> str | None:
    parsed = parse_fraction(value)
    if parsed is None:
        return None
    return f"{parsed:.3f}".rstrip("0").rstrip(".")


def has_alpha(video_stream: dict[str, Any]) -> bool | None:
    # FFmpeg expone DXV decodificado como RGBA incluso cuando el archivo fue
    # codificado con DXT1 (sin alpha). No inferimos transparencia desde ese
    # pixel format para evitar falsos positivos.
    if str(video_stream.get("codec_name") or "").lower() == "dxv":
        return None
    pixel_format = str(video_stream.get("pix_fmt") or "").lower()
    alpha_formats = ("rgba", "argb", "bgra", "abgr", "gbrap", "yuva", "ayuv")
    return any(marker in pixel_format for marker in alpha_formats)


def summarize_video(probe: dict[str, Any]) -> dict[str, Any]:
    video = probe["video"]
    format_data = probe.get("format") or {}
    duration = parse_fraction(video.get("duration"))
    if duration is None:
        duration = parse_fraction(format_data.get("duration"))
    frame_count = video.get("nb_frames")
    try:
        frame_count = int(frame_count) if frame_count is not None else None
    except (TypeError, ValueError):
        frame_count = None
    bitrate = video.get("bit_rate") or format_data.get("bit_rate")
    try:
        bitrate = int(bitrate) if bitrate is not None else None
    except (TypeError, ValueError):
        bitrate = None
    bit_depth = video.get("bits_per_raw_sample") or video.get("bits_per_coded_sample")
    try:
        bit_depth = int(bit_depth) if bit_depth is not None else None
    except (TypeError, ValueError):
        bit_depth = None
    return {
        "codec": video.get("codec_name"),
        "codec_long_name": video.get("codec_long_name"),
        "profile": video.get("profile"),
        "width": video.get("width"),
        "height": video.get("height"),
        "pixel_format": video.get("pix_fmt"),
        "average_fps": format_fps(video.get("avg_frame_rate")),
        "average_fps_value": parse_fraction(video.get("avg_frame_rate")),
        "nominal_fps": format_fps(video.get("r_frame_rate")),
        "nominal_fps_value": parse_fraction(video.get("r_frame_rate")),
        "duration_seconds": duration,
        "frame_count": frame_count,
        "bitrate_bps": bitrate,
        "bit_depth": bit_depth,
        "sample_aspect_ratio": video.get("sample_aspect_ratio"),
        "display_aspect_ratio": video.get("display_aspect_ratio"),
        "field_order": video.get("field_order"),
        "has_alpha": has_alpha(video),
        "color_range": video.get("color_range"),
        "color_space": video.get("color_space"),
        "color_transfer": video.get("color_transfer"),
        "color_primaries": video.get("color_primaries"),
        "audio_codec": (probe.get("audio") or {}).get("codec_name"),
    }

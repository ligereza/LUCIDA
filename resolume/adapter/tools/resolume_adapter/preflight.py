"""Preflight técnico de media para INSTAR.

Esta capa sólo inspecciona metadata del archivo. No decodifica el video completo
ni intenta inferir todavía su comportamiento visual.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .media import ResolumeAdapterError, ensure_file, parse_fraction, probe_media, summarize_video


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _container_name(
    format_name: str | None,
    format_long_name: str | None = None,
    suffix: str | None = None,
) -> str | None:
    """Normaliza el contenedor sin confundir los alias de QuickTime/MOV."""

    if suffix and suffix.lower() == ".mov":
        return "QuickTime MOV"
    if format_long_name and "quicktime" in format_long_name.lower():
        return "QuickTime MOV"
    if not format_name:
        return None
    names = {part.strip().lower() for part in format_name.split(",") if part.strip()}
    if names & {"mp4", "m4v", "3gp", "3g2", "mj2"}:
        return "MP4/ISO BMFF"
    if "mov" in names:
        return "QuickTime MOV"
    if "matroska" in names or "webm" in names:
        return "Matroska/WebM"
    if "avi" in names:
        return "AVI"
    return format_name.split(",", 1)[0]


def _alpha_summary(video_stream: dict[str, Any], video: dict[str, Any]) -> dict[str, Any]:
    codec = str(video_stream.get("codec_name") or "").lower()
    pixel_format = str(video_stream.get("pix_fmt") or "").lower()
    detected = video.get("has_alpha")

    if codec == "dxv" and detected is None:
        return {
            "status": "unknown",
            "encoded": None,
            "evidence": f"DXV decodificado como {pixel_format or 'pixel format desconocido'}; FFprobe no basta para confirmar si el alpha original está activo.",
        }
    if detected is True:
        return {
            "status": "present",
            "encoded": True,
            "evidence": f"El pixel format {pixel_format or 'desconocido'} expone un canal alpha.",
        }
    return {
        "status": "absent",
        "encoded": False,
        "evidence": f"El pixel format {pixel_format or 'desconocido'} no expone un canal alpha.",
    }


def preflight_file(
    path: str | Path,
    *,
    ffprobe: str = "ffprobe",
    target_fps: float | None = None,
    target_width: int | None = None,
    target_height: int | None = None,
    target_codec: str | None = None,
) -> dict[str, Any]:
    """Inspecciona un video y devuelve hechos técnicos y reglas accionables."""

    media_path = ensure_file(path)
    probe = probe_media(media_path, ffprobe)
    video_stream = probe["video"]
    audio_stream = probe.get("audio")
    video = summarize_video(probe)
    format_data = probe.get("format") or {}
    container = {
        "name": _container_name(
            format_data.get("format_name"),
            format_data.get("format_long_name"),
            media_path.suffix,
        ),
        "format_name": format_data.get("format_name"),
        "format_long_name": format_data.get("format_long_name"),
        "duration_seconds": parse_fraction(format_data.get("duration")),
        "size_bytes": int(format_data["size"]) if str(format_data.get("size", "")).isdigit() else media_path.stat().st_size,
    }
    audio = None
    if audio_stream:
        sample_rate = audio_stream.get("sample_rate")
        try:
            sample_rate = int(sample_rate) if sample_rate is not None else None
        except (TypeError, ValueError):
            sample_rate = None
        audio = {
            "codec": audio_stream.get("codec_name"),
            "sample_rate": sample_rate,
            "channels": audio_stream.get("channels"),
            "channel_layout": audio_stream.get("channel_layout"),
            "duration_seconds": parse_fraction(audio_stream.get("duration")),
        }
    alpha = _alpha_summary(video_stream, video)
    codec = str(video.get("codec") or "").lower()
    is_static_image = codec in {"png", "mjpeg", "webp", "bmp", "jpeg", "tiff"}

    checks: list[dict[str, str]] = [
        _check("Archivo legible", "PASS", "FFprobe encontró una pista de video."),
        _check(
            "Contenedor",
            "PASS" if container["name"] else "WARN",
            container["name"] or "No se pudo identificar el contenedor.",
        ),
    ]
    recommendations: list[str] = []

    width = video.get("width")
    height = video.get("height")
    if isinstance(width, int) and isinstance(height, int):
        if width <= 0 or height <= 0:
            checks.append(_check("Dimensiones", "WARN", "La resolución reportada no es válida."))
        elif width % 2 or height % 2:
            checks.append(
                _check("Dimensiones", "WARN", f"{width} × {height} px; contiene una dimensión impar.")
            )
            recommendations.append("Revisar compatibilidad antes de convertir o enviar el clip al show.")
        else:
            checks.append(_check("Dimensiones", "PASS", f"{width} × {height} px."))
        if target_width and target_height and (width != target_width or height != target_height):
            checks.append(
                _check(
                    "Resolución objetivo",
                    "WARN",
                    f"El archivo es {width} × {height}; objetivo configurado: {target_width} × {target_height}.",
                )
            )
            recommendations.append("Escalar sólo si la composición o la salida real lo requieren.")
    else:
        checks.append(_check("Dimensiones", "WARN", "No se pudo leer una resolución válida."))

    average_fps = parse_fraction(video_stream.get("avg_frame_rate"))
    nominal_fps = parse_fraction(video_stream.get("r_frame_rate"))
    if is_static_image:
        checks.append(_check("Tipo de asset", "PASS", "Imagen estática; no requiere FPS ni timeline."))
    elif average_fps is None:
        checks.append(_check("FPS", "WARN", "No se pudo leer un FPS promedio confiable."))
        recommendations.append("Revisar el timeline antes de usar el clip como loop.")
    else:
        fps_detail = f"Promedio {average_fps:.3f} FPS"
        if nominal_fps is not None and abs(average_fps - nominal_fps) > 0.1:
            fps_detail += f"; nominal {nominal_fps:.3f} FPS"
            checks.append(_check("FPS", "WARN", f"{fps_detail}; hay una diferencia que conviene revisar."))
            recommendations.append("Confirmar si el archivo es VFR o si sus timestamps son irregulares.")
        elif target_fps is not None and abs(average_fps - target_fps) > 0.1:
            checks.append(_check("FPS objetivo", "WARN", f"{fps_detail}; objetivo {target_fps:.3f} FPS."))
            recommendations.append("Normalizar el FPS sólo si la composición o la salida lo requieren.")
        else:
            checks.append(_check("FPS", "PASS", f"{fps_detail}."))

    field_order = str(video.get("field_order") or "unknown").lower()
    if field_order in {"progressive", "unknown", "0"}:
        checks.append(_check("Escaneo", "PASS", f"Campo reportado: {field_order}."))
    else:
        checks.append(_check("Escaneo", "WARN", f"Se detectó orden de campos: {field_order}."))
        recommendations.append("Preferir una versión progresiva para reproducción VJ.")

    if target_codec and codec != target_codec.lower():
        checks.append(_check("Codec objetivo", "WARN", f"Codec actual: {codec or 'desconocido'}; objetivo: {target_codec}."))
        recommendations.append(f"Preparar una versión {target_codec} sólo si ese es el perfil de reproducción elegido.")
    else:
        checks.append(_check("Codec", "PASS", codec or "desconocido"))

    if alpha["status"] == "present":
        checks.append(_check("Alpha", "PASS", alpha["evidence"]))
    elif alpha["status"] == "absent":
        checks.append(_check("Alpha", "PASS", f"No detectado. {alpha['evidence']}"))
    else:
        checks.append(_check("Alpha", "INFO", alpha["evidence"]))
        recommendations.append("Si la transparencia es importante, probar el clip sobre un fondo contrastante en Resolume.")

    if audio_stream:
        checks.append(
            _check(
                "Audio",
                "INFO",
                f"Pista embebida: {audio.get('codec') or 'codec desconocido'}, "
                f"{audio.get('sample_rate') or 'sample rate desconocido'} Hz.",
            )
        )
    else:
        checks.append(_check("Audio", "INFO", "No se detectó una pista de audio embebida."))

    color_fields = {
        key: video_stream.get(key)
        for key in ("color_range", "color_space", "color_transfer", "color_primaries")
        if video_stream.get(key) is not None
    }
    if color_fields:
        checks.append(_check("Color declarado", "INFO", ", ".join(f"{key}={value}" for key, value in color_fields.items())))
    else:
        checks.append(_check("Color declarado", "INFO", "No hay metadata de color completa."))

    warning_count = sum(check["status"] == "WARN" for check in checks)
    overall = "WARN" if warning_count else "PASS"
    if not recommendations:
        recommendations.append("No se detectaron incompatibilidades técnicas con los criterios configurados.")

    return {
        "schema_version": "0.1",
        "tool": "INSTAR Media Preflight",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(media_path),
        "overall_status": overall,
        "container": container,
        "video": video,
        "audio": audio,
        "alpha": alpha,
        "checks": checks,
        "recommendations": recommendations,
        "analysis": {
            "visual": "not_run",
            "temporal": "not_run",
            "audio_features": "not_run",
        },
        "limitations": [
            "La extensión MP4 o MOV no determina por sí sola el codec ni la presencia de alpha.",
            "Un canal alpha declarado no garantiza que el programa de reproducción lo interprete como se espera.",
            "Este modo no analiza todavía movimiento, paleta, flashes, loop ni banding visible.",
        ],
    }


def sidecar_from_report(report: dict[str, Any]) -> dict[str, Any]:
    """Reduce un preflight a un contrato reutilizable por NAYADE e IMAGO."""

    return {
        "schema_version": report.get("schema_version", "0.1"),
        "tool": report.get("tool", "INSTAR Media Preflight"),
        "generated_at": report.get("generated_at"),
        "media": {
            "path": report.get("input"),
            "filename": Path(str(report.get("input", ""))).name,
            "size_bytes": (report.get("container") or {}).get("size_bytes"),
        },
        "technical": {
            "container": (report.get("container") or {}).get("name"),
            **(report.get("video") or {}),
            "alpha": report.get("alpha"),
        },
        "audio": report.get("audio"),
        "status": report.get("overall_status"),
        "checks": report.get("checks", []),
        "recommendations": report.get("recommendations", []),
        "analysis": report.get("analysis", {}),
        "clip_profile": report.get("clip_profile"),
        "show_profile": report.get("show_profile"),
    }


def write_sidecar(report: dict[str, Any], output_dir: str | Path) -> Path:
    """Escribe un sidecar sin modificar el medio original."""

    output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    input_path = Path(str(report.get("input", "media")))
    sidecar_path = output_root / f"{input_path.name}.resolume_adapter.json"
    sidecar_path.write_text(
        json.dumps(sidecar_from_report(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return sidecar_path

"""Diagnóstico de medios para RESOLUME_ADAPTER."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .media import (
    ResolumeAdapterError,
    analyze_luminance,
    inspect_frame_timing,
    parse_fraction,
    probe_media,
    summarize_video,
)


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def diagnose_file(
    path: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    target_fps: float | None = None,
    target_width: int | None = None,
    target_height: int | None = None,
    max_samples: int = 300,
) -> dict[str, Any]:
    media_path = Path(path).expanduser().resolve()
    probe = probe_media(media_path, ffprobe)
    video = summarize_video(probe)
    checks: list[dict[str, str]] = [_check("Archivo legible", "PASS", "FFprobe encontró una pista de video.")]
    recommendations: list[str] = []

    width = video.get("width")
    height = video.get("height")
    if isinstance(width, int) and isinstance(height, int):
        if width % 2 or height % 2:
            checks.append(
                _check("Dimensiones", "WARN", "La resolución contiene un valor impar; conviene revisar compatibilidad.")
            )
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
            recommendations.append("Escalar solo si la composición o la salida real lo requieren.")

    average_fps = parse_fraction(probe["video"].get("avg_frame_rate"))
    if average_fps is None:
        checks.append(_check("FPS", "WARN", "No se pudo leer un FPS promedio confiable."))
    else:
        fps_detail = f"FPS promedio declarado: {average_fps:.3f}."
        if target_fps is not None and abs(average_fps - target_fps) > 0.1:
            checks.append(_check("FPS objetivo", "WARN", f"{fps_detail} Objetivo: {target_fps:.3f}."))
            recommendations.append("Normalizar el FPS a la composición antes de preparar el clip para el show.")
        else:
            checks.append(_check("FPS", "PASS", fps_detail))

    timing = inspect_frame_timing(media_path, ffprobe)
    if timing.get("status") == "warning":
        checks.append(
            _check(
                "Estabilidad temporal",
                "WARN",
                "La muestra presenta intervalos irregulares; puede ser VFR o contener timestamps problemáticos.",
            )
        )
        recommendations.append("Convertir a frame rate constante (CFR) si el clip se usará como loop VJ.")
    elif timing.get("status") == "pass":
        checks.append(_check("Estabilidad temporal", "PASS", "La ventana analizada parece estable."))
    else:
        checks.append(_check("Estabilidad temporal", "WARN", timing.get("reason", "No concluyente.")))

    field_order = str(video.get("field_order") or "unknown").lower()
    if field_order in {"progressive", "unknown", "0"}:
        checks.append(_check("Escaneo", "PASS", f"Campo reportado: {field_order}."))
    else:
        checks.append(_check("Escaneo", "WARN", f"Se detectó orden de campos: {field_order}."))
        recommendations.append("Preferir una versión progresiva para reproducción VJ.")

    codec = str(video.get("codec") or "").lower()
    if codec == "dxv":
        checks.append(_check("Codec Resolume", "PASS", "El archivo ya usa DXV."))
    else:
        checks.append(_check("Codec Resolume", "WARN", f"Codec actual: {codec or 'desconocido'}."))
        recommendations.append("Preparar una versión DXV para la reproducción principal en Resolume.")

    luminance = analyze_luminance(media_path, ffmpeg, max_samples=max_samples)
    if luminance.get("status") == "warning":
        checks.append(_check("Flicker de luminancia", "WARN", luminance["interpretation"]))
        recommendations.append("Comparar el archivo original con una versión deflicker y probar fuera del proyector.")
    elif luminance.get("status") == "pass":
        checks.append(_check("Flicker de luminancia", "PASS", luminance["interpretation"]))
    else:
        checks.append(_check("Flicker de luminancia", "WARN", luminance.get("reason", "No concluyente.")))

    warning_count = sum(check["status"] == "WARN" for check in checks)
    overall = "WARN" if warning_count else "PASS"
    if not recommendations:
        recommendations.append("El archivo no presenta alertas en las pruebas ejecutadas.")

    return {
        "schema_version": "0.1",
        "tool": "RESOLUME_ADAPTER Diagnose",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(media_path),
        "overall_status": overall,
        "video": video,
        "checks": checks,
        "timing": timing,
        "luminance": luminance,
        "recommendations": recommendations,
        "limitations": [
            "El análisis de luminancia es un cribado y puede confundir movimiento o flashes intencionales con flicker.",
            "El informe no puede confirmar problemas de PWM, refresco, tearing, cableado o el proyector sin una prueba de salida.",
            f"La señal de luminancia se tomó sobre un máximo de {max_samples} muestras a 10 FPS.",
        ],
    }


def text_report(report: dict[str, Any]) -> str:
    lines = [
        "RESOLUME_ADAPTER DIAGNOSE",
        "===============",
        f"Archivo: {report['input']}",
        f"Estado: {report['overall_status']}",
        "",
        "Video:",
    ]
    for key, value in report["video"].items():
        lines.append(f"  - {key}: {value}")
    lines.extend(["", "Comprobaciones:"])
    for check in report["checks"]:
        lines.append(f"  [{check['status']}] {check['name']}: {check['detail']}")
    lines.extend(["", "Recomendaciones:"])
    for recommendation in report["recommendations"]:
        lines.append(f"  - {recommendation}")
    return "\n".join(lines)

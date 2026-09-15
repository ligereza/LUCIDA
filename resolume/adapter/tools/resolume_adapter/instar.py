"""Preflight de media para la etapa INSTAR."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cache import InstarCache
from .contracts import analysis_cache_key, build_clip_profile, fingerprint_file
from .diagnose import diagnose_file
from .gpu import GpuUnavailable, analyze_visual_gpu
from .media import ResolumeAdapterError
from .preflight import preflight_file, write_sidecar
from .rules import apply_show_rules


MEDIA_EXTENSIONS = frozenset(
    {
        ".avi",
        ".bmp",
        ".dxv",
        ".gif",
        ".jpeg",
        ".jpg",
        ".mkv",
        ".mov",
        ".mp4",
        ".mxf",
        ".png",
        ".webm",
        ".webp",
    }
)

STATIC_IMAGE_EXTENSIONS = frozenset({".bmp", ".jpeg", ".jpg", ".png", ".webp"})


def discover_media_files(root: str | Path) -> list[Path]:
    """Encuentra medios compatibles dentro de una carpeta, de forma estable."""

    media_root = Path(root).expanduser().resolve()
    if not media_root.is_dir():
        raise ResolumeAdapterError(f"No se encontró la carpeta de media: {media_root}")

    return sorted(
        path
        for path in media_root.rglob("*")
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
    )


def _analyze_file(
    media_path: Path,
    *,
    ffmpeg: str,
    ffprobe: str,
    target_fps: float | None,
    target_width: int | None,
    target_height: int | None,
    max_samples: int,
    target_codec: str | None,
    deep: bool,
    gpu: bool,
    gpu_max_frames: int,
    gpu_batch_size: int,
) -> dict[str, Any]:
    if media_path.suffix.lower() in STATIC_IMAGE_EXTENSIONS:
        report = preflight_file(
            media_path,
            ffprobe=ffprobe,
            target_fps=target_fps,
            target_width=target_width,
            target_height=target_height,
            target_codec=target_codec,
        )
        report["analysis"] = {
            "status": "STATIC_IMAGE",
            "backend": "ffprobe",
            "reason": "Asset estático; no se aplica análisis de frames, loop ni NVDEC.",
        }
        report["checks"].append(
            {
                "name": "Asset estático",
                "status": "PASS",
                "detail": "La imagen se incorporó al catálogo sin forzarla a un flujo de video.",
            }
        )
        return report

    if gpu:
        report = preflight_file(
            media_path,
            ffprobe=ffprobe,
            target_fps=target_fps,
            target_width=target_width,
            target_height=target_height,
            target_codec=target_codec,
        )
        try:
            visual_analysis = analyze_visual_gpu(
                media_path,
                max_frames=gpu_max_frames,
                batch_size=gpu_batch_size,
            )
            report["analysis"] = visual_analysis
            candidate_count = visual_analysis["flash_screening"]["candidate_count"]
            if candidate_count:
                report["checks"].append(
                    {
                        "name": "Flash visual",
                        "status": "WARN",
                        "detail": f"Se detectaron {candidate_count} cambios globales de luminancia que requieren revisión.",
                    }
                )
                report["overall_status"] = "WARN"
                report["recommendations"].append(
                    "Revisar los candidatos de flash; movimiento y cortes también pueden producir esta señal."
                )
            else:
                report["checks"].append(
                    {
                        "name": "Análisis GPU",
                        "status": "PASS",
                        "detail": "NVDEC/CUDA procesó la muestra visual sin candidatos de flash global.",
                    }
                )
        except GpuUnavailable as exc:
            report["analysis"] = {
                "status": "GPU_UNAVAILABLE",
                "backend": "cuda_nvdec_cupy",
                "error": str(exc),
            }
            report["checks"].append(
                {
                    "name": "Análisis GPU",
                    "status": "WARN",
                    "detail": str(exc),
                }
            )
            report["recommendations"].append(
                "No se aplicó fallback CPU; usar un codec compatible con NVDEC o analizarlo manualmente."
            )
            report["overall_status"] = "WARN"
        return report

    if deep:
        return diagnose_file(
            media_path,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            target_fps=target_fps,
            target_width=target_width,
            target_height=target_height,
            max_samples=max_samples,
        )
    return preflight_file(
        media_path,
        ffprobe=ffprobe,
        target_fps=target_fps,
        target_width=target_width,
        target_height=target_height,
        target_codec=target_codec,
    )


def run_instar(
    root: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    target_fps: float | None = None,
    target_width: int | None = None,
    target_height: int | None = None,
    max_samples: int = 300,
    target_codec: str | None = None,
    deep: bool = False,
    sidecars_dir: str | Path | None = None,
    gpu: bool = False,
    gpu_max_frames: int = 900,
    gpu_batch_size: int = 16,
    show_profile: dict[str, Any] | None = None,
    cache_db: str | Path | None = None,
) -> dict[str, Any]:
    """Ejecuta el preflight de INSTAR sobre todos los medios de una carpeta.

    El modo normal inspecciona sólo metadata técnica. ``deep=True`` conserva
    el diagnóstico anterior, que además decodifica una muestra de luminancia.
    ``gpu=True`` usa NVDEC/CUDA y no hace fallback silencioso a CPU.
    """

    media_root = Path(root).expanduser().resolve()
    files = discover_media_files(media_root)
    if not files:
        raise ResolumeAdapterError(f"No se encontraron videos compatibles en: {media_root}")

    cache = InstarCache(cache_db) if cache_db is not None else None
    items: list[dict[str, Any]] = []
    mode = "gpu" if gpu else ("deep" if deep else "technical")
    show_profile_key = None
    if show_profile:
        show_profile_key = json.dumps(
            {
                "profile_id": show_profile.get("profile_id"),
                "target": show_profile.get("target") or show_profile.get("output"),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    cache_key = analysis_cache_key(
        mode=mode,
        target_fps=target_fps,
        target_width=target_width,
        target_height=target_height,
        target_codec=target_codec,
        max_samples=max_samples,
        gpu_max_frames=gpu_max_frames,
        gpu_batch_size=gpu_batch_size,
        show_profile_id=show_profile_key,
    )
    try:
        for media_path in files:
            try:
                fingerprint = fingerprint_file(media_path)
                report = cache.get(media_path, fingerprint, cache_key) if cache else None
                cache_hit = report is not None
                if report is None:
                    report = _analyze_file(
                        media_path,
                        ffmpeg=ffmpeg,
                        ffprobe=ffprobe,
                        target_fps=target_fps,
                        target_width=target_width,
                        target_height=target_height,
                        max_samples=max_samples,
                        target_codec=target_codec,
                        deep=deep,
                        gpu=gpu,
                        gpu_max_frames=gpu_max_frames,
                        gpu_batch_size=gpu_batch_size,
                    )
                    apply_show_rules(report, show_profile)
                    report["clip_profile"] = build_clip_profile(report, fingerprint, source_path=media_path)
                    if cache:
                        cache.put(
                            media_path,
                            fingerprint,
                            cache_key,
                            report,
                            report["clip_profile"],
                            report.get("generated_at", ""),
                        )
                else:
                    # El análisis pesado puede venir del cache, pero el perfil
                    # derivado debe reconstruirse para incorporar nuevos
                    # detectores (por ejemplo, las sugerencias de cues).
                    report["clip_profile"] = build_clip_profile(
                        report,
                        fingerprint,
                        source_path=media_path,
                    )
                    report["cache"] = {"hit": True, "path": str(cache.path)}
            except ResolumeAdapterError as exc:
                items.append(
                    {
                        "path": str(media_path),
                        "status": "FAIL",
                        "error": str(exc),
                    }
                )
                continue

            sidecar_path = None
            if sidecars_dir is not None:
                relative_parent = media_path.parent.relative_to(media_root)
                sidecar_path = write_sidecar(report, Path(sidecars_dir) / relative_parent)

            item = {
                "path": str(media_path),
                "status": report.get("overall_status", "WARN"),
                "cached": cache_hit,
                "report": report,
            }
            if sidecar_path is not None:
                item["sidecar"] = str(sidecar_path)
            items.append(item)
    finally:
        if cache is not None:
            cache.close()

    statuses = {item["status"] for item in items}
    if "FAIL" in statuses:
        overall_status = "FAIL"
    elif "WARN" in statuses:
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    return {
        "schema_version": "0.1",
        "tool": "INSTAR",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "media_root": str(media_root),
        "files_found": len(files),
        "mode": mode,
        "cache_db": str(Path(cache_db).expanduser().resolve()) if cache_db else None,
        "cache_hits": sum(1 for item in items if item.get("cached")),
        "show_profile": {
            "profile_id": (show_profile or {}).get("profile_id"),
            "name": (show_profile or {}).get("name"),
            "path": (show_profile or {}).get("path"),
            "target": (show_profile or {}).get("target") if show_profile else None,
        } if show_profile else None,
        "overall_status": overall_status,
        "items": items,
    }


def text_report(report: dict[str, Any]) -> str:
    """Convierte un informe INSTAR en una salida breve para PowerShell."""

    lines = [
        "INSTAR",
        "======",
        f"Carpeta: {report['media_root']}",
        f"Modo: {report.get('mode', 'technical')}",
        f"Estado: {report['overall_status']}",
        f"Archivos: {report['files_found']}",
        "",
        "Resultados:",
    ]
    for item in report["items"]:
        path = Path(item["path"])
        if item["status"] == "FAIL":
            lines.append(f"  [FAIL] {path.name}: {item['error']}")
            continue

        video = item["report"].get("video", {})
        codec = video.get("codec") or "desconocido"
        resolution = f"{video.get('width')} × {video.get('height')}"
        alpha = item["report"].get("alpha", {}).get("status", "n/a")
        analysis = item["report"].get("analysis", {})
        analysis_status = analysis.get("status")
        analysis_label = f", GPU {analysis_status}" if report.get("mode") == "gpu" else ""
        loop_status = ((item["report"].get("clip_profile") or {}).get("visual") or {}).get("loop", {}).get("status")
        loop_label = f", loop {loop_status}" if loop_status else ""
        cue_data = ((item["report"].get("clip_profile") or {}).get("events") or {}).get("cue_suggestions") or {}
        cue_counts: dict[str, int] = {}
        for cue in cue_data.get("cues") or []:
            role = cue.get("role")
            if role:
                cue_counts[role] = cue_counts.get(role, 0) + 1
        cue_total = sum(cue_counts.values())
        cue_label = f", cues {cue_total}" if cue_total else ""
        cache_label = ", cache" if item.get("cached") else ""
        lines.append(
            f"  [{item['status']}] {path.name}: {codec}, {resolution}, "
            f"FPS {video.get('average_fps') or 'desconocido'}, alpha {alpha}{analysis_label}{loop_label}{cue_label}{cache_label}"
        )
    return "\n".join(lines)


def write_report(report: dict[str, Any], path: str | Path) -> Path:
    """Guarda el informe JSON, creando sólo la carpeta de salida indicada."""

    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path

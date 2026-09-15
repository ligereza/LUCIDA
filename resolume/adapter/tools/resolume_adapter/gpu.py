"""Backend CUDA/NVDEC para análisis visual de INSTAR.

El módulo importa PyNvVideoCodec y CuPy de forma diferida para que el núcleo
normal de RESOLUME_ADAPTER siga funcionando en equipos sin NVIDIA/CUDA.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from .media import ResolumeAdapterError, ensure_file, parse_fraction


class GpuUnavailable(ResolumeAdapterError):
    """La ruta CUDA no está disponible para el archivo o el equipo."""


_DLL_HANDLES: list[Any] = []


def _find_cuda_path() -> Path | None:
    configured = os.environ.get("CUDA_PATH")
    if configured and Path(configured).is_dir():
        return Path(configured)

    toolkit_root = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "NVIDIA GPU Computing Toolkit" / "CUDA"
    candidates = sorted(
        (path for path in toolkit_root.glob("v*") if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_gpu_modules() -> tuple[Any, Any]:
    cuda_path = _find_cuda_path()
    if cuda_path:
        os.environ.setdefault("CUDA_PATH", str(cuda_path))
        bin_path = cuda_path / "bin"
        if hasattr(os, "add_dll_directory") and bin_path.is_dir():
            _DLL_HANDLES.append(os.add_dll_directory(str(bin_path)))

    try:
        import cupy as cp
        import PyNvVideoCodec as nvc
    except Exception as exc:  # pragma: no cover - depende del host y sus DLL
        raise GpuUnavailable(
            "No se pudo cargar la ruta CUDA/NVDEC. "
            "Verifica el driver NVIDIA, CUDA_PATH y las dependencias GPU. "
            f"Detalle: {exc}"
        ) from exc
    return cp, nvc


def _device_summary(cp: Any, device_id: int) -> dict[str, Any]:
    device = cp.cuda.Device(device_id)
    properties = cp.cuda.runtime.getDeviceProperties(device_id)
    name = properties.get("name", "GPU desconocida")
    if isinstance(name, bytes):
        name = name.decode(errors="replace")
    free_memory, total_memory = device.mem_info
    return {
        "id": device_id,
        "name": str(name),
        "free_memory_bytes": int(free_memory),
        "total_memory_bytes": int(total_memory),
    }


def _metadata_number(metadata: Any, name: str) -> float | None:
    value = getattr(metadata, name, None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return parse_fraction(value)


def _estimate_period(cp: Any, values: list[float], sample_rate: float | None) -> dict[str, Any]:
    """Estima periodicidad de luminancia mediante autocorrelación en CUDA."""

    if sample_rate is None or sample_rate <= 0 or len(values) < 8:
        return {
            "status": "unknown",
            "period_s": None,
            "confidence": 0.0,
            "reason": "No hubo suficientes muestras temporales para estimar periodicidad.",
        }

    signal = cp.asarray(values, dtype=cp.float32)
    centered = signal - cp.mean(signal)
    variance = float(cp.mean(centered * centered).get())
    if variance <= 1e-6:
        return {
            "status": "unknown",
            "period_s": None,
            "confidence": 0.0,
            "reason": "La luminancia analizada es demasiado estable.",
        }

    sample_count = int(signal.size)
    padded_size = 2 * sample_count
    spectrum = cp.fft.rfft(centered, n=padded_size)
    autocorrelation = cp.fft.irfft(cp.abs(spectrum) ** 2, n=padded_size)[:sample_count]
    normalized = autocorrelation / cp.maximum(autocorrelation[0], 1e-6)

    min_lag = max(2, int(round(sample_rate * 0.25)))
    max_lag = min(sample_count - 1, int(round(sample_rate * 10.0)))
    if max_lag <= min_lag:
        return {
            "status": "unknown",
            "period_s": None,
            "confidence": 0.0,
            "reason": "La ventana analizada es demasiado corta para buscar un loop.",
        }

    best_lag = min_lag + int(cp.argmax(normalized[min_lag : max_lag + 1]).get())
    confidence = float(normalized[best_lag].get())
    period = best_lag / sample_rate
    return {
        "status": "candidate" if confidence >= 0.35 else "weak",
        "period_s": round(period, 6),
        "confidence": round(max(0.0, min(1.0, confidence)), 6),
        "basis": "global_luminance_autocorrelation",
    }


def analyze_visual_gpu(
    path: str | Path,
    *,
    max_frames: int = 900,
    batch_size: int = 16,
    analysis_width: int = 320,
    gpu_id: int = 0,
) -> dict[str, Any]:
    """Analiza movimiento y luminancia con frames decodificados en NVDEC.

    No realiza fallback a CPU. Si el codec no puede ser decodificado por la
    ruta disponible, lanza ``GpuUnavailable`` para que el informe lo explicite.
    """

    if max_frames <= 0:
        raise ResolumeAdapterError("max_frames debe ser mayor que cero.")
    if batch_size <= 0:
        raise ResolumeAdapterError("batch_size debe ser mayor que cero.")
    if analysis_width <= 0:
        raise ResolumeAdapterError("analysis_width debe ser mayor que cero.")

    media_path = ensure_file(path)
    cp, nvc = _load_gpu_modules()
    decoder = None
    device_info = _device_summary(cp, gpu_id)
    selected_frames: list[dict[str, Any]] = []
    previous_luma = None
    frame_index = 0
    decoded_frames = 0
    analysis_shape: tuple[int, int] | None = None
    effective_sample_rate = None
    mean_luma_values: list[float] = []
    horizontal_edge_similarities: list[float] = []
    vertical_edge_similarities: list[float] = []
    horizontal_edge_energies: list[float] = []
    vertical_edge_energies: list[float] = []

    try:
        decoder = nvc.ThreadedDecoder(
            str(media_path),
            max(8, batch_size),
            gpu_id=gpu_id,
            use_device_memory=True,
            output_color_type=nvc.OutputColorType.RGBP,
        )
        metadata = decoder.get_stream_metadata()
        total_frames = _metadata_number(metadata, "num_frames")
        average_fps = _metadata_number(metadata, "average_fps")
        if total_frames is None or total_frames <= 0:
            total_frames = None
        if average_fps is None or average_fps <= 0:
            average_fps = None

        frame_stride = max(1, math.ceil(total_frames / max_frames)) if total_frames else 1
        effective_sample_rate = average_fps / frame_stride if average_fps else None
        while len(selected_frames) < max_frames:
            frames = decoder.get_batch_frames(batch_size)
            if not frames:
                break
            for decoded in frames:
                decoded_frames += 1
                if frame_index % frame_stride != 0:
                    frame_index += 1
                    continue

                frame = cp.from_dlpack(decoded)
                if getattr(frame, "ndim", 0) != 3 or frame.shape[0] < 3:
                    raise GpuUnavailable(
                        f"El decoder GPU devolvió un formato inesperado: {getattr(frame, 'shape', None)}"
                    )

                stride = max(1, math.ceil(frame.shape[2] / max(1, analysis_width)))
                sampled = frame[:, ::stride, ::stride]
                analysis_shape = (int(sampled.shape[2]), int(sampled.shape[1]))
                sampled_float = sampled[:3].astype(cp.float32)
                luma = (
                    sampled_float[0] * 0.2126
                    + sampled_float[1] * 0.7152
                    + sampled_float[2] * 0.0722
                )
                edge_width = max(1, min(16, int(luma.shape[1]) // 10))
                edge_height = max(1, min(16, int(luma.shape[0]) // 10))
                horizontal_edge_distance = float(
                    cp.mean(cp.abs(luma[:, :edge_width] - luma[:, -edge_width:])).get()
                ) / 255.0
                vertical_edge_distance = float(
                    cp.mean(cp.abs(luma[:edge_height, :] - luma[-edge_height:, :])).get()
                ) / 255.0
                horizontal_edge_energy = float(
                    cp.mean(cp.concatenate((luma[:, :edge_width], luma[:, -edge_width:]), axis=1)).get()
                ) / 255.0
                vertical_edge_energy = float(
                    cp.mean(cp.concatenate((luma[:edge_height, :], luma[-edge_height:, :]), axis=0)).get()
                ) / 255.0
                horizontal_edge_similarities.append(max(0.0, min(1.0, 1.0 - horizontal_edge_distance)))
                vertical_edge_similarities.append(max(0.0, min(1.0, 1.0 - vertical_edge_distance)))
                horizontal_edge_energies.append(max(0.0, min(1.0, horizontal_edge_energy)))
                vertical_edge_energies.append(max(0.0, min(1.0, vertical_edge_energy)))
                mean_luma = float(cp.mean(luma).get())
                min_luma = float(cp.min(luma).get())
                max_luma = float(cp.max(luma).get())
                black_ratio = float(cp.mean(luma <= 8.0).get())
                white_ratio = float(cp.mean(luma >= 247.0).get())
                mean_rgb = [float(value) for value in cp.mean(sampled_float, axis=(1, 2)).get()]
                channel_max = cp.max(sampled_float, axis=0)
                channel_min = cp.min(sampled_float, axis=0)
                saturation = float(
                    cp.mean((channel_max - channel_min) / cp.maximum(channel_max, 1.0)).get()
                )

                delta = None
                if previous_luma is not None and previous_luma.shape == luma.shape:
                    delta = float(cp.mean(cp.abs(luma - previous_luma)).get())
                previous_luma = luma.copy()
                mean_luma_values.append(mean_luma / 255.0)
                selected_frames.append(
                    {
                        "frame": frame_index,
                        "time_s": round(frame_index / average_fps, 6) if average_fps else None,
                        "mean_luma": round(mean_luma, 4),
                        "min_luma": round(min_luma, 4),
                        "max_luma": round(max_luma, 4),
                        "black_ratio": round(black_ratio, 6),
                        "white_ratio": round(white_ratio, 6),
                        "mean_rgb": [round(value, 4) for value in mean_rgb],
                        "saturation": round(saturation, 6),
                        "delta": round(delta, 4) if delta is not None else None,
                    }
                )
                frame_index += 1
                if len(selected_frames) >= max_frames:
                    break

        if len(selected_frames) < 2:
            raise GpuUnavailable("NVDEC no devolvió suficientes frames para analizar.")

        deltas = [item["delta"] for item in selected_frames if item["delta"] is not None]
        mean_luma = sum(item["mean_luma"] for item in selected_frames) / len(selected_frames)
        mean_black_ratio = sum(item["black_ratio"] for item in selected_frames) / len(selected_frames)
        mean_rgb = [
            sum(item["mean_rgb"][channel] for item in selected_frames) / len(selected_frames)
            for channel in range(3)
        ]
        mean_saturation = sum(item["saturation"] for item in selected_frames) / len(selected_frames)
        motion_mean = (sum(deltas) / len(deltas) / 255.0) if deltas else 0.0
        motion_peak = (max(deltas) / 255.0) if deltas else 0.0
        flash_threshold = 32.0
        flash_candidates = [
            {
                "frame": item["frame"],
                "time_s": item["time_s"],
                "delta": item["delta"],
            }
            for item in selected_frames
            if item["delta"] is not None and item["delta"] >= flash_threshold
        ]
        peaks = sorted(
            (item for item in selected_frames if item["delta"] is not None),
            key=lambda item: item["delta"],
            reverse=True,
        )[:10]
        periodicity = _estimate_period(cp, mean_luma_values, effective_sample_rate)
        energy = "low" if motion_mean < 0.02 else "medium" if motion_mean < 0.06 else "high"
        modulation = "strong" if energy == "low" else "moderate" if energy == "medium" else "subtle"
        spatial = {
            "edge_similarity_horizontal": round(
                sum(horizontal_edge_similarities) / len(horizontal_edge_similarities), 6
            ) if horizontal_edge_similarities else None,
            "edge_similarity_vertical": round(
                sum(vertical_edge_similarities) / len(vertical_edge_similarities), 6
            ) if vertical_edge_similarities else None,
            "edge_energy_horizontal": round(
                sum(horizontal_edge_energies) / len(horizontal_edge_energies), 6
            ) if horizontal_edge_energies else None,
            "edge_energy_vertical": round(
                sum(vertical_edge_energies) / len(vertical_edge_energies), 6
            ) if vertical_edge_energies else None,
            "edge_sample_count": len(horizontal_edge_similarities),
            "basis": "gpu_sampled_frame_edge_similarity",
            "interpretation": "Una similitud alta sugiere que el borde puede repetirse, pero necesita preview para confirmar que la unión no se percibe.",
        }

        return {
            "status": "PASS",
            "backend": "cuda_nvdec_cupy",
            "decoder": "NVDEC",
            "device": device_info,
            "decoded_frames": decoded_frames,
            "sampled_frames": len(selected_frames),
            "sample_stride": frame_stride,
            "analysis_resolution": list(analysis_shape or (0, 0)),
            "luminance": {
                "mean": round(mean_luma / 255.0, 6),
                "black_ratio": round(mean_black_ratio, 6),
            },
            "color": {
                "mean_rgb": [round(value / 255.0, 6) for value in mean_rgb],
                "mean_saturation": round(mean_saturation, 6),
            },
            "motion": {
                "mean": round(motion_mean, 6),
                "peak": round(motion_peak, 6),
            },
            "spatial": spatial,
            "visual_energy": energy,
            "reactive_recommendation": {
                "modulation": modulation,
                "reason": "La modulación debe compensar el movimiento ya presente en el clip.",
            },
            "periodicity": periodicity,
            "flash_screening": {
                "threshold_luma_delta": flash_threshold,
                "candidate_count": len(flash_candidates),
                "candidates": flash_candidates[:50],
                "risk": "medium" if flash_candidates else "low",
            },
            "visual_peaks": [
                {
                    "frame": item["frame"],
                    "time_s": item["time_s"],
                    "score": round(item["delta"] / 255.0, 6),
                }
                for item in peaks
            ],
            "samples": selected_frames,
            "limitations": [
                "Los cambios globales de luminancia pueden ser movimiento, cortes o flashes intencionales.",
                "Este análisis no confirma flickering de PWM, refresco, cableado ni procesador LED.",
                "El riesgo de flash es un cribado del archivo y requiere validación visual.",
            ],
        }
    except GpuUnavailable:
        raise
    except Exception as exc:  # pragma: no cover - depende del codec y del driver
        raise GpuUnavailable(
            f"El archivo no pudo procesarse con NVDEC/CUDA: {exc}"
        ) from exc
    finally:
        if decoder is not None:
            del decoder
        try:
            cp.cuda.Stream.null.synchronize()
            cp.get_default_memory_pool().free_all_blocks()
            cp.get_default_pinned_memory_pool().free_all_blocks()
        except Exception:
            pass

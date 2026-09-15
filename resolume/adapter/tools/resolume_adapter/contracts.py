"""Contratos y perfiles reutilizables de INSTAR.

El perfil de clip es la salida estable que pueden consumir NAYADE e IMAGO.
Contiene hechos técnicos, observaciones, eventos y riesgos sin acoplarlos a un
decodificador concreto.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ANALYZER_VERSION = "0.4"
CUE_SUGGESTION_VERSION = "0.1"
FINGERPRINT_CHUNK_SIZE = 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint_file(path: str | Path) -> dict[str, Any]:
    """Crea una huella rápida sin leer completo un archivo de video.

    Se combinan tamaño, mtime y los extremos del archivo. Esto invalida la
    caché cuando cambia el medio sin imponer el coste de hashear varios GB.
    """

    media_path = Path(path).expanduser().resolve()
    stat = media_path.stat()
    digest = hashlib.sha256()
    digest.update(str(stat.st_size).encode("ascii"))
    digest.update(str(stat.st_mtime_ns).encode("ascii"))
    with media_path.open("rb") as handle:
        first = handle.read(FINGERPRINT_CHUNK_SIZE)
        digest.update(first)
        if stat.st_size > FINGERPRINT_CHUNK_SIZE:
            handle.seek(max(0, stat.st_size - FINGERPRINT_CHUNK_SIZE))
            digest.update(handle.read(FINGERPRINT_CHUNK_SIZE))
    return {
        "algorithm": "sha256-head-tail",
        "value": digest.hexdigest(),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _mean(items: list[dict[str, Any]], key: str, default: float = 0.0) -> float:
    values = [float(item[key]) for item in items if item.get(key) is not None]
    return sum(values) / len(values) if values else default


def _mean_rgb(items: list[dict[str, Any]]) -> list[float]:
    values = [item.get("mean_rgb") for item in items if isinstance(item.get("mean_rgb"), list)]
    if not values:
        return [0.0, 0.0, 0.0]
    return [sum(float(value[index]) for value in values) / len(values) for index in range(3)]


def _distance_rgb(left: list[float], right: list[float]) -> float:
    if len(left) < 3 or len(right) < 3:
        return 1.0
    return min(1.0, math.sqrt(sum((float(left[i]) - float(right[i])) ** 2 for i in range(3))) / 441.6729559)


def _quantile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * max(0.0, min(1.0, fraction))
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower]) * (1.0 - weight) + float(ordered[upper]) * weight


def _local_peak_indexes(values: list[float], threshold: float, min_distance: int) -> list[int]:
    candidates = [
        index
        for index, value in enumerate(values)
        if value >= threshold
        and (index == 0 or value >= values[index - 1])
        and (index == len(values) - 1 or value >= values[index + 1])
    ]
    selected: list[int] = []
    for index in sorted(candidates, key=lambda item: values[item], reverse=True):
        if all(abs(index - other) >= min_distance for other in selected):
            selected.append(index)
    return sorted(selected)


def _cluster_times(times: list[float], max_gap_s: float) -> list[list[float]]:
    clusters: list[list[float]] = []
    for timestamp in sorted(times):
        if not clusters or timestamp - clusters[-1][-1] > max_gap_s:
            clusters.append([timestamp])
        else:
            clusters[-1].append(timestamp)
    return clusters


def _cue_confidence(value: float, baseline: float, strong: float) -> float:
    if strong <= baseline:
        return 0.0
    return round(max(0.0, min(1.0, (value - baseline) / (strong - baseline))), 6)


def suggest_semantic_cues(
    analysis: dict[str, Any],
    *,
    duration_seconds: float | None = None,
    max_per_role: int = 3,
) -> dict[str, Any]:
    """Sugiere puntos funcionales a partir de la serie temporal visual.

    Las sugerencias son deliberadamente conservadoras: describen evidencia
    visual y no se convierten todavía en acciones de Resolume. Los cues de
    impacto y estrobo requieren revisión humana; un cue de loop incluye un
    rango porque un único PositionN no puede representar sus dos extremos.
    """

    samples = [item for item in (analysis.get("samples") or []) if item.get("time_s") is not None]
    if len(samples) < 8:
        return {
            "version": CUE_SUGGESTION_VERSION,
            "status": "NOT_AVAILABLE",
            "basis": "sampled_visual_series",
            "cues": [],
            "limitations": [
                "No hubo suficientes muestras visuales para proponer cues semánticos.",
            ],
        }

    samples = sorted(samples, key=lambda item: float(item["time_s"]))
    times = [float(item["time_s"]) for item in samples]
    if duration_seconds is None or duration_seconds <= 0:
        duration_seconds = max(times)
    duration_seconds = max(float(duration_seconds), times[-1])

    luminance = [max(0.0, min(1.0, float(item.get("mean_luma", 0.0)) / 255.0)) for item in samples]
    motion = [max(0.0, min(1.0, float(item.get("delta", 0.0) or 0.0) / 255.0)) for item in samples]
    contrast = [
        max(
            0.0,
            min(
                1.0,
                (float(item.get("max_luma", 0.0)) - float(item.get("min_luma", 0.0))) / 255.0,
            ),
        )
        for item in samples
    ]
    luma_jump = [0.0] + [abs(luminance[index] - luminance[index - 1]) for index in range(1, len(samples))]
    # El contraste describe la riqueza de un frame, no necesariamente un
    # cambio temporal. Solo movimiento y salto de luminancia disparan un cue.
    change_signal = [
        0.75 * motion[index] + 0.25 * luma_jump[index]
        for index in range(len(samples))
    ]
    activity_floor = _quantile(change_signal, 0.50)
    activity_strong = _quantile(change_signal, 0.85)
    time_distance_s = max(0.5, min(8.0, duration_seconds * 0.04))
    sample_steps = [
        right - left for left, right in zip(times, times[1:]) if right > left
    ]
    average_step = (
        sum(sample_steps) / len(sample_steps)
        if sample_steps
        else max(duration_seconds / max(1, len(samples) - 1), 1e-6)
    )
    min_distance = max(1, int(round(time_distance_s / max(average_step, 1e-6))))
    flash_times = [
        float(item["time_s"])
        for item in ((analysis.get("flash_screening") or {}).get("candidates") or [])
        if item.get("time_s") is not None
    ]

    cues: list[dict[str, Any]] = []
    # Evita inventar puntos en loops o clips casi estáticos. La diferencia
    # entre los cuantiles exige que haya eventos destacados, no solo actividad
    # constante en todo el archivo.
    has_distinct_activity = (
        activity_strong >= 0.06
        and (
            activity_strong - activity_floor >= 0.025
            or max(luma_jump, default=0.0) >= 0.12
        )
    )
    impact_indexes = _local_peak_indexes(
        change_signal,
        max(activity_floor + 0.04, _quantile(change_signal, 0.80), 0.06),
        min_distance,
    )
    impact_indexes = [index for index in impact_indexes if has_distinct_activity]
    impact_indexes = sorted(
        impact_indexes,
        key=lambda index: change_signal[index],
        reverse=True,
    )[:max_per_role]
    impact_count = 0
    for index in impact_indexes:
        timestamp = times[index]
        near_flash = any(abs(timestamp - flash_time) <= max(0.25, time_distance_s / 2.0) for flash_time in flash_times)
        impact_count += 1
        cues.append(
            {
                "id": f"change-impact-{impact_count:02d}",
                "role": "change",
                "style": "impact",
                "position_ms": round(timestamp * 1000.0, 6),
                "position_s": round(timestamp, 6),
                "confidence": _cue_confidence(change_signal[index], activity_floor, activity_strong),
                "evidence": {
                    "change_signal": round(change_signal[index], 6),
                    "motion": round(motion[index], 6),
                    "luma_jump": round(luma_jump[index], 6),
                    "contrast": round(contrast[index], 6),
                },
                "strobe_candidate": near_flash,
                "requires_review": True,
            }
        )

    quiet_signal = [
        1.0 - (0.65 * motion[index] + 0.35 * luma_jump[index])
        for index in range(len(samples))
    ]
    quiet_indexes = _local_peak_indexes(
        quiet_signal,
        max(_quantile(quiet_signal, 0.80), 0.90),
        min_distance,
    )
    quiet_indexes = [
        index
        for index in quiet_indexes
        if has_distinct_activity
        if times[index] > max(0.25, duration_seconds * 0.03)
        and times[index] < duration_seconds - max(0.25, duration_seconds * 0.03)
        and all(abs(times[index] - times[impact_index]) >= time_distance_s for impact_index in impact_indexes)
    ]
    quiet_indexes = sorted(quiet_indexes, key=lambda index: quiet_signal[index], reverse=True)[:max_per_role]
    clean_count = 0
    for index in quiet_indexes:
        clean_count += 1
        cues.append(
            {
                "id": f"change-clean-{clean_count:02d}",
                "role": "change",
                "style": "clean",
                "position_ms": round(times[index] * 1000.0, 6),
                "position_s": round(times[index], 6),
                "confidence": round(max(0.0, min(1.0, quiet_signal[index])), 6),
                "evidence": {
                    "quiet_signal": round(quiet_signal[index], 6),
                    "motion": round(motion[index], 6),
                    "luma_jump": round(luma_jump[index], 6),
                },
                "strobe_candidate": False,
                "requires_review": False,
            }
        )

    for cluster in _cluster_times(flash_times, max_gap_s=0.5):
        if len(cluster) < 4:
            continue
        start_s, end_s = cluster[0], cluster[-1]
        if end_s - start_s < 0.1:
            continue
        candidate_samples = []
        for flash_time in cluster:
            nearest = min(samples, key=lambda item: abs(float(item["time_s"]) - flash_time))
            if abs(float(nearest["time_s"]) - flash_time) <= max(average_step * 1.5, 0.08):
                candidate_samples.append(nearest)
        candidate_lumas = [
            max(0.0, min(1.0, float(item.get("mean_luma", 0.0)) / 255.0))
            for item in candidate_samples
        ]
        directions = []
        for left, right in zip(candidate_lumas, candidate_lumas[1:]):
            difference = right - left
            if abs(difference) >= 0.08:
                directions.append(1 if difference > 0 else -1)
        alternations = sum(
            left != right for left, right in zip(directions, directions[1:])
        )
        luma_span = max(candidate_lumas, default=0.0) - min(candidate_lumas, default=0.0)
        if len(candidate_samples) < 4 or alternations < 2 or luma_span < 0.25:
            continue
        alternation_confidence = min(1.0, alternations / 6.0)
        luma_confidence = min(1.0, luma_span / 0.75)
        count_confidence = min(1.0, len(cluster) / 12.0)
        strobe_confidence = round(
            0.4 * alternation_confidence
            + 0.35 * luma_confidence
            + 0.25 * count_confidence,
            6,
        )
        cues.append(
            {
                "id": f"strobe-window-{len([cue for cue in cues if cue['role'] == 'strobe_window']) + 1:02d}",
                "role": "strobe_window",
                "position_ms": round(start_s * 1000.0, 6),
                "position_s": round(start_s, 6),
                "end_position_ms": round(end_s * 1000.0, 6),
                "end_position_s": round(end_s, 6),
                "confidence": strobe_confidence,
                "evidence": {
                    "flash_candidate_count": len(cluster),
                    "window_s": round(end_s - start_s, 6),
                    "luma_span": round(luma_span, 6),
                    "luma_alternations": alternations,
                },
                "requires_review": True,
                "safety_note": "No activar estrobo automáticamente; validar visualmente y considerar fotosensibilidad.",
            }
        )

    periodicity = analysis.get("periodicity") or {}
    period_s = periodicity.get("period_s")
    periodicity_confidence = float(periodicity.get("confidence") or 0.0)
    if period_s is not None:
        try:
            period_s = float(period_s)
        except (TypeError, ValueError):
            period_s = None
    periodicity_status = str(periodicity.get("status") or "")
    periodicity_is_strong = periodicity_status == "candidate" and periodicity_confidence >= 0.5
    if period_s is not None and periodicity_is_strong and 0.5 <= period_s < duration_seconds * 0.8:
        lag = max(1, int(round(period_s / max(average_step, 1e-6))))
        feature_vectors = [
            [luminance[index], motion[index], contrast[index]]
            for index in range(len(samples))
        ]
        loop_candidates: list[tuple[float, int, int, float]] = []
        for start in range(0, len(feature_vectors) - (3 * lag) + 1):
            end = start + lag
            second_end = end + lag
            third_end = second_end + lag
            first = feature_vectors[start:end]
            second = feature_vectors[end:second_end]
            third = feature_vectors[second_end:third_end]
            variation = sum(
                sum(abs(left[channel] - right[channel]) for channel in range(3)) / 3.0
                for left, right in zip(first, first[1:])
            ) / max(1, len(first) - 1)
            if variation < 0.05:
                continue
            distances_first_second = [
                sum(abs(left[channel] - right[channel]) for channel in range(3)) / 3.0
                for left, right in zip(first, second)
            ]
            distances_second_third = [
                sum(abs(left[channel] - right[channel]) for channel in range(3)) / 3.0
                for left, right in zip(second, third)
            ]
            similarity = min(
                1.0 - sum(distances_first_second) / max(1, len(distances_first_second)),
                1.0 - sum(distances_second_third) / max(1, len(distances_second_third)),
            )
            similarity = max(0.0, min(1.0, similarity))
            if similarity >= 0.80:
                loop_candidates.append((similarity, start, end, variation))
        loop_candidates.sort(reverse=True)
        selected_loops: list[tuple[float, int, int, float]] = []
        for candidate in loop_candidates:
            if all(abs(times[candidate[1]] - times[item[1]]) >= time_distance_s for item in selected_loops):
                selected_loops.append(candidate)
            if len(selected_loops) >= max_per_role:
                break
        for similarity, start, end, variation in selected_loops:
            confidence = round(max(0.0, min(1.0, 0.55 * similarity + 0.45 * periodicity_confidence)), 6)
            if confidence < 0.45:
                continue
            cues.append(
                {
                    "id": f"loop-{len([cue for cue in cues if cue['role'] == 'loop']) + 1:02d}",
                    "role": "loop",
                    "in_position_ms": round(times[start] * 1000.0, 6),
                    "in_position_s": round(times[start], 6),
                    "out_position_ms": round(times[end] * 1000.0, 6),
                    "out_position_s": round(times[end], 6),
                    "position_ms": round(times[start] * 1000.0, 6),
                    "position_s": round(times[start], 6),
                    "confidence": confidence,
                    "evidence": {
                        "period_s": round(period_s, 6),
                        "seam_similarity": round(similarity, 6),
                        "cycle_variation": round(variation, 6),
                        "periodicity_confidence": round(periodicity_confidence, 6),
                    },
                    "requires_review": True,
                }
            )

    cues.sort(key=lambda cue: (float(cue.get("position_s", cue.get("in_position_s", 0.0))), cue["role"]))
    role_counters: dict[str, int] = {}
    for cue in cues:
        role = cue["role"]
        if role == "change":
            style = cue.get("style", "candidate")
            counter_key = f"{role}-{style}"
            role_counters[counter_key] = role_counters.get(counter_key, 0) + 1
            cue["id"] = f"change-{style}-{role_counters[counter_key]:02d}"
        elif role == "strobe_window":
            role_counters[role] = role_counters.get(role, 0) + 1
            cue["id"] = f"strobe-window-{role_counters[role]:02d}"
        elif role == "loop":
            role_counters[role] = role_counters.get(role, 0) + 1
            cue["id"] = f"loop-{role_counters[role]:02d}"
    return {
        "version": CUE_SUGGESTION_VERSION,
        "status": "REVIEW" if cues else "NO_CANDIDATES",
        "basis": "sampled_luminance_motion_contrast_periodicity_flash_screening",
        "sample_count": len(samples),
        "duration_seconds": round(duration_seconds, 6),
        "cues": cues,
        "limitations": [
            "Las posiciones son candidatos heurísticos y deben revisarse visualmente.",
            "Un cue no activa por sí mismo un efecto ni define un loop completo dentro de Resolume.",
        ],
    }


def derive_loop_profile(analysis: dict[str, Any]) -> dict[str, Any]:
    """Estima continuidad entre el comienzo y el final de una muestra.

    Es una señal de selección, no una prueba de loop perfecto. La decisión
    usa luminancia, RGB y movimiento para evitar confiar en un solo frame.
    """

    samples = analysis.get("samples") or []
    if len(samples) < 8:
        return {
            "status": "unknown",
            "confidence": 0.0,
            "seam_luma_delta": None,
            "seam_rgb_distance": None,
            "reason": "No hubo suficientes muestras visuales para estimar continuidad.",
        }

    window = max(2, min(30, len(samples) // 10))
    start = samples[:window]
    end = samples[-window:]
    start_luma = _mean(start, "mean_luma") / 255.0
    end_luma = _mean(end, "mean_luma") / 255.0
    seam_luma_delta = abs(end_luma - start_luma)
    seam_rgb_distance = _distance_rgb(
        _mean_rgb(start),
        _mean_rgb(end),
    )
    start_motion = _mean(start, "delta") / 255.0
    end_motion = _mean(end, "delta") / 255.0
    motion_delta = min(1.0, abs(end_motion - start_motion))
    continuity = max(
        0.0,
        min(1.0, 1.0 - (0.45 * min(1.0, seam_luma_delta * 4.0) + 0.4 * seam_rgb_distance + 0.15 * motion_delta)),
    )
    if continuity >= 0.78:
        status = "candidate"
    elif continuity >= 0.55:
        status = "review"
    else:
        status = "weak"
    return {
        "status": status,
        "confidence": round(continuity, 6),
        "seam_luma_delta": round(seam_luma_delta, 6),
        "seam_rgb_distance": round(seam_rgb_distance, 6),
        "motion_delta": round(motion_delta, 6),
        "sample_window": window,
        "basis": "sampled_luminance_rgb_motion_continuity",
    }


def _behavior_signal(
    score: float | None,
    *,
    confidence: float,
    basis: list[str],
    status: str,
    requires_preview: bool = True,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "score": round(score, 6) if score is not None else None,
        "confidence": round(max(0.0, min(1.0, confidence)), 6),
        "status": status,
        "requires_preview": requires_preview,
        "basis": basis,
        **({"reason": reason} if reason else {}),
    }


def derive_behavior_profile(report: dict[str, Any], *, source_path: str | Path | None = None) -> dict[str, Any]:
    """Describe qué transformaciones conviene probar en NAYADE.

    La primera versión separa evidencia espacial real de inferencias débiles
    basadas en metadata, nombre y análisis temporal. Nunca autoriza una
    transformación automáticamente: sirve para ordenar el soundcheck.
    """

    input_path = Path(str(source_path or report.get("input", "media")))
    video = report.get("video") or {}
    analysis = report.get("analysis") or {}
    loop = derive_loop_profile(analysis)
    loop_confidence = float(loop.get("confidence") or 0.0)
    motion_mean = float((analysis.get("motion") or {}).get("mean") or 0.0)
    tokens = set(re.findall(r"[a-z0-9]+", input_path.stem.casefold()))
    abstract_tokens = {
        "abstract", "abstracto", "fluid", "liquid", "particles", "particle",
        "noise", "fractal", "generative", "generator", "waves", "wave",
        "smoke", "cloud", "texture", "pattern", "tunnel", "loop", "visual",
    }
    protected_tokens = {
        "logo", "logos", "text", "texto", "title", "titulo", "name", "nombre",
        "sponsor", "brand", "marca", "letter", "letras", "face", "rostro",
    }
    geometry_tokens = {
        "circle", "circulo", "round", "ring", "anillo", "orb",
        "square", "cuadrado", "grid", "cuadricula", "checker", "geometric",
        "geometrico", "geometry", "geometria",
    }
    is_abstract = bool(tokens & abstract_tokens)
    is_protected = bool(tokens & protected_tokens)
    geometry_hints = sorted(tokens & geometry_tokens)
    geometry_sensitive_hint = bool(geometry_hints)
    width = float(video.get("width") or 0)
    height = float(video.get("height") or 0)
    aspect = width / height if width > 0 and height > 0 else None
    source_orientation = (
        "vertical" if aspect is not None and aspect < 0.8
        else "horizontal" if aspect is not None and aspect > 1.25
        else "square" if aspect is not None
        else "unknown"
    )

    spatial = analysis.get("spatial") or {}
    horizontal_edge_similarity = spatial.get("edge_similarity_horizontal")
    vertical_edge_similarity = spatial.get("edge_similarity_vertical")
    spatial_basis = ["gpu_spatial_edge_analysis"] if spatial else []
    temporal_basis = ["loop_profile"] if loop.get("status") != "unknown" else []
    semantic_basis = ["filename_semantics"] if (is_abstract or is_protected) else []

    def repeat_signal(value: Any, axis: str) -> dict[str, Any]:
        if value is not None:
            edge_similarity = max(0.0, min(1.0, float(value)))
            edge_energy = spatial.get(f"edge_energy_{axis}")
            if edge_energy is None:
                score = edge_similarity
                confidence = 0.55
                status = "review"
                reason = f"comparación de bordes {axis} disponible, pero falta actividad de borde para confirmarla"
            else:
                edge_energy = max(0.0, min(1.0, float(edge_energy)))
                activity_factor = min(1.0, edge_energy / 0.12)
                score = 0.5 + 0.5 * edge_similarity * activity_factor
                confidence = 0.35 + 0.45 * activity_factor
                status = "candidate" if score >= 0.75 and edge_energy >= 0.08 else "review" if score >= 0.55 else "weak"
                reason = (
                    f"comparación de bordes {axis} y actividad de borde medidas en el análisis espacial GPU"
                    if edge_energy >= 0.08
                    else f"los bordes {axis} tienen poca actividad; la similitud puede deberse a negro uniforme"
                )
            return _behavior_signal(
                score,
                confidence=confidence,
                basis=spatial_basis,
                status=status,
                reason=reason,
            )
        if is_abstract and loop_confidence >= 0.55:
            score = min(0.82, 0.45 + 0.25 * loop_confidence + 0.12 * min(1.0, motion_mean / 0.06))
            return _behavior_signal(
                score,
                confidence=0.35,
                basis=temporal_basis + semantic_basis,
                status="inferred",
                reason="inferido por abstracción nominal, movimiento y continuidad temporal; necesita preview",
            )
        return _behavior_signal(
            None,
            confidence=0.0,
            basis=[],
            status="not_available",
            reason="faltan muestras espaciales para comparar los bordes del patrón",
        )

    repeat_horizontal = repeat_signal(horizontal_edge_similarity, "horizontal")
    repeat_vertical = repeat_signal(vertical_edge_similarity, "vertical")

    def marquee_signal(repeat_item: dict[str, Any], axis: str) -> dict[str, Any]:
        repeat_score = repeat_item.get("score")
        repeat_status = repeat_item.get("status")
        if repeat_score is None or repeat_status == "not_available":
            return _behavior_signal(
                None,
                confidence=0.0,
                basis=repeat_item.get("basis", []),
                status="not_available",
                reason=f"no hay evidencia espacial suficiente para una marquesina {axis}",
            )
        score = min(1.0, 0.7 * float(repeat_score) + 0.3 * min(1.0, motion_mean / 0.06))
        status = "inferred" if repeat_status in {"candidate", "inferred"} else "review"
        return _behavior_signal(
            score,
            confidence=min(0.55, float(repeat_item.get("confidence") or 0.0)),
            basis=repeat_item.get("basis", []) + (["temporal_motion"] if motion_mean > 0 else []),
            status=status,
            reason=(
                "la continuidad del borde y el movimiento sugieren una marquesina; probar con wrap"
                if status == "inferred"
                else f"la evidencia de repetición {axis} es débil; probar solo manualmente"
            ),
        )

    marquee_horizontal = marquee_signal(repeat_horizontal, "horizontal")
    marquee_vertical = marquee_signal(repeat_vertical, "vertical")

    flip_status = "review" if is_protected else "inferred"
    flip_basis = semantic_basis or ["no_content_semantics_detected"]
    rotation_status = "candidate" if aspect is not None and 0.85 <= aspect <= 1.18 else "review"
    return {
        "version": "0.1",
        "status": "inferred" if analysis else "metadata_only",
        "source_orientation": source_orientation,
        "pattern": {
            "horizontal": repeat_horizontal,
            "vertical": repeat_vertical,
        },
        "marquee": {
            "horizontal": marquee_horizontal,
            "vertical": marquee_vertical,
        },
        "transformations": {
            "flip_horizontal": _behavior_signal(
                0.2 if is_protected else 0.65,
                confidence=0.3,
                basis=flip_basis,
                status=flip_status,
                reason="texto, logos o nombres pueden quedar invertidos" if is_protected else "no se detectaron tokens protegidos; validar orientación en preview",
            ),
            "flip_vertical": _behavior_signal(
                0.2 if is_protected else 0.6,
                confidence=0.3,
                basis=flip_basis,
                status=flip_status,
                reason="texto, logos o nombres pueden quedar invertidos" if is_protected else "no se detectaron tokens protegidos; validar orientación en preview",
            ),
            "rotate_180": _behavior_signal(
                0.25 if is_protected else 0.55,
                confidence=0.25,
                basis=flip_basis,
                status="review" if is_protected else "inferred",
                reason="la rotación puede alterar la lectura aunque la proporción no cambie",
            ),
            "rotate_90": _behavior_signal(
                0.8 if rotation_status == "candidate" else 0.25,
                confidence=0.35,
                basis=["source_aspect_ratio"],
                status=rotation_status,
                reason="rotar 90° cambia la orientación de una visual no cuadrada",
            ),
        },
        "content_flags": {
            "abstract_filename_hint": is_abstract,
            "protected_filename_hint": is_protected,
            "geometry_sensitive": True if geometry_sensitive_hint or is_protected else None,
            "geometry_tokens": geometry_hints,
        },
        "geometry_test": {
            "required": geometry_sensitive_hint or is_protected,
            "reason": (
                "el nombre sugiere una forma geométrica o contenido protegido"
                if geometry_sensitive_hint or is_protected
                else "no hay evidencia suficiente en metadata; usar la prueba si la forma parece sensible"
            ),
        },
        "limitations": [
            "Los scores inferidos por nombre o temporalidad solo ordenan pruebas; no prueban que los bordes sean repetibles.",
            "Para scores espaciales se necesita ejecutar el análisis GPU con muestras de frames.",
            "La geometría sensible no se confirma solo por metadata: una tarjeta de círculo/cuadrado sigue siendo necesaria.",
        ],
    }


def _temporal_series(analysis: dict[str, Any]) -> dict[str, Any] | None:
    samples = analysis.get("samples") or []
    if not samples:
        return None
    return {
        "timestamps_s": [item.get("time_s") for item in samples],
        "luminance": [round(float(item.get("mean_luma", 0.0)) / 255.0, 6) for item in samples],
        "motion": [
            round(float(item.get("delta", 0.0) or 0.0) / 255.0, 6)
            for item in samples
        ],
        "saturation": [round(float(item.get("saturation", 0.0)), 6) for item in samples],
        "sample_count": len(samples),
        "sample_rate_hz": analysis.get("sample_rate_hz"),
        "resolution": "per_sample",
    }


def build_clip_profile(
    report: dict[str, Any],
    fingerprint: dict[str, Any] | None = None,
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Construye el contrato de clip a partir del informe actual de INSTAR."""

    input_path = Path(str(source_path or report.get("input", "media"))).expanduser().resolve()
    video = report.get("video") or {}
    analysis = report.get("analysis") or {}
    flash = analysis.get("flash_screening") or {}
    profile = {
        "schema_version": "0.1",
        "profile_type": "ClipProfile",
        "profile_id": (fingerprint or {}).get("value") or input_path.name,
        "generated_at": utc_now(),
        "analyzer": {
            "name": "INSTAR",
            "version": ANALYZER_VERSION,
            "mode": report.get("mode") or analysis.get("backend") or "technical",
            "backend": analysis.get("backend") or "ffprobe",
        },
        "source": {
            "path": str(input_path),
            "filename": input_path.name,
            "extension": input_path.suffix.lower(),
            "fingerprint": fingerprint,
        },
        "technical": {
            "container": report.get("container"),
            "video": video,
            "audio": report.get("audio"),
            "alpha": report.get("alpha"),
        },
        "visual": {
            "status": analysis.get("status", "not_run"),
            "resolution": analysis.get("analysis_resolution"),
            "luminance": analysis.get("luminance"),
            "color": analysis.get("color"),
            "motion": analysis.get("motion"),
            "visual_energy": analysis.get("visual_energy"),
            "periodicity": analysis.get("periodicity"),
            "loop": derive_loop_profile(analysis),
            "behavior": derive_behavior_profile(report, source_path=input_path),
        },
        "events": {
            "flash_candidates": flash.get("candidates", [])[:50],
            "visual_peaks": (analysis.get("visual_peaks") or [])[:50],
            "cue_suggestions": suggest_semantic_cues(
                analysis,
                duration_seconds=video.get("duration_seconds"),
            ),
        },
        "temporal_series": _temporal_series(analysis),
        "compatibility": {
            "status": report.get("overall_status"),
            "checks": report.get("checks", []),
            "recommendations": report.get("recommendations", []),
        },
        "limitations": report.get("limitations", []),
    }
    return profile


def analysis_cache_key(
    *,
    mode: str,
    target_fps: float | None,
    target_width: int | None,
    target_height: int | None,
    target_codec: str | None,
    max_samples: int,
    gpu_max_frames: int,
    gpu_batch_size: int,
    show_profile_id: str | None,
) -> str:
    payload = {
        "mode": mode,
        "target_fps": target_fps,
        "target_width": target_width,
        "target_height": target_height,
        "target_codec": target_codec,
        "max_samples": max_samples,
        "gpu_max_frames": gpu_max_frames,
        "gpu_batch_size": gpu_batch_size,
        "show_profile_id": show_profile_id,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))

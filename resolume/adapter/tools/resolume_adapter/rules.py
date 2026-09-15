"""Reglas de compatibilidad entre un clip y un perfil de show."""

from __future__ import annotations

from typing import Any


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def apply_show_rules(report: dict[str, Any], show_profile: dict[str, Any] | None) -> dict[str, Any]:
    """Añade reglas de destino sin modificar el medio ni la configuración externa."""

    if not show_profile:
        return report
    target = show_profile.get("target") or show_profile.get("output") or show_profile
    video = report.get("video") or {}
    alpha = report.get("alpha") or {}
    checks = report.setdefault("checks", [])
    recommendations = report.setdefault("recommendations", [])

    required_alpha = target.get("requires_alpha")
    if required_alpha is True:
        if alpha.get("status") == "present":
            checks.append(_check("Alpha del show", "PASS", "El perfil requiere alpha y el clip declara un canal compatible."))
        else:
            checks.append(_check("Alpha del show", "WARN", "El perfil requiere alpha, pero el clip no lo confirma."))
            recommendations.append("Probar el clip sobre fondo contrastante y preparar una versión con alpha real si corresponde.")

    allowed_codecs = target.get("allowed_codecs")
    codec = str(video.get("codec") or "").lower()
    if isinstance(allowed_codecs, list) and allowed_codecs:
        normalized = {str(value).lower() for value in allowed_codecs}
        if codec in normalized:
            checks.append(_check("Codec del show", "PASS", f"{codec or 'desconocido'} está dentro del perfil."))
        else:
            checks.append(_check("Codec del show", "WARN", f"{codec or 'desconocido'} no está dentro de {sorted(normalized)}."))
            recommendations.append("Preparar el clip en uno de los codecs permitidos por el perfil del show.")

    target_range = target.get("color_range")
    actual_range = video.get("color_range")
    if target_range and actual_range and str(target_range).lower() != str(actual_range).lower():
        checks.append(_check("Rango de color del show", "WARN", f"El clip declara {actual_range}; el perfil espera {target_range}."))
        recommendations.append("Confirmar el rango en la composición, la GPU y el procesador antes de aplicar una transformación.")
    elif target_range and not actual_range:
        checks.append(_check("Rango de color del show", "WARN", f"El clip no declara rango; el perfil espera {target_range}."))
        recommendations.append("Confirmar el rango real antes de usar el clip en el show.")

    report["show_profile"] = {
        "profile_id": show_profile.get("profile_id"),
        "name": show_profile.get("name"),
        "path": show_profile.get("path"),
        "target": target,
    }
    report["overall_status"] = "WARN" if any(check.get("status") == "WARN" for check in checks) else report.get("overall_status", "PASS")
    return report

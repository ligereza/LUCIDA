"""Carga y normaliza perfiles de destino para INSTAR."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .media import ResolumeAdapterError


def load_show_profile(path: str | Path) -> dict[str, Any]:
    profile_path = Path(path).expanduser().resolve()
    if not profile_path.is_file():
        raise ResolumeAdapterError(f"No se encontró el perfil de show: {profile_path}")
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResolumeAdapterError(f"El perfil de show no contiene JSON válido: {profile_path}") from exc
    if not isinstance(profile, dict):
        raise ResolumeAdapterError("El perfil de show debe ser un objeto JSON.")
    _validate_profile(profile)
    profile.setdefault("profile_id", profile_path.stem)
    profile.setdefault("name", profile_path.stem)
    profile["path"] = str(profile_path)
    return profile


def _validate_profile(profile: dict[str, Any]) -> None:
    """Valida el contrato si jsonschema está instalado."""

    try:
        import jsonschema
    except ImportError:  # pragma: no cover - depende del entorno
        _validate_minimal_profile(profile)
        return
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "show-profile.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(profile, schema)
    except FileNotFoundError as exc:
        raise ResolumeAdapterError(f"No se encontró el esquema de perfil: {schema_path}") from exc
    except jsonschema.ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path) or "raíz"
        raise ResolumeAdapterError(f"Perfil de show inválido en {location}: {exc.message}") from exc


def _validate_minimal_profile(profile: dict[str, Any]) -> None:
    """Validador pequeño para que INSTAR siga funcionando sin extras Python."""

    for key in ("schema_version", "profile_id", "name", "target"):
        if key not in profile:
            raise ResolumeAdapterError(f"Perfil de show inválido: falta el campo {key!r}.")
    if profile.get("schema_version") != "0.1":
        raise ResolumeAdapterError("Perfil de show inválido: schema_version debe ser '0.1'.")
    if not isinstance(profile.get("target"), dict):
        raise ResolumeAdapterError("Perfil de show inválido: target debe ser un objeto JSON.")


def target_values(profile: dict[str, Any]) -> dict[str, Any]:
    target = profile.get("target") or profile.get("output") or profile
    resolution = target.get("resolution")
    width = target.get("width")
    height = target.get("height")
    if isinstance(resolution, str) and "x" in resolution.lower():
        width_text, height_text = resolution.lower().split("x", 1)
        try:
            width, height = int(width_text), int(height_text)
        except ValueError:
            pass
    return {
        "fps": _number(target.get("fps") or target.get("refresh_fps")),
        "width": _integer(width),
        "height": _integer(height),
        "codec": target.get("codec"),
        "requires_alpha": target.get("requires_alpha"),
        "color_range": target.get("color_range"),
        "profile_id": profile.get("profile_id"),
    }


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None

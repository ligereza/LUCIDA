"""Read-only Windows output, adapter, and EDID probe for NAYADE."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from typing import Any, Mapping

from .contracts import utc_now
from .media import ResolumeAdapterError


PROBE_SCHEMA_VERSION = "0.1"
_POWERSHELL_QUERY = r'''
$adapters = @(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,VideoModeDescription)
$monitors = @(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID | Select-Object ManufacturerName,UserFriendlyName,ProductCodeID,Active)
[pscustomobject]@{ adapters = $adapters; monitors = $monitors } | ConvertTo-Json -Depth 4 -Compress
'''


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decode_u16(value: Any) -> str | None:
    if not isinstance(value, list):
        return _text(value)
    characters: list[str] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item == 0:
            break
        if 0 <= item <= 0x10FFFF:
            characters.append(chr(item))
    return "".join(characters).strip() or None


def _resolution(adapter: Mapping[str, Any]) -> str | None:
    width, height = adapter.get("CurrentHorizontalResolution"), adapter.get("CurrentVerticalResolution")
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        return f"{width}x{height}"
    return None


def _refresh(adapter: Mapping[str, Any]) -> int | float | None:
    value = adapter.get("CurrentRefreshRate")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return int(value) if float(value).is_integer() else float(value)


def _powershell_path() -> str:
    for name in ("pwsh", "powershell"):
        path = shutil.which(name)
        if path:
            return path
    raise ResolumeAdapterError("No se encontró PowerShell para consultar la salida Windows.")


def _run_query(powershell: str, timeout_seconds: float) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _POWERSHELL_QUERY],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ResolumeAdapterError(f"La sonda de salida excedió {timeout_seconds:g} segundos y fue detenida.") from exc
    except OSError as exc:
        raise ResolumeAdapterError(f"No se pudo ejecutar la sonda PowerShell: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "sin detalle").strip().splitlines()[-1]
        raise ResolumeAdapterError(f"La consulta WMI de salida falló: {detail}")
    try:
        value = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ResolumeAdapterError("La consulta WMI no devolvió JSON válido.") from exc
    if not isinstance(value, dict):
        raise ResolumeAdapterError("La consulta WMI no devolvió un objeto JSON.")
    return value


def probe_windows_output(*, timeout_seconds: float = 10.0) -> dict[str, Any]:
    """Capture current WMI adapter/display metadata without changing the host."""

    if platform.system().casefold() != "windows":
        raise ResolumeAdapterError("La sonda WMI de salida sólo está disponible en Windows.")
    if timeout_seconds <= 0:
        raise ResolumeAdapterError("timeout_seconds debe ser mayor que cero.")
    raw = _run_query(_powershell_path(), timeout_seconds)
    adapters: list[dict[str, Any]] = []
    for index, item in enumerate(_list(raw.get("adapters"))):
        if not isinstance(item, Mapping):
            continue
        adapter: dict[str, Any] = {"adapter_id": f"adapter-{index + 1:03d}"}
        for source_key, target_key in (("Name", "name"), ("DriverVersion", "driver_version"), ("VideoModeDescription", "video_mode_description")):
            value = _text(item.get(source_key))
            if value:
                adapter[target_key] = value
        current_resolution = _resolution(item)
        if current_resolution:
            adapter["current_resolution"] = current_resolution
        refresh_hz = _refresh(item)
        if refresh_hz is not None:
            adapter["current_refresh_hz"] = refresh_hz
        adapters.append(adapter)

    monitors: list[dict[str, Any]] = []
    for index, item in enumerate(_list(raw.get("monitors"))):
        if not isinstance(item, Mapping):
            continue
        monitor: dict[str, Any] = {"display_id": f"display-{index + 1:03d}"}
        for source_key, target_key in (("ManufacturerName", "manufacturer"), ("UserFriendlyName", "name"), ("ProductCodeID", "product_code")):
            value = _decode_u16(item.get(source_key))
            if value:
                monitor[target_key] = value
        active = item.get("Active")
        if isinstance(active, bool):
            monitor["active"] = active
        monitors.append(monitor)

    status = "PASS" if adapters or monitors else "REVIEW"
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "probe_type": "NayadeOutputProbe",
        "captured_at": utc_now(),
        "platform": "windows",
        "backend": "powershell_wmi",
        "status": status,
        "adapters": adapters,
        "displays": monitors,
        "output_signal": {
            "resolution": adapters[0].get("current_resolution") if adapters else None,
            "refresh_hz": adapters[0].get("current_refresh_hz") if adapters else None,
            "color_range": "unknown",
            "color_space": "unknown",
        },
        "limitations": [
            "WMI puede describir el modo actual del adaptador, no necesariamente el modo efectivo recibido por el procesador LED.",
            "El rango RGB Full/Limited de NVIDIA no se confirma de forma universal mediante WMI y queda unknown.",
            "EDID identifica el display cuando está expuesto; no prueba el routing interno de la consola o del procesador.",
        ],
        "safety": {
            "read_only": True,
            "commands_sent": False,
            "writes_attempted": False,
            "external_side_effects": False,
        },
    }


def output_probe_text_report(report: Mapping[str, Any]) -> str:
    """Render a compact output probe summary."""

    signal = report.get("output_signal") or {}
    lines = [
        "RESOLUME_ADAPTER NAYADE - OUTPUT PROBE",
        "============================",
        f"Estado: {report.get('status')}",
        f"Resolucion actual: {signal.get('resolution') or 'unknown'}",
        f"Refresh actual: {signal.get('refresh_hz') or 'unknown'} Hz",
        f"Rango RGB: {signal.get('color_range') or 'unknown'}",
        f"Adaptadores: {len(report.get('adapters') or [])}",
        f"Displays EDID: {len(report.get('displays') or [])}",
        "Modo: SOLO LECTURA; no se modifico la salida.",
    ]
    return "\n".join(lines)


__all__ = ["PROBE_SCHEMA_VERSION", "output_probe_text_report", "probe_windows_output"]

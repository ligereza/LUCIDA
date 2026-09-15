"""Diagnostico portable y de solo lectura para RESOLUME_ADAPTER."""

from __future__ import annotations

import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_MODULES = {
    "numpy": "numpy",
    "Pillow": "PIL",
    "PyAV": "av",
    "PySceneDetect": "scenedetect",
    "jsonschema": "jsonschema",
    "pyserial": "serial",
}
OPTIONAL_GPU_MODULES = {
    "PyNvVideoCodec": "PyNvVideoCodec",
    "CuPy CUDA 12": "cupy",
}


def _check(name: str, status: str, detail: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "status": status, "detail": detail}
    result.update(extra)
    return result


def _python_check() -> dict[str, Any]:
    version = platform.python_version()
    status = "PASS" if sys.version_info >= (3, 11) else "FAIL"
    return _check("Python", status, f"Python {version}; se requiere 3.11 o superior.", version=version)


def _module_check(name: str, module_name: str, *, optional: bool = False) -> dict[str, Any]:
    available = importlib.util.find_spec(module_name) is not None
    if available:
        return _check(name, "PASS", f"Módulo disponible: {module_name}.", module=module_name)
    return _check(
        name,
        "WARN" if optional else "FAIL",
        f"No se encontró el módulo {module_name}.",
        module=module_name,
        optional=optional,
    )


def _command_check(name: str, command: str) -> dict[str, Any]:
    executable = shutil.which(command)
    if executable is None:
        return _check(
            name,
            "WARN",
            f"{command} no está en PATH; los comandos de media que lo requieren no podrán ejecutarse.",
            command=command,
            available=False,
        )
    try:
        completed = subprocess.run(
            [executable, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _check(
            name,
            "WARN",
            f"{command} fue encontrado, pero no respondió a la comprobación: {exc}.",
            command=command,
            available=False,
        )
    if completed.returncode != 0:
        return _check(
            name,
            "WARN",
            f"{command} existe, pero devolvió código {completed.returncode}.",
            command=command,
            available=False,
        )
    first_line = next(
        (line.strip() for line in (completed.stdout + completed.stderr).splitlines() if line.strip()),
        "versión no reportada",
    )
    return _check(name, "PASS", first_line[:180], command=command, available=True)


def _repository_check(repository_root: Path) -> dict[str, Any]:
    expected = ["tools/resolume_adapter_cli.py", "requirements.txt", "adapters/vj", "schemas"]
    missing = [item for item in expected if not (repository_root / item).exists()]
    if missing:
        return _check(
            "Repositorio RESOLUME_ADAPTER",
            "FAIL",
            "Faltan componentes esperados del repositorio.",
            missing=missing,
        )
    return _check("Repositorio RESOLUME_ADAPTER", "PASS", "Estructura portable mínima encontrada.", root=str(repository_root))


def run_doctor(repository_root: str | Path | None = None) -> dict[str, Any]:
    """Comprueba el entorno sin escribir archivos ni controlar dispositivos."""

    root = Path(repository_root or Path(__file__).resolve().parents[2]).expanduser().resolve()
    checks = [_repository_check(root), _python_check()]
    checks.extend(_module_check(name, module) for name, module in BASE_MODULES.items())
    checks.extend(_module_check(name, module, optional=True) for name, module in OPTIONAL_GPU_MODULES.items())
    checks.extend(
        [
            _command_check("FFmpeg", "ffmpeg"),
            _command_check("FFprobe", "ffprobe"),
        ]
    )
    statuses = {check["status"] for check in checks}
    overall_status = "FAIL" if "FAIL" in statuses else ("WARN" if "WARN" in statuses else "PASS")
    recommendations: list[str] = []
    if any(check["name"] == "FFmpeg" and check["status"] != "PASS" for check in checks):
        recommendations.append("Instala FFmpeg y FFprobe y agrega su carpeta bin al PATH para analizar o convertir media.")
    if any(check["name"] in OPTIONAL_GPU_MODULES and check["status"] != "PASS" for check in checks):
        recommendations.append("El análisis GPU es opcional; usa Bootstrap-RESOLUME_ADAPTER.ps1 -Gpu sólo si el equipo tiene CUDA/NVIDIA funcional.")
    if overall_status == "FAIL":
        recommendations.append("Ejecuta Bootstrap-RESOLUME_ADAPTER.ps1 -Dev para reparar el entorno Python antes de usar la CLI.")
    return {
        "schema_version": "0.1",
        "tool": "RESOLUME_ADAPTER Doctor",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository_root": str(root),
        "overall_status": overall_status,
        "read_only": True,
        "checks": checks,
        "recommendations": recommendations,
        "safety": {
            "files_written": False,
            "hardware_opened": False,
            "hardware_changed": False,
            "resolume_controlled": False,
        },
    }


def doctor_text_report(report: dict[str, Any]) -> str:
    """Convierte el diagnóstico en una salida breve para PowerShell."""

    lines = [
        "RESOLUME_ADAPTER DOCTOR",
        "=============",
        f"Estado: {report['overall_status']}",
        f"Repositorio: {report['repository_root']}",
        "",
        "Comprobaciones:",
    ]
    for check in report.get("checks") or []:
        lines.append(f"  [{check['status']}] {check['name']}: {check['detail']}")
    if report.get("recommendations"):
        lines.extend(["", "Recomendaciones:"])
        lines.extend(f"  - {item}" for item in report["recommendations"])
    lines.append("\nModo: solo lectura; no se escribieron archivos ni se controló hardware.")
    return "\n".join(lines)


def write_doctor_report(report: dict[str, Any], path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


__all__ = ["doctor_text_report", "run_doctor", "write_doctor_report"]

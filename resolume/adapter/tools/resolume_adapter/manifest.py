"""Manifiestos portables de assets producidos por INSTAR."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_manifest(report: dict[str, Any]) -> dict[str, Any]:
    root = Path(str(report.get("media_root", "media"))).expanduser().resolve()
    assets: list[dict[str, Any]] = []
    for item in report.get("items", []):
        path = Path(str(item.get("path", ""))).expanduser()
        try:
            relative_path = str(path.resolve().relative_to(root))
        except ValueError:
            relative_path = path.name
        profile = (item.get("report") or {}).get("clip_profile") or {}
        assets.append(
            {
                "path": relative_path,
                "absolute_path": str(path.resolve()),
                "profile_id": profile.get("profile_id"),
                "status": item.get("status", "UNKNOWN"),
                "cached": bool(item.get("cached")),
                "profile": profile,
            }
        )
    return {
        "schema_version": "0.1",
        "manifest_type": "AssetManifest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "source_report": report.get("generated_at"),
        "assets": assets,
    }


def write_manifest(report: dict[str, Any], path: str | Path) -> Path:
    manifest_path = Path(path).expanduser().resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(build_manifest(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path

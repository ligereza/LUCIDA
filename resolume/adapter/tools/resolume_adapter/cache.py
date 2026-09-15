"""Caché local SQLite para evitar repetir análisis de INSTAR."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class InstarCache:
    """Almacena reportes por archivo, huella y configuración de análisis."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS clip_cache (
                media_path TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                analysis_key TEXT NOT NULL,
                report_json TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (media_path, analysis_key)
            )
            """
        )
        self.connection.commit()

    def get(
        self,
        media_path: str | Path,
        fingerprint: dict[str, Any],
        analysis_key: str,
    ) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT fingerprint, report_json FROM clip_cache WHERE media_path = ? AND analysis_key = ?",
            (str(Path(media_path).expanduser().resolve()), analysis_key),
        ).fetchone()
        if row is None or row[0] != fingerprint.get("value"):
            return None
        try:
            report = json.loads(row[1])
        except json.JSONDecodeError:
            return None
        report["cache"] = {"hit": True, "path": str(self.path)}
        return report

    def put(
        self,
        media_path: str | Path,
        fingerprint: dict[str, Any],
        analysis_key: str,
        report: dict[str, Any],
        profile: dict[str, Any],
        updated_at: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO clip_cache(media_path, fingerprint, analysis_key, report_json, profile_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(media_path, analysis_key) DO UPDATE SET
              fingerprint = excluded.fingerprint,
              report_json = excluded.report_json,
              profile_json = excluded.profile_json,
              updated_at = excluded.updated_at
            """,
            (
                str(Path(media_path).expanduser().resolve()),
                fingerprint.get("value", ""),
                analysis_key,
                json.dumps(report, ensure_ascii=False, separators=(",", ":")),
                json.dumps(profile, ensure_ascii=False, separators=(",", ":")),
                updated_at,
            ),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "InstarCache":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

"""Reporte HTML autónomo para revisar un catálogo INSTAR."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _text(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _status_class(status: str) -> str:
    return {"PASS": "pass", "WARN": "warn", "FAIL": "fail"}.get(status, "info")


def render_html(report: dict[str, Any]) -> str:
    rows: list[str] = []
    for item in report.get("items", []):
        if item.get("status") == "FAIL":
            rows.append(
                f'<tr><td><span class="badge fail">FAIL</span></td><td>{html.escape(Path(item.get("path", "")).name)}</td>'
                f'<td colspan="6">{html.escape(str(item.get("error", "Error desconocido")))}</td></tr>'
            )
            continue
        detail = item.get("report") or {}
        video = detail.get("video") or {}
        visual = (detail.get("clip_profile") or {}).get("visual") or {}
        events = (detail.get("clip_profile") or {}).get("events") or {}
        cue_suggestions = events.get("cue_suggestions") or {}
        cue_counts: dict[str, int] = {}
        for cue in cue_suggestions.get("cues") or []:
            role = cue.get("role")
            if role:
                cue_counts[role] = cue_counts.get(role, 0) + 1
        cue_label = " · ".join(
            f"{label} {cue_counts[role]}"
            for role, label in (("change", "cambio"), ("loop", "loop"), ("strobe_window", "strobo"))
            if cue_counts.get(role)
        ) or "—"
        loop = visual.get("loop") or {}
        resolution = f"{video.get('width')} × {video.get('height')}"
        rows.append(
            "<tr>"
            f'<td><span class="badge {_status_class(str(item.get("status")))}">{html.escape(str(item.get("status")))}</span></td>'
            f'<td title="{html.escape(str(item.get("path", "")))}">{html.escape(Path(item.get("path", "")).name)}</td>'
            f'<td>{html.escape(_text(video.get("codec")))}</td>'
            f'<td>{html.escape(resolution)}</td>'
            f'<td>{html.escape(_text(video.get("average_fps")))}</td>'
            f'<td>{html.escape(_text(visual.get("visual_energy")))}</td>'
            f'<td>{html.escape(_text(loop.get("status")))}</td>'
            f'<td>{html.escape(cue_label)}</td>'
            "</tr>"
        )
    target = report.get("show_profile") or {}
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>INSTAR — catálogo de media</title>
<style>
:root {{ color-scheme: dark; font-family: Segoe UI, system-ui, sans-serif; background:#101217; color:#edf1f7; }}
body {{ margin:0; padding:32px; }} main {{ max-width:1400px; margin:auto; }}
h1 {{ margin:0 0 8px; }} .muted {{ color:#9aa5b5; }}
.summary {{ display:flex; gap:12px; flex-wrap:wrap; margin:22px 0; }}
.card {{ background:#1a1e27; border:1px solid #2b3342; border-radius:10px; padding:14px 18px; min-width:130px; }}
.card strong {{ display:block; font-size:24px; margin-top:3px; }}
table {{ width:100%; border-collapse:collapse; background:#171a21; border:1px solid #2b3342; }}
th,td {{ padding:11px 12px; border-bottom:1px solid #2b3342; text-align:left; vertical-align:top; }} th {{ color:#aeb9c9; font-size:12px; text-transform:uppercase; }}
.badge {{ display:inline-block; border-radius:999px; padding:3px 8px; font-size:11px; font-weight:700; }}
.pass {{ background:#164d37; color:#9bf1c9; }} .warn {{ background:#614616; color:#ffd88a; }} .fail {{ background:#61272a; color:#ffabb0; }} .info {{ background:#29384f; color:#b7d4ff; }}
code {{ color:#b9d6ff; }}
</style></head><body><main>
<h1>INSTAR — catálogo de media</h1>
<div class="muted">Generado: {html.escape(_text(report.get("generated_at")))} · Carpeta: <code>{html.escape(_text(report.get("media_root")))}</code></div>
<div class="summary">
<div class="card">Estado<strong>{html.escape(_text(report.get("overall_status")))}</strong></div>
<div class="card">Archivos<strong>{html.escape(_text(report.get("files_found")))}</strong></div>
<div class="card">Modo<strong>{html.escape(_text(report.get("mode")))}</strong></div>
<div class="card">Perfil<strong>{html.escape(_text(target.get("name") or "sin perfil"))}</strong></div>
</div>
<table><thead><tr><th>Estado</th><th>Archivo</th><th>Codec</th><th>Resolución</th><th>FPS</th><th>Energía</th><th>Loop</th><th>Cues sugeridos</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
</main></body></html>"""


def write_html_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_html(report), encoding="utf-8")
    return report_path

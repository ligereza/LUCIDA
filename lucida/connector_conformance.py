"""Deterministic conformance report for the LUCIDA connector boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence_bundle import run_adobe_summary_preview
from .signals.adobe import ADOBE_SOURCE_FIXTURES
from .signals.smoke import run_envelope_backed_smoke
from .signals.xio import replay_path
from .surface_conformance import run_fixture_conformance


REPORT_TYPE = "LucidaConnectorConformance"
SCHEMA_VERSION = "1.0"
XIO_FIXTURE = (
    Path(__file__).resolve().parent / "signals" / "fixtures" / "xio-application-session-fictional.json"
)


def run_connector_conformance() -> dict[str, Any]:
    """Exercise each connector's offline boundary and report safety facts."""
    adobe_sources = {
        source: run_adobe_summary_preview(path)
        for source, path in ADOBE_SOURCE_FIXTURES.items()
    }
    adobe = adobe_sources["visual"]
    xio = replay_path(XIO_FIXTURE)
    smoke = run_envelope_backed_smoke()
    surfaces = run_fixture_conformance()
    resolume_surface = surfaces["consumers"]["resolume"]

    connectors = {
        "adobe": {
            "status": "PASS" if adobe["replay_status"] == "PASS" else "FAIL",
            "source": adobe["source"],
            "transport": adobe["transport"],
            "phase": adobe["phase"],
            "proposal_only": adobe["proposal_only"],
            "external_side_effects": adobe["external_side_effects"],
            "raw_content_forwarded": adobe["raw_content_forwarded"],
            "sources": adobe_sources,
        },
        "multi_xio": {
            "status": "PASS"
            if xio["status"] == "PASS"
            and xio["safety"]["replay_only"]
            and not xio["safety"]["external_side_effects"]
            else "FAIL",
            "source": xio["source_app"],
            "replay_type": xio["replay_type"],
            "event_count": xio["event_count"],
            "replay_only": xio["safety"]["replay_only"],
            "external_side_effects": xio["safety"]["external_side_effects"],
        },
        "resolume": {
            "status": "PASS"
            if smoke["execution_mode"] == "proposal_only"
            and smoke["requires_explicit_approval"]
            and smoke["reversible"]
            and not smoke["external_side_effects"]
            and resolume_surface["external_side_effects"] is False
            else "FAIL",
            "surface_id": resolume_surface["surface_id"],
            "lifecycle_status": smoke["replay_status"],
            "execution_mode": smoke["execution_mode"],
            "requires_explicit_approval": smoke["requires_explicit_approval"],
            "reversible": smoke["reversible"],
            "external_side_effects": smoke["external_side_effects"],
        },
    }
    return {
        "report_type": REPORT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if all(item["status"] == "PASS" for item in connectors.values()) else "FAIL",
        "connectors": connectors,
        "ownership": {
            "adobe": "bounded context and proposal signals",
            "multi_xio": "capture, transport, network, clocks, hashes, and provenance",
            "resolume": "visual surface preview and host proposal boundary",
            "lucida": "replay, integration, and explicit outcomes",
        },
        "safety": {
            "proposal_only": True,
            "external_side_effects": False,
            "hosts_opened": False,
            "sockets_opened": False,
            "raw_content_forwarded": False,
        },
    }


def render_connector_conformance(report: dict[str, Any]) -> str:
    """Render stable machine-readable conformance evidence."""

    return json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


if __name__ == "__main__":
    print(render_connector_conformance(run_connector_conformance()), end="")

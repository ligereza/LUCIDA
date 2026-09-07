"""Offline conformance check for generic surface projection consumers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from .surface_projection import SurfaceProjectionV1


CONFORMANCE_REPORT_TYPE = "SurfaceProjectionConformance"
CONFORMANCE_SCHEMA_VERSION = "1.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESOLUME_FIXTURE = (
    REPOSITORY_ROOT
    / "tests"
    / "lucida"
    / "fixtures"
    / "resolume-surface-projection-v1.json"
)
DEFAULT_GENERIC_FIXTURE = (
    REPOSITORY_ROOT
    / "tests"
    / "lucida"
    / "fixtures"
    / "fictional-surface-projection-v1.json"
)


def validate_consumer_projection(value: Mapping[str, Any]) -> SurfaceProjectionV1:
    """Validate one consumer projection using only the shared contract."""
    return SurfaceProjectionV1.from_dict(value)


def run_conformance(
    projections: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate labeled projections without applying domain-specific rules."""
    if not isinstance(projections, Mapping) or not projections:
        raise ValueError("surface projection conformance needs labeled projections.")
    consumers: dict[str, dict[str, Any]] = {}
    for name in sorted(projections):
        if not isinstance(name, str) or not name.isascii() or not name:
            raise ValueError("surface projection consumer name is invalid.")
        projection = validate_consumer_projection(projections[name])
        consumers[name] = {
            "host_id": projection.host_id,
            "surface_id": projection.surface_id,
            "status": projection.status,
            "proposal_id": projection.proposal.proposal_id,
            "execution_mode": projection.proposal.execution_mode,
            "requires_explicit_approval": projection.proposal.requires_explicit_approval,
            "reversible": projection.proposal.reversible,
            "proposal_only": projection.safety.proposal_only,
            "external_side_effects": projection.safety.external_side_effects,
        }
    return {
        "report_type": CONFORMANCE_REPORT_TYPE,
        "schema_version": CONFORMANCE_SCHEMA_VERSION,
        "consumer_count": len(consumers),
        "consumers": consumers,
        "unknown_optional_fields_ignored": True,
        "external_side_effects": False,
    }


def run_fixture_conformance(
    resolume_fixture: str | Path = DEFAULT_RESOLUME_FIXTURE,
    generic_fixture: str | Path = DEFAULT_GENERIC_FIXTURE,
) -> dict[str, Any]:
    """Run the deterministic two-consumer fixture conformance check."""
    return run_conformance(
        {
            "fictional": _load_json(generic_fixture),
            "resolume": _load_json(resolume_fixture),
        }
    )


def render_conformance(report: Mapping[str, Any]) -> str:
    """Render stable machine-readable conformance evidence."""
    return json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def _load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("surface projection fixture must be an object.")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate generic surface projection consumer fixtures."
    )
    parser.add_argument("--resolume-fixture", type=Path, default=DEFAULT_RESOLUME_FIXTURE)
    parser.add_argument("--generic-fixture", type=Path, default=DEFAULT_GENERIC_FIXTURE)
    args = parser.parse_args(argv)
    try:
        print(
            render_conformance(
                run_fixture_conformance(args.resolume_fixture, args.generic_fixture)
            ),
            end="",
        )
    except (OSError, ValueError) as exc:
        print(f"surface_conformance_error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

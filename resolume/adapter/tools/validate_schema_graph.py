"""Validate the local JSON Schema registry and optional instances."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class SchemaGraphError(ValueError):
    """Raised when the local schema registry is incomplete or invalid."""


def _load_schema(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaGraphError(f"Cannot read schema: {path}") from exc
    if not isinstance(value, dict):
        raise SchemaGraphError(f"Schema must be an object: {path}")
    return value


def _walk_references(value: Any) -> Iterator[str]:
    if isinstance(value, Mapping):
        reference = value.get("$ref")
        if isinstance(reference, str):
            yield reference
        for item in value.values():
            yield from _walk_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_references(item)


def load_registry(root: Path) -> tuple[Registry, dict[str, Path], dict[Path, dict[str, Any]]]:
    """Load every local schema by its stable `$id` and check its syntax."""

    schema_paths = sorted(root.rglob("*.schema.json"))
    if not schema_paths:
        raise SchemaGraphError(f"No schemas found below: {root}")
    by_id: dict[str, Path] = {}
    schemas: dict[Path, dict[str, Any]] = {}
    resources: list[tuple[str, Resource[Any]]] = []
    for path in schema_paths:
        schema = _load_schema(path)
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            raise SchemaGraphError(f"Schema has no stable $id: {path}")
        if schema_id in by_id:
            raise SchemaGraphError(f"Duplicate schema $id {schema_id}: {path}")
        Draft202012Validator.check_schema(schema)
        by_id[schema_id] = path
        schemas[path] = schema
        resources.append((schema_id, Resource.from_contents(schema)))
    return Registry().with_resources(resources), by_id, schemas


def validate_references(schemas: Mapping[Path, Mapping[str, Any]], schema_ids: Mapping[str, Path]) -> int:
    references = sorted({reference for schema in schemas.values() for reference in _walk_references(schema)})
    missing = [
        reference
        for reference in references
        if not reference.startswith("#")
        and not reference.startswith("http://")
        and not reference.startswith("https://")
        and reference not in schema_ids
    ]
    if missing:
        raise SchemaGraphError(f"Unregistered local schema refs: {missing}")
    return len(references)


def validate_instance(schema_path: Path, instance_path: Path, registry: Registry) -> None:
    schema = _load_schema(schema_path)
    try:
        instance = json.loads(instance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaGraphError(f"Cannot read instance: {instance_path}") from exc
    errors = sorted(
        Draft202012Validator(schema, registry=registry).iter_errors(instance),
        key=lambda error: list(error.path),
    )
    if errors:
        details = "; ".join(f"{list(error.path)}: {error.message}" for error in errors)
        raise SchemaGraphError(f"Instance does not validate: {details}")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_schema_graph",
        description="Validate local JSON Schema IDs, references, and an optional instance.",
    )
    parser.add_argument("--root", help="Repository root; defaults to the parent of tools.")
    parser.add_argument("--schema", help="Schema path for --instance validation.")
    parser.add_argument("--instance", help="JSON instance to validate against --schema.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    if bool(args.schema) != bool(args.instance):
        print("--schema and --instance must be provided together.", file=sys.stderr)
        return 2
    try:
        registry, schema_ids, schemas = load_registry(root)
        reference_count = validate_references(schemas, schema_ids)
        print(f"schemas: {len(schemas)}")
        print(f"registered_ids: {len(schema_ids)}")
        print(f"references: {reference_count}")
        if args.schema and args.instance:
            validate_instance(_resolve(root, args.schema), _resolve(root, args.instance), registry)
            print("instance: valid")
    except (OSError, SchemaGraphError, ValueError) as exc:
        print(f"schema validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline guard for ASCII-only technical zones."""

from __future__ import annotations

from pathlib import Path


DEFAULT_ROOTS = (
    "lucida",
    "adapters/vj",
    "tests/lucida",
    "tests/vj",
)
TECHNICAL_SUFFIXES = {".py", ".json"}


def find_non_ascii(
    repository_root: str | Path,
    roots: tuple[str, ...] = DEFAULT_ROOTS,
) -> tuple[str, ...]:
    """Return technical files containing non-ASCII bytes or path segments."""

    root = Path(repository_root).resolve()
    issues: list[str] = []
    for relative_root in roots:
        scan_root = root / relative_root
        if not scan_root.exists():
            continue
        for path in sorted(scan_root.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            relative_path = path.relative_to(root)
            display_path = relative_path.as_posix()
            if any(any(ord(char) > 127 for char in part) for part in relative_path.parts):
                issues.append(f"{display_path}: non-ASCII path segment")
                continue
            if path.suffix.lower() not in TECHNICAL_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                issues.append(f"{display_path}: cannot decode as UTF-8 ({type(exc).__name__})")
                continue
            if any(ord(char) > 127 for char in text):
                issues.append(f"{display_path}: non-ASCII technical content")
    return tuple(issues)

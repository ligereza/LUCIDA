from pathlib import Path

from lucida.ascii_guard import find_non_ascii


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_technical_zones_are_ascii_clean():
    assert find_non_ascii(REPOSITORY_ROOT) == ()


def test_guard_detects_non_ascii_python_and_json(tmp_path):
    technical_root = tmp_path / "technical"
    technical_root.mkdir()
    (technical_root / "bad.py").write_text('value = "\N{LATIN SMALL LETTER N WITH TILDE}"\n', encoding="utf-8")
    (technical_root / "bad.json").write_text('{"key": "\N{LATIN SMALL LETTER O WITH ACUTE}"}', encoding="utf-8")

    issues = find_non_ascii(tmp_path, roots=("technical",))

    assert issues == (
        "technical/bad.json: non-ASCII technical content",
        "technical/bad.py: non-ASCII technical content",
    )

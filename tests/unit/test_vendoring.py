"""Vendored official files: byte for byte and traceable to a release (ADR-008)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENDORED = ("src/haflinger/artefacts", "tests/data")
PROVENANCE_ROWS = ("Source", "Release", "Commit", "Licence")


def sources() -> list[Path]:
    return sorted(
        path
        for base in VENDORED
        if (ROOT / base).is_dir()
        for path in (ROOT / base).iterdir()
        if path.is_dir() and path.name != "__pycache__"
    )


def test_vendored_files_are_not_normalised_by_git() -> None:
    lines = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    for base in VENDORED:
        assert f"{base}/** -text" in lines


def test_every_source_has_its_provenance() -> None:
    for source in sources():
        readme = source / "README.md"
        assert readme.is_file(), f"{source.relative_to(ROOT)} has no README.md"
        text = readme.read_text(encoding="utf-8")
        for row in PROVENANCE_ROWS:
            assert re.search(rf"^\| \*\*{row}\*\* \| \S", text, re.MULTILINE), (
                f"{readme.relative_to(ROOT)} has no {row} row"
            )

"""The indexes of the ADRs and the specs match the documents they list (ADR index, specs index)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADRS = ROOT / "docs/arc42/adr"
SPECS = ROOT / "docs/specs"


def meta(path: Path) -> dict[str, str]:
    """A document's meta table: `| **Status** | Accepted |` and so on."""
    text = path.read_text(encoding="utf-8")
    return dict(re.findall(r"^\| \*\*(\w+)\*\* \| (.+?) \|$", text, re.M))


def rows(index: Path) -> list[list[str]]:
    """The index's rows that link a document, as their cells."""
    lines = index.read_text(encoding="utf-8").splitlines()
    return [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in lines
        if re.match(r"\| \[(ADR|REQ)-\d{3}\]", line)
    ]


def test_the_adr_index_lists_every_adr_with_its_title_status_and_last_change() -> None:
    listed: dict[str, list[str]] = {}
    for link, title, status, changed in rows(ADRS / "README.md"):
        match = re.fullmatch(r"\[(ADR-\d{3})\]\((.+\.md)\)", link)
        assert match, link
        listed[match[2]] = [match[1], title, status, changed]
    assert sorted(listed) == sorted(path.name for path in ADRS.glob("ADR-*.md"))
    for name, (number, title, status, changed) in listed.items():
        heading = (ADRS / name).read_text(encoding="utf-8").splitlines()[0]
        assert heading == f"# {number}: {title}", name
        assert [status, changed] == [meta(ADRS / name)[key] for key in ("Status", "Date")], name


def test_the_specs_index_lists_every_spec_with_its_status() -> None:
    listed: dict[str, str] = {}
    for link, _, status in rows(SPECS / "README.md"):
        match = re.fullmatch(r"\[REQ-\d{3}\]\((.+\.md)\)", link)
        assert match, link
        listed[match[1]] = status
    specs = [path.name for path in SPECS.glob("req-*.md") if not path.name.endswith(".history.md")]
    assert sorted(listed) == sorted(specs)
    for name, status in listed.items():
        assert status == meta(SPECS / name)["Status"], name

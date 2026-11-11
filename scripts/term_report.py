"""The business terms that invoices carry and the model doesn't hold yet, by how many files carry
each: the order in which ADR-007 grows the model by what incoming invoices commonly carry.

Each PDF and XML file below a directory goes through KoSIT's reading stylesheet, which names
every business term it finds; the model's terms are those REQ-001-PRS-F001 lists. XRechnung's
extension (`BT-DEX-…`, `BG-DEX-…`) is left out with the terms within its groups, such as a
sub-invoice line's: ADR-007 doesn't model extensions. Prints a Markdown table with one column per
directory: the KoSIT test suite, then each directory given, such as a clone of the ZUGFeRD corpus
(development guide).

    uv run python scripts/term_report.py [<directory>...]
"""

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree.ElementTree import Element

from corpus_report import LARGE, invoice_files

from haflinger import InvoiceReadError, _kosit
from haflinger._saxon import TransformError, WorkerError
from haflinger._xml import XML_WHITESPACE, local_name, parse
from haflinger.pdf import extract_xml

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "tests/data/kosit-testsuite"
REQ_001 = ROOT / "docs/specs/req-001-core.md"
_ID = f"{{{_kosit.XR}}}id"
_TERM = re.compile(r"\b(?:BT|BG)-[0-9]+\b")
# A business term of EN 16931 itself, not of an extension.
_EN16931_TERM = re.compile(r"BT-[0-9]+")
# XRechnung's extension: a term of its own or a group, such as a sub-invoice line.
_EXTENSION = "-DEX-"


@dataclass
class Column:
    """One directory's files: how many, which weren't read and why, and how many carry each
    business term."""

    name: str
    files: int = 0
    not_read: Counter[str] = field(default_factory=Counter[str])
    carried: Counter[str] = field(default_factory=Counter[str])


def held() -> set[str]:
    """The business terms and groups REQ-001-PRS-F001's table names."""
    text = REQ_001.read_text(encoding="utf-8")
    section = text.split("#### REQ-001-PRS-F001")[1].split("\n#### ")[0]
    return set(_TERM.findall(section))


def terms(semantic: Element, names: dict[str, tuple[str, str]]) -> set[str]:
    """The business terms in KoSIT's semantic XML that hold a value; `names` gains each one's
    name and the group it lies in."""
    found: set[str] = set()

    def visit(parent: Element, group: str) -> None:
        for element in parent:
            term = element.get(_ID) or ""
            if _EXTENSION in term:
                continue
            if _EN16931_TERM.fullmatch(term) and "".join(element.itertext()).strip(XML_WHITESPACE):
                found.add(term)
                names.setdefault(term, (local_name(element.tag).replace("_", " "), group))
            visit(element, term)

    visit(semantic, "")
    return found


def count(directory: Path, names: dict[str, tuple[str, str]]) -> Column:
    column = Column(directory.resolve().name)
    for path in invoice_files(directory):
        column.files += 1
        try:
            data = path.read_bytes()
            xml = extract_xml(data) if path.suffix.lower() == ".pdf" else data
            if len(xml) > LARGE:
                column.not_read["above 5 MB"] += 1
                continue
            semantic, _ = _kosit.semantic_xml(xml)
        except OSError:
            column.not_read["unreadable"] += 1
            continue
        except WorkerError, TransformError:
            # The stylesheet's time limit, a crash: no verdict on the file.
            column.not_read["failed in KoSIT's stylesheet"] += 1
            continue
        except InvoiceReadError:
            column.not_read["refused"] += 1
            continue
        column.carried.update(terms(parse(semantic), names))
    return column


def main(arguments: list[str]) -> int:
    directories = [SUITE, *map(Path, arguments)]
    missing_directories = [str(d) for d in directories if not d.is_dir()]
    if missing_directories:
        print(__doc__, file=sys.stderr)
        for directory in missing_directories:
            print(f"{directory} is not a directory", file=sys.stderr)
        return 2
    names: dict[str, tuple[str, str]] = {}
    columns = [count(directory, names) for directory in directories]
    missing = {term for column in columns for term in column.carried} - held()
    for column in columns:
        read = column.files - sum(column.not_read.values())
        reasons = "".join(f", {n} {why}" for why, n in sorted(column.not_read.items()))
        print(f"{column.name}: {column.files} files, {read} read{reasons}")
    print()
    print("| Term | Name | Group | " + " | ".join(column.name for column in columns) + " |")
    print("| :- | :- | :- | " + " | ".join("-:" for _ in columns) + " |")
    order = sorted(
        missing,
        key=lambda term: (-sum(c.carried[term] for c in columns), int(term.split("-")[1])),
    )
    for term in order:
        name, group = names[term]
        counts = " | ".join(str(column.carried[term]) for column in columns)
        print(f"| {term} | {name} | {group} | {counts} |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

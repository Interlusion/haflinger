"""Run a corpus of e-invoices through Haflinger and report what happens to each file.

For every PDF and XML file below the given directory: take the invoice out of a PDF, read it with
Haflinger's mapping and through KoSIT's stylesheet, compare the two models, and validate it with
the official rules. Prints a summary and, given a second argument, writes one row per file as
TSV. Run it on a clone of the ZUGFeRD corpus (development guide).

    uv run python scripts/corpus_report.py <directory> [<output.tsv>]
"""

import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import cast

from haflinger import Invoice, InvoiceReadError, kosit, read_invoice, validate
from haflinger.pdf import extract_xml

# KoSIT's stylesheet takes minutes for invoices of tens of MB; their size is the benchmarks'.
LARGE = 5_000_000
COLUMNS = (
    "path",
    "kind",
    "filed_as_failing",
    "specification_id",
    "extract",
    "read",
    "read_findings",
    "kosit",
    "kosit_findings",
    "agree",
    "differences",
    "validation",
    "rules",
    "seconds",
)


@dataclass
class Row:
    path: str
    kind: str
    filed_as_failing: bool
    specification_id: str = ""
    extract: str = ""
    read: str = ""
    read_findings: list[str] = field(default_factory=list[str])
    kosit: str = ""
    kosit_findings: list[str] = field(default_factory=list[str])
    agree: str = ""
    differences: list[str] = field(default_factory=list[str])
    validation: str = ""
    rules: list[str] = field(default_factory=list[str])
    seconds: str = ""


def outcome(error: Exception) -> str:
    if isinstance(error, InvoiceReadError):
        return f"refused: {error}"
    return f"CRASH {type(error).__name__}: {error}"


def differences(ours: object, theirs: object, path: str = "") -> list[str]:
    """The model paths at which two models differ."""
    if is_dataclass(ours) and is_dataclass(theirs):
        return [
            difference
            for item in fields(ours)
            if item.compare
            for difference in differences(
                getattr(ours, item.name),
                getattr(theirs, item.name),
                f"{path}.{item.name}".lstrip("."),
            )
        ]
    if isinstance(ours, tuple) and isinstance(theirs, tuple):
        left, right = cast(tuple[object, ...], ours), cast(tuple[object, ...], theirs)
        if len(left) == len(right):
            pairs = enumerate(zip(left, right, strict=True))
            return [d for i, (a, b) in pairs for d in differences(a, b, f"{path}.{i}")]
    return [] if ours == theirs else [path]


def run(path: Path, base: Path) -> Row:
    relative = path.relative_to(base)
    row = Row(
        path=str(relative),
        kind=path.suffix.lower().lstrip("."),
        filed_as_failing="fail" in relative.parts,
    )
    data = path.read_bytes()
    xml = data
    if row.kind == "pdf":
        try:
            xml = extract_xml(data)
            row.extract = "ok"
        except Exception as error:  # noqa: BLE001 - a crash is what the report looks for
            row.extract = outcome(error)
            return row
    try:
        result = read_invoice(xml)
    except Exception as error:  # noqa: BLE001
        row.read = outcome(error)
        return row
    ours: Invoice = result.invoice
    row.read = "ok"
    row.specification_id = ours.specification_id or ""
    row.read_findings = sorted({finding.rule for finding in result.findings})
    if len(xml) > LARGE:
        row.kosit = row.validation = f"skipped: {len(xml) / 1e6:.1f} MB"
        return row
    try:
        semantic = kosit.read_invoice(xml)
        theirs = kosit.with_subject_codes(semantic.invoice)
        row.kosit = "ok"
        # A limit of KoSIT's stylesheet shows here: two EXTENDED due dates joined into one value
        # are a HAFL-VALUE for BT-9 (ADR-005).
        row.kosit_findings = sorted({f"{f.rule} {f.text.split()[0]}" for f in semantic.findings})
        row.differences = differences(ours, theirs)
        row.agree = "no" if row.differences else "yes"
    except Exception as error:  # noqa: BLE001
        row.kosit = outcome(error)
    try:
        findings = validate(xml)
    except Exception as error:  # noqa: BLE001
        row.validation = outcome(error)
        return row
    failed = [finding for finding in findings if finding.flag in ("fatal", "error")]
    row.validation = f"invalid ({len(failed)})" if failed else "valid"
    row.rules = sorted({finding.rule for finding in failed})
    if any(finding.rule == "HAFL-PROFILE" for finding in findings):
        row.validation += ", HAFL-PROFILE"
    return row


def cell(row: Row, column: str) -> str:
    value = getattr(row, column)
    text = " ".join(cast(list[str], value)) if isinstance(value, list) else str(value)
    return text.replace("\t", " ").replace("\n", " ")


def short(text: str) -> str:
    """An outcome without its reason or count, for counting."""
    if text.startswith(("refused", "CRASH", "skipped")):
        return text.split(":", 1)[0]
    return re.sub(r" \(\d+\)", "", text)


def main(arguments: list[str]) -> int:
    if len(arguments) not in (1, 2):
        print(__doc__, file=sys.stderr)
        return 2
    base = Path(arguments[0])
    files = sorted(
        p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in (".pdf", ".xml")
    )
    rows: list[Row] = []
    for path in files:
        start = time.perf_counter()
        row = run(path, base)
        row.seconds = f"{time.perf_counter() - start:.2f}"
        rows.append(row)
    if len(arguments) == 2:
        lines = ["\t".join(COLUMNS), *("\t".join(cell(row, c) for c in COLUMNS) for row in rows)]
        Path(arguments[1]).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} files")
    for column in ("kind", "extract", "read", "kosit", "agree", "validation"):
        counts = Counter(short(cell(row, column)) or "-" for row in rows)
        print(f"{column}: {dict(counts.most_common())}")
    rules = Counter(rule for row in rows for rule in row.rules)
    print(f"most failed rules: {rules.most_common(15)}")
    outcomes = ("extract", "read", "kosit", "validation")
    crashes = [row.path for row in rows if any(cell(row, c).startswith("CRASH") for c in outcomes)]
    print(f"crashes: {len(crashes)}", *crashes, sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

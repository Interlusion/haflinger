"""KoSIT's reading stylesheet as the second reader: it reads every official file to the same model
as Haflinger (REQ-003-PRS-F005, ADR-005)."""

from pathlib import Path

import pytest

from haflinger import InvoiceReadError, kosit, read_invoice
from haflinger.pdf import extract_xml

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/data/kosit-testsuite/instances"
CREDIT_NOTE = ROOT / "tests/data/cen-en16931/ubl/examples/ubl-tc434-creditnote1.xml"
CORPUS = ROOT / "tests/data/zugferd-corpus"


def readable(path: Path) -> bool:
    try:
        read_invoice(path.read_bytes())
    except InvoiceReadError:
        return False
    return True


# The corpus PDFs `read_invoice` reads; KoSIT's stylesheet gets their embedded XML.
PDFS = [path for path in sorted(CORPUS.rglob("*.pdf")) if readable(path)]
FILES = [*sorted(SUITE.rglob("*.xml")), CREDIT_NOTE, *PDFS]


def test_the_files_are_there() -> None:
    assert len(FILES) == 87 + 4


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_kosit_reads_what_haflinger_reads(path: Path) -> None:
    data = path.read_bytes()
    xml = extract_xml(data) if path.suffix == ".pdf" else data
    ours, theirs = read_invoice(data), kosit.read_invoice(xml)
    assert theirs.findings == ()
    assert theirs.invoice.syntax == ours.invoice.syntax
    assert kosit.with_subject_codes(theirs.invoice) == ours.invoice


def test_kosit_still_leaves_the_subject_code_in_ubl_notes() -> None:
    """Once a new release reads `#XXX#` as BT-21, `kosit.with_subject_codes` goes."""
    data = (SUITE / "standard/01.01a-INVOICE_ubl.xml").read_bytes()
    (note,) = kosit.read_invoice(data).invoice.notes
    assert note.subject_code is None
    assert (note.text or "").startswith("#ADU#")

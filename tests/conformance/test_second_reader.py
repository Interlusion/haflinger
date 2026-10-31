"""KoSIT's reading stylesheet as the second reader: it reads every official file to the same model
as Haflinger (REQ-003-PRS-F005, ADR-005)."""

import re
from dataclasses import replace
from pathlib import Path

import pytest

from haflinger import Invoice, InvoiceReadError, Note, kosit, read_invoice
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

# REQ-003-PRS-F005: the limits of KoSIT's stylesheet, each applied to its model before comparing.
#
# UBL has no element for the note's subject code (BT-21). KoSIT's stylesheet leaves the `#XXX#`
# that XRechnung and Peppol put at the start of the note's text (BT-22) in the text, while
# REQ-003-PRS-F002 reads it as BT-21. No report needed: the prefix is a convention, not part of
# EN 16931-3-2.
_SUBJECT_CODE = re.compile(r"#([A-Z]{3})#(.*)", re.DOTALL)


def with_subject_codes(invoice: Invoice) -> Invoice:
    """The model KoSIT's stylesheet gives, with each UBL note's `#XXX#` read as BT-21."""
    if invoice.syntax != "ubl":
        return invoice
    notes: list[Note] = []
    for note in invoice.notes:
        match = _SUBJECT_CODE.fullmatch(note.text or "")
        if note.subject_code is None and match is not None:
            note = Note(subject_code=match[1], text=match[2].strip(" \t\r\n") or None)
        notes.append(note)
    return replace(invoice, notes=tuple(notes))


def test_the_files_are_there() -> None:
    assert len(FILES) == 87 + 4


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_kosit_reads_what_haflinger_reads(path: Path) -> None:
    data = path.read_bytes()
    xml = extract_xml(data) if path.suffix == ".pdf" else data
    ours, theirs = read_invoice(data), kosit.read_invoice(xml)
    assert theirs.findings == ()
    assert theirs.invoice.syntax == ours.invoice.syntax
    assert with_subject_codes(theirs.invoice) == ours.invoice


def test_kosit_still_leaves_the_subject_code_in_ubl_notes() -> None:
    """Once a new release reads `#XXX#` as BT-21, `with_subject_codes` goes."""
    data = (SUITE / "standard/01.01a-INVOICE_ubl.xml").read_bytes()
    (note,) = kosit.read_invoice(data).invoice.notes
    assert note.subject_code is None
    assert (note.text or "").startswith("#ADU#")

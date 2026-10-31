"""Reading an invoice: bytes in, the model and what reading noticed out (REQ-003)."""

from dataclasses import dataclass

from haflinger import cii, ubl
from haflinger._input import open_invoice
from haflinger._xml import MAX_SIZE
from haflinger.findings import Finding
from haflinger.model import Invoice


@dataclass(frozen=True, kw_only=True)
class ReadResult:
    """The invoice as read, and the findings of reading in document order (REQ-003-PRS-F001)."""

    invoice: Invoice
    findings: tuple[Finding, ...]


def read_invoice(data: bytes, *, max_size: int = MAX_SIZE) -> ReadResult:
    """Read a CII invoice or a UBL invoice or credit note; the syntax is detected from the root
    element. Raises `InvoiceReadError` for input that can't be read (REQ-003-PRS-F006)."""
    opened = open_invoice(
        data,
        max_size,
        pdf="the input is a PDF; reading PDFs needs the extra 'pdf', which isn't installed",
    )
    root, specification_id = opened.reading.root, opened.specification_id
    match opened.document:
        case "cii":
            invoice = cii.read(root, specification_id)
        case "ubl-invoice" | "ubl-credit-note":
            credit_note = opened.document == "ubl-credit-note"
            invoice = ubl.read(root, specification_id, credit_note=credit_note)
    return ReadResult(invoice=invoice, findings=opened.reading.findings())

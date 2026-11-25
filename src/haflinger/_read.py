"""Reading an invoice: bytes in, the model and what reading noticed out (REQ-003)."""

from dataclasses import dataclass

from haflinger import _cii, _ubl
from haflinger._errors import InvoiceReadError
from haflinger._findings import Finding
from haflinger._input import Opened, is_pdf, open_invoice
from haflinger._model import Invoice
from haflinger._xml import MAX_SIZE, check_bytes, check_size


@dataclass(frozen=True, kw_only=True)
class ReadResult:
    """The invoice as read, and the findings of reading in document order (REQ-003-PRS-F001)."""

    invoice: Invoice
    findings: tuple[Finding, ...]


def read_invoice(data: bytes, *, max_size: int = MAX_SIZE) -> ReadResult:
    """Read a CII invoice or a UBL invoice or credit note; the syntax is detected from the root
    element. Raises `InvoiceReadError` for input that can't be read (REQ-003-PRS-F006)."""
    check_bytes(data)
    if is_pdf(data):
        return _read_pdf(data, max_size)
    opened = open_invoice(data, max_size, pdf="")
    return ReadResult(invoice=model(opened), findings=opened.reading.findings())


def model(opened: Opened) -> Invoice:
    """The model of an invoice that passed the checks, by its syntax."""
    root, specification_id = opened.reading.root, opened.specification_id
    match opened.document:
        case "cii":
            return _cii.read(root, specification_id)
        case "ubl-invoice" | "ubl-credit-note":
            credit_note = opened.document == "ubl-credit-note"
            return _ubl.read(root, specification_id, credit_note=credit_note)


def _read_pdf(data: bytes, max_size: int) -> ReadResult:
    """The invoice embedded in a ZUGFeRD PDF (REQ-003-PRS-F007)."""
    check_size(data, max_size)
    try:
        from haflinger.pdf import extract_xml  # the extra "pdf" is optional
    except ImportError:
        raise InvoiceReadError(
            "the input is a PDF; reading PDFs needs the extra 'pdf', which isn't installed"
        ) from None
    xml = extract_xml(data, max_size=max_size)
    if is_pdf(xml):
        raise InvoiceReadError("the PDF's embedded invoice is a PDF itself")
    try:
        return read_invoice(xml, max_size=max_size)
    except InvoiceReadError as error:
        raise InvoiceReadError(f"the PDF's embedded invoice: {error}") from None

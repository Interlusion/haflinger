"""Reading an invoice: bytes in, the model and what reading noticed out (REQ-003)."""

from dataclasses import dataclass

from haflinger import cii, ubl
from haflinger._xml import MAX_SIZE, Reading, check_size, local_name, parse
from haflinger.errors import InvoiceReadError
from haflinger.findings import Finding
from haflinger.model import Invoice

# Formats Haflinger recognises but doesn't read, by the local name of their root element.
_OTHER_FORMATS = {
    "CrossIndustryDocument": "a ZUGFeRD 1.0 invoice (CrossIndustryDocument)",
    "FatturaElettronica": "an Italian FatturaPA invoice",
}
_SUPPORTED_EDITIONS = {"2017", None}


@dataclass(frozen=True, kw_only=True)
class ReadResult:
    """The invoice as read, and the findings of reading in document order (REQ-003-PRS-F001)."""

    invoice: Invoice
    findings: tuple[Finding, ...]


def read_invoice(data: bytes, *, max_size: int = MAX_SIZE) -> ReadResult:
    """Read a CII invoice or a UBL invoice or credit note; the syntax is detected from the root
    element. Raises `InvoiceReadError` for input that can't be read (REQ-003-PRS-F006)."""
    check_size(data, max_size)
    if b"%PDF-" in data[:1024]:
        raise InvoiceReadError(
            "the input is a PDF; reading PDFs needs the extra 'pdf', which isn't installed"
        )
    root = parse(data)
    match root.tag:
        case cii.TAG:
            reading = Reading(root, cii.NAMESPACES, f"rsm:{cii.ROOT}")
            specification_id = _supported(cii.specification_id(reading.root))
            invoice = cii.read(reading.root, specification_id)
        case ubl.INVOICE_TAG | ubl.CREDIT_NOTE_TAG:
            name = local_name(root.tag)
            reading = Reading(root, ubl.NAMESPACES, name)
            specification_id = _supported(ubl.specification_id(reading.root))
            invoice = ubl.read(reading.root, specification_id, credit_note=name == "CreditNote")
        case _:
            other = _OTHER_FORMATS.get(local_name(root.tag))
            if other is not None:
                raise InvoiceReadError(f"the input is {other}, which Haflinger doesn't read")
            raise InvoiceReadError(
                f"the root element {root.tag} is neither a CII invoice nor a UBL invoice or"
                " credit note"
            )
    return ReadResult(invoice=invoice, findings=reading.findings())


def _supported(specification_id: str | None) -> str | None:
    """BT-24, if it names an edition Haflinger supports (REQ-002-PRS-F009)."""
    edition = Invoice(specification_id=specification_id).edition
    if edition not in _SUPPORTED_EDITIONS:
        raise InvoiceReadError(
            f"the invoice follows EN 16931-1:{edition} (BT-24 {specification_id!r});"
            " Haflinger supports only the 2017 edition"
        )
    return specification_id

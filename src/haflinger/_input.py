"""Outside input checked before it is read or validated: size, safety, root element, edition
(REQ-003-PRS-F006, REQ-002-PRS-F001)."""

from dataclasses import dataclass
from typing import Literal

from haflinger import _cii, _ubl
from haflinger._errors import InvoiceReadError
from haflinger._model import Invoice
from haflinger._xml import Node, Reading, check_bytes, check_size, local_name, parse

type Document = Literal["cii", "ubl-invoice", "ubl-credit-note"]

# Formats Haflinger recognises but doesn't read, by the local name of their root element.
_OTHER_FORMATS = {
    "CrossIndustryDocument": "a ZUGFeRD 1.0 invoice (CrossIndustryDocument)",
    "FatturaElettronica": "an Italian FatturaPA invoice",
}
_SUPPORTED_EDITIONS = {"2017", None}


@dataclass(frozen=True, kw_only=True)
class Opened:
    """An invoice that passed the checks: its reading, which document it is, and its BT-24."""

    reading: Reading
    document: Document
    specification: Node | None  # BT-24's element

    @property
    def specification_id(self) -> str | None:
        return None if self.specification is None else self.specification.value


def is_pdf(data: bytes) -> bool:
    """The PDF header within the first 1,024 bytes, before any `<`, which XML would have
    (REQ-003-PRS-F006)."""
    header = data.find(b"%PDF-", 0, 1024)
    return header >= 0 and b"<" not in data[:header]


def open_invoice(data: bytes, max_size: int, *, pdf: str) -> Opened:
    """Check and parse `data`; `pdf` is the reason given for a PDF."""
    check_bytes(data)
    check_size(data, max_size)
    if is_pdf(data):
        raise InvoiceReadError(pdf)
    root = parse(data)
    match root.tag:
        case _cii.TAG:
            reading = Reading(root, _cii.NAMESPACES)
            document: Document = "cii"
            specification = _cii.specification(reading.root)
        case _ubl.INVOICE_TAG | _ubl.CREDIT_NOTE_TAG:
            name = local_name(root.tag)
            reading = Reading(root, _ubl.NAMESPACES)
            document = "ubl-credit-note" if name == "CreditNote" else "ubl-invoice"
            specification = _ubl.specification(reading.root)
        case _:
            other = _OTHER_FORMATS.get(local_name(root.tag))
            if other is not None:
                raise InvoiceReadError(f"the input is {other}, which Haflinger doesn't read")
            raise InvoiceReadError(
                f"the root element {root.tag} is neither a CII invoice nor a UBL invoice or"
                " credit note"
            )
    opened = Opened(reading=reading, document=document, specification=specification)
    _check_edition(opened.specification_id)
    return opened


def _check_edition(specification_id: str | None) -> None:
    """Refuse an edition other than 2017 (REQ-002-PRS-F009)."""
    edition = Invoice(specification_id=specification_id).edition
    if edition not in _SUPPORTED_EDITIONS:
        raise InvoiceReadError(
            f"the invoice follows EN 16931-1:{edition} (BT-24 {specification_id!r});"
            " Haflinger supports only the 2017 edition"
        )

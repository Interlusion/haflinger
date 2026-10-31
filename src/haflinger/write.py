"""Writing an invoice: the model out as CII, handed out only when valid (REQ-004)."""

from typing import cast

from haflinger import _xsd, cii
from haflinger.errors import InvoiceReadError, InvoiceWriteError
from haflinger.findings import Finding
from haflinger.model import Invoice
from haflinger.validation import validate

# REQ-004-PRS-F002, by BT-24 exactly as given.
TARGET_PROFILES = (
    "urn:cen.eu:en16931:2017",
    "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0",
)


def write_cii(invoice: Invoice) -> bytes:
    """The invoice as CII D16B, UTF-8 with an XML declaration, when it passes the XML Schema and
    the official rules of its target profile. Raises `InvoiceWriteError` otherwise
    (REQ-004-PRS-F001)."""
    # The model's static types aren't checked at run time; a caller may pass anything.
    if not isinstance(cast(object, invoice), Invoice):
        raise InvoiceWriteError(f"the invoice is not an Invoice: {invoice!r}")
    if invoice.specification_id not in TARGET_PROFILES:
        raise InvoiceWriteError(
            f"BT-24 {invoice.specification_id!r} is no target profile Haflinger writes;"
            f" it writes {' and '.join(TARGET_PROFILES)}"
        )
    document = cii.write(invoice)
    refuse_if_invalid(check_written(document, invoice.specification_id), document)
    return document


def check_written(document: bytes, specification_id: str | None) -> tuple[Finding, ...]:
    """The findings of the XML Schemas and the official rules for a CII invoice of the target
    profile `specification_id` to hand out (REQ-004-PRS-F004, REQ-004-PRS-F005)."""
    factur_x = specification_id == TARGET_PROFILES[0]  # Factur-X's EN 16931 profile
    findings = tuple(_xsd.check_cii(document, factur_x_en16931=factur_x))
    try:
        return (*findings, *validate(document))
    except InvoiceReadError as error:
        raise InvoiceWriteError(
            f"the invoice can't be validated: {error}", findings=findings, document=document
        ) from None


def refuse_if_invalid(findings: tuple[Finding, ...], document: bytes) -> None:
    failed = sorted({f.rule for f in findings if f.flag in ("fatal", "error")})
    if failed:
        raise InvoiceWriteError(
            f"the invoice is not valid; it fails {', '.join(failed)}",
            findings=findings,
            document=document,
        )

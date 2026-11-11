"""Writing an invoice: the model out as CII, handed out only when valid (REQ-004)."""

from typing import cast

from haflinger import _cii, _saxon, _xsd
from haflinger._errors import InvoiceReadError, InvoiceWriteError
from haflinger._findings import INVALID, Finding
from haflinger._model import Invoice
from haflinger._validation import FACTUR_X_EN16931, check_rules
from haflinger._xml import quoted

# REQ-004-PRS-F002, by BT-24 exactly as given. A ZUGFeRD PDF labels EN 16931 Factur-X EN 16931.
EN16931 = "urn:cen.eu:en16931:2017"
XRECHNUNG = f"{EN16931}#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
TARGET_PROFILES = (EN16931, XRECHNUNG)


def write_cii(invoice: Invoice, *, timeout: float | None = None) -> bytes:
    """The invoice as CII D16B, UTF-8 with an XML declaration, when it passes the XML Schema and
    the official rules of its target profile, which end within `timeout` seconds, by default
    `HAFLINGER_RULES_TIMEOUT` or 60 (REQ-002-PRS-NF004). Raises `InvoiceWriteError` otherwise
    (REQ-004-PRS-F001)."""
    # The model's static types aren't checked at run time; a caller may pass anything.
    if not isinstance(cast(object, invoice), Invoice):
        raise InvoiceWriteError(f"the invoice is not an Invoice: {quoted(invoice)}")
    limit = rules_timeout(timeout)
    if invoice.specification_id not in TARGET_PROFILES:
        raise InvoiceWriteError(
            f"BT-24 {quoted(invoice.specification_id)} is no target profile Haflinger writes;"
            f" it writes {' and '.join(TARGET_PROFILES)}"
        )
    document = _cii.write(invoice)
    refuse_if_invalid(check_written(document, invoice.specification_id, limit), document)
    return document


def rules_timeout(timeout: object) -> float:
    """`_saxon.time_limit`, refused before writing (REQ-004-PRS-F001)."""
    try:
        return _saxon.time_limit(timeout)
    except InvoiceReadError as error:
        raise InvoiceWriteError(str(error)) from None


def check_written(
    document: bytes, specification_id: str | None, timeout: float
) -> tuple[Finding, ...]:
    """The findings of the XML Schemas and the official rules for a CII invoice of the target
    profile `specification_id` to hand out (REQ-004-PRS-F004, REQ-004-PRS-F005): for EN 16931,
    which a ZUGFeRD PDF labels Factur-X EN 16931, FeRD's schema and rules of that profile too."""
    factur_x = specification_id == EN16931
    findings = tuple(_xsd.check_cii(document, factur_x_en16931=factur_x))
    if findings:
        return findings  # the rules run only on a schema-valid invoice (REQ-002-PRS-F011)
    try:
        also = [FACTUR_X_EN16931] if factur_x else []
        return check_rules(document, *also, timeout=timeout)
    except InvoiceReadError as error:
        raise InvoiceWriteError(
            f"the invoice can't be validated: {error}", findings=findings, document=document
        ) from None


def refuse_if_invalid(findings: tuple[Finding, ...], document: bytes) -> None:
    failed = sorted({f.rule for f in findings if f.flag in INVALID})
    if failed:
        raise InvoiceWriteError(
            f"the invoice is not valid; it fails {', '.join(failed)}",
            findings=findings,
            document=document,
        )

"""Writing CII (REQ-004), on the model of KoSIT case 01.01a written as plain EN 16931."""

import contextlib
import re
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from haflinger import InvoiceReadError, InvoiceWriteError, Note, read_invoice, write_cii
from haflinger._xsd import check_cii

ROOT = Path(__file__).resolve().parents[2]
CII = ROOT / "tests/data/kosit-testsuite/instances/standard/01.01a-INVOICE_uncefact.xml"
EN16931 = "urn:cen.eu:en16931:2017"
XRECHNUNG = f"{EN16931}#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"

INVOICE = replace(read_invoice(CII.read_bytes()).invoice, specification_id=EN16931)
assert INVOICE.totals is not None
assert INVOICE.seller is not None
TOTALS, SELLER, LINE = INVOICE.totals, INVOICE.seller, INVOICE.lines[0]


def written(invoice: Any) -> bytes:
    """The written document, handed out or carried by the refusal after writing."""
    try:
        return write_cii(invoice)
    except InvoiceWriteError as error:
        refusal = error
    assert refusal.document is not None, refusal
    return refusal.document


# REQ-004-PRS-F001


def test_writes_a_valid_invoice() -> None:
    document = write_cii(INVOICE)
    assert document.startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n<rsm:CrossIndustryInvoice')
    document.decode("utf-8")
    assert read_invoice(document).invoice == INVOICE


def test_refuses_an_invalid_invoice_after_writing() -> None:
    invoice = replace(INVOICE, totals=replace(TOTALS, total_with_vat=Decimal("336.91")))
    with pytest.raises(InvoiceWriteError, match="BR-CO-15") as refusal:
        write_cii(invoice)
    assert "BR-CO-15" in {finding.rule for finding in refusal.value.findings}
    assert refusal.value.document is not None
    assert read_invoice(refusal.value.document).invoice == invoice


@pytest.mark.parametrize(
    ("invoice", "reason"),
    [
        (replace(INVOICE, totals=replace(TOTALS, total_with_vat=336.9)), "BT-112 is not a finite"),
        (replace(INVOICE, totals=replace(TOTALS, amount_due=Decimal("NaN"))), "BT-115 is not a"),
        (replace(INVOICE, issue_date="2016-04-04"), "BT-2 is not a date"),
        (replace(INVOICE, issue_date=datetime(2016, 4, 4, 12)), "BT-2 is not a date"),
        (replace(INVOICE, seller=replace(SELLER, name=" Example GmbH")), "BT-27 has whitespace"),
        (replace(INVOICE, seller=replace(SELLER, name="")), "BT-27 is empty"),
        (replace(INVOICE, number=123456), "BT-1 is not a str"),
        (
            replace(
                INVOICE, lines=(replace(LINE, item_name="Zeitschrift\x01"), *INVOICE.lines[1:])
            ),
            "BT-153 holds a character XML doesn't allow",
        ),
        (
            replace(INVOICE, totals=replace(TOTALS, vat_total_in_tax_currency=Decimal("22.04"))),
            "BT-111 needs the VAT accounting currency code (BT-6)",
        ),
        (
            replace(INVOICE, lines=(replace(LINE, quantity=None), *INVOICE.lines[1:])),
            "BT-130 needs the invoiced quantity (BT-129)",
        ),
        (replace(INVOICE, notes=[Note(text="a list")]), "BG-1 is not a tuple of Note"),
        (replace(INVOICE, seller="Example GmbH"), "BG-4 is not a Party"),
        ("<Invoice/>", "the invoice is not an Invoice"),
    ],
    ids=[
        "float",
        "nan",
        "str-date",
        "datetime",
        "whitespace",
        "empty",
        "int-text",
        "control-character",
        "bt-111-without-bt-6",
        "bt-130-without-bt-129",
        "list",
        "str-party",
        "not-an-invoice",
    ],
)
def test_refuses_before_writing(invoice: Any, reason: str) -> None:
    with pytest.raises(InvoiceWriteError, match=re.escape(reason)) as refusal:
        write_cii(invoice)
    assert refusal.value.findings == ()
    assert refusal.value.document is None


# REQ-004-PRS-F002


@pytest.mark.parametrize(
    "specification_id",
    [
        f"{EN16931}#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0",
        "urn:factur-x.eu:1p0:minimum",
        f"{EN16931}:compliant:factur-x.eu:1p0:basic",
        "urn:cen.eu:en16931:2026",
        None,
    ],
)
def test_refuses_other_target_profiles(specification_id: str | None) -> None:
    with pytest.raises(InvoiceWriteError, match=r"BT-24 .* is no target profile") as refusal:
        write_cii(replace(INVOICE, specification_id=specification_id))
    assert refusal.value.document is None


def test_writes_xrechnung_with_its_rules() -> None:
    """KoSIT's XRechnung rules run: the model lacks the seller's city (BT-37), among others."""
    with pytest.raises(InvoiceWriteError, match="BR-DE-3") as refusal:
        write_cii(replace(INVOICE, specification_id=XRECHNUNG))
    assert refusal.value.document is not None


# REQ-004-PRS-F003


def test_numbers_keep_their_digits() -> None:
    line = replace(LINE, quantity=Decimal("1.000"), vat_rate=Decimal("7.00"))
    invoice = replace(INVOICE, lines=(line, *INVOICE.lines[1:]))
    document = written(invoice)
    assert b'<ram:BilledQuantity unitCode="XPP">1.000</ram:BilledQuantity>' in document
    back = read_invoice(document).invoice.lines[0]
    assert (str(back.quantity), str(back.vat_rate)) == ("1.000", "7.00")


def test_an_exponent_is_written_plain() -> None:
    line = replace(LINE, quantity=Decimal("1E+2"))
    document = written(replace(INVOICE, lines=(line, *INVOICE.lines[1:])))
    assert b'<ram:BilledQuantity unitCode="XPP">100</ram:BilledQuantity>' in document


def test_missing_terms_are_left_out() -> None:
    invoice = replace(
        INVOICE,
        buyer_reference=None,
        business_process=None,
        notes=(),
        seller=replace(SELLER, trading_name=None, legal_registration_id=None),
    )
    document = written(invoice)
    for tag in (
        b"ram:BuyerReference",
        b"ram:BusinessProcessSpecifiedDocumentContextParameter",
        b"ram:IncludedNote",
        b"ram:TaxCurrencyCode",
        b"ram:SpecifiedLegalOrganization",
    ):
        assert tag not in document
    assert b"<ram:ApplicableHeaderTradeDelivery />" in document
    assert read_invoice(document).invoice == invoice


def test_a_carriage_return_reads_back() -> None:
    invoice = replace(INVOICE, notes=(Note(text="first\r\nsecond"),))
    assert read_invoice(written(invoice)).invoice == invoice


def test_dates_before_1000() -> None:
    invoice = replace(INVOICE, issue_date=date(999, 1, 2))
    assert b">09990102</udt:DateTimeString>" in written(invoice)


# REQ-004-PRS-F004


def test_a_schema_violation_is_hafl_xsd() -> None:
    """ExchangedDocument needs its ID (BT-1), in both XML Schemas of the EN 16931 profile."""
    with pytest.raises(InvoiceWriteError) as refusal:
        write_cii(replace(INVOICE, number=None))
    findings = [f for f in refusal.value.findings if f.rule == "HAFL-XSD"]
    assert [f.text.split(":")[0] for f in findings] == [
        "CII D16B XML Schema",
        "Factur-X EN 16931 XML Schema",
    ]
    assert all(f.flag == "fatal" and "ID" in f.text for f in findings)


def test_the_schema_check_reports_each_violation() -> None:
    document = write_cii(INVOICE).replace(b"<ram:TypeCode>380</ram:TypeCode>", b"<ram:Unknown/>")
    findings = check_cii(document)
    assert [finding.rule for finding in findings] == ["HAFL-XSD"]
    assert findings[0].location.startswith("/")


def test_a_huge_text_is_checked_not_crashed_on() -> None:
    """A text over libxml2's default limit of 10 MB: a result or InvoiceWriteError, nothing else."""
    with contextlib.suppress(InvoiceWriteError):
        write_cii(replace(INVOICE, notes=(Note(text="A" * 11_000_000),)))


def test_a_document_validation_refuses_is_refused_after_writing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation's own refusals, such as the size limit, become InvoiceWriteError with the
    document."""

    def refuse(data: bytes) -> list[object]:
        raise InvoiceReadError("the input is larger than max_size")

    monkeypatch.setattr("haflinger.write.validate", refuse)
    with pytest.raises(InvoiceWriteError, match="larger than max_size") as refusal:
        write_cii(INVOICE)
    assert refusal.value.document is not None


def test_bt_111_in_the_invoice_currency_reads_back() -> None:
    invoice = replace(
        INVOICE,
        tax_currency_code="EUR",
        totals=replace(TOTALS, vat_total_in_tax_currency=TOTALS.vat_total),
    )
    assert read_invoice(written(invoice)).invoice == invoice


# REQ-004-PRS-F004: Factur-X's XML Schema of the EN 16931 profile


def test_en16931_is_checked_against_factur_xs_schema_too() -> None:
    """ExchangedDocument may hold a name in CII D16B, not in Factur-X's EN 16931 profile."""
    document = write_cii(INVOICE).replace(
        b"<ram:ID>123456XX</ram:ID>", b"<ram:ID>123456XX</ram:ID><ram:Name>Rechnung</ram:Name>", 1
    )
    assert check_cii(document) == []
    findings = check_cii(document, factur_x_en16931=True)
    assert [finding.rule for finding in findings] == ["HAFL-XSD"]
    assert findings[0].text.startswith("Factur-X EN 16931 XML Schema: ")


def test_xrechnung_isnt_checked_against_factur_xs_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def check(document: bytes, *, factur_x_en16931: bool = False) -> list[object]:
        calls.append(factur_x_en16931)
        return []

    monkeypatch.setattr("haflinger._xsd.check_cii", check)
    with contextlib.suppress(InvoiceWriteError):
        write_cii(replace(INVOICE, specification_id=XRECHNUNG))
    with contextlib.suppress(InvoiceWriteError):
        write_cii(INVOICE)
    assert calls == [False, True]

"""Writing CII (REQ-004), on the model of KoSIT case 01.01a written as plain EN 16931."""

import contextlib
import re
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from haflinger import (
    AllowanceCharge,
    Contact,
    CreditTransfer,
    Delivery,
    DirectDebit,
    Identifier,
    Invoice,
    InvoiceReadError,
    InvoiceWriteError,
    ItemAttribute,
    ItemClassification,
    Note,
    Payee,
    PaymentCard,
    PaymentInstructions,
    Period,
    PrecedingInvoice,
    SupportingDocument,
    TaxRepresentative,
    read_invoice,
    validate,
    write_cii,
)
from haflinger._xsd import check_cii

ROOT = Path(__file__).resolve().parents[2]
CII = ROOT / "tests/data/kosit-testsuite/instances/standard/01.01a-INVOICE_uncefact.xml"
EN16931 = "urn:cen.eu:en16931:2017"
XRECHNUNG = f"{EN16931}#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"

INVOICE = replace(read_invoice(CII.read_bytes()).invoice, specification_id=EN16931)
assert INVOICE.totals is not None
assert INVOICE.seller is not None
assert INVOICE.buyer is not None
TOTALS, SELLER, BUYER, LINE = INVOICE.totals, INVOICE.seller, INVOICE.buyer, INVOICE.lines[0]


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
        (
            replace(INVOICE, lines=(replace(LINE, price_discount=Decimal(1)), *INVOICE.lines[1:])),
            "BT-147 needs the item gross price (BT-148)",
        ),
        (
            replace(
                INVOICE,
                lines=(replace(LINE, base_quantity_unit_code="C62"), *INVOICE.lines[1:]),
            ),
            "BT-150 needs the item price base quantity (BT-149)",
        ),
        (replace(INVOICE, vat_point_date="2016-04-01"), "BT-7 is not a date"),
        (replace(INVOICE, vat_breakdown=(), vat_point_date="2016-04-01"), "BT-7 is not a date"),
        (
            replace(INVOICE, vat_point_date_code="29"),
            "BT-8 holds CII's code '29'; the model holds EN 16931's, '35'",
        ),
        (replace(INVOICE, vat_point_date_code=3), "BT-8 is not a str"),
        (
            replace(INVOICE, vat_breakdown=(), vat_point_date=date(2016, 4, 1)),
            "BT-7 needs a VAT breakdown (BG-23), which is missing",
        ),
        (
            replace(INVOICE, vat_breakdown=(), vat_point_date_code="3"),
            "BT-8 needs a VAT breakdown (BG-23), which is missing",
        ),
        (
            replace(
                INVOICE, lines=(replace(LINE, standard_item_id="4000001000005"), *INVOICE.lines[1:])
            ),
            "BT-157 is not an Identifier",
        ),
        (
            replace(INVOICE, lines=(replace(LINE, object_id="O-1"), *INVOICE.lines[1:])),
            "BT-128 is not an Identifier",
        ),
        (
            replace(
                INVOICE,
                lines=(
                    replace(LINE, item_classifications=[ItemClassification(value="49021000")]),
                    *INVOICE.lines[1:],
                ),
            ),
            "BT-158 is not a tuple of ItemClassification",
        ),
        (
            replace(
                INVOICE,
                lines=(
                    replace(LINE, item_attributes=[ItemAttribute(name="Farbe", value="Rot")]),
                    *INVOICE.lines[1:],
                ),
            ),
            "BG-32 is not a tuple of ItemAttribute",
        ),
        (
            replace(
                INVOICE, lines=(replace(LINE, item_attributes=("Farbe: Rot",)), *INVOICE.lines[1:])
            ),
            "BG-32 holds something other than ItemAttribute",
        ),
        (
            replace(
                INVOICE,
                lines=(replace(LINE, item_classifications=("49021000",)), *INVOICE.lines[1:]),
            ),
            "BT-158 holds something other than ItemClassification",
        ),
        (
            replace(
                INVOICE,
                lines=(
                    replace(
                        LINE,
                        item_classifications=(ItemClassification(value="49021000", scheme=1),),  # pyright: ignore[reportArgumentType]
                    ),
                    *INVOICE.lines[1:],
                ),
            ),
            "BT-158-1 is not a str",
        ),
        (
            replace(
                INVOICE,
                lines=(
                    replace(
                        LINE,
                        item_classifications=(
                            ItemClassification(
                                value="49021000", scheme="HS", scheme_version=" 2022"
                            ),
                        ),
                    ),
                    *INVOICE.lines[1:],
                ),
            ),
            "BT-158-2 has whitespace around it",
        ),
        (replace(INVOICE, invoiced_object_id="O-18"), "BT-18 is not an Identifier"),
        (
            replace(INVOICE, supporting_documents=[SupportingDocument(reference="A-1")]),
            "BG-24 is not a tuple of SupportingDocument",
        ),
        (
            replace(
                INVOICE,
                supporting_documents=(SupportingDocument(reference=1),),  # pyright: ignore[reportArgumentType]
            ),
            "BT-122 is not a str",
        ),
        (replace(INVOICE, payee="Example Factoring GmbH"), "BG-10 is not a Payee"),
        (replace(INVOICE, tax_representative="Example"), "BG-11 is not a TaxRepresentative"),
        (
            replace(INVOICE, seller=replace(SELLER, legal_registration_id="HRB 1")),
            "BT-30 is not an Identifier",
        ),
        (replace(INVOICE, notes=[Note(text="a list")]), "BG-1 is not a tuple of Note"),
        (replace(INVOICE, seller="Example GmbH"), "BG-4 is not a Party"),
        (replace(INVOICE, seller=replace(SELLER, contact="Sales")), "BG-6 is not a Contact"),
        (
            replace(INVOICE, seller=replace(SELLER, identifiers=[Identifier(value="A1")])),
            "BT-29 is not a tuple of Identifier",
        ),
        (
            replace(INVOICE, buyer=replace(BUYER, electronic_address="buyer@info.de")),
            "BT-49 is not an Identifier",
        ),
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
        "bt-147-without-bt-148",
        "bt-150-without-bt-149",
        "str-vat-point-date",
        "str-vat-point-date-without-bg-23",
        "ciis-vat-point-date-code",
        "int-vat-point-date-code",
        "bt-7-without-bg-23",
        "bt-8-without-bg-23",
        "str-standard-item-id",
        "str-line-object",
        "list-item-classifications",
        "list-item-attributes",
        "str-item-attribute",
        "str-item-classification",
        "int-classification-scheme",
        "whitespace-classification-version",
        "str-invoiced-object",
        "list-supporting-documents",
        "int-supporting-document-reference",
        "str-payee",
        "str-tax-representative",
        "str-legal-registration",
        "list",
        "str-party",
        "str-contact",
        "list-identifiers",
        "str-electronic-address",
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
    """KoSIT case 01.01a, whose terms the model holds, passes KoSIT's XRechnung rules; without
    its payment instructions it fails BR-DE-1."""
    invoice = replace(INVOICE, specification_id=XRECHNUNG)
    assert read_invoice(write_cii(invoice)).invoice == invoice
    with pytest.raises(InvoiceWriteError, match="BR-DE-1") as refusal:
        write_cii(replace(invoice, payment_instructions=None))
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
        seller=replace(
            SELLER,
            trading_name=None,
            legal_registration_id=None,
            electronic_address=None,
            address_line_1=None,
            city=None,
            post_code=None,
            contact=None,
        ),
        buyer=replace(BUYER, identifiers=(), electronic_address=None, address_line_1=None),
        lines=tuple(
            replace(
                line,
                note=None,
                purchase_order_line_reference=None,
                period=None,
                item_description=None,
                seller_item_id=None,
                item_classifications=(),
            )
            for line in INVOICE.lines
        ),
    )
    document = written(invoice)
    for tag in (
        b"ram:BuyerReference",
        b"ram:DefinedTradeContact",
        b"ram:URIUniversalCommunication",
        b"ram:LineOne",
        b"ram:CityName>[Seller",
        b"ram:ID>[Buyer",
        b"ram:BusinessProcessSpecifiedDocumentContextParameter",
        b"ram:IncludedNote",
        b"ram:BillingSpecifiedPeriod",
        b"ram:TaxCurrencyCode",
        b"ram:SpecifiedLegalOrganization",
        b"ram:SellerAssignedID",
        b"ram:GrossPriceProductTradePrice",
        b"ram:BasisQuantity",
        b"ram:BuyerOrderReferencedDocument",
        b"ram:AdditionalReferencedDocument",
        b"ram:SpecifiedProcuringProject",
        b"ram:DespatchAdviceReferencedDocument",
        b"ram:ReceivableSpecifiedTradeAccountingAccount",
        b"ram:DesignatedProductClassification",
        b"ram:OriginTradeCountry",
        b"ram:ApplicableProductCharacteristic",
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


def test_a_huge_text_is_written() -> None:
    """A text over libxml2's default limit of 10 MB passes the schema check (`huge_tree`)."""
    document = write_cii(replace(INVOICE, notes=(Note(text="A" * 11_000_000),)))
    assert b"A" * 11_000_000 in document


def test_a_document_validation_refuses_is_refused_after_writing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation's own refusals, such as the size limit, become InvoiceWriteError with the
    document."""

    def refuse(data: bytes, *also: str, timeout: float | None = None) -> list[object]:
        raise InvoiceReadError("the input is larger than max_size")

    monkeypatch.setattr("haflinger.write.check_rules", refuse)
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


# The second review of 2026-11-01


@pytest.mark.parametrize(
    ("invoice", "reason"),
    [
        (replace(INVOICE, notes=(Note(),)), "BG-1 holds a note with neither subject code nor text"),
        (
            replace(INVOICE, totals=replace(TOTALS, amount_due=Decimal("1E+999999999"))),
            "BT-115 has more than 1,000 digits",
        ),
        (
            replace(INVOICE, totals=replace(TOTALS, amount_due=Decimal("1" * 1001))),
            "BT-115 has more than 1,000 digits",
        ),
    ],
    ids=["empty-note", "huge-exponent", "long-number"],
)
def test_refuses_what_cant_be_written_sensibly(invoice: Any, reason: str) -> None:
    with pytest.raises(InvoiceWriteError, match=re.escape(reason)) as refusal:
        write_cii(invoice)
    assert refusal.value.document is None


# REQ-004-PRS-F001: parties


@pytest.mark.parametrize(
    ("invoice", "reason"),
    [
        (
            replace(INVOICE, seller=replace(SELLER, contact=Contact())),
            "BG-6 holds a contact without any term",
        ),
        (
            replace(INVOICE, buyer=replace(BUYER, contact=Contact())),
            "BG-9 holds a contact without any term",
        ),
        (
            replace(INVOICE, seller=replace(SELLER, identifiers=(Identifier(scheme="0088"),))),
            "BG-4 holds an identifier without its value (BT-29)",
        ),
        (
            replace(INVOICE, buyer=replace(BUYER, electronic_address=Identifier(scheme="EM"))),
            "BG-7 holds an electronic address without its value (BT-49)",
        ),
        (
            replace(INVOICE, seller=replace(SELLER, electronic_address=Identifier(value="a@b.de"))),
            "BG-4 holds an electronic address without its scheme (BT-34-1)",
        ),
        (
            replace(INVOICE, payment_instructions=PaymentInstructions()),
            "BG-16 holds payment instructions without any term",
        ),
        (
            replace(
                INVOICE,
                payment_instructions=PaymentInstructions(
                    means_code="58", credit_transfers=(CreditTransfer(),)
                ),
            ),
            "BG-17 holds a credit transfer without any term",
        ),
        (
            replace(
                INVOICE,
                payment_instructions=PaymentInstructions(
                    means_code="48", card=PaymentCard(holder_name="Max Muster")
                ),
            ),
            "BG-18 holds a card without its account number (BT-87)",
        ),
        (
            replace(
                INVOICE,
                payment_instructions=PaymentInstructions(
                    means_code="59", direct_debit=DirectDebit()
                ),
            ),
            "BG-19 holds a direct debit without any term",
        ),
        (
            replace(INVOICE, payment_instructions="58"),
            "BG-16 is not a PaymentInstructions",
        ),
        (
            replace(
                INVOICE,
                payment_instructions=PaymentInstructions(
                    means_code="58",
                    credit_transfers=[CreditTransfer(account_id="DE1")],  # pyright: ignore[reportArgumentType]
                ),
            ),
            "BG-17 is not a tuple of CreditTransfer",
        ),
        (
            replace(
                INVOICE,
                preceding_invoices=(PrecedingInvoice(number="R-0"), PrecedingInvoice(number="R-1")),
            ),
            "BG-3 holds more preceding invoices than CII D16B can, which is one",
        ),
        (
            replace(INVOICE, preceding_invoices=(PrecedingInvoice(),)),
            "BG-3 holds a preceding invoice without any term",
        ),
        (
            replace(INVOICE, delivery=Delivery()),
            "BG-13 holds delivery information without any term",
        ),
        (replace(INVOICE, invoicing_period=Period()), "BG-14 holds a period without any term"),
        (
            replace(INVOICE, lines=(replace(LINE, period=Period()), *INVOICE.lines[1:])),
            "BG-26 holds a period without any term",
        ),
        (
            replace(INVOICE, allowances=(AllowanceCharge(),)),
            "BG-20 holds an allowance without any term",
        ),
        (replace(INVOICE, charges=(AllowanceCharge(),)), "BG-21 holds a charge without any term"),
        (
            replace(
                INVOICE, lines=(replace(LINE, allowances=(AllowanceCharge(),)), *INVOICE.lines[1:])
            ),
            "BG-27 holds a line allowance without any term",
        ),
        (
            replace(
                INVOICE, lines=(replace(LINE, charges=(AllowanceCharge(),)), *INVOICE.lines[1:])
            ),
            "BG-28 holds a line charge without any term",
        ),
        (
            replace(
                INVOICE,
                lines=(
                    replace(LINE, allowances=[AllowanceCharge(amount=Decimal(1))]),
                    *INVOICE.lines[1:],
                ),
            ),
            "BG-27 is not a tuple of AllowanceCharge",
        ),
        (
            replace(
                INVOICE,
                lines=(
                    replace(
                        LINE,
                        charges=(AllowanceCharge(amount=Decimal(1), vat_category_code="S"),),
                    ),
                    *INVOICE.lines[1:],
                ),
            ),
            "BG-28 holds a VAT category code or rate, which a line charge hasn't",
        ),
        (
            replace(
                INVOICE,
                lines=(
                    replace(
                        LINE, allowances=(AllowanceCharge(amount=Decimal(1), vat_rate=Decimal(7)),)
                    ),
                    *INVOICE.lines[1:],
                ),
            ),
            "BG-27 holds a VAT category code or rate, which a line allowance hasn't",
        ),
        (
            replace(
                INVOICE,
                lines=(
                    replace(
                        LINE,
                        allowances=(
                            AllowanceCharge(amount=Decimal(1), reason=" x", vat_category_code="S"),
                        ),
                    ),
                    *INVOICE.lines[1:],
                ),
            ),
            "BG-27 holds a VAT category code or rate, which a line allowance hasn't",
        ),
        (
            replace(INVOICE, allowances=[AllowanceCharge(amount=Decimal(1))]),
            "BG-20 is not a tuple of AllowanceCharge",
        ),
        (
            replace(INVOICE, delivery=Delivery(city="")),
            "BT-77 is empty; a missing term is None",
        ),
        (replace(INVOICE, delivery="Lager"), "BG-13 is not a Delivery"),
        (replace(INVOICE, invoicing_period="March"), "BG-14 is not a Period"),
        (
            replace(INVOICE, lines=(replace(LINE, period="2016"), *INVOICE.lines[1:])),
            "BG-26 is not a Period",
        ),
        (
            replace(INVOICE, preceding_invoices=[PrecedingInvoice(number="R-0")]),
            "BG-3 is not a tuple of PrecedingInvoice",
        ),
        (
            replace(INVOICE, buyer=replace(BUYER, tax_registration_id="201/113/40209")),
            "BT-32 is the seller's alone; the buyer (BG-7) has none",
        ),
        (
            replace(
                INVOICE,
                buyer=replace(BUYER, identifiers=(Identifier(value="A1"), Identifier(value="B2"))),
            ),
            "BG-7 holds more than one identifier (BT-46)",
        ),
        (
            replace(
                INVOICE,
                lines=(
                    replace(LINE, standard_item_id=Identifier(scheme="0160")),
                    *INVOICE.lines[1:],
                ),
            ),
            "BG-31 holds a standard identifier without its value (BT-157)",
        ),
        (
            replace(
                INVOICE,
                lines=(replace(LINE, object_id=Identifier(scheme="ABZ")), *INVOICE.lines[1:]),
            ),
            "BG-25 holds an object identifier without its value (BT-128)",
        ),
        (
            replace(
                INVOICE,
                lines=(
                    replace(LINE, item_classifications=(ItemClassification(scheme="HS"),)),
                    *INVOICE.lines[1:],
                ),
            ),
            "BG-31 holds an item classification without its value (BT-158)",
        ),
        (
            replace(
                INVOICE,
                lines=(replace(LINE, item_attributes=(ItemAttribute(),)), *INVOICE.lines[1:]),
            ),
            "BG-32 holds an item attribute without any term",
        ),
        (
            replace(INVOICE, invoiced_object_id=Identifier(scheme="ABZ")),
            "the invoice holds an invoiced object identifier without its value (BT-18)",
        ),
        (replace(INVOICE, payee=Payee()), "BG-10 holds a payee without any term"),
        (
            replace(INVOICE, supporting_documents=(SupportingDocument(),)),
            "BG-24 holds a supporting document without any term",
        ),
        (
            replace(INVOICE, tax_representative=TaxRepresentative()),
            "BG-11 holds a tax representative without any term",
        ),
        (
            replace(INVOICE, buyer=replace(BUYER, additional_legal_information="GmbH")),
            "BT-33 is the seller's alone; the buyer (BG-7) has none",
        ),
        (
            replace(INVOICE, buyer=replace(BUYER, additional_legal_information="")),
            "BT-33 is the seller's alone; the buyer (BG-7) has none",
        ),
        (
            replace(
                INVOICE, seller=replace(SELLER, legal_registration_id=Identifier(scheme="0002"))
            ),
            "BG-4 holds a legal registration identifier without its value (BT-30)",
        ),
        (
            replace(INVOICE, payee=Payee(name="Example", identifier=Identifier(scheme="0088"))),
            "BG-10 holds an identifier without its value (BT-60)",
        ),
    ],
    ids=[
        "empty-seller-contact",
        "empty-buyer-contact",
        "identifier-without-value",
        "electronic-address-without-value",
        "electronic-address-without-scheme",
        "empty-instructions",
        "empty-credit-transfer",
        "card-without-number",
        "empty-direct-debit",
        "str-instructions",
        "list-credit-transfers",
        "two-preceding-invoices",
        "empty-preceding-invoice",
        "empty-delivery",
        "empty-period",
        "empty-line-period",
        "empty-allowance",
        "empty-charge",
        "empty-line-allowance",
        "empty-line-charge",
        "list-line-allowances",
        "line-charge-with-vat-category",
        "line-allowance-with-vat-rate",
        "line-allowance-with-vat-category-before-its-other-terms",
        "list-allowances",
        "empty-city",
        "str-delivery",
        "str-period",
        "str-line-period",
        "list-preceding-invoices",
        "buyer-tax-registration",
        "two-buyer-identifiers",
        "standard-item-id-without-value",
        "line-object-without-value",
        "item-classification-without-value",
        "empty-item-attribute",
        "invoiced-object-without-value",
        "empty-payee",
        "empty-supporting-document",
        "empty-tax-representative",
        "buyer-bt-33",
        "empty-buyer-bt-33",
        "legal-registration-without-value",
        "payee-identifier-without-value",
    ],
)
def test_refuses_parties_that_cant_be_written(invoice: Any, reason: str) -> None:
    with pytest.raises(InvoiceWriteError, match=re.escape(reason)) as refusal:
        write_cii(invoice)
    assert refusal.value.document is None


# REQ-004-PRS-F003: parties


def test_writes_the_parties_terms_and_reads_them_back() -> None:
    seller = replace(
        SELLER,
        identifiers=(
            Identifier(value="A1"),
            Identifier(value="4000001000005", scheme="0088"),
        ),
        tax_registration_id="201/113/40209",
        address_line_2="Hinterhaus",
        address_line_3="3. OG",
        country_subdivision="Berlin",
    )
    buyer = replace(BUYER, contact=Contact(point="Einkauf", email="buyer@info.de"))
    document = written(replace(INVOICE, seller=seller, buyer=buyer))
    assert (
        b"<ram:SellerTradeParty><ram:ID>A1</ram:ID>"
        b'<ram:GlobalID schemeID="0088">4000001000005</ram:GlobalID>' in document
    )
    assert b'<ram:ID schemeID="FC">201/113/40209</ram:ID>' in document
    assert b"<ram:PersonName>Einkauf</ram:PersonName>" in document
    assert (
        b"<ram:LineOne>[Seller address line 1]</ram:LineOne><ram:LineTwo>Hinterhaus</ram:LineTwo>"
        b"<ram:LineThree>3. OG</ram:LineThree><ram:CityName>[Seller city]</ram:CityName>"
        b"<ram:CountryID>DE</ram:CountryID>"
        b"<ram:CountrySubDivisionName>Berlin</ram:CountrySubDivisionName>" in document
    )
    back = read_invoice(document).invoice
    assert back.seller == seller
    assert back.buyer == buyer


def test_writes_payment_terms_and_instructions_and_reads_them_back() -> None:
    instructions = PaymentInstructions(
        means_code="58",
        means_text="SEPA credit transfer",
        remittance_information="R-1",
        credit_transfers=(
            CreditTransfer(
                account_id="DE16000000002345678901",
                account_name="Example GmbH",
                provider_id="EXMPDEFFXXX",
            ),
            CreditTransfer(account_id="12345678"),
        ),
        card=PaymentCard(account_number="1234", holder_name="Max Muster"),
        direct_debit=DirectDebit(
            mandate_reference="M-1",
            creditor_id="DE98ZZZ09999999999",
            debited_account_id="DE79000000001234567890",
        ),
    )
    invoice = replace(INVOICE, payment_terms="30 days", payment_instructions=instructions)
    document = written(invoice)
    for expected in (
        b"<ram:CreditorReferenceID>DE98ZZZ09999999999</ram:CreditorReferenceID>"
        b"<ram:PaymentReference>R-1</ram:PaymentReference>",
        b"<ram:SpecifiedTradeSettlementPaymentMeans><ram:TypeCode>58</ram:TypeCode>"
        b"<ram:Information>SEPA credit transfer</ram:Information>"
        b"<ram:ApplicableTradeSettlementFinancialCard><ram:ID>1234</ram:ID>"
        b"<ram:CardholderName>Max Muster</ram:CardholderName>"
        b"</ram:ApplicableTradeSettlementFinancialCard>"
        b"<ram:PayerPartyDebtorFinancialAccount><ram:IBANID>DE79000000001234567890</ram:IBANID>"
        b"</ram:PayerPartyDebtorFinancialAccount>"
        b"<ram:PayeePartyCreditorFinancialAccount><ram:IBANID>DE16000000002345678901</ram:IBANID>"
        b"<ram:AccountName>Example GmbH</ram:AccountName></ram:PayeePartyCreditorFinancialAccount>"
        b"<ram:PayeeSpecifiedCreditorFinancialInstitution><ram:BICID>EXMPDEFFXXX</ram:BICID>"
        b"</ram:PayeeSpecifiedCreditorFinancialInstitution>"
        b"</ram:SpecifiedTradeSettlementPaymentMeans>",
        b"<ram:SpecifiedTradeSettlementPaymentMeans><ram:TypeCode>58</ram:TypeCode>"
        b"<ram:Information>SEPA credit transfer</ram:Information>"
        b"<ram:PayeePartyCreditorFinancialAccount><ram:ProprietaryID>12345678</ram:ProprietaryID>"
        b"</ram:PayeePartyCreditorFinancialAccount></ram:SpecifiedTradeSettlementPaymentMeans>",
        b"<ram:SpecifiedTradePaymentTerms><ram:Description>30 days</ram:Description>"
        b"<ram:DirectDebitMandateID>M-1</ram:DirectDebitMandateID>"
        b"</ram:SpecifiedTradePaymentTerms>",
    ):
        assert expected in document
    assert read_invoice(document).invoice == invoice


def test_xrechnungs_discount_terms_end_with_a_line_feed() -> None:
    """KoSIT case 01.10a's discount terms, whose line feed at the end reading removes."""
    for terms, line_feed in (
        ("#SKONTO#TAGE=7#PROZENT=2.00#\n#SKONTO#TAGE=14#PROZENT=1.00#", "\n"),
        ("#SKONTO#TAGE=7#PROZENT=2.00#\nZahlbar netto gemaess #AGB#", "\n"),
        ("#SKONTO#TAGE=7#PROZENT=2.00#\nZahlbar netto", ""),
    ):
        invoice = replace(INVOICE, specification_id=XRECHNUNG, payment_terms=terms)
        document = write_cii(invoice)
        assert f"<ram:Description>{terms}{line_feed}</ram:Description>".encode() in document
        assert read_invoice(document).invoice == invoice


def test_writes_preceding_invoice_delivery_and_period_and_reads_them_back() -> None:
    invoice = replace(
        INVOICE,
        preceding_invoices=(PrecedingInvoice(number="R-0", issue_date=date(2016, 3, 1)),),
        delivery=Delivery(
            party_name="Example Lager",
            location=Identifier(value="4000001000005", scheme="0088"),
            date=date(2016, 4, 1),
            address_line_1="Lagerstr. 1",
            city="Example City",
            post_code="12345",
            country_code="DE",
        ),
        invoicing_period=Period(start=date(2016, 3, 1), end=date(2016, 3, 31)),
    )
    document = written(invoice)
    for expected in (
        b"<ram:ApplicableHeaderTradeDelivery><ram:ShipToTradeParty>"
        b'<ram:GlobalID schemeID="0088">4000001000005</ram:GlobalID>'
        b"<ram:Name>Example Lager</ram:Name><ram:PostalTradeAddress>"
        b"<ram:PostcodeCode>12345</ram:PostcodeCode><ram:LineOne>Lagerstr. 1</ram:LineOne>"
        b"<ram:CityName>Example City</ram:CityName><ram:CountryID>DE</ram:CountryID>"
        b"</ram:PostalTradeAddress></ram:ShipToTradeParty><ram:ActualDeliverySupplyChainEvent>"
        b'<ram:OccurrenceDateTime><udt:DateTimeString format="102">20160401</udt:DateTimeString>'
        b"</ram:OccurrenceDateTime></ram:ActualDeliverySupplyChainEvent>"
        b"</ram:ApplicableHeaderTradeDelivery>",
        b'<ram:BillingSpecifiedPeriod><ram:StartDateTime><udt:DateTimeString format="102">'
        b"20160301</udt:DateTimeString></ram:StartDateTime><ram:EndDateTime>"
        b'<udt:DateTimeString format="102">20160331</udt:DateTimeString></ram:EndDateTime>'
        b"</ram:BillingSpecifiedPeriod>",
        b"</ram:SpecifiedTradeSettlementHeaderMonetarySummation><ram:InvoiceReferencedDocument>"
        b"<ram:IssuerAssignedID>R-0</ram:IssuerAssignedID><ram:FormattedIssueDateTime>"
        b'<qdt:DateTimeString format="102">20160301</qdt:DateTimeString>'
        b"</ram:FormattedIssueDateTime></ram:InvoiceReferencedDocument>",
    ):
        assert expected in document
    assert read_invoice(document).invoice == invoice


@pytest.mark.parametrize(
    ("invoice", "rule"),
    [
        (
            replace(
                INVOICE,
                payment_instructions=PaymentInstructions(means_text="SEPA"),
                specification_id=XRECHNUNG,
            ),
            "BR-49",
        ),
        (replace(INVOICE, payment_instructions=PaymentInstructions(means_text="SEPA")), "HAFL-XSD"),
        (
            replace(
                INVOICE,
                payment_instructions=PaymentInstructions(
                    means_code="58", credit_transfers=(CreditTransfer(account_name="Example"),)
                ),
            ),
            "BR-50",
        ),
        (
            replace(INVOICE, preceding_invoices=(PrecedingInvoice(issue_date=date(2016, 3, 1)),)),
            "BR-55",
        ),
        (
            replace(
                INVOICE,
                allowances=(AllowanceCharge(amount=Decimal(0), reason="Rabatt"),),
                totals=replace(TOTALS, allowance_total=Decimal(0)),
                specification_id=XRECHNUNG,
            ),
            "BR-32",
        ),
        (
            replace(
                INVOICE,
                allowances=(AllowanceCharge(amount=Decimal(0), reason="Rabatt"),),
                totals=replace(TOTALS, allowance_total=Decimal(0)),
            ),
            "BR-32",
        ),
        (
            replace(INVOICE, delivery=Delivery(city="Example City"), specification_id=XRECHNUNG),
            "BR-57",
        ),
        (replace(INVOICE, delivery=Delivery(city="Example City")), "HAFL-XSD"),
        (
            replace(
                INVOICE, supporting_documents=(SupportingDocument(description="Stundenzettel"),)
            ),
            "BR-52",
        ),
    ],
    ids=[
        "instructions-without-means-code",
        "instructions-without-means-code-factur-x",
        "credit-transfer-without-account",
        "preceding-invoice-without-number",
        "allowance-without-vat-category",
        "allowance-without-vat-category-factur-x",
        "deliver-to-address-without-country",
        "deliver-to-address-without-country-factur-x",
        "supporting-document-without-reference",
    ],
)
def test_the_official_artefacts_refuse_a_group_without_a_term_it_needs(
    invoice: Invoice, rule: str
) -> None:
    """Written, since CII D16B can hold the rest, and refused after writing: payment
    instructions without their means code (BT-81) by BR-49, a credit transfer without its
    account (BT-84) by BR-50, a preceding invoice without its number (BT-25) by BR-55, an
    allowance without its VAT category code (BT-95) by BR-32, a deliver to address without its
    country code (BT-80) by BR-57, a supporting document without its reference (BT-122) by
    BR-52; for EN 16931, Factur-X's XML Schema requires BT-81 and BT-80
    (REQ-004-PRS-F001)."""
    with pytest.raises(InvoiceWriteError, match=rule) as refusal:
        write_cii(invoice)
    assert rule in {finding.rule for finding in refusal.value.findings}
    assert refusal.value.document is not None
    assert read_invoice(refusal.value.document).invoice == invoice


ALLOWANCES_AND_CHARGES = replace(
    INVOICE,
    allowances=(
        AllowanceCharge(
            amount=Decimal("10.00"),
            base_amount=Decimal("200.00"),
            percentage=Decimal(5),
            vat_category_code="S",
            vat_rate=Decimal(7),
            reason="Rabatt",
            reason_code="95",
        ),
        AllowanceCharge(
            amount=Decimal("1.00"), vat_category_code="S", vat_rate=Decimal(7), reason="Skonto"
        ),
    ),
    charges=(
        AllowanceCharge(
            amount=Decimal("4.50"),
            base_amount=Decimal("300.00"),
            percentage=Decimal("1.5"),
            vat_category_code="S",
            vat_rate=Decimal(7),
            reason="Fracht",
            reason_code="FC",
        ),
    ),
    totals=replace(
        TOTALS,
        allowance_total=Decimal("11.00"),
        charge_total=Decimal("4.50"),
        total_without_vat=Decimal("308.36"),
        vat_total=Decimal("21.59"),
        total_with_vat=Decimal("329.95"),
        amount_due=Decimal("329.95"),
    ),
    vat_breakdown=(
        replace(
            INVOICE.vat_breakdown[0], taxable_amount=Decimal("308.36"), tax_amount=Decimal("21.59")
        ),
    ),
)


@pytest.mark.parametrize("specification_id", [EN16931, XRECHNUNG])
def test_writes_allowances_and_charges_and_reads_them_back(specification_id: str) -> None:
    """Handed out: the totals and the VAT breakdown add up with them (BR-CO-11, BR-CO-12,
    BR-S-08)."""
    invoice = replace(ALLOWANCES_AND_CHARGES, specification_id=specification_id)
    document = write_cii(invoice)
    assert (
        b"<ram:SpecifiedTradeAllowanceCharge><ram:ChargeIndicator><udt:Indicator>false"
        b"</udt:Indicator></ram:ChargeIndicator><ram:CalculationPercent>5</ram:CalculationPercent>"
        b"<ram:BasisAmount>200.00</ram:BasisAmount><ram:ActualAmount>10.00</ram:ActualAmount>"
        b"<ram:ReasonCode>95</ram:ReasonCode><ram:Reason>Rabatt</ram:Reason><ram:CategoryTradeTax>"
        b"<ram:TypeCode>VAT</ram:TypeCode><ram:CategoryCode>S</ram:CategoryCode>"
        b"<ram:RateApplicablePercent>7</ram:RateApplicablePercent></ram:CategoryTradeTax>"
        b"</ram:SpecifiedTradeAllowanceCharge>" in document
    )
    assert (
        b"<udt:Indicator>true</udt:Indicator></ram:ChargeIndicator>"
        b"<ram:CalculationPercent>1.5</ram:CalculationPercent>"
        b"<ram:BasisAmount>300.00</ram:BasisAmount><ram:ActualAmount>4.50</ram:ActualAmount>"
        in document
    )
    assert document.index(b"<udt:Indicator>false") < document.index(b"<udt:Indicator>true")
    assert read_invoice(document).invoice == invoice


# REQ-004-PRS-F003: the payee, the tax representative and the parties' remaining terms

PAYEE_AND_REPRESENTATIVE = replace(
    INVOICE,
    seller=replace(
        SELLER,
        legal_registration_id=Identifier(value="[HRA-Eintrag]", scheme="0002"),
        additional_legal_information="Kapitalgesellschaft",
    ),
    payee=Payee(
        name="Example Factoring GmbH",
        identifier=Identifier(value="4000001000005", scheme="0088"),
        legal_registration_id=Identifier(value="HRB 12345", scheme="0002"),
    ),
    tax_representative=TaxRepresentative(
        name="Example Steuervertretung GmbH",
        vat_id="DE123456789",
        address_line_1="Musterstrasse 1",
        address_line_2="Hinterhaus",
        address_line_3="3. OG",
        city="Berlin",
        post_code="10115",
        country_subdivision="Berlin",
        country_code="DE",
    ),
)


@pytest.mark.parametrize("specification_id", [EN16931, XRECHNUNG])
def test_writes_the_payee_and_tax_representative_and_reads_them_back(
    specification_id: str,
) -> None:
    invoice = replace(PAYEE_AND_REPRESENTATIVE, specification_id=specification_id)
    document = write_cii(invoice)
    assert (
        b"<ram:Name>[Seller name]</ram:Name><ram:Description>Kapitalgesellschaft</ram:Description>"
        b'<ram:SpecifiedLegalOrganization><ram:ID schemeID="0002">[HRA-Eintrag]</ram:ID>'
        in document
    )
    assert (
        b"</ram:BuyerTradeParty><ram:SellerTaxRepresentativeTradeParty>"
        b"<ram:Name>Example Steuervertretung GmbH</ram:Name><ram:PostalTradeAddress>"
        b"<ram:PostcodeCode>10115</ram:PostcodeCode><ram:LineOne>Musterstrasse 1</ram:LineOne>"
        b"<ram:LineTwo>Hinterhaus</ram:LineTwo><ram:LineThree>3. OG</ram:LineThree>"
        b"<ram:CityName>Berlin</ram:CityName><ram:CountryID>DE</ram:CountryID>"
        b"<ram:CountrySubDivisionName>Berlin</ram:CountrySubDivisionName></ram:PostalTradeAddress>"
        b'<ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">DE123456789</ram:ID>'
        b"</ram:SpecifiedTaxRegistration></ram:SellerTaxRepresentativeTradeParty>" in document
    )
    assert (
        b"<ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode><ram:PayeeTradeParty>"
        b'<ram:GlobalID schemeID="0088">4000001000005</ram:GlobalID>'
        b"<ram:Name>Example Factoring GmbH</ram:Name><ram:SpecifiedLegalOrganization>"
        b'<ram:ID schemeID="0002">HRB 12345</ram:ID></ram:SpecifiedLegalOrganization>'
        b"</ram:PayeeTradeParty>" in document
    )
    assert read_invoice(document).invoice == invoice


# REQ-004-PRS-F003: the document references

REFERENCES = replace(
    INVOICE,
    project_reference="P-11",
    contract_reference="C-12",
    purchase_order_reference="PO-13",
    sales_order_reference="SO-14",
    receiving_advice_reference="R-15",
    despatch_advice_reference="D-16",
    tender_or_lot_reference="T-17",
    invoiced_object_id=Identifier(value="O-18", scheme="ABZ"),
    buyer_accounting_reference="A-19",
)


@pytest.mark.parametrize("specification_id", [EN16931, XRECHNUNG])
def test_writes_the_document_references_and_reads_them_back(specification_id: str) -> None:
    """In the XML Schema's order, with the project name it requires; the advice references
    without delivery information."""
    invoice = replace(REFERENCES, specification_id=specification_id)
    document = write_cii(invoice)
    assert (
        b"</ram:BuyerTradeParty><ram:SellerOrderReferencedDocument>"
        b"<ram:IssuerAssignedID>SO-14</ram:IssuerAssignedID></ram:SellerOrderReferencedDocument>"
        b"<ram:BuyerOrderReferencedDocument><ram:IssuerAssignedID>PO-13</ram:IssuerAssignedID>"
        b"</ram:BuyerOrderReferencedDocument><ram:ContractReferencedDocument>"
        b"<ram:IssuerAssignedID>C-12</ram:IssuerAssignedID></ram:ContractReferencedDocument>"
        b"<ram:AdditionalReferencedDocument><ram:IssuerAssignedID>T-17</ram:IssuerAssignedID>"
        b"<ram:TypeCode>50</ram:TypeCode></ram:AdditionalReferencedDocument>"
        b"<ram:AdditionalReferencedDocument><ram:IssuerAssignedID>O-18</ram:IssuerAssignedID>"
        b"<ram:TypeCode>130</ram:TypeCode><ram:ReferenceTypeCode>ABZ</ram:ReferenceTypeCode>"
        b"</ram:AdditionalReferencedDocument><ram:SpecifiedProcuringProject><ram:ID>P-11</ram:ID>"
        b"<ram:Name>Project reference</ram:Name></ram:SpecifiedProcuringProject>"
        b"</ram:ApplicableHeaderTradeAgreement>" in document
    )
    assert (
        b"<ram:ApplicableHeaderTradeDelivery><ram:DespatchAdviceReferencedDocument>"
        b"<ram:IssuerAssignedID>D-16</ram:IssuerAssignedID></ram:DespatchAdviceReferencedDocument>"
        b"<ram:ReceivingAdviceReferencedDocument><ram:IssuerAssignedID>R-15</ram:IssuerAssignedID>"
        b"</ram:ReceivingAdviceReferencedDocument></ram:ApplicableHeaderTradeDelivery>" in document
    )
    assert (
        b"<ram:ReceivableSpecifiedTradeAccountingAccount><ram:ID>A-19</ram:ID>"
        b"</ram:ReceivableSpecifiedTradeAccountingAccount></ram:ApplicableHeaderTradeSettlement>"
        in document
    )
    assert read_invoice(document).invoice == invoice


@pytest.mark.parametrize("specification_id", [EN16931, XRECHNUNG])
def test_writes_the_supporting_documents_and_reads_them_back(specification_id: str) -> None:
    """After BT-17's and BT-18's additional documents, each with the type code 916, in the XML
    Schema's order."""
    invoice = replace(
        REFERENCES,
        specification_id=specification_id,
        supporting_documents=(
            SupportingDocument(
                reference="A-1",
                description="Stundenzettel",
                external_location="https://example.com/a-1.pdf",
            ),
            SupportingDocument(reference="A-2"),
        ),
    )
    document = write_cii(invoice)
    assert (
        b"<ram:ReferenceTypeCode>ABZ</ram:ReferenceTypeCode></ram:AdditionalReferencedDocument>"
        b"<ram:AdditionalReferencedDocument><ram:IssuerAssignedID>A-1</ram:IssuerAssignedID>"
        b"<ram:URIID>https://example.com/a-1.pdf</ram:URIID><ram:TypeCode>916</ram:TypeCode>"
        b"<ram:Name>Stundenzettel</ram:Name></ram:AdditionalReferencedDocument>"
        b"<ram:AdditionalReferencedDocument><ram:IssuerAssignedID>A-2</ram:IssuerAssignedID>"
        b"<ram:TypeCode>916</ram:TypeCode></ram:AdditionalReferencedDocument>"
        b"<ram:SpecifiedProcuringProject>" in document
    )
    assert read_invoice(document).invoice == invoice


def test_two_supporting_documents_with_descriptions_still_warn_with_cii_sr_475() -> None:
    """CEN's CII-SR-475 counts the descriptions of all supporting documents, where EN 16931 gives
    each its own (ITEM-006); once a release counts them per document, this test goes."""
    invoice = replace(
        INVOICE,
        supporting_documents=(
            SupportingDocument(reference="A-1", description="Stundenzettel"),
            SupportingDocument(reference="A-2", description="Lieferschein"),
        ),
    )
    findings = validate(write_cii(invoice))
    assert [(f.rule, f.flag) for f in findings if f.rule == "CII-SR-475"] == [
        ("CII-SR-475", "warning")
    ]


def test_the_advice_references_follow_the_delivery_information() -> None:
    invoice = replace(REFERENCES, delivery=Delivery(party_name="Lager Nord", country_code="DE"))
    document = write_cii(invoice)
    assert document.index(b"</ram:ShipToTradeParty>") < document.index(
        b"<ram:DespatchAdviceReferencedDocument>"
    )
    assert read_invoice(document).invoice == invoice


# REQ-004-PRS-F003: the VAT point date and its code

TAX_POINT_AFTER = b"<ram:CategoryCode>S</ram:CategoryCode>"
TAX_POINT_BEFORE = (
    b"<ram:RateApplicablePercent>7</ram:RateApplicablePercent></ram:ApplicableTradeTax>"
)


@pytest.mark.parametrize("specification_id", [EN16931, XRECHNUNG])
def test_writes_the_vat_point_date_and_reads_it_back(specification_id: str) -> None:
    """In the VAT breakdown's ram:ApplicableTradeTax, after its category code."""
    invoice = replace(INVOICE, specification_id=specification_id, vat_point_date=date(2016, 4, 1))
    document = write_cii(invoice)
    assert (
        TAX_POINT_AFTER
        + b'<ram:TaxPointDate><udt:DateString format="102">20160401</udt:DateString>'
        b"</ram:TaxPointDate>" + TAX_POINT_BEFORE in document
    )
    assert document.count(b"<ram:TaxPointDate>") == 1
    assert read_invoice(document).invoice == invoice


@pytest.mark.parametrize(
    ("code", "written"),
    [("3", b"5"), ("35", b"29"), ("432", b"72")],
    ids=["date-of-invoice", "date-of-delivery", "paid-to-date"],
)
def test_writes_a_vat_point_date_code_as_ciis(code: str, written: bytes) -> None:
    """EN 16931's codes of UNTDID 2005 as CII's of UNTDID 2475 (REQ-001-URS-NF001)."""
    invoice = replace(INVOICE, vat_point_date_code=code)
    document = write_cii(invoice)
    assert (
        TAX_POINT_AFTER
        + b"<ram:DueDateTypeCode>"
        + written
        + b"</ram:DueDateTypeCode>"
        + TAX_POINT_BEFORE
        in document
    )
    assert read_invoice(document).invoice == invoice


def test_a_cii_file_with_en_16931s_code_is_written_with_ciis() -> None:
    """A CII 35, which CEN's rules reject there, reads as EN 16931's code and is written as CII's
    29 (REQ-001-URS-NF001)."""
    header = b"<ram:BasisAmount>314.86</ram:BasisAmount><ram:CategoryCode>S</ram:CategoryCode>"
    document = written(INVOICE)
    assert document.count(header) == 1
    data = document.replace(header, header + b"<ram:DueDateTypeCode>35</ram:DueDateTypeCode>")
    invoice = read_invoice(data).invoice
    assert invoice.vat_point_date_code == "35"
    assert b"<ram:DueDateTypeCode>29</ram:DueDateTypeCode>" in write_cii(invoice)


def test_writes_another_vat_point_date_code_as_it_is() -> None:
    """And refused after writing by CEN's code list (BR-CL-06)."""
    invoice = replace(INVOICE, vat_point_date_code="ZZ")
    with pytest.raises(InvoiceWriteError, match="BR-CL-06") as refusal:
        write_cii(invoice)
    assert refusal.value.document is not None
    assert b"<ram:DueDateTypeCode>ZZ</ram:DueDateTypeCode>" in refusal.value.document
    assert read_invoice(refusal.value.document).invoice == invoice


def test_a_vat_point_date_with_its_code_fails_br_co_03() -> None:
    """Written as the model holds it, and refused after writing (REQ-004-PRS-F001)."""
    invoice = replace(INVOICE, vat_point_date=date(2016, 4, 1), vat_point_date_code="3")
    with pytest.raises(InvoiceWriteError, match="BR-CO-03") as refusal:
        write_cii(invoice)
    assert refusal.value.document is not None
    assert read_invoice(refusal.value.document).invoice == invoice


# REQ-004-PRS-F003: a line's price and item details

LINE_DETAILS = replace(
    LINE,
    note="Lieferung direkt vom Verlag",
    object_id=Identifier(value="ANG987654321", scheme="ABZ"),
    purchase_order_line_reference="6171175.2",
    buyer_accounting_reference="4711-K",
    period=Period(start=date(2016, 7, 1), end=date(2016, 12, 31)),
    allowances=(
        AllowanceCharge(
            amount=Decimal("14.44"),
            base_amount=Decimal("288.79"),
            percentage=Decimal(5),
            reason="Rabatt",
            reason_code="95",
        ),
        AllowanceCharge(amount=Decimal("1.00"), reason="Treue"),
    ),
    # The charge makes up for the allowances, so that the line net amount (BT-131) stays as
    # EN 16931's line calculation gives it (PEPPOL-EN16931-R120).
    charges=(AllowanceCharge(amount=Decimal("15.44"), reason="Verpackung", reason_code="ABL"),),
    price_discount=Decimal("11.21"),
    gross_price=Decimal("300.00"),
    base_quantity=Decimal(1),
    base_quantity_unit_code="XPP",
    item_description="Zeitschrift Inland",
    seller_item_id="246",
    buyer_item_id="B-246",
    standard_item_id=Identifier(value="4000001000005", scheme="0160"),
    item_classifications=(
        ItemClassification(value="0721-880X", scheme="IB"),
        ItemClassification(value="49021000", scheme="HS", scheme_version="2022"),
    ),
    item_country_of_origin="DE",
    item_attributes=(
        ItemAttribute(name="Farbe", value="Rot"),
        ItemAttribute(name="Größe", value="XL"),
    ),
)


@pytest.mark.parametrize("specification_id", [EN16931, XRECHNUNG])
def test_writes_a_lines_price_and_item_details_and_reads_them_back(specification_id: str) -> None:
    """The base quantity in both prices; the item's terms in the XML Schema's order; the period
    after the line's VAT; the purchase order line before the prices, the object identifier and
    the accounting reference after the line's totals."""
    invoice = replace(
        INVOICE, specification_id=specification_id, lines=(LINE_DETAILS, *INVOICE.lines[1:])
    )
    document = write_cii(invoice)
    assert (
        b"<ram:LineID>Zeitschrift [...]</ram:LineID><ram:IncludedNote>"
        b"<ram:Content>Lieferung direkt vom Verlag</ram:Content></ram:IncludedNote>" in document
    )
    assert (
        b'<ram:SpecifiedTradeProduct><ram:GlobalID schemeID="0160">4000001000005</ram:GlobalID>'
        b"<ram:SellerAssignedID>246</ram:SellerAssignedID>"
        b"<ram:BuyerAssignedID>B-246</ram:BuyerAssignedID><ram:Name>Zeitschrift [...]</ram:Name>"
        b"<ram:Description>Zeitschrift Inland</ram:Description>"
        b"<ram:ApplicableProductCharacteristic><ram:Description>Farbe</ram:Description>"
        b"<ram:Value>Rot</ram:Value></ram:ApplicableProductCharacteristic>"
        b"<ram:ApplicableProductCharacteristic><ram:Description>"
        + "Größe".encode()
        + b"</ram:Description><ram:Value>XL</ram:Value></ram:ApplicableProductCharacteristic>"
        b"<ram:DesignatedProductClassification>"
        b'<ram:ClassCode listID="IB">0721-880X</ram:ClassCode>'
        b"</ram:DesignatedProductClassification><ram:DesignatedProductClassification>"
        b'<ram:ClassCode listID="HS" listVersionID="2022">49021000</ram:ClassCode>'
        b"</ram:DesignatedProductClassification>"
        b"<ram:OriginTradeCountry><ram:ID>DE</ram:ID></ram:OriginTradeCountry>"
        b"</ram:SpecifiedTradeProduct>" in document
    )
    assert (
        b"<ram:GrossPriceProductTradePrice><ram:ChargeAmount>300.00</ram:ChargeAmount>"
        b'<ram:BasisQuantity unitCode="XPP">1</ram:BasisQuantity><ram:AppliedTradeAllowanceCharge>'
        b"<ram:ChargeIndicator><udt:Indicator>false</udt:Indicator></ram:ChargeIndicator>"
        b"<ram:ActualAmount>11.21</ram:ActualAmount></ram:AppliedTradeAllowanceCharge>"
        b"</ram:GrossPriceProductTradePrice><ram:NetPriceProductTradePrice>"
        b"<ram:ChargeAmount>288.79</ram:ChargeAmount>"
        b'<ram:BasisQuantity unitCode="XPP">1</ram:BasisQuantity></ram:NetPriceProductTradePrice>'
        in document
    )
    assert (
        b"<ram:RateApplicablePercent>7</ram:RateApplicablePercent></ram:ApplicableTradeTax>"
        b'<ram:BillingSpecifiedPeriod><ram:StartDateTime><udt:DateTimeString format="102">'
        b"20160701</udt:DateTimeString></ram:StartDateTime><ram:EndDateTime>"
        b'<udt:DateTimeString format="102">20161231</udt:DateTimeString></ram:EndDateTime>'
        b"</ram:BillingSpecifiedPeriod>" in document
    )
    assert (
        b"</ram:BillingSpecifiedPeriod><ram:SpecifiedTradeAllowanceCharge><ram:ChargeIndicator>"
        b"<udt:Indicator>false</udt:Indicator></ram:ChargeIndicator>"
        b"<ram:CalculationPercent>5</ram:CalculationPercent>"
        b"<ram:BasisAmount>288.79</ram:BasisAmount><ram:ActualAmount>14.44</ram:ActualAmount>"
        b"<ram:ReasonCode>95</ram:ReasonCode><ram:Reason>Rabatt</ram:Reason>"
        b"</ram:SpecifiedTradeAllowanceCharge><ram:SpecifiedTradeAllowanceCharge>"
        b"<ram:ChargeIndicator><udt:Indicator>false</udt:Indicator></ram:ChargeIndicator>"
        b"<ram:ActualAmount>1.00</ram:ActualAmount><ram:Reason>Treue</ram:Reason>"
        b"</ram:SpecifiedTradeAllowanceCharge><ram:SpecifiedTradeAllowanceCharge>"
        b"<ram:ChargeIndicator><udt:Indicator>true</udt:Indicator></ram:ChargeIndicator>"
        b"<ram:ActualAmount>15.44</ram:ActualAmount><ram:ReasonCode>ABL</ram:ReasonCode>"
        b"<ram:Reason>Verpackung</ram:Reason></ram:SpecifiedTradeAllowanceCharge>"
        b"<ram:SpecifiedTradeSettlementLineMonetarySummation>" in document
    )
    assert (
        b"<ram:SpecifiedLineTradeAgreement><ram:BuyerOrderReferencedDocument>"
        b"<ram:LineID>6171175.2</ram:LineID></ram:BuyerOrderReferencedDocument>"
        b"<ram:GrossPriceProductTradePrice>" in document
    )
    assert (
        b"</ram:SpecifiedTradeSettlementLineMonetarySummation><ram:AdditionalReferencedDocument>"
        b"<ram:IssuerAssignedID>ANG987654321</ram:IssuerAssignedID><ram:TypeCode>130</ram:TypeCode>"
        b"<ram:ReferenceTypeCode>ABZ</ram:ReferenceTypeCode></ram:AdditionalReferencedDocument>"
        b"<ram:ReceivableSpecifiedTradeAccountingAccount><ram:ID>4711-K</ram:ID>"
        b"</ram:ReceivableSpecifiedTradeAccountingAccount></ram:SpecifiedLineTradeSettlement>"
        in document
    )
    assert read_invoice(document).invoice == invoice


def test_a_line_period_that_ends_before_it_starts_fails_br_30() -> None:
    """Written as the model holds it, and refused after writing (REQ-004-PRS-F001)."""
    period = Period(start=date(2016, 12, 31), end=date(2016, 1, 1))
    invoice = replace(INVOICE, lines=(replace(LINE, period=period), *INVOICE.lines[1:]))
    with pytest.raises(InvoiceWriteError, match="BR-30") as refusal:
        write_cii(invoice)
    assert "BR-30" in {finding.rule for finding in refusal.value.findings}
    assert refusal.value.document is not None
    assert read_invoice(refusal.value.document).invoice == invoice


@pytest.mark.parametrize(
    ("classification", "written"),
    [
        (ItemClassification(value="49021000"), b"<ram:ClassCode>49021000</ram:ClassCode>"),
        (
            ItemClassification(value="49021000", scheme_version="2022"),
            b'<ram:ClassCode listVersionID="2022">49021000</ram:ClassCode>',
        ),
    ],
    ids=["without-a-scheme", "a-version-without-a-scheme"],
)
def test_an_item_classification_without_a_scheme_fails_br_65(
    classification: ItemClassification, written: bytes
) -> None:
    """Written without listID, and refused after writing (REQ-004-PRS-F001)."""
    line = replace(LINE, item_classifications=(classification,))
    invoice = replace(INVOICE, lines=(line, *INVOICE.lines[1:]))
    with pytest.raises(InvoiceWriteError, match="BR-65") as refusal:
        write_cii(invoice)
    assert refusal.value.document is not None
    assert written in refusal.value.document
    assert read_invoice(refusal.value.document).invoice == invoice


@pytest.mark.parametrize(
    ("specification_id", "rules"),
    [(EN16931, {"HAFL-XSD"}), (XRECHNUNG, {"BR-54"})],
    ids=["en16931", "xrechnung"],
)
@pytest.mark.parametrize(
    ("attribute", "written"),
    [
        (ItemAttribute(name="Farbe"), b"<ram:Description>Farbe</ram:Description>"),
        (ItemAttribute(value="Rot"), b"<ram:Value>Rot</ram:Value>"),
    ],
    ids=["without-a-value", "without-a-name"],
)
def test_an_item_attribute_without_its_name_or_value_fails_br_54(
    specification_id: str, rules: set[str], attribute: ItemAttribute, written: bytes
) -> None:
    """Written without the missing one, and refused after writing (REQ-004-PRS-F001); for
    EN 16931, Factur-X's XML Schema, which requires both, refuses it before the rules run."""
    line = replace(LINE, item_attributes=(attribute,))
    invoice = replace(INVOICE, specification_id=specification_id, lines=(line, *INVOICE.lines[1:]))
    with pytest.raises(InvoiceWriteError) as refusal:
        write_cii(invoice)
    assert rules <= {finding.rule for finding in refusal.value.findings}
    assert refusal.value.document is not None
    assert (
        b"<ram:ApplicableProductCharacteristic>"
        + written
        + b"</ram:ApplicableProductCharacteristic>"
        in refusal.value.document
    )
    assert read_invoice(refusal.value.document).invoice == invoice


def test_a_base_quantity_without_a_gross_price_is_the_net_prices() -> None:
    line = replace(LINE, base_quantity=Decimal(1), base_quantity_unit_code="XPP")
    invoice = replace(INVOICE, lines=(line, *INVOICE.lines[1:]))
    document = write_cii(invoice)
    assert b"GrossPriceProductTradePrice" not in document
    assert (
        b"<ram:NetPriceProductTradePrice><ram:ChargeAmount>288.79</ram:ChargeAmount>"
        b'<ram:BasisQuantity unitCode="XPP">1</ram:BasisQuantity></ram:NetPriceProductTradePrice>'
        in document
    )
    assert read_invoice(document).invoice == invoice


def test_identifiers_in_another_order_are_written_as_the_schema_wants() -> None:
    seller = replace(
        SELLER,
        identifiers=(Identifier(value="4000001000005", scheme="0088"), Identifier(value="A1")),
    )
    back = read_invoice(written(replace(INVOICE, seller=seller))).invoice.seller
    assert back is not None
    assert back.identifiers == seller.identifiers[::-1]


def test_amounts_keep_their_digits() -> None:
    invoice = replace(INVOICE, totals=replace(TOTALS, total_with_vat=Decimal("336.900")))
    document = written(invoice)
    assert b"<ram:GrandTotalAmount>336.900</ram:GrandTotalAmount>" in document
    totals = read_invoice(document).invoice.totals
    assert totals is not None
    assert str(totals.total_with_vat) == "336.900"


def test_bt_111_with_its_own_value_reads_back() -> None:
    invoice = replace(
        INVOICE,
        tax_currency_code="GBP",
        totals=replace(TOTALS, vat_total_in_tax_currency=Decimal("18.71")),
    )
    back = read_invoice(written(invoice)).invoice
    assert back == invoice
    assert back.totals is not None
    assert (back.totals.vat_total, back.totals.vat_total_in_tax_currency) == (
        Decimal("22.04"),
        Decimal("18.71"),
    )


# The third review of 2026-11-01


@pytest.mark.parametrize(
    ("value", "text"),
    [(Decimal("9" * 1000), "9" * 1000), (Decimal("0E+2000"), "0"), (Decimal("0E-5"), "0.00000")],
    ids=["1000-digits", "zero-with-a-large-exponent", "zero-with-places"],
)
def test_numbers_up_to_the_limit_are_written(value: Decimal, text: str) -> None:
    """REQ-004-PRS-F001: the limit is more than 1,000 digits in plain notation."""
    document = written(replace(INVOICE, totals=replace(TOTALS, prepaid_amount=value)))
    assert f"<ram:TotalPrepaidAmount>{text}</ram:TotalPrepaidAmount>".encode() in document


def test_en16931_runs_ferds_rules_of_the_profile_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-004-PRS-F005: for EN 16931, FeRD's Factur-X rules besides CEN's; not for XRechnung."""
    calls: list[tuple[str, ...]] = []

    def rules(data: bytes, *also: str, timeout: float | None = None) -> list[object]:
        calls.append(also)
        return []

    monkeypatch.setattr("haflinger.write.check_rules", rules)
    write_cii(INVOICE)
    with contextlib.suppress(InvoiceWriteError):
        write_cii(replace(INVOICE, specification_id=XRECHNUNG))
    assert calls == [("Factur-X EN 16931",), ()]


def test_written_invoices_pass_ferds_rules() -> None:
    from haflinger.validation import FACTUR_X_EN16931, check_rules

    findings = check_rules(write_cii(INVOICE), FACTUR_X_EN16931)
    assert [f for f in findings if f.flag in ("fatal", "error")] == []

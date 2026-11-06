"""Reading CII and UBL: refusals, reading choices and exact values.

REQ-003-PRS-F001 to REQ-003-PRS-F003, REQ-003-PRS-F006, REQ-003-PRS-F008; REQ-001-PRS-F004,
REQ-001-PRS-F005, REQ-001-PRS-NF001 and REQ-001-PRS-NF003 for reading. Most inputs are KoSIT
case 01.01a with one change.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from haflinger import (
    AllowanceCharge,
    Contact,
    CreditTransfer,
    Delivery,
    DirectDebit,
    Identifier,
    Invoice,
    InvoiceLine,
    InvoiceReadError,
    Note,
    PaymentCard,
    PaymentInstructions,
    Period,
    PrecedingInvoice,
    ReadResult,
    read_invoice,
)

ROOT = Path(__file__).resolve().parents[2]
STANDARD = ROOT / "tests/data/kosit-testsuite/instances/standard"
CII = (STANDARD / "01.01a-INVOICE_uncefact.xml").read_bytes()
UBL = (STANDARD / "01.01a-INVOICE_ubl.xml").read_bytes()

GRAND_TOTAL = b"<ram:GrandTotalAmount>336.9</ram:GrandTotalAmount>"
TAX_TOTAL = b'<ram:TaxTotalAmount currencyID="EUR">22.04</ram:TaxTotalAmount>'
ISSUE_DATE = b'<udt:DateTimeString format="102">20160404</udt:DateTimeString>'
PAYMENT_TERMS = b"<ram:Description>Zahlbar sofort ohne Abzug.</ram:Description>"
BUYER_REFERENCE = b"<ram:BuyerReference>04011000-12345-03</ram:BuyerReference>"
UBL_TAX_TOTAL_START = b"<cac:TaxTotal>"
UBL_TAX_AMOUNT = b'<cbc:TaxAmount currencyID="EUR">22.04</cbc:TaxAmount>'


def edit(data: bytes, old: bytes, new: bytes) -> bytes:
    """`data` with its single occurrence of `old` replaced by `new`."""
    assert data.count(old) == 1, old
    return data.replace(old, new)


def due_dates(*values: str) -> bytes:
    terms = b"".join(
        b"<ram:SpecifiedTradePaymentTerms><ram:DueDateDateTime>"
        b'<udt:DateTimeString format="102">' + value.encode() + b"</udt:DateTimeString>"
        b"</ram:DueDateDateTime></ram:SpecifiedTradePaymentTerms>"
        for value in values
    )
    return edit(
        CII,
        b"<ram:SpecifiedTradeSettlementHeaderMonetarySummation>",
        terms + b"<ram:SpecifiedTradeSettlementHeaderMonetarySummation>",
    )


def refusal(data: bytes, **kwargs: int) -> str:
    with pytest.raises(InvoiceReadError) as error:
        read_invoice(data, **kwargs)
    return str(error.value)


# REQ-003-PRS-F001: one entry point


def test_reads_cii_and_ubl_with_their_syntax() -> None:
    cii, ubl = read_invoice(CII), read_invoice(UBL)
    assert isinstance(cii, ReadResult)
    assert (cii.invoice.syntax, ubl.invoice.syntax) == ("cii", "ubl")
    assert cii.invoice.number == ubl.invoice.number == "123456XX"
    assert cii.findings == ubl.findings == ()


def test_reads_ubl_with_a_prefixed_root_and_with_a_default_namespace() -> None:
    assert b"<ubl:Invoice " in UBL
    default = UBL.replace(b"<ubl:Invoice ", b"<Invoice ").replace(b"</ubl:Invoice>", b"</Invoice>")
    default = edit(default, b'xmlns:ubl="', b'xmlns="')
    assert read_invoice(default).invoice == read_invoice(UBL).invoice


# REQ-003-PRS-F002: reading choices


def test_ubl_note_with_a_subject_code() -> None:
    data = edit(UBL, b"<cbc:Note>#ADU#Es gelten", b"<cbc:Note>#AAI#Es gelten")
    note = read_invoice(data).invoice.notes[0]
    assert note == Note(
        subject_code="AAI",
        text="Es gelten unsere Allgem. Geschäftsbedingungen, die Sie unter […] finden.",
    )


def test_ubl_note_without_a_subject_code() -> None:
    data = edit(UBL, b"<cbc:Note>#ADU#Es gelten", b"<cbc:Note>Es gelten")
    assert read_invoice(data).invoice.notes[0].subject_code is None


def test_cii_vat_total_without_currency_is_bt_110() -> None:
    data = edit(CII, TAX_TOTAL, b"<ram:TaxTotalAmount>22.04</ram:TaxTotalAmount>")
    result = read_invoice(data)
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total == Decimal("22.04")
    assert result.findings == ()


def test_cii_vat_total_in_a_third_currency_is_dropped() -> None:
    usd = b'<ram:TaxTotalAmount currencyID="USD">25.00</ram:TaxTotalAmount>'
    result = read_invoice(edit(CII, TAX_TOTAL, TAX_TOTAL + usd))
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total == Decimal("22.04")
    assert result.invoice.totals.vat_total_in_tax_currency is None
    [finding] = result.findings
    assert (finding.rule, finding.flag) == ("HAFL-DROPPED", "warning")
    assert "BT-110" in finding.text
    assert "USD" in finding.text
    assert finding.location.endswith("ram:TaxTotalAmount[2]")


def test_ubl_vat_total_in_a_third_currency_is_dropped() -> None:
    usd = b'<cac:TaxTotal><cbc:TaxAmount currencyID="USD">25.00</cbc:TaxAmount></cac:TaxTotal>'
    result = read_invoice(edit(UBL, UBL_TAX_TOTAL_START, usd + UBL_TAX_TOTAL_START))
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total == Decimal("22.04")
    assert len(result.invoice.vat_breakdown) == 1
    [finding] = result.findings
    assert finding.rule == "HAFL-DROPPED"
    assert "USD" in finding.text


def test_cii_second_vat_total_in_one_currency_is_dropped() -> None:
    again = b'<ram:TaxTotalAmount currencyID="EUR">99.99</ram:TaxTotalAmount>'
    result = read_invoice(edit(CII, TAX_TOTAL, TAX_TOTAL + again))
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total == Decimal("22.04")
    [finding] = result.findings
    assert finding.rule == "HAFL-DROPPED"
    assert "BT-110" in finding.text


def test_ubl_second_vat_total_in_one_currency_is_dropped() -> None:
    again = b'<cac:TaxTotal><cbc:TaxAmount currencyID="EUR">99.99</cbc:TaxAmount></cac:TaxTotal>'
    result = read_invoice(
        edit(UBL, b"<cac:LegalMonetaryTotal>", again + b"<cac:LegalMonetaryTotal>")
    )
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total == Decimal("22.04")
    [finding] = result.findings
    assert finding.rule == "HAFL-DROPPED"
    assert "BT-110" in finding.text


def test_repeated_due_date_reads_the_first_and_drops_the_rest() -> None:
    result = read_invoice(due_dates("20181120", "20181114"))
    assert result.invoice.due_date == date(2018, 11, 20)
    [finding] = result.findings
    assert (finding.rule, finding.flag) == ("HAFL-DROPPED", "warning")
    assert "BT-9" in finding.text
    assert "20181114" in finding.text


def test_whitespace_around_a_value_is_removed() -> None:
    data = edit(CII, b"<ram:ID>123456XX</ram:ID>", b"<ram:ID>\r\n  123456XX\t </ram:ID>")
    assert read_invoice(data).invoice.number == "123456XX"


def test_an_element_holding_only_whitespace_is_missing() -> None:
    data = edit(CII, BUYER_REFERENCE, b"<ram:BuyerReference> \r\n\t </ram:BuyerReference>")
    result = read_invoice(data)
    assert result.invoice.buyer_reference is None
    assert result.findings == ()


def test_a_number_in_exponent_notation_is_missing_with_a_finding() -> None:
    data = edit(CII, GRAND_TOTAL, b"<ram:GrandTotalAmount>1E+2</ram:GrandTotalAmount>")
    result = read_invoice(data)
    assert result.invoice.totals is not None
    assert result.invoice.totals.total_with_vat is None
    [finding] = result.findings
    assert (finding.rule, finding.flag) == ("HAFL-VALUE", "error")
    assert "BT-112" in finding.text
    assert "1E+2" in finding.text
    assert finding.location.endswith("ram:GrandTotalAmount")


def test_a_cii_date_in_iso_form_is_missing_with_a_finding() -> None:
    data = edit(
        CII, ISSUE_DATE, b'<udt:DateTimeString format="102">2026-10-30</udt:DateTimeString>'
    )
    result = read_invoice(data)
    assert result.invoice.issue_date is None
    [finding] = result.findings
    assert finding.rule == "HAFL-VALUE"
    assert "BT-2" in finding.text


@pytest.mark.parametrize(
    "element",
    [
        b'<udt:DateTimeString format="610">201604</udt:DateTimeString>',
        b"<udt:DateTimeString>20160404</udt:DateTimeString>",
        b'<udt:DateTimeString format="102">20160231</udt:DateTimeString>',
    ],
)
def test_a_cii_date_not_in_format_102_is_missing_with_a_finding(element: bytes) -> None:
    result = read_invoice(edit(CII, ISSUE_DATE, element))
    assert result.invoice.issue_date is None
    assert [finding.rule for finding in result.findings] == ["HAFL-VALUE"]


@pytest.mark.parametrize("value", [b"20160404", b"2016-04-04Z", b"2016-4-4"])
def test_a_ubl_date_not_in_iso_form_is_missing_with_a_finding(value: bytes) -> None:
    data = edit(
        UBL,
        b"<cbc:IssueDate>2016-04-04</cbc:IssueDate>",
        b"<cbc:IssueDate>" + value + b"</cbc:IssueDate>",
    )
    result = read_invoice(data)
    assert result.invoice.issue_date is None
    assert [finding.rule for finding in result.findings] == ["HAFL-VALUE"]


def test_findings_come_in_document_order() -> None:
    quantity = b'<ram:BilledQuantity unitCode="XPP">1</ram:BilledQuantity>'
    data = CII.replace(quantity, b'<ram:BilledQuantity unitCode="XPP">one</ram:BilledQuantity>', 1)
    data = edit(
        data, ISSUE_DATE, b'<udt:DateTimeString format="102">2016-04-04</udt:DateTimeString>'
    )
    data = edit(data, GRAND_TOTAL, b"<ram:GrandTotalAmount>n/a</ram:GrandTotalAmount>")
    terms = ["BT-2", "BT-129", "BT-112"]
    findings = read_invoice(data).findings
    assert len(findings) == len(terms)
    for finding, term in zip(findings, terms, strict=True):
        assert term in finding.text


# REQ-003-PRS-F003: missing terms


def test_an_invoice_without_lines_reads_without_findings() -> None:
    start = CII.index(b"<ram:IncludedSupplyChainTradeLineItem>")
    end = CII.rindex(b"</ram:IncludedSupplyChainTradeLineItem>") + len(
        b"</ram:IncludedSupplyChainTradeLineItem>"
    )
    result = read_invoice(CII[:start] + CII[end:])
    assert result.invoice.lines == ()
    assert result.invoice.number == "123456XX"
    assert result.findings == ()


def test_an_invoice_without_parties_and_totals_reads_without_findings() -> None:
    start = CII.index(b"<ram:ApplicableHeaderTradeAgreement>")
    end = CII.index(b"</ram:ApplicableHeaderTradeAgreement>") + len(
        b"</ram:ApplicableHeaderTradeAgreement>"
    )
    data = CII[:start] + CII[end:]
    start = data.index(b"<ram:SpecifiedTradeSettlementHeaderMonetarySummation>")
    end = data.index(b"</ram:SpecifiedTradeSettlementHeaderMonetarySummation>") + len(
        b"</ram:SpecifiedTradeSettlementHeaderMonetarySummation>"
    )
    result = read_invoice(data[:start] + data[end:])
    assert (result.invoice.seller, result.invoice.buyer, result.invoice.totals) == (
        None,
        None,
        None,
    )
    assert result.findings == ()


# REQ-003-PRS-F006: refusals


def test_refuses_xml_that_is_not_well_formed() -> None:
    assert "well-formed" in refusal(CII[:-20])


@pytest.mark.parametrize("prefix", [b"", b"\x00" * 100, b"junk\r\n" * 100])
def test_detects_a_pdf_within_the_first_1024_bytes(prefix: bytes) -> None:
    """Read as a PDF, not as XML; this one is broken (the extra's absence: test_pdf)."""
    assert "isn't a readable PDF" in refusal(prefix + b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n")


DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>'


@pytest.mark.parametrize(
    "doctype",
    [
        b"<!DOCTYPE rsm:CrossIndustryInvoice [<!ELEMENT rsm:CrossIndustryInvoice ANY>]>",
        b'<!DOCTYPE rsm:CrossIndustryInvoice [<!ENTITY seller "Example GmbH">]>',
        b'<!DOCTYPE rsm:CrossIndustryInvoice [<!ENTITY seller SYSTEM "file:///etc/passwd">]>',
    ],
    ids=["internal DTD", "entity", "external entity"],
)
def test_refuses_dtds_and_entities(doctype: bytes) -> None:
    data = edit(CII, DECLARATION, DECLARATION + doctype)
    data = (
        edit(data, b"<ram:Name>[Seller name]</ram:Name>", b"<ram:Name>&seller;</ram:Name>")
        if b"ENTITY" in doctype
        else data
    )
    reason = refusal(data)
    assert "DTD" in reason or "entit" in reason


def test_refuses_an_entity_expansion() -> None:
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaaaaaaaa">'
        b'<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]><x>&b;</x>'
    )
    reason = refusal(bomb)
    assert "DTD" in reason or "entit" in reason


@pytest.mark.parametrize(
    ("data", "name"),
    [
        (
            b'<rsm:CrossIndustryDocument xmlns:rsm="urn:ferd:CrossIndustryDocument:invoice:1p0"/>',
            "ZUGFeRD 1.0",
        ),
        (
            b'<p:FatturaElettronica versione="FPR12"'
            b' xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"/>',
            "FatturaPA",
        ),
    ],
)
def test_refuses_formats_it_does_not_read_by_name(data: bytes, name: str) -> None:
    assert name in refusal(data)


@pytest.mark.parametrize(
    "data",
    [
        b"<Invoice/>",
        b'<Invoice xmlns="urn:example:other"/>',
        b'<Order xmlns="urn:oasis:names:specification:ubl:schema:xsd:Order-2"/>',
    ],
)
def test_refuses_other_root_elements(data: bytes) -> None:
    assert "root element" in refusal(data)


@pytest.mark.parametrize("data", [CII, UBL], ids=["cii", "ubl"])
def test_refuses_another_edition(data: bytes) -> None:
    old = b"urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
    assert "2026" in refusal(edit(data, old, b"urn:cen.eu:en16931:2026"))


def test_reads_an_invoice_that_names_no_edition_as_2017() -> None:
    old = b"urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
    result = read_invoice(edit(CII, old, b"urn:example:other"))
    assert result.invoice.specification_id == "urn:example:other"
    assert result.invoice.edition is None


def test_refuses_input_larger_than_max_size() -> None:
    reason = refusal(CII, max_size=len(CII) - 1)
    assert f"{len(CII) - 1:,}" in reason


def test_reads_input_as_large_as_max_size() -> None:
    assert read_invoice(CII, max_size=len(CII)).invoice.number == "123456XX"


def test_default_max_size_is_100_mib() -> None:
    reason = refusal(b" " * (100 * 1024 * 1024 + 1))
    assert "104,857,600" in reason


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\x00",
        b"\xff\xfe<\x00",
        b'<?xml version="1.0" encoding="no-such-encoding"?><x/>',
        b"<x>\xff</x>",
        bytes(range(256)),
    ],
)
def test_refuses_odd_input_with_invoice_read_error_only(data: bytes) -> None:
    refusal(data)


# REQ-003-PRS-F008: reading doesn't validate


def test_a_wrong_total_reads_as_written_without_findings() -> None:
    data = edit(CII, GRAND_TOTAL, b"<ram:GrandTotalAmount>336.91</ram:GrandTotalAmount>")
    result = read_invoice(data)
    assert result.invoice.totals is not None
    assert result.invoice.totals.total_with_vat == Decimal("336.91")
    assert result.findings == ()


# REQ-001-PRS-F004: exact values


def test_an_amount_keeps_the_digits_as_written() -> None:
    data = edit(CII, GRAND_TOTAL, b"<ram:GrandTotalAmount>336.9000</ram:GrandTotalAmount>")
    totals = read_invoice(data).invoice.totals
    assert totals is not None
    assert str(totals.total_with_vat) == "336.9000"


@pytest.mark.parametrize("value", ["+336.9", "336.", ".9", "-0.00"])
def test_numbers_in_xs_decimal_form_are_taken(value: str) -> None:
    data = edit(CII, GRAND_TOTAL, f"<ram:GrandTotalAmount>{value}</ram:GrandTotalAmount>".encode())
    result = read_invoice(data)
    assert result.invoice.totals is not None
    assert result.invoice.totals.total_with_vat == Decimal(value)
    assert result.findings == ()


@pytest.mark.parametrize("value", ["1_000", "1E+2", "١٢", "1 000", "1,5", "NaN", "Infinity", "--1"])
def test_numbers_not_in_xs_decimal_form_are_not_taken(value: str) -> None:
    data = edit(CII, GRAND_TOTAL, f"<ram:GrandTotalAmount>{value}</ram:GrandTotalAmount>".encode())
    result = read_invoice(data)
    assert result.invoice.totals is not None
    assert result.invoice.totals.total_with_vat is None
    assert [finding.rule for finding in result.findings] == ["HAFL-VALUE"]


# REQ-001-PRS-F005: findings name their business term


def test_a_malformed_due_date_names_bt_9() -> None:
    [finding] = read_invoice(due_dates("2018-11-20")).findings
    assert finding.rule == "HAFL-VALUE"
    assert "BT-9" in finding.text


# REQ-003-PRS-F002: the choices the review of 2026-10-31 found open

CII_02 = (STANDARD / "02.01a-INVOICE_uncefact.xml").read_bytes()
UBL_02 = (STANDARD / "02.01a-INVOICE_ubl.xml").read_bytes()
SELLER = b"<ram:SellerTradeParty>"
SUMMATION = b"<ram:SpecifiedTradeSettlementHeaderMonetarySummation>"
UBL_SUPPLIER = b"<cac:AccountingSupplierParty>"


def test_cii_vat_totals_in_one_currency_when_bt_6_equals_bt_5() -> None:
    data = edit(CII_02, b"<ram:TaxCurrencyCode>GBP<", b"<ram:TaxCurrencyCode>EUR<")
    data = edit(
        data,
        b'<ram:TaxTotalAmount currencyID="GBP">2048.44<',
        b'<ram:TaxTotalAmount currencyID="EUR">2048.45<',
    )
    result = read_invoice(data)
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total == Decimal("2048.44")
    assert result.invoice.totals.vat_total_in_tax_currency == Decimal("2048.45")
    assert result.findings == ()


def test_ubl_vat_totals_in_one_currency_when_bt_6_equals_bt_5() -> None:
    data = edit(UBL_02, b"<cbc:TaxCurrencyCode>GBP<", b"<cbc:TaxCurrencyCode>EUR<")
    data = edit(
        data,
        b'<cbc:TaxAmount currencyID="GBP">2048.44<',
        b'<cbc:TaxAmount currencyID="EUR">2048.45<',
    )
    result = read_invoice(data)
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total == Decimal("2048.44")
    assert result.invoice.totals.vat_total_in_tax_currency == Decimal("2048.45")
    assert len(result.invoice.vat_breakdown) == 2
    assert result.findings == ()


def test_a_group_is_read_from_the_first_element_holding_a_value() -> None:
    cii = read_invoice(
        edit(CII, SELLER, b"<ram:SellerTradeParty> </ram:SellerTradeParty>" + SELLER)
    )
    empty_ubl = UBL_SUPPLIER + b"<cac:Party/></cac:AccountingSupplierParty>"
    ubl = read_invoice(edit(UBL, UBL_SUPPLIER, empty_ubl + UBL_SUPPLIER))
    for result in (cii, ubl):
        assert result.invoice.seller is not None
        assert result.invoice.seller.name == "[Seller name]"
        assert result.findings == ()


def test_a_second_group_holding_values_is_dropped_with_a_finding() -> None:
    second = b"<ram:SellerTradeParty><ram:Name>Example GmbH</ram:Name></ram:SellerTradeParty>"
    data = edit(CII, b"<ram:BuyerTradeParty>", second + b"<ram:BuyerTradeParty>")
    data = edit(
        data,
        SUMMATION,
        SUMMATION + b"<ram:GrandTotalAmount>1</ram:GrandTotalAmount>"
        b"</ram:SpecifiedTradeSettlementHeaderMonetarySummation>" + SUMMATION,
    )
    result = read_invoice(data)
    assert result.invoice.seller is not None
    assert result.invoice.seller.name == "[Seller name]"
    assert result.invoice.totals is not None
    assert result.invoice.totals.total_with_vat == Decimal(1)
    assert [(f.rule, f.text.split()[0], f.location.rsplit("/", 1)[1]) for f in result.findings] == [
        ("HAFL-DROPPED", "BG-4", "ram:SellerTradeParty[2]"),
        ("HAFL-DROPPED", "BG-22", "ram:SpecifiedTradeSettlementHeaderMonetarySummation[2]"),
    ]


def test_ubl_breakdown_without_a_vat_total() -> None:
    # The total's TaxAmount comes first; its subtotal repeats it.
    data = UBL.replace(UBL_TAX_AMOUNT, b'<cbc:TaxAmount currencyID="EUR"> </cbc:TaxAmount>', 1)
    result = read_invoice(data)
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total is None
    assert [vat.category_code for vat in result.invoice.vat_breakdown] == ["S"]
    assert result.findings == ()


def test_ubl_breakdown_of_another_tax_total_is_dropped_with_a_finding() -> None:
    other = (
        b'<cac:TaxTotal><cbc:TaxAmount currencyID="GBP">1</cbc:TaxAmount><cac:TaxSubtotal>'
        b'<cbc:TaxableAmount currencyID="GBP">1</cbc:TaxableAmount>'
        b'<cbc:TaxAmount currencyID="GBP">1</cbc:TaxAmount>'
        b"<cac:TaxCategory><cbc:ID>S</cbc:ID></cac:TaxCategory>"
        b"</cac:TaxSubtotal></cac:TaxTotal>"
    )
    result = read_invoice(edit(UBL, b"</cac:TaxTotal>", b"</cac:TaxTotal>" + other))
    assert len(result.invoice.vat_breakdown) == 1
    assert [(f.rule, f.text.split()[0], f.location.rsplit("/", 1)[1]) for f in result.findings] == [
        ("HAFL-DROPPED", "BT-110", "cbc:TaxAmount"),
        ("HAFL-DROPPED", "BG-23", "cac:TaxSubtotal"),
    ]


def test_a_location_indexes_the_step_that_repeats() -> None:
    registration = (
        b'<ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">DE 987654321</ram:ID>'
        b"</ram:SpecifiedTaxRegistration>"
    )
    data = edit(
        CII,
        b"</ram:SpecifiedTaxRegistration>\r\n            </ram:SellerTradeParty>",
        b"</ram:SpecifiedTaxRegistration>" + registration + b"</ram:SellerTradeParty>",
    )
    [finding] = read_invoice(data).findings
    assert finding.location.endswith("ram:SellerTradeParty/ram:SpecifiedTaxRegistration[2]/ram:ID")


def test_pdf_header_in_xml_text_is_not_a_pdf() -> None:
    data = edit(
        CII, b"<rsm:ExchangedDocumentContext>", b"<!-- %PDF-1.7 --><rsm:ExchangedDocumentContext>"
    )
    assert read_invoice(data).invoice.number == "123456XX"


# The second review of 2026-11-01

CII_LINE_TAX = (
    b"<ram:ApplicableTradeTax>\r\n                    <ram:TypeCode>VAT</ram:TypeCode>\r\n"
    b"                    <ram:CategoryCode>S</ram:CategoryCode>"
)
UBL_SELLER_ENTITY = b"<cac:PartyLegalEntity>\r\n                <cbc:RegistrationName>[Seller name]"


def test_a_lines_vat_information_comes_from_one_element() -> None:
    """REQ-003-PRS-F002: a second BG-30 doesn't lend its rate to the first."""
    exempt = (
        b"<ram:ApplicableTradeTax><ram:TypeCode>VAT</ram:TypeCode>"
        b"<ram:CategoryCode>E</ram:CategoryCode></ram:ApplicableTradeTax>"
    )
    data = CII.replace(CII_LINE_TAX, exempt + CII_LINE_TAX, 1)
    result = read_invoice(data)
    line = result.invoice.lines[0]
    assert (line.vat_category_code, line.vat_rate) == ("E", None)
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == [("HAFL-DROPPED", "BG-30")]


def test_a_partys_legal_entity_comes_from_one_element() -> None:
    other = (
        b"<cac:PartyLegalEntity><cbc:RegistrationName>Other AG</cbc:RegistrationName>"
        b"<cbc:CompanyID>HRB 1</cbc:CompanyID></cac:PartyLegalEntity>"
    )
    first = (
        b"<cac:PartyLegalEntity><cbc:RegistrationName>Example GmbH</cbc:RegistrationName>"
        b"</cac:PartyLegalEntity>"
    )
    result = read_invoice(edit(UBL, UBL_SELLER_ENTITY, first + other + UBL_SELLER_ENTITY))
    assert result.invoice.seller is not None
    assert (result.invoice.seller.name, result.invoice.seller.legal_registration_id) == (
        "Example GmbH",
        None,
    )
    assert {f.rule for f in result.findings} == {"HAFL-DROPPED"}


def test_ubl_vat_totals_without_document_totals() -> None:
    start, end = UBL.index(b"<cac:LegalMonetaryTotal>"), UBL.index(b"</cac:LegalMonetaryTotal>")
    data = UBL[:start] + UBL[end + len(b"</cac:LegalMonetaryTotal>") :]
    result = read_invoice(data)
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total == Decimal("22.04")
    assert result.findings == ()


@pytest.mark.parametrize(
    ("data", "old", "new"),
    [
        (
            CII,
            b'<ram:BilledQuantity unitCode="XPP">1</ram:BilledQuantity>',
            b'<ram:BilledQuantity unitCode="XPP"></ram:BilledQuantity>',
        ),
        (
            UBL,
            b'<cbc:InvoicedQuantity unitCode="XPP">1</cbc:InvoicedQuantity>',
            b'<cbc:InvoicedQuantity unitCode="XPP"></cbc:InvoicedQuantity>',
        ),
    ],
    ids=["cii", "ubl"],
)
def test_the_unit_of_an_empty_quantity_is_read(data: bytes, old: bytes, new: bytes) -> None:
    line = read_invoice(data.replace(old, new, 1)).invoice.lines[0]
    assert (line.quantity, line.unit_code) == (None, "XPP")


def test_a_value_holding_elements_is_malformed() -> None:
    data = edit(CII, b"<ram:ID>123456XX</ram:ID>", b"<ram:ID>123<b/>456XX</ram:ID>")
    result = read_invoice(data)
    assert result.invoice.number is None
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == [("HAFL-VALUE", "BT-1")]


@pytest.mark.parametrize("data", [CII, UBL], ids=["cii", "ubl"])
def test_any_year_after_the_prefix_is_an_edition(data: bytes) -> None:
    xrechnung = b"urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
    reason = refusal(data.replace(xrechnung, b"urn:cen.eu:en16931:2026-01#compliant#x", 1))
    assert "2026" in reason


def test_a_vat_total_without_currency_is_bt_110_also_without_bt_5() -> None:
    data = edit(CII, b"<ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>", b"")
    data = edit(data, TAX_TOTAL, b"<ram:TaxTotalAmount>22.04</ram:TaxTotalAmount>")
    result = read_invoice(data)
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total == Decimal("22.04")
    assert result.findings == ()


@pytest.mark.parametrize("syntax", ["cii", "ubl"])
def test_vat_totals_in_two_currencies_keep_their_values(syntax: str) -> None:
    """The official files give both totals the same number; here they differ."""
    if syntax == "cii":
        old, new = b'currencyID="GBP">2048.44<', b'currencyID="GBP">1702.13<'
        data = edit(CII_02, old, new)
    else:
        data = edit(
            UBL_02,
            b'<cbc:TaxAmount currencyID="GBP">2048.44<',
            b'<cbc:TaxAmount currencyID="GBP">1702.13<',
        )
    totals = read_invoice(data).invoice.totals
    assert totals is not None
    assert (totals.vat_total, totals.vat_total_in_tax_currency) == (
        Decimal("2048.44"),
        Decimal("1702.13"),
    )


def test_ubl_keeps_the_digits_as_written() -> None:
    data = edit(
        UBL,
        b'<cbc:TaxInclusiveAmount currencyID="EUR">336.9<',
        b'<cbc:TaxInclusiveAmount currencyID="EUR">336.900<',
    )
    totals = read_invoice(data).invoice.totals
    assert totals is not None
    assert str(totals.total_with_vat) == "336.900"


def test_ubl_repeated_groups_are_dropped_with_findings_in_document_order() -> None:
    totals = (
        b'<cac:LegalMonetaryTotal><cbc:PayableAmount currencyID="EUR">1</cbc:PayableAmount>'
        b"</cac:LegalMonetaryTotal>"
    )
    buyer = (
        b"<cac:AccountingCustomerParty><cac:Party><cac:PartyLegalEntity>"
        b"<cbc:RegistrationName>Other AG</cbc:RegistrationName>"
        b"</cac:PartyLegalEntity></cac:Party></cac:AccountingCustomerParty>"
    )
    data = edit(UBL, b"<cac:LegalMonetaryTotal>", totals + b"<cac:LegalMonetaryTotal>")
    data = edit(data, b"<cac:AccountingCustomerParty>", buyer + b"<cac:AccountingCustomerParty>")
    result = read_invoice(data)
    assert result.invoice.buyer is not None
    assert result.invoice.buyer.name == "Other AG"
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == [
        ("HAFL-DROPPED", "BG-7"),
        ("HAFL-DROPPED", "BG-22"),
    ]


def test_a_ubl_credit_notes_due_date() -> None:
    note = (ROOT / "tests/data/cen-en16931/ubl/examples/ubl-tc434-creditnote1.xml").read_bytes()
    data = edit(
        note,
        b"<cac:PaymentMeans>",
        b"<cac:PaymentMeans><cbc:PaymentDueDate>2019-10-23</cbc:PaymentDueDate>",
    )
    assert read_invoice(data).invoice.due_date == date(2019, 10, 23)


# The third review of 2026-11-01

CII_HEADER_TAX = b"<ram:ApplicableHeaderTradeSettlement>"
OTHER_TAX = (
    b"<ram:ApplicableTradeTax><ram:CalculatedAmount>1.04</ram:CalculatedAmount>"
    b"<ram:TypeCode>AAA</ram:TypeCode><ram:CategoryCode>S</ram:CategoryCode>"
    b"<ram:RateApplicablePercent>2.00</ram:RateApplicablePercent></ram:ApplicableTradeTax>"
)


def test_a_tax_other_than_vat_gives_no_lines_vat_information() -> None:
    """REQ-003-PRS-F002: Factur-X EXTENDED allows other taxes beside VAT."""
    result = read_invoice(CII.replace(CII_LINE_TAX, OTHER_TAX + CII_LINE_TAX, 1))
    line = result.invoice.lines[0]
    assert (line.vat_category_code, line.vat_rate) == ("S", Decimal(7))
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == [("HAFL-DROPPED", "BG-30")]


def test_a_tax_other_than_vat_gives_no_vat_breakdown() -> None:
    settlement = CII.index(CII_HEADER_TAX) + len(CII_HEADER_TAX)
    tax = CII.index(b"<ram:ApplicableTradeTax>", settlement)
    result = read_invoice(CII[:tax] + OTHER_TAX + CII[tax:])
    assert [(vat.category_code, vat.rate) for vat in result.invoice.vat_breakdown] == [
        ("S", Decimal(7))
    ]
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == [("HAFL-DROPPED", "BG-23")]


@pytest.mark.parametrize(
    ("data", "old", "new", "term"),
    [
        (
            CII,
            TAX_TOTAL,
            b'<ram:TaxTotalAmount currencyID="EUR">1<b/>22.04</ram:TaxTotalAmount>',
            "BT-110",
        ),
        (
            UBL,
            UBL_TAX_AMOUNT,
            b'<cbc:TaxAmount currencyID="EUR">1<b/>22.04</cbc:TaxAmount>',
            "BT-110",
        ),
        (
            CII,
            b'<ram:ID schemeID="VA">DE 123456789</ram:ID>',
            b'<ram:ID schemeID="VA">DE<b/> 123456789</ram:ID>',
            "BT-31",
        ),
        (
            UBL,
            b"<cbc:CompanyID>DE 123456789</cbc:CompanyID>",
            b"<cbc:CompanyID>DE<b/> 123456789</cbc:CompanyID>",
            "BT-31",
        ),
        (UBL, b"<cbc:Note>#ADU#Es gelten", b"<cbc:Note>#ADU#Es <b/>gelten", "BT-22"),
    ],
    ids=["cii-bt-110", "ubl-bt-110", "cii-bt-31", "ubl-bt-31", "ubl-note"],
)
def test_every_value_holding_elements_is_malformed(
    data: bytes, old: bytes, new: bytes, term: str
) -> None:
    assert old in data
    result = read_invoice(data.replace(old, new, 1))
    invoice = result.invoice
    assert invoice.totals is not None
    assert invoice.seller is not None
    value = {
        "BT-110": invoice.totals.vat_total,
        "BT-31": invoice.seller.vat_id,
        "BT-22": next((n for n in invoice.notes if n.subject_code == "ADU"), None),
    }[term]
    assert value is None
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == [("HAFL-VALUE", term)]


def test_ubl_reads_the_first_tax_amount_holding_a_value() -> None:
    empty = b'<cbc:TaxAmount currencyID="EUR"/>'
    result = read_invoice(UBL.replace(UBL_TAX_AMOUNT, empty + UBL_TAX_AMOUNT, 1))
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total == Decimal("22.04")
    assert result.findings == ()


def test_ubl_drops_a_second_tax_amount_of_one_tax_total() -> None:
    second = b'<cbc:TaxAmount currencyID="EUR">99.99</cbc:TaxAmount>'
    result = read_invoice(UBL.replace(UBL_TAX_AMOUNT, UBL_TAX_AMOUNT + second, 1))
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total == Decimal("22.04")
    assert [(f.rule, f.location.rsplit("/", 1)[1]) for f in result.findings] == [
        ("HAFL-DROPPED", "cbc:TaxAmount[2]")
    ]


@pytest.mark.parametrize(
    ("old", "new", "vat_id", "findings"),
    [
        (
            b"<cbc:CompanyID>DE 123456789</cbc:CompanyID>",
            b"<cbc:CompanyID/><cbc:CompanyID>DE 123456789</cbc:CompanyID>",
            "DE 123456789",
            [],
        ),
        (
            b"<cbc:CompanyID>DE 123456789</cbc:CompanyID>",
            b"<cbc:CompanyID>DE 123456789</cbc:CompanyID><cbc:CompanyID>DE 1</cbc:CompanyID>",
            "DE 123456789",
            [("HAFL-DROPPED", "BT-31")],
        ),
        (
            b"<cac:TaxScheme>\r\n                    <cbc:ID>VAT</cbc:ID>",
            b"<cac:TaxScheme><cbc:ID/><cbc:ID>VAT</cbc:ID>",
            "DE 123456789",
            [],
        ),
    ],
    ids=["empty-first", "second-value", "empty-scheme-first"],
)
def test_ubl_vat_identifier_from_the_first_value(
    old: bytes, new: bytes, vat_id: str, findings: list[tuple[str, str]]
) -> None:
    result = read_invoice(UBL.replace(old, new, 1))
    assert result.invoice.seller is not None
    assert result.invoice.seller.vat_id == vat_id
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == findings


@pytest.mark.parametrize(
    ("data", "old", "new"),
    [
        (
            CII,
            b"<ram:IncludedSupplyChainTradeLineItem>",
            b"<ram:IncludedSupplyChainTradeLineItem/><ram:IncludedSupplyChainTradeLineItem>",
        ),
        (UBL, b"<cac:InvoiceLine>", b"<cac:InvoiceLine> </cac:InvoiceLine><cac:InvoiceLine>"),
    ],
    ids=["cii", "ubl"],
)
def test_an_empty_invoice_line_is_missing(data: bytes, old: bytes, new: bytes) -> None:
    result = read_invoice(data.replace(old, new, 1))
    assert len(result.invoice.lines) == len(read_invoice(data).invoice.lines)
    assert result.findings == ()


def test_an_empty_vat_breakdown_is_missing() -> None:
    settlement = CII.index(CII_HEADER_TAX) + len(CII_HEADER_TAX)
    tax = CII.index(b"<ram:ApplicableTradeTax>", settlement)
    result = read_invoice(CII[:tax] + b"<ram:ApplicableTradeTax/>" + CII[tax:])
    assert len(result.invoice.vat_breakdown) == 1
    assert result.findings == ()


@pytest.mark.parametrize(
    ("data", "old", "new", "term"),
    [
        (
            CII,
            b"</ram:PostalTradeAddress>",
            b"</ram:PostalTradeAddress><ram:PostalTradeAddress><ram:CountryID>FR</ram:CountryID>"
            b"</ram:PostalTradeAddress>",
            "BG-5",
        ),
        (
            CII,
            b"</ram:SpecifiedLegalOrganization>",
            b"</ram:SpecifiedLegalOrganization><ram:SpecifiedLegalOrganization><ram:ID>HRB 1"
            b"</ram:ID></ram:SpecifiedLegalOrganization>",
            "BT-30,",
        ),
        (
            UBL,
            b"</cac:PostalAddress>",
            b"</cac:PostalAddress><cac:PostalAddress><cac:Country><cbc:IdentificationCode>FR"
            b"</cbc:IdentificationCode></cac:Country></cac:PostalAddress>",
            "BG-5",
        ),
        (
            UBL,
            b"</cac:Item>",
            b"</cac:Item><cac:Item><cbc:Name>Other item</cbc:Name></cac:Item>",
            "BG-31",
        ),
        (
            CII,
            b"</ram:SpecifiedTradeProduct>",
            b"</ram:SpecifiedTradeProduct><ram:SpecifiedTradeProduct><ram:Name>Other item"
            b"</ram:Name></ram:SpecifiedTradeProduct>",
            "BG-31",
        ),
        (
            CII,
            b"</ram:SpecifiedLineTradeAgreement>",
            b"</ram:SpecifiedLineTradeAgreement><ram:SpecifiedLineTradeAgreement>"
            b"<ram:GrossPriceProductTradePrice><ram:ChargeAmount>999.00</ram:ChargeAmount>"
            b"</ram:GrossPriceProductTradePrice></ram:SpecifiedLineTradeAgreement>",
            "BG-29",
        ),
        (
            UBL,
            b"</cac:Price>",
            b'</cac:Price><cac:Price><cbc:PriceAmount currencyID="EUR">1.00</cbc:PriceAmount>'
            b"</cac:Price>",
            "BG-29",
        ),
        (
            UBL,
            b"</cac:ClassifiedTaxCategory>",
            b"</cac:ClassifiedTaxCategory><cac:ClassifiedTaxCategory><cbc:ID>E</cbc:ID>"
            b"</cac:ClassifiedTaxCategory>",
            "BG-30",
        ),
        (
            UBL,
            b"</cac:PartyTaxScheme>",
            b"</cac:PartyTaxScheme><cac:PartyTaxScheme><cbc:CompanyID>DE 1</cbc:CompanyID>"
            b"<cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>",
            "BT-31",
        ),
    ],
    ids=[
        "cii-address",
        "cii-organization",
        "ubl-address",
        "ubl-item",
        "cii-item",
        "cii-price",
        "ubl-price",
        "ubl-bg-30",
        "ubl-bt-31",
    ],
)
def test_each_group_is_read_from_one_element(
    data: bytes, old: bytes, new: bytes, term: str
) -> None:
    """REQ-003-PRS-F002: the first element is read, a second one dropped naming its term."""
    result = read_invoice(data.replace(old, new, 1))
    assert result.invoice == read_invoice(data).invoice
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == [("HAFL-DROPPED", term)]


def test_a_buyers_address_finding_names_bg_8() -> None:
    buyer = CII.index(b"<ram:BuyerTradeParty>")
    end = CII.index(b"</ram:PostalTradeAddress>", buyer) + len(b"</ram:PostalTradeAddress>")
    second = b"<ram:PostalTradeAddress><ram:CountryID>FR</ram:CountryID></ram:PostalTradeAddress>"
    result = read_invoice(CII[:end] + second + CII[end:])
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == [("HAFL-DROPPED", "BG-8")]


def test_ubl_breakdown_comes_from_the_total_in_the_invoice_currency() -> None:
    """The total in the VAT accounting currency comes first and holds subtotals of its own."""
    data = edit(
        UBL,
        b"<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>",
        b"<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>"
        b"<cbc:TaxCurrencyCode>GBP</cbc:TaxCurrencyCode>",
    )
    gbp = (
        b'<cac:TaxTotal><cbc:TaxAmount currencyID="GBP">19.10</cbc:TaxAmount><cac:TaxSubtotal>'
        b'<cbc:TaxableAmount currencyID="GBP">272.80</cbc:TaxableAmount>'
        b'<cbc:TaxAmount currencyID="GBP">19.10</cbc:TaxAmount>'
        b"<cac:TaxCategory><cbc:ID>Z</cbc:ID></cac:TaxCategory></cac:TaxSubtotal></cac:TaxTotal>"
    )
    result = read_invoice(data.replace(UBL_TAX_TOTAL_START, gbp + UBL_TAX_TOTAL_START, 1))
    assert result.invoice.totals is not None
    assert result.invoice.totals.vat_total_in_tax_currency == Decimal("19.10")
    assert [vat.category_code for vat in result.invoice.vat_breakdown] == ["S"]
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == [("HAFL-DROPPED", "BG-23")]


def test_a_ubl_note_over_several_lines_keeps_its_subject_code() -> None:
    data = edit(UBL, b"<cbc:Note>#ADU#Es gelten", b"<cbc:Note>#ADU#Zeile eins\nEs gelten")
    note = read_invoice(data).invoice.notes[0]
    assert note.subject_code == "ADU"
    assert note.text is not None
    assert note.text.startswith("Zeile eins\nEs gelten")


def test_whitespace_other_than_xml_whitespace_is_kept() -> None:
    data = edit(
        CII, b"<ram:ID>123456XX</ram:ID>", "<ram:ID>\N{NO-BREAK SPACE}123456XX</ram:ID>".encode()
    )
    assert read_invoice(data).invoice.number == "\N{NO-BREAK SPACE}123456XX"


def test_a_number_keeps_its_value_and_decimal_places_not_its_notation() -> None:
    """REQ-001-URS-NF001: the exception for the notation of numbers."""
    data = edit(CII, GRAND_TOTAL, b"<ram:GrandTotalAmount>+0336.90</ram:GrandTotalAmount>")
    totals = read_invoice(data).invoice.totals
    assert totals is not None
    assert str(totals.total_with_vat) == "336.90"


@pytest.mark.parametrize(
    "data",
    ["text", memoryview(CII), bytearray(CII), None],
    ids=["str", "memoryview", "bytearray", "none"],
)
def test_refuses_input_that_is_not_bytes(data: object) -> None:
    with pytest.raises(InvoiceReadError, match="not bytes"):
        read_invoice(data)  # pyright: ignore[reportArgumentType]


def test_refuses_a_byte_order_mark_that_contradicts_the_declaration() -> None:
    declaration = b'<?xml version="1.0" encoding="UTF-8"?>'
    data = b"\xef\xbb\xbf" + edit(CII, declaration, b'<?xml version="1.0" encoding="ISO-8859-1"?>')
    assert "byte order mark" in refusal(data)


@pytest.mark.parametrize(
    "declaration",
    [
        b'<?xml version="1.0" encoding="UTF-8"?>',
        b'<?xml version="1.0"?>',
    ],
)
def test_reads_a_byte_order_mark_that_agrees_with_the_declaration(declaration: bytes) -> None:
    data = b"\xef\xbb\xbf" + edit(CII, b'<?xml version="1.0" encoding="UTF-8"?>', declaration)
    assert read_invoice(data).invoice.number == "123456XX"


# REQ-003-PRS-F002: the parties' addresses, contacts and identifiers

UBL_SELLER_ENDPOINT = b'<cbc:EndpointID schemeID="EM">seller@email.de</cbc:EndpointID>'
UBL_BUYER_ENDPOINT = b'<cbc:EndpointID schemeID="EM">buyer@info.de</cbc:EndpointID>'
CII_SELLER_VAT_ID = b'<ram:ID schemeID="VA">DE 123456789</ram:ID>'
CII_BUYER_ADDRESS = b"<ram:LineOne>[Buyer address line 1]</ram:LineOne>"
CII_PERSON = b"<ram:PersonName>nicht vorhanden</ram:PersonName>"
FC = b"201/113/40209"


def dropped(result: ReadResult) -> list[str]:
    """The term or group each `HAFL-DROPPED` finding names, in document order."""
    return [f.text.split()[0] for f in result.findings if f.rule == "HAFL-DROPPED"]


def test_seller_identifiers_with_and_without_scheme() -> None:
    cii = edit(
        CII,
        SELLER,
        SELLER + b"<ram:ID>A1</ram:ID><ram:ID>B2</ram:ID>"
        b'<ram:GlobalID schemeID="0088">4000001000005</ram:GlobalID>',
    )
    ubl = edit(
        UBL,
        UBL_SELLER_ENDPOINT,
        UBL_SELLER_ENDPOINT
        + b"<cac:PartyIdentification><cbc:ID>A1</cbc:ID></cac:PartyIdentification>"
        b'<cac:PartyIdentification><cbc:ID schemeID="SEPA">DE98ZZZ09999999999</cbc:ID>'
        b"</cac:PartyIdentification>"
        b"<cac:PartyIdentification><cbc:ID>B2</cbc:ID></cac:PartyIdentification>"
        b'<cac:PartyIdentification><cbc:ID schemeID="0088">4000001000005</cbc:ID>'
        b"</cac:PartyIdentification>",
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.seller is not None
        assert result.invoice.seller.identifiers == (
            Identifier(value="A1"),
            Identifier(value="B2"),
            Identifier(value="4000001000005", scheme="0088"),
        )
        # The UBL SEPA identifier is no BT-29, and without a mandate no BT-90 either.
        assert dropped(result) == ([] if data is cii else ["BT-90"])


def test_seller_tax_registration_identifier() -> None:
    cii = edit(
        CII,
        CII_SELLER_VAT_ID,
        CII_SELLER_VAT_ID
        + b'</ram:SpecifiedTaxRegistration><ram:SpecifiedTaxRegistration><ram:ID schemeID="FC">'
        + FC
        + b"</ram:ID>",
    )
    ubl = edit(
        UBL,
        b"</cac:PartyTaxScheme>",
        b"</cac:PartyTaxScheme><cac:PartyTaxScheme><cbc:CompanyID>"
        + FC
        + b"</cbc:CompanyID><cac:TaxScheme><cbc:ID>FC</cbc:ID></cac:TaxScheme>"
        b"</cac:PartyTaxScheme>",
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.seller is not None
        assert (result.invoice.seller.vat_id, result.invoice.seller.tax_registration_id) == (
            "DE 123456789",
            FC.decode(),
        )
        assert result.findings == ()


def test_address_lines_and_subdivision() -> None:
    cii = edit(
        CII,
        CII_BUYER_ADDRESS,
        CII_BUYER_ADDRESS
        + b"<ram:LineTwo>Hinterhaus</ram:LineTwo><ram:LineThree>3. OG</ram:LineThree>",
    )
    cii = edit(
        cii,
        b"<ram:CityName>[Buyer city]</ram:CityName>",
        b"<ram:CityName>[Buyer city]</ram:CityName>"
        b"<ram:CountrySubDivisionName>Berlin</ram:CountrySubDivisionName>",
    )
    ubl = edit(
        UBL,
        b"<cbc:CityName>[Buyer city]</cbc:CityName>",
        b"<cbc:AdditionalStreetName>Hinterhaus</cbc:AdditionalStreetName>"
        b"<cbc:CityName>[Buyer city]</cbc:CityName>"
        b"<cbc:CountrySubentity>Berlin</cbc:CountrySubentity>"
        b"<cac:AddressLine><cbc:Line>3. OG</cbc:Line></cac:AddressLine>"
        b"<cac:AddressLine><cbc:Line>Aufgang B</cbc:Line></cac:AddressLine>",
    )
    for data, findings in ((cii, []), (ubl, ["BT-163"])):
        result = read_invoice(data)
        buyer = result.invoice.buyer
        assert buyer is not None
        assert (
            buyer.address_line_1,
            buyer.address_line_2,
            buyer.address_line_3,
            buyer.city,
            buyer.post_code,
            buyer.country_subdivision,
            buyer.country_code,
        ) == (
            "[Buyer address line 1]",
            "Hinterhaus",
            "3. OG",
            "[Buyer city]",
            "12345",
            "Berlin",
            "DE",
        )
        assert dropped(result) == findings


def test_a_cii_contact_with_a_department_name() -> None:
    alone = read_invoice(edit(CII, CII_PERSON, b"<ram:DepartmentName>Sales</ram:DepartmentName>"))
    both = read_invoice(
        edit(CII, CII_PERSON, CII_PERSON + b"<ram:DepartmentName>Sales</ram:DepartmentName>")
    )
    assert alone.invoice.seller is not None
    assert both.invoice.seller is not None
    assert alone.invoice.seller.contact == Contact(
        point="Sales", telephone="+49 1234-5678", email="seller@email.de"
    )
    assert alone.findings == ()
    assert both.invoice.seller.contact is not None
    assert both.invoice.seller.contact.point == "nicht vorhanden"
    assert dropped(both) == ["BT-41"]


def test_terms_held_once_are_read_from_the_first_and_the_rest_dropped() -> None:
    other_contact = (
        b"<ram:DefinedTradeContact><ram:PersonName>Other</ram:PersonName></ram:DefinedTradeContact>"
    )
    cii = edit(CII, b"</ram:DefinedTradeContact>", b"</ram:DefinedTradeContact>" + other_contact)
    cii = edit(
        cii,
        CII_SELLER_VAT_ID,
        CII_SELLER_VAT_ID
        + b'<ram:ID schemeID="FC">'
        + FC
        + b'</ram:ID><ram:ID schemeID="FC">999/999/99999</ram:ID>',
    )
    cii = edit(
        cii,
        b'<ram:URIID schemeID="EM">buyer@info.de</ram:URIID>',
        b'<ram:URIID schemeID="EM">buyer@info.de</ram:URIID></ram:URIUniversalCommunication>'
        b'<ram:URIUniversalCommunication><ram:URIID schemeID="0204">991-1</ram:URIID>',
    )
    cii = edit(
        cii,
        b"<ram:ID>[Buyer identifier]</ram:ID>",
        b"<ram:ID>[Buyer identifier]</ram:ID>"
        b'<ram:GlobalID schemeID="0088">4000001000005</ram:GlobalID>',
    )
    ubl = edit(
        UBL,
        b"</cac:Contact>",
        b"</cac:Contact><cac:Contact><cbc:Name>Other</cbc:Name></cac:Contact>",
    )
    ubl = edit(
        ubl,
        b"</cac:PartyTaxScheme>",
        b"</cac:PartyTaxScheme>"
        + b"".join(
            b"<cac:PartyTaxScheme><cbc:CompanyID>"
            + value
            + b"</cbc:CompanyID><cac:TaxScheme><cbc:ID>FC</cbc:ID></cac:TaxScheme>"
            b"</cac:PartyTaxScheme>"
            for value in (FC, b"999/999/99999")
        ),
    )
    ubl = edit(
        ubl,
        UBL_BUYER_ENDPOINT,
        UBL_BUYER_ENDPOINT + b'<cbc:EndpointID schemeID="0204">991-1</cbc:EndpointID>',
    )
    ubl = edit(
        ubl,
        b"<cbc:ID>[Buyer identifier]</cbc:ID>",
        b"<cbc:ID>[Buyer identifier]</cbc:ID></cac:PartyIdentification>"
        b'<cac:PartyIdentification><cbc:ID schemeID="0088">4000001000005</cbc:ID>',
    )
    for data, order in (
        (cii, ["BG-6", "BT-32", "BT-46", "BT-49"]),
        (ubl, ["BT-32", "BG-6", "BT-49", "BT-46"]),
    ):
        result = read_invoice(data)
        seller, buyer = result.invoice.seller, result.invoice.buyer
        assert seller is not None
        assert buyer is not None
        assert seller.contact is not None
        assert seller.contact.point == "nicht vorhanden"
        assert seller.tax_registration_id == FC.decode()
        assert buyer.electronic_address == Identifier(value="buyer@info.de", scheme="EM")
        # The identifier with a scheme is read before the one without (CII-SR-450).
        assert buyer.identifiers == (Identifier(value="4000001000005", scheme="0088"),)
        assert dropped(result) == order


def test_identifiers_take_one_order_whatever_the_syntax() -> None:
    """Those without a scheme first, as CII's XML Schema puts ram:ID before ram:GlobalID."""
    ubl = edit(
        UBL,
        UBL_SELLER_ENDPOINT,
        UBL_SELLER_ENDPOINT
        + b'<cac:PartyIdentification><cbc:ID schemeID="0088">4000001000005</cbc:ID>'
        b"</cac:PartyIdentification>"
        b"<cac:PartyIdentification><cbc:ID>A1</cbc:ID></cac:PartyIdentification>",
    )
    cii = edit(
        CII,
        SELLER,
        SELLER + b'<ram:ID>A1</ram:ID><ram:GlobalID schemeID="0088">4000001000005</ram:GlobalID>',
    )
    for data in (ubl, cii):
        result = read_invoice(data)
        assert result.invoice.seller is not None
        assert result.invoice.seller.identifiers == (
            Identifier(value="A1"),
            Identifier(value="4000001000005", scheme="0088"),
        )
        assert result.findings == ()


def test_a_cii_global_id_without_scheme_is_dropped() -> None:
    result = read_invoice(edit(CII, SELLER, SELLER + b"<ram:GlobalID>X1</ram:GlobalID>"))
    assert result.invoice.seller is not None
    assert result.invoice.seller.identifiers == ()
    assert dropped(result) == ["BT-29"]


def test_a_contact_element_holding_none_of_the_contacts_terms_is_not_the_contact() -> None:
    fax = (
        b"<ram:DefinedTradeContact><ram:FaxUniversalCommunication>"
        b"<ram:CompleteNumber>+49 1234-5679</ram:CompleteNumber>"
        b"</ram:FaxUniversalCommunication></ram:DefinedTradeContact>"
    )
    cii = edit(CII, b"<ram:DefinedTradeContact>", fax + b"<ram:DefinedTradeContact>")
    ubl = edit(
        UBL,
        b"<cac:Contact>",
        b"<cac:Contact><cbc:Telefax>+49 1234-5679</cbc:Telefax></cac:Contact><cac:Contact>",
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.seller is not None
        assert result.invoice.seller.contact == Contact(
            point="nicht vorhanden", telephone="+49 1234-5678", email="seller@email.de"
        )
        assert result.findings == ()


# REQ-003-PRS-F002: payment instructions

# Dummy IBANs from KoSIT's test files.
IBAN, OTHER_IBAN = "DE79000000001234567890", "DE16000000002345678901"
CII_MEANS_END = b"</ram:SpecifiedTradeSettlementPaymentMeans>"
CII_MEANS_CODE = (
    b"<ram:TypeCode>58</ram:TypeCode>\r\n                <ram:PayeePartyCreditorFinancialAccount>"
)
UBL_MEANS_END = b"</cac:PaymentMeans>"
UBL_MEANS_CODE = b"<cbc:PaymentMeansCode>58</cbc:PaymentMeansCode>"


def cii_means(code: str, account: bytes) -> bytes:
    return (
        b"<ram:SpecifiedTradeSettlementPaymentMeans><ram:TypeCode>"
        + code.encode()
        + b"</ram:TypeCode><ram:Information>SEPA</ram:Information>"
        b"<ram:PayeePartyCreditorFinancialAccount>"
        + account
        + b"</ram:PayeePartyCreditorFinancialAccount></ram:SpecifiedTradeSettlementPaymentMeans>"
    )


def ubl_means(code: str, account: str) -> bytes:
    return (
        b'<cac:PaymentMeans><cbc:PaymentMeansCode name="SEPA">'
        + code.encode()
        + b"</cbc:PaymentMeansCode><cac:PayeeFinancialAccount><cbc:ID>"
        + account.encode()
        + b"</cbc:ID></cac:PayeeFinancialAccount></cac:PaymentMeans>"
    )


def test_a_payment_means_repeated_for_another_account_is_one() -> None:
    """One with another means code is left out with what it holds."""
    cii = edit(
        CII,
        CII_MEANS_CODE,
        CII_MEANS_CODE.replace(
            b"</ram:TypeCode>", b"</ram:TypeCode><ram:Information>SEPA</ram:Information>"
        ),
    )
    cii = edit(
        cii,
        CII_MEANS_END,
        CII_MEANS_END
        + cii_means("58", b"<ram:ProprietaryID>12345678</ram:ProprietaryID>")
        + cii_means("30", b"<ram:IBANID>" + OTHER_IBAN.encode() + b"</ram:IBANID>"),
    )
    ubl = edit(UBL, UBL_MEANS_CODE, b'<cbc:PaymentMeansCode name="SEPA">58</cbc:PaymentMeansCode>')
    ubl = edit(
        ubl,
        UBL_MEANS_END,
        UBL_MEANS_END + ubl_means("58", "12345678") + ubl_means("30", OTHER_IBAN),
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.payment_instructions == PaymentInstructions(
            means_code="58",
            means_text="SEPA",
            credit_transfers=(
                CreditTransfer(account_id=IBAN),
                CreditTransfer(account_id="12345678"),
            ),
        )
        assert dropped(result) == ["BG-16"]


def test_card_direct_debit_and_creditor_identifier() -> None:
    card_and_debtor = (
        b"<ram:ApplicableTradeSettlementFinancialCard><ram:ID>1234</ram:ID>"
        b"<ram:CardholderName>Max Muster</ram:CardholderName>"
        b"</ram:ApplicableTradeSettlementFinancialCard>"
        b"<ram:PayerPartyDebtorFinancialAccount><ram:IBANID>"
        + OTHER_IBAN.encode()
        + b"</ram:IBANID></ram:PayerPartyDebtorFinancialAccount>"
    )
    cii = edit(
        CII,
        CII_MEANS_CODE,
        CII_MEANS_CODE.replace(
            b"<ram:PayeePartyCreditorFinancialAccount>",
            card_and_debtor + b"<ram:PayeePartyCreditorFinancialAccount>",
        ),
    )
    cii = edit(
        cii,
        b"<ram:IBANID>DE79000000001234567890</ram:IBANID>",
        b"<ram:IBANID>DE79000000001234567890</ram:IBANID>"
        b"<ram:AccountName>Example GmbH</ram:AccountName>",
    )
    cii = edit(
        cii,
        CII_MEANS_END,
        b"<ram:PayeeSpecifiedCreditorFinancialInstitution><ram:BICID>EXMPDEFFXXX</ram:BICID>"
        b"</ram:PayeeSpecifiedCreditorFinancialInstitution>" + CII_MEANS_END,
    )
    cii = edit(
        cii,
        b"<ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>",
        b"<ram:CreditorReferenceID>DE98ZZZ09999999999</ram:CreditorReferenceID>"
        b"<ram:PaymentReference>R-1</ram:PaymentReference>"
        b"<ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>",
    )
    cii = edit(
        cii,
        PAYMENT_TERMS,
        PAYMENT_TERMS + b"<ram:DirectDebitMandateID>M-1</ram:DirectDebitMandateID>",
    )
    ubl = edit(
        UBL,
        UBL_MEANS_CODE,
        UBL_MEANS_CODE + b"<cbc:PaymentID>R-1</cbc:PaymentID>"
        b"<cac:CardAccount><cbc:PrimaryAccountNumberID>1234</cbc:PrimaryAccountNumberID>"
        b"<cbc:NetworkID>VISA</cbc:NetworkID><cbc:HolderName>Max Muster</cbc:HolderName>"
        b"</cac:CardAccount>",
    )
    ubl = edit(
        ubl,
        b"<cbc:ID>DE79000000001234567890</cbc:ID>",
        b"<cbc:ID>DE79000000001234567890</cbc:ID><cbc:Name>Example GmbH</cbc:Name>"
        b"<cac:FinancialInstitutionBranch><cbc:ID>EXMPDEFFXXX</cbc:ID>"
        b"</cac:FinancialInstitutionBranch>",
    )
    ubl = edit(
        ubl,
        UBL_MEANS_END,
        b"<cac:PaymentMandate><cbc:ID>M-1</cbc:ID><cac:PayerFinancialAccount><cbc:ID>"
        + OTHER_IBAN.encode()
        + b"</cbc:ID></cac:PayerFinancialAccount></cac:PaymentMandate>"
        + UBL_MEANS_END,
    )
    sepa = b'<cac:PartyIdentification><cbc:ID schemeID="SEPA">{}</cbc:ID></cac:PartyIdentification>'
    ubl = edit(
        ubl,
        UBL_SELLER_ENDPOINT,
        UBL_SELLER_ENDPOINT + sepa.replace(b"{}", b"DE98ZZZ09999999999"),
    )
    ubl = edit(
        ubl,
        b"</cac:AccountingCustomerParty>",
        b"</cac:AccountingCustomerParty><cac:PayeeParty>"
        + sepa.replace(b"{}", b"DE11ZZZ00000000001")
        + b"<cac:PartyName><cbc:Name>Example Factoring GmbH</cbc:Name></cac:PartyName>"
        b"</cac:PayeeParty>",
    )
    for data, creditor in ((cii, "DE98ZZZ09999999999"), (ubl, "DE11ZZZ00000000001")):
        result = read_invoice(data)
        assert result.invoice.payment_instructions == PaymentInstructions(
            means_code="58",
            remittance_information="R-1",
            credit_transfers=(
                CreditTransfer(
                    account_id=IBAN, account_name="Example GmbH", provider_id="EXMPDEFFXXX"
                ),
            ),
            card=PaymentCard(account_number="1234", holder_name="Max Muster"),
            direct_debit=DirectDebit(
                mandate_reference="M-1", creditor_id=creditor, debited_account_id=OTHER_IBAN
            ),
        )
        # The seller's identifier beside the payee's is a second one.
        assert dropped(result) == ([] if data is cii else ["BT-90"])


def test_a_cii_account_given_also_as_proprietary_id_reads_the_iban() -> None:
    result = read_invoice(
        edit(
            CII,
            b"<ram:IBANID>DE79000000001234567890</ram:IBANID>",
            b"<ram:IBANID>DE79000000001234567890</ram:IBANID>"
            b"<ram:ProprietaryID>44421800</ram:ProprietaryID>",
        )
    )
    assert result.invoice.payment_instructions is not None
    assert result.invoice.payment_instructions.credit_transfers == (
        CreditTransfer(account_id=IBAN),
    )
    assert dropped(result) == ["BT-84"]


def test_an_invoice_without_payment_means() -> None:
    cii = (
        CII[: CII.index(b"<ram:SpecifiedTradeSettlementPaymentMeans>")]
        + CII[CII.index(CII_MEANS_END) + len(CII_MEANS_END) :]
    )
    ubl = (
        UBL[: UBL.index(b"<cac:PaymentMeans>")]
        + UBL[UBL.index(UBL_MEANS_END) + len(UBL_MEANS_END) :]
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.payment_instructions is None
        assert result.invoice.payment_terms == "Zahlbar sofort ohne Abzug."
        assert result.findings == ()


def test_a_repeated_payment_means_with_another_text_keeps_its_account() -> None:
    """Payment means differ by their code alone; another text or remittance information is
    dropped as that term."""
    cii = edit(
        CII,
        CII_MEANS_CODE,
        CII_MEANS_CODE.replace(
            b"</ram:TypeCode>", b"</ram:TypeCode><ram:Information>SEPA</ram:Information>"
        ),
    )
    other = cii_means("58", b"<ram:IBANID>" + OTHER_IBAN.encode() + b"</ram:IBANID>")
    cii = edit(cii, CII_MEANS_END, CII_MEANS_END + other.replace(b">SEPA<", b">Other<"))
    ubl = edit(UBL, UBL_MEANS_CODE, UBL_MEANS_CODE + b"<cbc:PaymentID>R-1</cbc:PaymentID>")
    ubl = edit(
        ubl,
        UBL_MEANS_END,
        UBL_MEANS_END
        + ubl_means("58", OTHER_IBAN).replace(
            b"</cbc:PaymentMeansCode>", b"</cbc:PaymentMeansCode><cbc:PaymentID>R-2</cbc:PaymentID>"
        ),
    )
    for data, findings in ((cii, ["BT-82"]), (ubl, ["BT-83"])):
        result = read_invoice(data)
        payment = result.invoice.payment_instructions
        assert payment is not None
        assert payment.credit_transfers == (
            CreditTransfer(account_id=IBAN),
            CreditTransfer(account_id=OTHER_IBAN),
        )
        assert (payment.means_text, payment.remittance_information) == (
            ("SEPA", None) if data is cii else ("SEPA", "R-1")
        )
        assert dropped(result) == findings


def test_a_ubl_creditor_identifier_without_a_mandate_is_dropped() -> None:
    """Without a direct debit there is no BT-90; a scheme counts with whitespace removed."""
    for scheme in (b"SEPA", b" SEPA "):
        data = edit(
            UBL,
            UBL_SELLER_ENDPOINT,
            UBL_SELLER_ENDPOINT
            + b'<cac:PartyIdentification><cbc:ID schemeID="'
            + scheme
            + b'">DE98ZZZ09999999999</cbc:ID></cac:PartyIdentification>',
        )
        result = read_invoice(data)
        assert result.invoice.seller is not None
        assert result.invoice.seller.identifiers == ()
        assert result.invoice.payment_instructions is not None
        assert result.invoice.payment_instructions.direct_debit is None
        assert dropped(result) == ["BT-90"]


def test_a_cii_bic_without_an_account_is_dropped() -> None:
    data = edit(
        CII,
        CII_MEANS_END,
        CII_MEANS_END + b"<ram:SpecifiedTradeSettlementPaymentMeans><ram:TypeCode>58</ram:TypeCode>"
        b"<ram:PayeeSpecifiedCreditorFinancialInstitution><ram:BICID>EXMPDEFFXXX</ram:BICID>"
        b"</ram:PayeeSpecifiedCreditorFinancialInstitution>"
        b"</ram:SpecifiedTradeSettlementPaymentMeans>",
    )
    result = read_invoice(data)
    assert result.invoice.payment_instructions is not None
    assert result.invoice.payment_instructions.credit_transfers == (
        CreditTransfer(account_id=IBAN),
    )
    assert dropped(result) == ["BT-86"]


# REQ-003-PRS-F002: preceding invoices, delivery and invoicing period

CII_SUMMATION_END = b"</ram:SpecifiedTradeSettlementHeaderMonetarySummation>"
UBL_SUPPLIER_START = b"<cac:AccountingSupplierParty>"
UBL_MEANS_START = b"<cac:PaymentMeans>"


def test_preceding_invoices() -> None:
    """CII D16B holds one; UBL any number, here one without its date."""
    cii = edit(
        CII,
        CII_SUMMATION_END,
        CII_SUMMATION_END
        + b"<ram:InvoiceReferencedDocument><ram:IssuerAssignedID>R-0</ram:IssuerAssignedID>"
        b'<ram:FormattedIssueDateTime><qdt:DateTimeString format="102">20160301'
        b"</qdt:DateTimeString></ram:FormattedIssueDateTime></ram:InvoiceReferencedDocument>",
    )
    ubl = edit(
        UBL,
        UBL_SUPPLIER_START,
        b"<cac:BillingReference><cac:InvoiceDocumentReference><cbc:ID>R-0</cbc:ID>"
        b"<cbc:IssueDate>2016-03-01</cbc:IssueDate></cac:InvoiceDocumentReference>"
        b"</cac:BillingReference><cac:BillingReference><cac:InvoiceDocumentReference>"
        b"<cbc:ID>R-00</cbc:ID></cac:InvoiceDocumentReference></cac:BillingReference>"
        + UBL_SUPPLIER_START,
    )
    first = PrecedingInvoice(number="R-0", issue_date=date(2016, 3, 1))
    for data, expected in ((cii, (first,)), (ubl, (first, PrecedingInvoice(number="R-00")))):
        result = read_invoice(data)
        assert result.invoice.preceding_invoices == expected
        assert result.findings == ()


def test_a_preceding_invoice_without_its_terms_is_left_out() -> None:
    """A reference holding only what the model doesn't read is no preceding invoice."""
    cii = edit(
        CII,
        CII_SUMMATION_END,
        CII_SUMMATION_END + b"<ram:InvoiceReferencedDocument><ram:TypeCode>380</ram:TypeCode>"
        b"</ram:InvoiceReferencedDocument>",
    )
    ubl = edit(
        UBL,
        UBL_SUPPLIER_START,
        b"<cac:BillingReference><cac:InvoiceDocumentReference><cbc:ID> </cbc:ID>"
        b"<cbc:DocumentTypeCode>380</cbc:DocumentTypeCode></cac:InvoiceDocumentReference>"
        b"</cac:BillingReference>" + UBL_SUPPLIER_START,
    )
    for data in (cii, ubl):
        assert read_invoice(data).invoice.preceding_invoices == ()


def delivered(cii_location: bytes, ubl_location: bytes) -> tuple[bytes, bytes]:
    """01.01a with delivery information and an invoicing period, in both syntaxes."""
    cii = edit(
        CII,
        b"<ram:ApplicableHeaderTradeDelivery/>",
        b"<ram:ApplicableHeaderTradeDelivery><ram:ShipToTradeParty>"
        + cii_location
        + b"<ram:Name>Example Lager</ram:Name><ram:PostalTradeAddress>"
        b"<ram:PostcodeCode>12345</ram:PostcodeCode><ram:LineOne>Lagerstr. 1</ram:LineOne>"
        b"<ram:CityName>Example City</ram:CityName><ram:CountryID>DE</ram:CountryID>"
        b"</ram:PostalTradeAddress></ram:ShipToTradeParty><ram:ActualDeliverySupplyChainEvent>"
        b'<ram:OccurrenceDateTime><udt:DateTimeString format="102">20160401</udt:DateTimeString>'
        b"</ram:OccurrenceDateTime></ram:ActualDeliverySupplyChainEvent>"
        b"</ram:ApplicableHeaderTradeDelivery>",
    )
    cii = edit(
        cii,
        b"<ram:SpecifiedTradePaymentTerms>",
        b'<ram:BillingSpecifiedPeriod><ram:StartDateTime><udt:DateTimeString format="102">'
        b"20160301</udt:DateTimeString></ram:StartDateTime><ram:EndDateTime>"
        b'<udt:DateTimeString format="102">20160331</udt:DateTimeString></ram:EndDateTime>'
        b"</ram:BillingSpecifiedPeriod><ram:SpecifiedTradePaymentTerms>",
    )
    ubl = edit(
        UBL,
        UBL_MEANS_START,
        b"<cac:InvoicePeriod><cbc:StartDate>2016-03-01</cbc:StartDate>"
        b"<cbc:EndDate>2016-03-31</cbc:EndDate></cac:InvoicePeriod><cac:Delivery>"
        b"<cbc:ActualDeliveryDate>2016-04-01</cbc:ActualDeliveryDate><cac:DeliveryLocation>"
        + ubl_location
        + b"<cac:Address><cbc:StreetName>Lagerstr. 1</cbc:StreetName>"
        b"<cbc:CityName>Example City</cbc:CityName><cbc:PostalZone>12345</cbc:PostalZone>"
        b"<cac:Country><cbc:IdentificationCode>DE</cbc:IdentificationCode></cac:Country>"
        b"</cac:Address></cac:DeliveryLocation><cac:DeliveryParty><cac:PartyName>"
        b"<cbc:Name>Example Lager</cbc:Name></cac:PartyName></cac:DeliveryParty></cac:Delivery>"
        + UBL_MEANS_START,
    )
    return cii, ubl


DELIVERY = Delivery(
    party_name="Example Lager",
    date=date(2016, 4, 1),
    address_line_1="Lagerstr. 1",
    city="Example City",
    post_code="12345",
    country_code="DE",
)


def test_delivery_and_invoicing_period() -> None:
    for location, cii_location, ubl_location in (
        (
            Identifier(value="4000001000005", scheme="0088"),
            b'<ram:GlobalID schemeID="0088">4000001000005</ram:GlobalID>',
            b'<cbc:ID schemeID="0088">4000001000005</cbc:ID>',
        ),
        (Identifier(value="L-1"), b"<ram:ID>L-1</ram:ID>", b"<cbc:ID>L-1</cbc:ID>"),
    ):
        for data in delivered(cii_location, ubl_location):
            result = read_invoice(data)
            assert result.invoice.delivery == replace(DELIVERY, location=location)
            assert result.invoice.invoicing_period == Period(
                start=date(2016, 3, 1), end=date(2016, 3, 31)
            )
            assert result.findings == ()


def test_a_second_ubl_delivery_is_dropped() -> None:
    _, ubl = delivered(b"", b"")
    ubl = edit(
        ubl,
        b"</cac:Delivery>",
        b"</cac:Delivery><cac:Delivery><cbc:ActualDeliveryDate>2016-04-02"
        b"</cbc:ActualDeliveryDate></cac:Delivery>",
    )
    result = read_invoice(ubl)
    assert result.invoice.delivery == DELIVERY
    assert dropped(result) == ["BG-13"]


def test_a_ubl_delivery_and_period_without_the_models_terms_dont_count() -> None:
    """A first cac:Delivery or cac:InvoicePeriod holding only terms the model doesn't read
    leaves the group to the next one."""
    _, ubl = delivered(b"", b"")
    ubl = edit(
        ubl,
        b"<cac:InvoicePeriod><cbc:StartDate>",
        b"<cac:InvoicePeriod><cbc:DescriptionCode>35</cbc:DescriptionCode></cac:InvoicePeriod>"
        b"<cac:InvoicePeriod><cbc:StartDate>",
    )
    ubl = edit(
        ubl, b"<cac:Delivery>", b"<cac:Delivery><cbc:ID>D-1</cbc:ID></cac:Delivery><cac:Delivery>"
    )
    result = read_invoice(ubl)
    assert result.invoice.delivery == DELIVERY
    assert result.invoice.invoicing_period == Period(start=date(2016, 3, 1), end=date(2016, 3, 31))
    assert dropped(result) == []


# An allowance's or a charge's VAT category in the tests: standard rated, 7 %.
STANDARD_RATE = AllowanceCharge(vat_category_code="S", vat_rate=Decimal(7))


def cii_allowance_charge(
    indicator: bytes, amount: bytes, terms: bytes = b"", after: bytes = b""
) -> bytes:
    """An allowance or a charge with `terms` before its amount and `after` after it."""
    return (
        b"<ram:SpecifiedTradeAllowanceCharge><ram:ChargeIndicator><udt:Indicator>"
        + indicator
        + b"</udt:Indicator></ram:ChargeIndicator>"
        + terms
        + b"<ram:ActualAmount>"
        + amount
        + b"</ram:ActualAmount>"
        + after
        + b"<ram:CategoryTradeTax><ram:TypeCode>VAT</ram:TypeCode>"
        b"<ram:CategoryCode>S</ram:CategoryCode><ram:RateApplicablePercent>7"
        b"</ram:RateApplicablePercent></ram:CategoryTradeTax></ram:SpecifiedTradeAllowanceCharge>"
    )


def ubl_allowance_charge(
    indicator: bytes, amount: bytes, terms: bytes = b"", after: bytes = b""
) -> bytes:
    """An allowance or a charge with `terms` before its amount and `after` after it."""
    return (
        b"<cac:AllowanceCharge><cbc:ChargeIndicator>"
        + indicator
        + b"</cbc:ChargeIndicator>"
        + terms
        + b'<cbc:Amount currencyID="EUR">'
        + amount
        + b"</cbc:Amount>"
        + after
        + b"<cac:TaxCategory><cbc:ID>S</cbc:ID><cbc:Percent>7</cbc:Percent>"
        b"<cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:TaxCategory>"
        b"</cac:AllowanceCharge>"
    )


def with_allowances_and_charges(cii: list[bytes], ubl: list[bytes]) -> tuple[bytes, bytes]:
    """01.01a with these allowances and charges, in both syntaxes."""
    return (
        edit(
            CII,
            b"<ram:SpecifiedTradePaymentTerms>",
            b"".join(cii) + b"<ram:SpecifiedTradePaymentTerms>",
        ),
        edit(UBL, UBL_TAX_TOTAL_START, b"".join(ubl) + UBL_TAX_TOTAL_START),
    )


def test_allowances_and_charges() -> None:
    """Each term in its syntax's order: in CII the percentage and the base amount before the
    amount, the reason code and the reason after it; in UBL the reason code, the reason and the
    percentage before the amount, the base amount after it."""
    cii, ubl = with_allowances_and_charges(
        [
            cii_allowance_charge(
                b"false",
                b"10.00",
                b"<ram:CalculationPercent>5</ram:CalculationPercent>"
                b"<ram:BasisAmount>200.00</ram:BasisAmount>",
                b"<ram:ReasonCode>95</ram:ReasonCode><ram:Reason>Rabatt</ram:Reason>",
            ),
            cii_allowance_charge(
                b"true",
                b"4.50",
                b"<ram:CalculationPercent>1.5</ram:CalculationPercent>"
                b"<ram:BasisAmount>300.00</ram:BasisAmount>",
                b"<ram:ReasonCode>FC</ram:ReasonCode><ram:Reason>Fracht</ram:Reason>",
            ),
            cii_allowance_charge(b"false", b"1.00"),
        ],
        [
            ubl_allowance_charge(
                b"false",
                b"10.00",
                b"<cbc:AllowanceChargeReasonCode>95</cbc:AllowanceChargeReasonCode>"
                b"<cbc:AllowanceChargeReason>Rabatt</cbc:AllowanceChargeReason>"
                b"<cbc:MultiplierFactorNumeric>5</cbc:MultiplierFactorNumeric>",
                b'<cbc:BaseAmount currencyID="EUR">200.00</cbc:BaseAmount>',
            ),
            ubl_allowance_charge(
                b"true",
                b"4.50",
                b"<cbc:AllowanceChargeReasonCode>FC</cbc:AllowanceChargeReasonCode>"
                b"<cbc:AllowanceChargeReason>Fracht</cbc:AllowanceChargeReason>"
                b"<cbc:MultiplierFactorNumeric>1.5</cbc:MultiplierFactorNumeric>",
                b'<cbc:BaseAmount currencyID="EUR">300.00</cbc:BaseAmount>',
            ),
            ubl_allowance_charge(b"false", b"1.00"),
        ],
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.allowances == (
            replace(
                STANDARD_RATE,
                amount=Decimal("10.00"),
                base_amount=Decimal("200.00"),
                percentage=Decimal(5),
                reason="Rabatt",
                reason_code="95",
            ),
            replace(STANDARD_RATE, amount=Decimal("1.00")),
        )
        assert result.invoice.charges == (
            replace(
                STANDARD_RATE,
                amount=Decimal("4.50"),
                base_amount=Decimal("300.00"),
                percentage=Decimal("1.5"),
                reason="Fracht",
                reason_code="FC",
            ),
        )
        assert result.findings == ()


def test_the_charge_indicator_takes_the_values_of_xs_boolean() -> None:
    """`1` is a charge, `0` an allowance; any other value makes neither, which is left out."""
    cii, ubl = with_allowances_and_charges(
        [
            cii_allowance_charge(b"1", b"4.50"),
            cii_allowance_charge(b" 0 ", b"1.00"),
            cii_allowance_charge(b"yes", b"2.00"),
        ],
        [
            ubl_allowance_charge(b"1", b"4.50"),
            ubl_allowance_charge(b" 0 ", b"1.00"),
            ubl_allowance_charge(b"yes", b"2.00"),
        ],
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.allowances == (replace(STANDARD_RATE, amount=Decimal("1.00")),)
        assert result.invoice.charges == (replace(STANDARD_RATE, amount=Decimal("4.50")),)
        assert dropped(result) == ["BG-20/BG-21"]


def test_the_charge_indicator_is_read_as_any_term() -> None:
    """The first indicator holding a value counts, a further one is left out with a finding, and
    one holding elements is no value, so its allowance or charge is left out."""
    cii, ubl = with_allowances_and_charges(
        [
            cii_allowance_charge(b"true</udt:Indicator><udt:Indicator>false", b"4.50"),
            cii_allowance_charge(b"</udt:Indicator><udt:Indicator>false", b"1.00"),
            cii_allowance_charge(b"<ram:Name>true</ram:Name>", b"2.00"),
        ],
        [
            ubl_allowance_charge(b"true</cbc:ChargeIndicator><cbc:ChargeIndicator>false", b"4.50"),
            ubl_allowance_charge(b"</cbc:ChargeIndicator><cbc:ChargeIndicator>false", b"1.00"),
            ubl_allowance_charge(b"<cbc:Name>true</cbc:Name>", b"2.00"),
        ],
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.allowances == (replace(STANDARD_RATE, amount=Decimal("1.00")),)
        assert result.invoice.charges == (replace(STANDARD_RATE, amount=Decimal("4.50")),)
        assert dropped(result) == ["BG-20/BG-21", "BG-20/BG-21"]
        assert [f.rule for f in result.findings if f.rule == "HAFL-VALUE"] == ["HAFL-VALUE"]


def test_an_allowances_vat_category_is_the_first_of_vat() -> None:
    """A tax category of another tax is left out, as is a further one of VAT, each with a
    finding."""
    cii, ubl = with_allowances_and_charges(
        [
            cii_allowance_charge(
                b"false",
                b"1.00",
                after=b"<ram:CategoryTradeTax><ram:TypeCode>LOC</ram:TypeCode>"
                b"<ram:CategoryCode>Z</ram:CategoryCode>"
                b"<ram:RateApplicablePercent>3</ram:RateApplicablePercent></ram:CategoryTradeTax>",
            ),
            cii_allowance_charge(
                b"true",
                b"4.50",
                after=b"<ram:CategoryTradeTax><ram:TypeCode>VAT</ram:TypeCode>"
                b"<ram:CategoryCode>Z</ram:CategoryCode>"
                b"<ram:RateApplicablePercent>0</ram:RateApplicablePercent></ram:CategoryTradeTax>",
            ),
        ],
        [
            ubl_allowance_charge(
                b"false",
                b"1.00",
                after=b"<cac:TaxCategory><cbc:ID>Z</cbc:ID><cbc:Percent>3</cbc:Percent>"
                b"<cac:TaxScheme><cbc:ID>LOC</cbc:ID></cac:TaxScheme></cac:TaxCategory>",
            ),
            ubl_allowance_charge(
                b"true",
                b"4.50",
                after=b"<cac:TaxCategory><cbc:ID>Z</cbc:ID><cbc:Percent>0</cbc:Percent>"
                b"<cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:TaxCategory>",
            ),
        ],
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.allowances == (replace(STANDARD_RATE, amount=Decimal("1.00")),)
        assert result.invoice.charges == (
            AllowanceCharge(amount=Decimal("4.50"), vat_category_code="Z", vat_rate=Decimal(0)),
        )
        assert dropped(result) == ["BT-95", "BT-102"]


def test_a_tax_vat_counts_in_any_case() -> None:
    """REQ-003-PRS-F002: CEN's rules compare the type code and the tax scheme in upper case, so
    `vat` is VAT; the tax scheme is the first one holding a value."""
    data = CII.replace(b"<ram:TypeCode>VAT</ram:TypeCode>", b"<ram:TypeCode>vat</ram:TypeCode>")
    assert read_invoice(data) == read_invoice(CII)
    cii, ubl = with_allowances_and_charges(
        [
            cii_allowance_charge(
                b"false",
                b"1.00",
                after=b"<ram:CategoryTradeTax><ram:TypeCode> vat </ram:TypeCode>"
                b"<ram:CategoryCode>Z</ram:CategoryCode>"
                b"<ram:RateApplicablePercent>0</ram:RateApplicablePercent></ram:CategoryTradeTax>",
            ),
        ],
        [
            ubl_allowance_charge(
                b"false",
                b"1.00",
                after=b"<cac:TaxCategory><cbc:ID>Z</cbc:ID><cbc:Percent>0</cbc:Percent>"
                b"<cac:TaxScheme><cbc:ID> vat </cbc:ID></cac:TaxScheme></cac:TaxCategory>",
            ),
        ],
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.allowances == (
            AllowanceCharge(amount=Decimal("1.00"), vat_category_code="Z", vat_rate=Decimal(0)),
        )
        assert dropped(result) == ["BT-95"]
    ubl = with_allowances_and_charges(
        [],
        [
            ubl_allowance_charge(
                b"true",
                b"4.50",
                after=b"<cac:TaxCategory><cbc:ID>Z</cbc:ID><cbc:Percent>0</cbc:Percent>"
                b"<cac:TaxScheme><cbc:ID/></cac:TaxScheme>"
                b"<cac:TaxScheme><cbc:ID>LOC</cbc:ID></cac:TaxScheme></cac:TaxCategory>",
            ),
        ],
    )[1]
    result = read_invoice(ubl)
    assert result.invoice.charges == (replace(STANDARD_RATE, amount=Decimal("4.50")),)
    assert dropped(result) == ["BT-102"]


def test_a_ubl_lines_allowance_isnt_the_invoices() -> None:
    ubl = edit(
        UBL,
        b"</cac:OrderLineReference>",
        b"</cac:OrderLineReference>" + ubl_allowance_charge(b"false", b"1.00"),
    )
    result = read_invoice(ubl)
    assert result.invoice.allowances == ()
    assert result.findings == ()


# REQ-003-PRS-F002: a line's price and item details

CII_SELLER_ITEM = b"<ram:SellerAssignedID>246</ram:SellerAssignedID>"
CII_NET_PRICE = b"<ram:NetPriceProductTradePrice>"
CII_NET_END = b"</ram:NetPriceProductTradePrice>"
UBL_SELLER_ITEM = b"<cac:SellersItemIdentification>"
UBL_PRICE_AMOUNT = b'<cbc:PriceAmount currencyID="EUR">288.79</cbc:PriceAmount>'
FIRST_LINE = InvoiceLine(
    id="Zeitschrift [...]",
    note="Die letzte Lieferung im Rahmen des abgerechneten Abonnements erfolgt in 12/2016"
    " Lieferung erfolgt / erfolgte direkt vom Verlag",
    quantity=Decimal(1),
    unit_code="XPP",
    net_amount=Decimal("288.79"),
    net_price=Decimal("288.79"),
    vat_category_code="S",
    vat_rate=Decimal(7),
    item_name="Zeitschrift [...]",
    item_description="Zeitschrift Inland",
    seller_item_id="246",
)


def cii_gross_price(*parts: bytes) -> bytes:
    """01.01a with a gross price of these parts before the first line's net price."""
    return CII.replace(
        CII_NET_PRICE,
        b"<ram:GrossPriceProductTradePrice>"
        + b"".join(parts)
        + b"</ram:GrossPriceProductTradePrice>"
        + CII_NET_PRICE,
        1,
    )


def cii_price_allowance(indicator: bytes | None, amount: bytes) -> bytes:
    """An allowance on the price; without its charge indicator where `indicator` is None."""
    return (
        b"<ram:AppliedTradeAllowanceCharge>"
        + (
            b""
            if indicator is None
            else b"<ram:ChargeIndicator><udt:Indicator>"
            + indicator
            + b"</udt:Indicator></ram:ChargeIndicator>"
        )
        + b"<ram:ActualAmount>"
        + amount
        + b"</ram:ActualAmount></ram:AppliedTradeAllowanceCharge>"
    )


def ubl_price_allowance(indicator: bytes, amount: bytes, base_amount: bytes) -> bytes:
    return (
        b"<cac:AllowanceCharge><cbc:ChargeIndicator>"
        + indicator
        + b'</cbc:ChargeIndicator><cbc:Amount currencyID="EUR">'
        + amount
        + b'</cbc:Amount><cbc:BaseAmount currencyID="EUR">'
        + base_amount
        + b"</cbc:BaseAmount></cac:AllowanceCharge>"
    )


def ubl_price(*parts: bytes) -> bytes:
    """01.01a with these parts after the first line's net price."""
    return UBL.replace(UBL_PRICE_AMOUNT, UBL_PRICE_AMOUNT + b"".join(parts), 1)


def test_a_lines_note_price_and_item_details() -> None:
    """Every term of BT-127 and BG-29 to BG-31; the gross price less the discount is the net
    price."""
    cii = cii_gross_price(
        b"<ram:ChargeAmount>300.00</ram:ChargeAmount>",
        b'<ram:BasisQuantity unitCode="XPP">1</ram:BasisQuantity>',
        cii_price_allowance(b"false", b"11.21"),
    ).replace(
        CII_SELLER_ITEM,
        b'<ram:GlobalID schemeID="0160">4000001000005</ram:GlobalID>'
        + CII_SELLER_ITEM
        + b"<ram:BuyerAssignedID>B-246</ram:BuyerAssignedID>",
        1,
    )
    ubl = ubl_price(
        b'<cbc:BaseQuantity unitCode="XPP">1</cbc:BaseQuantity>',
        ubl_price_allowance(b"false", b"11.21", b"300.00"),
    )
    # In UBL's order: the buyer's identifier, the seller's, then the standard one.
    ubl = edit(
        ubl,
        UBL_SELLER_ITEM,
        b"<cac:BuyersItemIdentification><cbc:ID>B-246</cbc:ID></cac:BuyersItemIdentification>"
        + UBL_SELLER_ITEM,
    )
    ubl = edit(
        ubl,
        b"</cac:SellersItemIdentification>",
        b"</cac:SellersItemIdentification><cac:StandardItemIdentification>"
        b'<cbc:ID schemeID="0160">4000001000005</cbc:ID></cac:StandardItemIdentification>',
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.lines[0] == replace(
            FIRST_LINE,
            price_discount=Decimal("11.21"),
            gross_price=Decimal("300.00"),
            base_quantity=Decimal(1),
            base_quantity_unit_code="XPP",
            buyer_item_id="B-246",
            standard_item_id=Identifier(value="4000001000005", scheme="0160"),
        )
        assert result.findings == ()


def test_a_credit_notes_item_details() -> None:
    note = (ROOT / "tests/data/cen-en16931/ubl/examples/ubl-tc434-creditnote1.xml").read_bytes()
    line = read_invoice(note).invoice.lines[0]
    assert (line.item_description, line.seller_item_id) == ("Exonération du versement du PP", "V55")


GROSS_AMOUNT = b"<ram:ChargeAmount>288.79</ram:ChargeAmount>"


def cii_base_quantities(gross: bytes | None, net: bytes | None) -> bytes:
    """01.01a with a gross price and these base quantities in the first line's prices."""
    data = CII if gross is None else cii_gross_price(GROSS_AMOUNT, gross)
    return data if net is None else data.replace(CII_NET_END, net + CII_NET_END, 1)


def basis(attributes: bytes, value: bytes) -> bytes:
    return b"<ram:BasisQuantity" + attributes + b">" + value + b"</ram:BasisQuantity>"


C62 = b' unitCode="C62"'


@pytest.mark.parametrize(
    ("data", "quantity", "dropped_terms"),
    [
        (cii_base_quantities(basis(C62, b"2"), None), (Decimal(2), "C62"), []),
        (cii_base_quantities(None, basis(C62, b"2")), (Decimal(2), "C62"), []),
        (cii_base_quantities(basis(C62, b"2.0"), basis(C62, b"2")), (Decimal(2), "C62"), []),
        (cii_base_quantities(basis(C62, b"2"), basis(C62, b"1")), (Decimal(1), "C62"), ["BT-149"]),
        (
            cii_base_quantities(basis(C62, b"2"), basis(b' unitCode="KGM"', b"2")),
            (Decimal(2), "KGM"),
            ["BT-150"],
        ),
        (cii_base_quantities(basis(b"", b"1"), basis(C62, b"1")), (Decimal(1), "C62"), []),
        (cii_base_quantities(basis(C62, b"1"), basis(b"", b"1")), (Decimal(1), "C62"), []),
        (
            ubl_price(b'<cbc:BaseQuantity unitCode="C62"> </cbc:BaseQuantity>'),
            (None, "C62"),
            [],
        ),
    ],
    ids=[
        "gross",
        "net",
        "both-the-same",
        "both-differing",
        "units-differing",
        "unit-on-the-net-price",
        "unit-on-the-gross-price",
        "ubl-unit-alone",
    ],
)
def test_a_lines_base_quantity(
    data: bytes, quantity: tuple[Decimal | None, str], dropped_terms: list[str]
) -> None:
    """In CII the net price's, to which BT-146 applies, else the gross price's; a unit that only
    one of them gives counts, and also where the quantity's element is empty."""
    result = read_invoice(data)
    line = result.invoice.lines[0]
    assert (line.base_quantity, line.base_quantity_unit_code) == quantity
    assert dropped(result) == dropped_terms
    assert [f.rule for f in result.findings if f.rule != "HAFL-DROPPED"] == []


def test_a_base_quantity_is_a_number_as_any_other() -> None:
    """A gross price's `1E0` isn't an xs:decimal: missing, with a finding, and the net price's
    is read."""
    result = read_invoice(cii_base_quantities(basis(C62, b"1E0"), basis(C62, b"1")))
    line = result.invoice.lines[0]
    assert (line.base_quantity, line.base_quantity_unit_code) == (Decimal(1), "C62")
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == [("HAFL-VALUE", "BT-149")]


def test_only_an_allowance_on_the_price_gives_the_discount() -> None:
    """A charge, which EN 16931 doesn't have on a price, one whose indicator is neither, and a
    second allowance are left out; a CII one without its indicator is an allowance."""
    cii = cii_gross_price(
        GROSS_AMOUNT,
        cii_price_allowance(b"true", b"5.00"),
        cii_price_allowance(b"maybe", b"3.00"),
        cii_price_allowance(b"", b"4.00"),
        cii_price_allowance(None, b"1.00"),
        cii_price_allowance(b"false", b"2.00"),
    )
    ubl = ubl_price(
        ubl_price_allowance(b"true", b"5.00", b"290.00"),
        ubl_price_allowance(b"maybe", b"3.00", b"291.00"),
        ubl_price_allowance(b"0", b"1.00", b"288.79"),
        ubl_price_allowance(b"false", b"2.00", b"292.00"),
    )
    for data, drops in ((cii, 4), (ubl, 3)):
        result = read_invoice(data)
        line = result.invoice.lines[0]
        assert (line.price_discount, line.gross_price) == (Decimal("1.00"), Decimal("288.79"))
        assert [term.rstrip(",") for term in dropped(result)] == ["BT-147"] * drops


def test_a_price_allowance_without_an_amount_gives_nothing() -> None:
    """It holds no term of BG-29, so the allowance after it gives the discount."""
    cii = cii_gross_price(
        GROSS_AMOUNT,
        b"<ram:AppliedTradeAllowanceCharge><ram:ChargeIndicator><udt:Indicator>false"
        b"</udt:Indicator></ram:ChargeIndicator></ram:AppliedTradeAllowanceCharge>",
        cii_price_allowance(b"false", b"2.00"),
    )
    ubl = ubl_price(
        b"<cac:AllowanceCharge><cbc:ChargeIndicator>false</cbc:ChargeIndicator>"
        b"<cbc:AllowanceChargeReason>Rabatt</cbc:AllowanceChargeReason></cac:AllowanceCharge>",
        ubl_price_allowance(b"false", b"2.00", b"290.79"),
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        assert result.invoice.lines[0].price_discount == Decimal("2.00")
        assert result.findings == ()


def test_a_cii_gross_price_without_a_discount() -> None:
    result = read_invoice(cii_gross_price(b"<ram:ChargeAmount>288.79</ram:ChargeAmount>"))
    line = result.invoice.lines[0]
    assert (line.gross_price, line.price_discount) == (Decimal("288.79"), None)
    assert result.findings == ()


def test_a_standard_item_identifier_without_a_scheme() -> None:
    """Read without one, which BR-64 reports."""
    result = read_invoice(
        CII.replace(
            CII_SELLER_ITEM, b"<ram:GlobalID>4000001000005</ram:GlobalID>" + CII_SELLER_ITEM, 1
        )
    )
    assert result.invoice.lines[0].standard_item_id == Identifier(value="4000001000005")
    assert result.findings == ()


# REQ-003-PRS-F002: the document references


def cii_document(type_code: bytes, issuer_id: bytes, after: bytes = b"") -> bytes:
    """An additional referenced document of this type code, with `after` after the type code."""
    return (
        b"<ram:AdditionalReferencedDocument><ram:IssuerAssignedID>"
        + issuer_id
        + b"</ram:IssuerAssignedID><ram:TypeCode>"
        + type_code
        + b"</ram:TypeCode>"
        + after
        + b"</ram:AdditionalReferencedDocument>"
    )


def ubl_document(type_code: bytes, identifier: bytes) -> bytes:
    """An additional document reference of this document type code, `identifier` its cbc:ID."""
    return (
        b"<cac:AdditionalDocumentReference>"
        + identifier
        + b"<cbc:DocumentTypeCode>"
        + type_code
        + b"</cbc:DocumentTypeCode></cac:AdditionalDocumentReference>"
    )


def cii_referenced(element: bytes, issuer_id: bytes) -> bytes:
    return (
        b"<ram:"
        + element
        + b"><ram:IssuerAssignedID>"
        + issuer_id
        + b"</ram:IssuerAssignedID></ram:"
        + element
        + b">"
    )


CII_BUYER_END = b"</ram:BuyerTradeParty>"
CII_REFERENCES = edit(
    edit(
        edit(
            CII,
            CII_BUYER_END,
            CII_BUYER_END
            + cii_referenced(b"SellerOrderReferencedDocument", b"SO-14")
            + cii_referenced(b"BuyerOrderReferencedDocument", b"PO-13")
            + cii_referenced(b"ContractReferencedDocument", b"C-12")
            + cii_document(b"916", b"Anhang")
            + cii_document(b"50", b"T-17")
            + cii_document(b" 130 ", b"O-18", b"<ram:ReferenceTypeCode>ABZ</ram:ReferenceTypeCode>")
            + b"<ram:SpecifiedProcuringProject><ram:ID>P-11</ram:ID>"
            b"<ram:Name>Project reference</ram:Name></ram:SpecifiedProcuringProject>",
        ),
        b"<ram:ApplicableHeaderTradeDelivery/>",
        b"<ram:ApplicableHeaderTradeDelivery>"
        + cii_referenced(b"DespatchAdviceReferencedDocument", b"D-16")
        + cii_referenced(b"ReceivingAdviceReferencedDocument", b"R-15")
        + b"</ram:ApplicableHeaderTradeDelivery>",
    ),
    b"</ram:ApplicableHeaderTradeSettlement>",
    b"<ram:ReceivableSpecifiedTradeAccountingAccount><ram:ID>A-19</ram:ID>"
    b"</ram:ReceivableSpecifiedTradeAccountingAccount></ram:ApplicableHeaderTradeSettlement>",
)
# In UBL's order; an additional document of type code 50 is a project reference only in a
# credit note.
UBL_REFERENCES = edit(
    edit(
        UBL,
        b"<cbc:BuyerReference>",
        b"<cbc:AccountingCost>A-19</cbc:AccountingCost><cbc:BuyerReference>",
    ),
    UBL_SUPPLIER,
    b"<cac:OrderReference><cbc:ID>PO-13</cbc:ID><cbc:SalesOrderID>SO-14</cbc:SalesOrderID>"
    b"</cac:OrderReference><cac:DespatchDocumentReference><cbc:ID>D-16</cbc:ID>"
    b"</cac:DespatchDocumentReference><cac:ReceiptDocumentReference><cbc:ID>R-15</cbc:ID>"
    b"</cac:ReceiptDocumentReference><cac:OriginatorDocumentReference><cbc:ID>T-17</cbc:ID>"
    b"</cac:OriginatorDocumentReference><cac:ContractDocumentReference><cbc:ID>C-12</cbc:ID>"
    b"</cac:ContractDocumentReference>"
    + ubl_document(b"916", b"<cbc:ID>Anhang</cbc:ID>")
    + ubl_document(b"50", b"<cbc:ID>Ausschreibung</cbc:ID>")
    + ubl_document(b" 130 ", b'<cbc:ID schemeID="ABZ">O-18</cbc:ID>')
    + b"<cac:ProjectReference><cbc:ID>P-11</cbc:ID></cac:ProjectReference>"
    + UBL_SUPPLIER,
)


def with_references(invoice: Invoice) -> Invoice:
    return replace(
        invoice,
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


@pytest.mark.parametrize(
    ("base", "data"), [(CII, CII_REFERENCES), (UBL, UBL_REFERENCES)], ids=["cii", "ubl"]
)
def test_the_document_references(base: bytes, data: bytes) -> None:
    """BT-11 to BT-19; a supporting document (BG-24) is neither BT-17 nor BT-18."""
    result = read_invoice(data)
    assert result.invoice == with_references(read_invoice(base).invoice)
    assert result.findings == ()


def test_a_credit_notes_project_reference() -> None:
    """A UBL credit note has no cac:ProjectReference: the project is an additional document of
    type code 50."""
    note = (ROOT / "tests/data/cen-en16931/ubl/examples/ubl-tc434-creditnote1.xml").read_bytes()
    data = edit(
        note,
        b"<cac:AccountingSupplierParty>",
        ubl_document(b"50", b"<cbc:ID>P-11</cbc:ID>") + b"<cac:AccountingSupplierParty>",
    )
    invoice = read_invoice(data).invoice
    assert (invoice.project_reference, invoice.tender_or_lot_reference) == ("P-11", None)


def test_a_second_contract_reference_and_invoiced_object_are_dropped() -> None:
    cii = edit(
        CII,
        CII_BUYER_END,
        CII_BUYER_END
        + cii_referenced(b"ContractReferencedDocument", b"C-1")
        + cii_referenced(b"ContractReferencedDocument", b"C-2")
        + cii_document(b"130", b"O-1")
        + cii_document(b"130", b"O-2"),
    )
    ubl = edit(
        UBL,
        UBL_SUPPLIER,
        b"<cac:ContractDocumentReference><cbc:ID>C-1</cbc:ID></cac:ContractDocumentReference>"
        b"<cac:ContractDocumentReference><cbc:ID>C-2</cbc:ID></cac:ContractDocumentReference>"
        + ubl_document(b"130", b"<cbc:ID>O-1</cbc:ID>")
        + ubl_document(b"130", b"<cbc:ID>O-2</cbc:ID>")
        + UBL_SUPPLIER,
    )
    for data in (cii, ubl):
        result = read_invoice(data)
        invoice = result.invoice
        assert (invoice.contract_reference, invoice.invoiced_object_id) == (
            "C-1",
            Identifier(value="O-1"),
        )
        assert dropped(result) == ["BT-12", "BT-18"]
        # Each finding names the value left out.
        assert [f.text.rsplit(": ", 1)[-1] for f in result.findings] == ["'C-2'", "'O-2'"]


def test_a_cii_lines_object_identifier_isnt_the_invoices() -> None:
    """A line's additional document of type code 130 is BT-128."""
    summation = b"</ram:SpecifiedTradeSettlementLineMonetarySummation>"
    data = CII.replace(summation, summation + cii_document(b"130", b"ANG-1"), 1)
    result = read_invoice(data)
    assert result.invoice.invoiced_object_id is None
    assert result.findings == ()


def test_a_tender_reference_holding_elements_is_reported_once() -> None:
    data = edit(
        CII,
        CII_BUYER_END,
        CII_BUYER_END
        + cii_document(b"50", b"<ram:X>a</ram:X></ram:IssuerAssignedID><ram:IssuerAssignedID>T-17"),
    )
    result = read_invoice(data)
    assert result.invoice.tender_or_lot_reference == "T-17"
    assert [(f.rule, f.text.split()[0]) for f in result.findings] == [("HAFL-VALUE", "BT-17")]


def test_a_cii_invoiced_objects_scheme() -> None:
    """ram:ReferenceTypeCode, or else the schemeID; a differing schemeID beside it, and a scheme
    without its identifier, are left out."""
    attribute = b'<ram:IssuerAssignedID schemeID="AAA">O-18</ram:IssuerAssignedID>'
    code = b"<ram:ReferenceTypeCode>ABZ</ram:ReferenceTypeCode>"
    cases: list[tuple[bytes, Identifier | None, list[str]]] = [
        (
            attribute + b"<ram:TypeCode>130</ram:TypeCode>",
            Identifier(value="O-18", scheme="AAA"),
            [],
        ),
        (
            attribute + b"<ram:TypeCode>130</ram:TypeCode>" + code,
            Identifier(value="O-18", scheme="ABZ"),
            ["BT-18-1"],
        ),
        (b"<ram:TypeCode>130</ram:TypeCode>" + code, None, ["BT-18-1"]),
    ]
    for document, expected, drops in cases:
        data = edit(
            CII,
            CII_BUYER_END,
            CII_BUYER_END
            + b"<ram:AdditionalReferencedDocument>"
            + document
            + b"</ram:AdditionalReferencedDocument>",
        )
        result = read_invoice(data)
        assert result.invoice.invoiced_object_id == expected
        assert dropped(result) == drops
        assert [f.rule for f in result.findings if f.rule != "HAFL-DROPPED"] == []


def test_a_supporting_documents_findings_name_bg_24() -> None:
    """Its type code decides between BG-24, BT-17 and BT-18; a second one names all three."""
    data = edit(
        CII,
        CII_BUYER_END,
        CII_BUYER_END + cii_document(b"916", b"Anhang", b"<ram:TypeCode>916</ram:TypeCode>"),
    )
    result = read_invoice(data)
    assert [f.text.split(" (")[0] for f in result.findings] == ["BG-24, BT-17, BT-18"]

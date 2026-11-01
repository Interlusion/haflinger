"""Reading CII and UBL: refusals, reading choices and exact values.

REQ-003-PRS-F001 to REQ-003-PRS-F003, REQ-003-PRS-F006, REQ-003-PRS-F008; REQ-001-PRS-F004,
REQ-001-PRS-F005, REQ-001-PRS-NF001 and REQ-001-PRS-NF003 for reading. Most inputs are KoSIT
case 01.01a with one change.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from haflinger import InvoiceReadError, Note, ReadResult, read_invoice

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
    ids=["cii-address", "cii-organization", "ubl-address", "ubl-item", "ubl-bg-30", "ubl-bt-31"],
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

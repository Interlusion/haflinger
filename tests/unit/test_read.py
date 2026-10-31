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
def test_refuses_a_pdf_without_the_pdf_extra(prefix: bytes) -> None:
    assert "pdf" in refusal(prefix + b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n").lower()


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

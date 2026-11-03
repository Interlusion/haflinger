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
    Contact,
    CreditTransfer,
    Delivery,
    DirectDebit,
    Identifier,
    Invoice,
    InvoiceReadError,
    InvoiceWriteError,
    Note,
    PaymentCard,
    PaymentInstructions,
    Period,
    PrecedingInvoice,
    read_invoice,
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
            replace(INVOICE, delivery=Delivery(city="")),
            "BT-77 is empty; a missing term is None",
        ),
        (replace(INVOICE, delivery="Lager"), "BG-13 is not a Delivery"),
        (replace(INVOICE, invoicing_period="March"), "BG-14 is not a Period"),
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
        "empty-city",
        "str-delivery",
        "str-period",
        "list-preceding-invoices",
        "buyer-tax-registration",
        "two-buyer-identifiers",
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
            replace(INVOICE, delivery=Delivery(city="Example City"), specification_id=XRECHNUNG),
            "BR-57",
        ),
        (replace(INVOICE, delivery=Delivery(city="Example City")), "HAFL-XSD"),
    ],
    ids=[
        "instructions-without-means-code",
        "instructions-without-means-code-factur-x",
        "credit-transfer-without-account",
        "preceding-invoice-without-number",
        "deliver-to-address-without-country",
        "deliver-to-address-without-country-factur-x",
    ],
)
def test_the_official_artefacts_refuse_a_group_without_a_term_it_needs(
    invoice: Invoice, rule: str
) -> None:
    """Written, since CII D16B can hold the rest, and refused after writing: payment
    instructions without their means code (BT-81) by BR-49, a credit transfer without its
    account (BT-84) by BR-50, a preceding invoice without its number (BT-25) by BR-55, a deliver
    to address without its country code (BT-80) by BR-57; for EN 16931, Factur-X's XML Schema
    requires BT-81 and BT-80 (REQ-004-PRS-F001)."""
    with pytest.raises(InvoiceWriteError, match=rule) as refusal:
        write_cii(invoice)
    assert rule in {finding.rule for finding in refusal.value.findings}
    assert refusal.value.document is not None
    assert read_invoice(refusal.value.document).invoice == invoice


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

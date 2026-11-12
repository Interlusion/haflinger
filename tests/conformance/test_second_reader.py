"""KoSIT's reading stylesheet as the second reader: it reads every official file to the same model
as Haflinger (REQ-003-PRS-F005, ADR-005)."""

from dataclasses import replace
from pathlib import Path

import pytest

from haflinger import (
    DirectDebit,
    Identifier,
    InvoiceReadError,
    PaymentInstructions,
    _kosit,
    read_invoice,
)
from haflinger.pdf import extract_xml

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/data/kosit-testsuite/instances"
CREDIT_NOTE = ROOT / "tests/data/cen-en16931/ubl/examples/ubl-tc434-creditnote1.xml"
CORPUS = ROOT / "tests/data/zugferd-corpus"


def readable(path: Path) -> bool:
    try:
        read_invoice(path.read_bytes())
    except InvoiceReadError:
        return False
    return True


# The corpus PDFs `read_invoice` reads; KoSIT's stylesheet gets their embedded XML.
PDFS = [path for path in sorted(CORPUS.rglob("*.pdf")) if readable(path)]
FILES = [*sorted(SUITE.rglob("*.xml")), CREDIT_NOTE, *PDFS]


def test_the_files_are_there() -> None:
    assert len(FILES) == 87 + 12


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_kosit_reads_what_haflinger_reads(path: Path) -> None:
    data = path.read_bytes()
    xml = extract_xml(data) if path.suffix == ".pdf" else data
    ours, theirs = read_invoice(data), _kosit.read_invoice(xml)
    assert theirs.findings == ()
    assert theirs.invoice.syntax == ours.invoice.syntax
    expected, read = _kosit.comparable(ours.invoice, theirs.invoice)
    assert read == expected


def test_kosit_still_loses_a_cii_line_objects_scheme() -> None:
    """Once a new release gives `ram:ReferenceTypeCode` as BT-128-1 without a schemeID,
    `_kosit.comparable` stops evening it out."""
    data = (SUITE / "standard/03.07a-INVOICE_uncefact.xml").read_bytes()
    ours = [line.object_id for line in read_invoice(data).invoice.lines if line.object_id]
    theirs = [line.object_id for line in _kosit.read_invoice(data).invoice.lines if line.object_id]
    assert ours == [Identifier(value="ANG987654321", scheme="ABZ")]
    assert theirs == [Identifier(value="ANG987654321")]


def test_kosit_still_loses_a_cii_invoiced_objects_scheme() -> None:
    """Once a new release gives `ram:ReferenceTypeCode` as BT-18-1 without a schemeID,
    `_kosit.comparable` stops evening it out."""
    data = with_invoiced_object(b"<ram:ReferenceTypeCode>ABZ</ram:ReferenceTypeCode>")
    ours, theirs = read_invoice(data).invoice, _kosit.read_invoice(data).invoice
    assert ours.invoiced_object_id == Identifier(value="O-18", scheme="ABZ")
    assert theirs.invoiced_object_id == Identifier(value="O-18")
    expected, read = _kosit.comparable(ours, theirs)
    assert read == expected


def with_invoiced_object(after: bytes) -> bytes:
    """01.01a with an invoiced object identifier `O-18`, `after` after its type code."""
    data = (SUITE / "standard/01.01a-INVOICE_uncefact.xml").read_bytes()
    end = b"</ram:BuyerTradeParty>"
    assert data.count(end) == 1
    document = (
        b"<ram:AdditionalReferencedDocument><ram:IssuerAssignedID>O-18</ram:IssuerAssignedID>"
        b"<ram:TypeCode>130</ram:TypeCode>" + after + b"</ram:AdditionalReferencedDocument>"
    )
    return data.replace(end, end + document)


def test_comparable_still_compares_the_schemes_kosit_gives() -> None:
    """A scheme KoSIT's CII stylesheet gives, and every one in UBL, is compared: only one it
    loses is evened out."""
    ours = read_invoice(with_invoiced_object(b"")).invoice
    other = Identifier(value="O-18", scheme="AAA")
    line = replace(ours.lines[0], object_id=Identifier(value="O-1", scheme="ABZ"))
    ours = replace(ours, invoiced_object_id=other, lines=(line, *ours.lines[1:]))
    theirs = replace(
        ours,
        invoiced_object_id=Identifier(value="O-18", scheme="ABZ"),
        lines=(replace(line, object_id=Identifier(value="O-1", scheme="AAA")), *ours.lines[1:]),
    )
    expected, read = _kosit.comparable(ours, theirs)
    assert read.invoiced_object_id != expected.invoiced_object_id
    assert read.lines[0].object_id != expected.lines[0].object_id
    lost = replace(theirs, invoiced_object_id=Identifier(value="O-18"))
    assert _kosit.comparable(ours, lost)[0].invoiced_object_id == Identifier(value="O-18")
    ubl = replace(ours, syntax="ubl")
    expected, read = _kosit.comparable(ubl, replace(lost, syntax="ubl"))
    assert expected.invoiced_object_id == other
    assert read.invoiced_object_id == Identifier(value="O-18")


def test_kosit_still_gives_a_cii_vat_point_date_code_as_written() -> None:
    """Once a new release gives EN 16931's code for CII's, `_kosit.comparable` stops evening it
    out."""
    data = (SUITE / "technical-cases/cius/01.02_comprehensive_test_uncefact.xml").read_bytes()
    ours, theirs = read_invoice(data).invoice, _kosit.read_invoice(data).invoice
    assert (ours.vat_point_date_code, theirs.vat_point_date_code) == ("3", "5")
    expected, read = _kosit.comparable(ours, theirs)
    assert read == expected


def test_kosit_still_loses_a_cii_payment_reference_without_payment_means() -> None:
    """Once a new release gives BT-83 without a `ram:SpecifiedTradeSettlementPaymentMeans`,
    `_kosit.comparable` stops evening it out (ITEM-006)."""
    pdf = CORPUS / "ZUGFeRDv2/fail/FNFE-factur-x-examples/Avoir_FR_type380_EN16931.pdf"
    ours = read_invoice(pdf.read_bytes()).invoice
    theirs = _kosit.read_invoice(extract_xml(pdf.read_bytes())).invoice
    assert ours.payment_instructions is not None
    assert ours.payment_instructions.remittance_information == "AV-2017-0005"
    assert theirs.payment_instructions is None
    expected, read = _kosit.comparable(ours, theirs)
    assert read == expected


def test_comparable_still_compares_payment_instructions_with_a_payment_means() -> None:
    """Only CII payment instructions without a payment means, which KoSIT's stylesheet loses, are
    evened out, a direct debit's mandate and creditor among them: those with a payment means
    term, those KoSIT gives and UBL's are compared."""
    pdf = CORPUS / "ZUGFeRDv2/fail/FNFE-factur-x-examples/Avoir_FR_type380_EN16931.pdf"
    ours = read_invoice(pdf.read_bytes()).invoice
    theirs = _kosit.read_invoice(extract_xml(pdf.read_bytes())).invoice
    payment = ours.payment_instructions
    assert payment is not None

    def evened(instructions: PaymentInstructions, kosits: PaymentInstructions | None) -> bool:
        mine = replace(ours, payment_instructions=instructions)
        return _kosit.comparable(mine, replace(theirs, payment_instructions=kosits))[0] != mine

    mandate = DirectDebit(mandate_reference="M-1", creditor_id="C-1")
    assert evened(replace(payment, direct_debit=mandate), None)
    assert not evened(replace(payment, means_code="58"), None)
    assert not evened(replace(payment, direct_debit=replace(mandate, debited_account_id="A")), None)
    assert not evened(payment, PaymentInstructions(remittance_information="other"))
    ubl = replace(ours, syntax="ubl")
    assert _kosit.comparable(ubl, replace(theirs, syntax="ubl"))[0] == ubl


def test_kosit_reads_a_cii_vat_point_date_code_repeated_in_each_vat_entry_once() -> None:
    """KoSIT's CII stylesheet gives one BT-8 for each ram:ApplicableTradeTax holding one, which
    CEN's CII-SR-462 allows with the same code; another code is left out with a finding."""
    data = (SUITE / "standard/01.01a-INVOICE_uncefact.xml").read_bytes()
    head, header, settlement = data.partition(b"<ram:ApplicableHeaderTradeSettlement>")
    end = b"</ram:ApplicableTradeTax>"
    assert settlement.count(end) == 1

    def second_tax(code: bytes) -> bytes:
        return (
            head
            + header
            + settlement.replace(
                end,
                end + b"<ram:ApplicableTradeTax><ram:CalculatedAmount>0.00</ram:CalculatedAmount>"
                b"<ram:TypeCode>VAT</ram:TypeCode><ram:BasisAmount>0.00</ram:BasisAmount>"
                b"<ram:CategoryCode>Z</ram:CategoryCode><ram:DueDateTypeCode>"
                + code
                + b"</ram:DueDateTypeCode><ram:RateApplicablePercent>0</ram:RateApplicablePercent>"
                b"</ram:ApplicableTradeTax>",
            ).replace(
                b"<ram:RateApplicablePercent>7",
                b"<ram:DueDateTypeCode>5</ram:DueDateTypeCode><ram:RateApplicablePercent>7",
                1,
            )
        )

    same = _kosit.read_invoice(second_tax(b"5"))
    assert (same.invoice.vat_point_date_code, same.findings) == ("5", ())
    other = _kosit.read_invoice(second_tax(b"29"))
    assert other.invoice.vat_point_date_code == "5"
    assert [finding.text.split()[0] for finding in other.findings] == ["BT-8"]


def test_kosit_reads_a_repeated_ubl_vat_point_date_code_as_haflinger_does() -> None:
    """UBL-SR-49 allows one: a second one, with the same code, is left out with a finding."""
    data = (SUITE / "standard/01.01a-INVOICE_ubl.xml").read_bytes()
    supplier = b"<cac:AccountingSupplierParty>"
    period = b"<cac:InvoicePeriod><cbc:DescriptionCode>35</cbc:DescriptionCode></cac:InvoicePeriod>"
    assert data.count(supplier) == 1
    data = data.replace(supplier, period + period + supplier)
    for result in (read_invoice(data), _kosit.read_invoice(data)):
        assert result.invoice.vat_point_date_code == "35"
        assert [finding.text.split()[0] for finding in result.findings] == ["BT-8"]


def test_kosit_reads_no_allowance_where_its_elements_are_empty() -> None:
    """KoSIT's stylesheet gives BG-20 and BG-27 for an allowance whose only term element is
    empty; it holds no term, as Haflinger's reading finds."""
    data = (SUITE / "standard/01.01a-INVOICE_uncefact.xml").read_bytes()
    empty = (
        b"<ram:SpecifiedTradeAllowanceCharge><ram:ChargeIndicator><udt:Indicator>false"
        b"</udt:Indicator></ram:ChargeIndicator><ram:Reason/></ram:SpecifiedTradeAllowanceCharge>"
    )
    period, terms = b"</ram:BillingSpecifiedPeriod>", b"<ram:SpecifiedTradePaymentTerms>"
    assert data.count(period) == data.count(terms) == 1
    data = data.replace(period, period + empty).replace(terms, empty + terms)
    for result in (read_invoice(data), _kosit.read_invoice(data)):
        assert (result.invoice.allowances, result.invoice.lines[0].allowances) == ((), ())
        assert result.findings == ()


def test_kosit_still_leaves_the_subject_code_in_ubl_notes() -> None:
    """Once a new release reads `#XXX#` as BT-21, `_kosit.comparable` stops evening it out."""
    data = (SUITE / "standard/01.01a-INVOICE_ubl.xml").read_bytes()
    (note,) = _kosit.read_invoice(data).invoice.notes
    assert note.subject_code is None
    assert (note.text or "").startswith("#ADU#")


def test_kosit_leaves_out_the_references_documents_as_supporting_documents() -> None:
    """KoSIT's stylesheets give BT-17's and BT-18's additional documents as supporting documents
    too where they hold a description or location; REQ-003-PRS-F002 reads neither as one."""
    data = (SUITE / "standard/01.01a-INVOICE_uncefact.xml").read_bytes()
    documents = (
        b"<ram:AdditionalReferencedDocument><ram:IssuerAssignedID>T-17</ram:IssuerAssignedID>"
        b"<ram:TypeCode>50</ram:TypeCode><ram:Name>Ausschreibung</ram:Name>"
        b"</ram:AdditionalReferencedDocument><ram:AdditionalReferencedDocument>"
        b"<ram:IssuerAssignedID>O-18</ram:IssuerAssignedID>"
        b"<ram:URIID>https://example.com/o-18</ram:URIID><ram:TypeCode>130</ram:TypeCode>"
        b"</ram:AdditionalReferencedDocument>"
    )
    end = b"</ram:BuyerTradeParty>"
    assert data.count(end) == 1
    invoice = _kosit.read_invoice(data.replace(end, end + documents)).invoice
    assert (invoice.tender_or_lot_reference, invoice.supporting_documents) == ("T-17", ())

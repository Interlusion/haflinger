"""Reading through KoSIT's visualisation stylesheets: the tests' independent second reader
(ADR-005, REQ-003-PRS-F005). Never on the path of `read_invoice`.

KoSIT's stylesheets turn a CII invoice, a UBL invoice or a UBL credit note into one semantic XML
in which every element carries its business term ID (`xr:id="BT-1"`). This module reads the
model from that XML by business term ID alone, apart from the root elements that pick the
stylesheet and four limits of KoSIT's stylesheet: the UBL notes' subject codes and a CII
invoiced or line object identifier's scheme, which `comparable` evens out between the two
models; and a CII account given in two forms and BT-17's and BT-18's additional documents given
as supporting documents too, for which `_account` and `_supporting_documents` read the source
path KoSIT's stylesheet records.
"""

import re
from dataclasses import replace
from datetime import date
from decimal import Decimal

from haflinger import _saxon, cii, ubl
from haflinger._allowances import ALLOWANCE, CHARGE, AllowanceChargeTerms
from haflinger._items import classifications
from haflinger._parties import (
    BUYER,
    DELIVER_TO,
    LOCATION,
    PAYEE_IDENTIFIER,
    SELLER,
    TAX_REPRESENTATIVE_ADDRESS,
    Address,
    AddressTerms,
    PartyTerms,
    contact,
    identifier,
    identifiers,
    one_identifier,
)
from haflinger._periods import INVOICING_PERIOD, LINE_PERIOD, PeriodTerms
from haflinger._xml import XML_WHITESPACE, Node, Reading, none_if_empty, parse
from haflinger.errors import InvoiceReadError
from haflinger.model import (
    AllowanceCharge,
    CreditTransfer,
    Delivery,
    DirectDebit,
    Identifier,
    Invoice,
    InvoiceLine,
    Note,
    Party,
    Payee,
    PaymentCard,
    PaymentInstructions,
    Period,
    PrecedingInvoice,
    SupportingDocument,
    Syntax,
    TaxRepresentative,
    Totals,
    VatBreakdown,
)
from haflinger.read import ReadResult

XR = "urn:ce.eu:en16931:2017:xoev-de:kosit:standard:xrechnung-1"

_STYLESHEETS: dict[str, tuple[str, Syntax]] = {
    cii.TAG: ("kosit-visualization/xsl/cii-xr.xsl", "cii"),
    ubl.INVOICE_TAG: ("kosit-visualization/xsl/ubl-invoice-xr.xsl", "ubl"),
    ubl.CREDIT_NOTE_TAG: ("kosit-visualization/xsl/ubl-creditnote-xr.xsl", "ubl"),
}
# The source path KoSIT's stylesheet gives a BT-84 read from ram:IBANID, indexed where repeated.
_IBAN_SOURCE = re.compile(r"ram:IBANID(\[[0-9]+\])?$")
# KoSIT's stylesheets write dates as YYYY-MM-DD in both syntaxes.
_ISO_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")


def read_invoice(data: bytes) -> ReadResult:
    """Like `haflinger.read_invoice` for XML, through KoSIT's stylesheets. The findings are
    those of reading the semantic XML, with its locations."""
    semantic, syntax = semantic_xml(data)
    reading = Reading(parse(semantic), {"xr": XR}, "xr:invoice")
    return ReadResult(invoice=_invoice(reading.root, syntax), findings=reading.findings())


def semantic_xml(data: bytes) -> tuple[bytes, Syntax]:
    """The semantic XML KoSIT's stylesheet makes of a CII or UBL invoice, with the syntax it was
    read from."""
    root = parse(data)
    if root.tag not in _STYLESHEETS:
        raise InvoiceReadError(
            f"the root element {root.tag} is neither a CII invoice nor a UBL invoice or credit note"
        )
    stylesheet, syntax = _STYLESHEETS[root.tag]
    (semantic,) = _saxon.transform(data, stylesheet)
    return semantic, syntax


# REQ-003-PRS-F005: the limits of KoSIT's stylesheet, to apply to its model before comparing it
# with Haflinger's.
#
# UBL has no element for the note's subject code (BT-21). KoSIT's stylesheet leaves the `#XXX#`
# that XRechnung and Peppol put at the start of the note's text (BT-22) in the text, while
# REQ-003-PRS-F002 reads it as BT-21. No report needed: the prefix is a convention, not part of
# EN 16931-3-2.
#
# The pattern repeats `ubl`'s on purpose: sharing its code would carry a mistake in Haflinger's
# reading of notes into the reader that checks it.
_SUBJECT_CODE = re.compile(r"#([A-Z]{3})#(.*)", re.DOTALL)


def _with_subject_codes(invoice: Invoice) -> Invoice:
    """The model KoSIT's stylesheet gives, with each UBL note's `#XXX#` read as BT-21."""
    if invoice.syntax != "ubl":
        return invoice
    notes: list[Note] = []
    for note in invoice.notes:
        match = _SUBJECT_CODE.fullmatch(note.text or "")
        if note.subject_code is None and match is not None:
            note = Note(subject_code=match[1], text=match[2].strip(XML_WHITESPACE) or None)
        notes.append(note)
    return replace(invoice, notes=tuple(notes))


def comparable(ours: Invoice, theirs: Invoice) -> tuple[Invoice, Invoice]:
    """Haflinger's model and KoSIT's of one invoice, with the limits of KoSIT's stylesheet that
    the models show evened out: the UBL notes' subject codes, read as BT-21 in `theirs`; and the
    scheme of a CII invoiced object identifier (BT-18-1) and of a line object identifier
    (BT-128-1), left out of `ours` where `theirs` holds the identifier without one. KoSIT's CII
    stylesheet gives `ram:ReferenceTypeCode` as the scheme only where the `ram:IssuerAssignedID`
    has a `schemeID` too (the template `identifier-with-scheme` in `common-xr.xsl` tests
    `@schemeID`), where REQ-003-PRS-F002 reads it; every scheme it gives is still compared, and
    the CII and UBL files of a case agree on it (REQ-003-PRS-F004, ITEM-006)."""
    if theirs.syntax == "ubl":
        return ours, _with_subject_codes(theirs)
    if theirs.syntax != "cii":
        return ours, theirs
    lines = ours.lines
    if len(lines) == len(theirs.lines):
        lines = tuple(
            replace(line, object_id=_without_lost_scheme(line.object_id, their.object_id))
            for line, their in zip(lines, theirs.lines, strict=True)
        )
    invoiced_object = _without_lost_scheme(ours.invoiced_object_id, theirs.invoiced_object_id)
    return replace(ours, invoiced_object_id=invoiced_object, lines=lines), theirs


def _without_lost_scheme(ours: Identifier | None, theirs: Identifier | None) -> Identifier | None:
    """`ours` without its scheme where `theirs` is the same identifier without one."""
    if ours is None or theirs is None or theirs.scheme is not None or ours.value != theirs.value:
        return ours
    return replace(ours, scheme=None)


def _term(*terms: str) -> str:
    """The path to a business term by its ID, through the groups before it."""
    return "/".join(f"xr:*[@xr:id='{term}']" for term in terms)


def _text(node: Node, *terms: str) -> str | None:
    return node.text(_term(*terms), terms[-1])


def _identifier(node: Node, *terms: str) -> Identifier | None:
    """An identifier with its scheme, which KoSIT's stylesheets give as `scheme_identifier`."""
    return identifier(node.first(_term(*terms), terms[-1]), "scheme_identifier")


def _decimal(node: Node, *terms: str) -> Decimal | None:
    return node.decimal(_term(*terms), terms[-1])


def _date(node: Node, term: str) -> date | None:
    found = node.first(_term(term), term)
    return None if found is None else found.as_date(term, _ISO_DATE, "YYYY-MM-DD")


def _invoice(invoice: Node, syntax: Syntax) -> Invoice:
    return Invoice(
        syntax=syntax,
        number=_text(invoice, "BT-1"),
        issue_date=_date(invoice, "BT-2"),
        type_code=_text(invoice, "BT-3"),
        currency_code=_text(invoice, "BT-5"),
        tax_currency_code=_text(invoice, "BT-6"),
        due_date=_date(invoice, "BT-9"),
        buyer_reference=_text(invoice, "BT-10"),
        project_reference=_text(invoice, "BT-11"),
        contract_reference=_text(invoice, "BT-12"),
        purchase_order_reference=_text(invoice, "BT-13"),
        sales_order_reference=_text(invoice, "BT-14"),
        receiving_advice_reference=_text(invoice, "BT-15"),
        despatch_advice_reference=_text(invoice, "BT-16"),
        tender_or_lot_reference=_text(invoice, "BT-17"),
        invoiced_object_id=_identifier(invoice, "BT-18"),
        buyer_accounting_reference=_text(invoice, "BT-19"),
        payment_terms=_text(invoice, "BT-20"),
        business_process=_text(invoice, "BG-2", "BT-23"),
        specification_id=_text(invoice, "BG-2", "BT-24"),
        notes=tuple(
            Note(subject_code=_text(note, "BT-21"), text=_text(note, "BT-22"))
            for note in invoice.findall(_term("BG-1"))
        ),
        preceding_invoices=tuple(
            PrecedingInvoice(number=_text(reference, "BT-25"), issue_date=_date(reference, "BT-26"))
            for reference in invoice.findall(_term("BG-3"))
        ),
        seller=_party(invoice.find(_term("BG-4")), SELLER),
        buyer=_party(invoice.find(_term("BG-7")), BUYER),
        payee=_payee(invoice.group(_term("BG-10"), "BG-10")),
        tax_representative=_tax_representative(invoice.group(_term("BG-11"), "BG-11")),
        delivery=_delivery(invoice.group(_term("BG-13"), "BG-13")),
        invoicing_period=_period(invoice, INVOICING_PERIOD),
        payment_instructions=_payment_instructions(invoice.group(_term("BG-16"), "BG-16")),
        allowances=tuple(
            _allowance_charge(node, ALLOWANCE) for node in invoice.findall(_term("BG-20"))
        ),
        charges=tuple(_allowance_charge(node, CHARGE) for node in invoice.findall(_term("BG-21"))),
        totals=_totals(invoice.find(_term("BG-22"))),
        vat_breakdown=tuple(_vat_breakdown(vat) for vat in invoice.findall(_term("BG-23"))),
        supporting_documents=_supporting_documents(invoice),
        lines=tuple(_line(line) for line in invoice.findall(_term("BG-25"))),
    )


def _party(party: Node | None, terms: PartyTerms) -> Party | None:
    if party is None:
        return None
    contact_group = party.find(_term(terms.contact))
    return Party(
        name=_text(party, terms.name),
        trading_name=_text(party, terms.trading_name),
        # KoSIT's stylesheets give an identifier's scheme as `scheme_identifier`.
        identifiers=identifiers(
            party.holding(terms.identifier, _term(terms.identifier)),
            terms.identifier,
            one=terms.one_identifier,
            scheme="scheme_identifier",
        ),
        legal_registration_id=_identifier(party, terms.legal_registration_id),
        additional_legal_information=None
        if terms.additional_legal_information is None
        else _text(party, terms.additional_legal_information),
        vat_id=_text(party, terms.vat_id),
        tax_registration_id=(
            None if terms.tax_registration is None else _text(party, terms.tax_registration)
        ),
        electronic_address=_identifier(party, terms.electronic_address),
        **_address(party, terms.address),
        contact=None
        if contact_group is None
        else contact(
            point=_text(contact_group, terms.contact_point),
            telephone=_text(contact_group, terms.telephone),
            email=_text(contact_group, terms.email),
        ),
    )


def _payee(payee: Node | None) -> Payee | None:
    if payee is None:
        return None
    return none_if_empty(
        Payee(
            name=_text(payee, "BT-59"),
            identifier=one_identifier(
                payee.holding(PAYEE_IDENTIFIER, _term(PAYEE_IDENTIFIER)),
                PAYEE_IDENTIFIER,
                "scheme_identifier",
            ),
            legal_registration_id=_identifier(payee, "BT-61"),
        )
    )


def _tax_representative(party: Node | None) -> TaxRepresentative | None:
    if party is None:
        return None
    return none_if_empty(
        TaxRepresentative(
            name=_text(party, "BT-62"),
            vat_id=_text(party, "BT-63"),
            **_address(party, TAX_REPRESENTATIVE_ADDRESS),
        )
    )


def _address(holder: Node, terms: AddressTerms) -> Address:
    """The address group within `holder`: a party, or the delivery information."""
    return Address(
        address_line_1=_text(holder, terms.group, terms.address_line_1),
        address_line_2=_text(holder, terms.group, terms.address_line_2),
        address_line_3=_text(holder, terms.group, terms.address_line_3),
        city=_text(holder, terms.group, terms.city),
        post_code=_text(holder, terms.group, terms.post_code),
        country_subdivision=_text(holder, terms.group, terms.country_subdivision),
        country_code=_text(holder, terms.group, terms.country_code),
    )


def _delivery(delivery: Node | None) -> Delivery | None:
    if delivery is None:
        return None
    return none_if_empty(
        Delivery(
            party_name=_text(delivery, "BT-70"),
            location=one_identifier(
                delivery.holding(LOCATION, _term(LOCATION)), LOCATION, "scheme_identifier"
            ),
            date=_date(delivery, "BT-72"),
            **_address(delivery, DELIVER_TO),
        )
    )


def _period(parent: Node, terms: PeriodTerms) -> Period | None:
    """BG-14 or BG-26."""
    period = parent.group(_term(terms.group), terms.group)
    if period is None:
        return None
    return none_if_empty(Period(start=_date(period, terms.start), end=_date(period, terms.end)))


def _payment_instructions(payment: Node | None) -> PaymentInstructions | None:
    if payment is None:
        return None
    card = payment.group(_term("BG-18"), "BG-18")
    debit = payment.group(_term("BG-19"), "BG-19")
    return none_if_empty(
        PaymentInstructions(
            means_code=_text(payment, "BT-81"),
            means_text=_text(payment, "BT-82"),
            remittance_information=_text(payment, "BT-83"),
            credit_transfers=tuple(
                CreditTransfer(
                    account_id=_account(transfer),
                    account_name=_text(transfer, "BT-85"),
                    provider_id=_text(transfer, "BT-86"),
                )
                for transfer in payment.findall(_term("BG-17"))
            ),
            card=None
            if card is None
            else PaymentCard(account_number=_text(card, "BT-87"), holder_name=_text(card, "BT-88")),
            direct_debit=None
            if debit is None
            else none_if_empty(
                DirectDebit(
                    mandate_reference=_text(debit, "BT-89"),
                    creditor_id=_text(debit, "BT-90"),
                    debited_account_id=_text(debit, "BT-91"),
                )
            ),
        )
    )


def _supporting_documents(invoice: Node) -> tuple[SupportingDocument, ...]:
    """BG-24. KoSIT's stylesheets give BT-17's and BT-18's additional documents as supporting
    documents too, the CII ones where they hold a description or location, where
    REQ-003-PRS-F002 reads neither as one: one that BT-17's or BT-18's source path lies in is
    left out (REQ-003-PRS-F005)."""
    references = [
        _source(node) for term in ("BT-17", "BT-18") for node in invoice.findall(_term(term))
    ]
    return tuple(
        document
        for node in invoice.findall(_term("BG-24"))
        if not (
            (source := _source(node))
            and any(reference.startswith(f"{source}/") for reference in references)
        )
        and (
            document := none_if_empty(
                SupportingDocument(
                    reference=_text(node, "BT-122"),
                    description=_text(node, "BT-123"),
                    external_location=_text(node, "BT-124"),
                )
            )
        )
        is not None
    )


def _source(node: Node) -> str:
    """The path of the element in the invoice that KoSIT's stylesheet read `node` from."""
    return node.element.get(f"{{{XR}}}src", "")


def _account(transfer: Node) -> str | None:
    """BT-84. KoSIT's stylesheet gives a CII account's `ram:ProprietaryID` and `ram:IBANID` both
    as BT-84, the first first, where REQ-003-PRS-F002 reads the IBAN: the one from `ram:IBANID`
    is taken (REQ-003-PRS-F005)."""
    accounts = transfer.holding("BT-84", _term("BT-84"))
    ibans = [node for node in accounts if _IBAN_SOURCE.search(_source(node))]
    chosen = ibans or accounts
    return chosen[0].value if chosen else None


def _totals(totals: Node | None) -> Totals | None:
    if totals is None:
        return None
    return Totals(
        line_net_total=_decimal(totals, "BT-106"),
        allowance_total=_decimal(totals, "BT-107"),
        charge_total=_decimal(totals, "BT-108"),
        total_without_vat=_decimal(totals, "BT-109"),
        vat_total=_decimal(totals, "BT-110"),
        vat_total_in_tax_currency=_decimal(totals, "BT-111"),
        total_with_vat=_decimal(totals, "BT-112"),
        prepaid_amount=_decimal(totals, "BT-113"),
        rounding_amount=_decimal(totals, "BT-114"),
        amount_due=_decimal(totals, "BT-115"),
    )


def _allowance_charge(node: Node, terms: AllowanceChargeTerms) -> AllowanceCharge:
    return AllowanceCharge(
        amount=_decimal(node, terms.amount),
        base_amount=_decimal(node, terms.base_amount),
        percentage=_decimal(node, terms.percentage),
        vat_category_code=_text(node, terms.vat_category_code),
        vat_rate=_decimal(node, terms.vat_rate),
        reason=_text(node, terms.reason),
        reason_code=_text(node, terms.reason_code),
    )


def _vat_breakdown(vat: Node) -> VatBreakdown:
    return VatBreakdown(
        taxable_amount=_decimal(vat, "BT-116"),
        tax_amount=_decimal(vat, "BT-117"),
        category_code=_text(vat, "BT-118"),
        rate=_decimal(vat, "BT-119"),
        exemption_reason=_text(vat, "BT-120"),
        exemption_reason_code=_text(vat, "BT-121"),
    )


def _line(line: Node) -> InvoiceLine:
    return InvoiceLine(
        id=_text(line, "BT-126"),
        note=_text(line, "BT-127"),
        object_id=_identifier(line, "BT-128"),
        quantity=_decimal(line, "BT-129"),
        unit_code=_text(line, "BT-130"),
        net_amount=_decimal(line, "BT-131"),
        purchase_order_line_reference=_text(line, "BT-132"),
        buyer_accounting_reference=_text(line, "BT-133"),
        period=_period(line, LINE_PERIOD),
        net_price=_decimal(line, "BG-29", "BT-146"),
        price_discount=_decimal(line, "BG-29", "BT-147"),
        gross_price=_decimal(line, "BG-29", "BT-148"),
        base_quantity=_decimal(line, "BG-29", "BT-149"),
        base_quantity_unit_code=_text(line, "BG-29", "BT-150"),
        vat_category_code=_text(line, "BG-30", "BT-151"),
        vat_rate=_decimal(line, "BG-30", "BT-152"),
        item_name=_text(line, "BG-31", "BT-153"),
        item_description=_text(line, "BG-31", "BT-154"),
        seller_item_id=_text(line, "BG-31", "BT-155"),
        buyer_item_id=_text(line, "BG-31", "BT-156"),
        standard_item_id=_identifier(line, "BG-31", "BT-157"),
        # KoSIT's stylesheets give a classification's scheme and its version as
        # `scheme_identifier` and `scheme_version_identifier`.
        item_classifications=classifications(
            line.holding("BT-158", _term("BG-31", "BT-158")),
            "scheme_identifier",
            "scheme_version_identifier",
        ),
        item_country_of_origin=_text(line, "BG-31", "BT-159"),
    )

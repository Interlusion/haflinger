"""Reading through KoSIT's visualisation stylesheets: the tests' independent second reader
(ADR-005, REQ-003-PRS-F005). Never on the path of `read_invoice`.

KoSIT's stylesheets turn a CII invoice, a UBL invoice or a UBL credit note into one semantic XML
in which every element carries its business term ID (`xr:id="BT-1"`). This module reads the
model from that XML by business term ID alone, apart from the root elements that pick the
stylesheet and the one limit of KoSIT's stylesheet that `with_subject_codes` evens out.
"""

import re
from dataclasses import replace
from datetime import date
from decimal import Decimal

from haflinger import _saxon, cii, ubl
from haflinger._parties import BUYER, SELLER, PartyTerms, contact, identifier, identifiers
from haflinger._xml import XML_WHITESPACE, Node, Reading, parse
from haflinger.errors import InvoiceReadError
from haflinger.model import (
    Invoice,
    InvoiceLine,
    Note,
    Party,
    Syntax,
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
# KoSIT's stylesheets write dates as YYYY-MM-DD in both syntaxes.
_ISO_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")


def read_invoice(data: bytes) -> ReadResult:
    """Like `haflinger.read_invoice` for XML, through KoSIT's stylesheets. The findings are
    those of reading the semantic XML, with its locations."""
    root = parse(data)
    if root.tag not in _STYLESHEETS:
        raise InvoiceReadError(
            f"the root element {root.tag} is neither a CII invoice nor a UBL invoice or credit note"
        )
    stylesheet, syntax = _STYLESHEETS[root.tag]
    (semantic,) = _saxon.transform(data, stylesheet)
    reading = Reading(parse(semantic), {"xr": XR}, "xr:invoice")
    return ReadResult(invoice=_invoice(reading.root, syntax), findings=reading.findings())


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


def with_subject_codes(invoice: Invoice) -> Invoice:
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


def _term(*terms: str) -> str:
    """The path to a business term by its ID, through the groups before it."""
    return "/".join(f"xr:*[@xr:id='{term}']" for term in terms)


def _text(node: Node, *terms: str) -> str | None:
    return node.text(_term(*terms), terms[-1])


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
        business_process=_text(invoice, "BG-2", "BT-23"),
        specification_id=_text(invoice, "BG-2", "BT-24"),
        notes=tuple(
            Note(subject_code=_text(note, "BT-21"), text=_text(note, "BT-22"))
            for note in invoice.findall(_term("BG-1"))
        ),
        seller=_party(invoice.find(_term("BG-4")), SELLER),
        buyer=_party(invoice.find(_term("BG-7")), BUYER),
        totals=_totals(invoice.find(_term("BG-22"))),
        vat_breakdown=tuple(_vat_breakdown(vat) for vat in invoice.findall(_term("BG-23"))),
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
            party.holding(terms.identifier, _term(terms.identifier)), terms, "scheme_identifier"
        ),
        legal_registration_id=_text(party, terms.legal_registration_id),
        vat_id=_text(party, terms.vat_id),
        tax_registration_id=(
            None if terms.tax_registration is None else _text(party, terms.tax_registration)
        ),
        electronic_address=identifier(
            party.first(_term(terms.electronic_address), terms.electronic_address),
            "scheme_identifier",
        ),
        address_line_1=_text(party, terms.address, terms.address_line_1),
        address_line_2=_text(party, terms.address, terms.address_line_2),
        address_line_3=_text(party, terms.address, terms.address_line_3),
        city=_text(party, terms.address, terms.city),
        post_code=_text(party, terms.address, terms.post_code),
        country_subdivision=_text(party, terms.address, terms.country_subdivision),
        country_code=_text(party, terms.address, terms.country_code),
        contact=None
        if contact_group is None
        else contact(
            point=_text(contact_group, terms.contact_point),
            telephone=_text(contact_group, terms.telephone),
            email=_text(contact_group, terms.email),
        ),
    )


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
        quantity=_decimal(line, "BT-129"),
        unit_code=_text(line, "BT-130"),
        net_amount=_decimal(line, "BT-131"),
        net_price=_decimal(line, "BG-29", "BT-146"),
        vat_category_code=_text(line, "BG-30", "BT-151"),
        vat_rate=_decimal(line, "BG-30", "BT-152"),
        item_name=_text(line, "BG-31", "BT-153"),
    )

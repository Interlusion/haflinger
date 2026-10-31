"""CII into the model and the model into CII, by the elements EN 16931-3-3 assigns
(REQ-003-PRS-F002, REQ-004-PRS-F003)."""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import cast
from xml.etree.ElementTree import Element, SubElement, tostring

from haflinger._xml import XML_WHITESPACE, Node, choose_vat_totals
from haflinger.errors import InvoiceWriteError
from haflinger.model import Invoice, InvoiceLine, Note, Party, Totals, VatBreakdown

NAMESPACE = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
NAMESPACES = {
    "rsm": NAMESPACE,
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}
ROOT = "CrossIndustryInvoice"
TAG = f"{{{NAMESPACE}}}{ROOT}"

_DATE_102 = re.compile(r"([0-9]{4})([0-9]{2})([0-9]{2})")

_CONTEXT = "rsm:ExchangedDocumentContext"
_DOCUMENT = "rsm:ExchangedDocument"
_TRANSACTION = "rsm:SupplyChainTradeTransaction"
_AGREEMENT = f"{_TRANSACTION}/ram:ApplicableHeaderTradeAgreement"
_SETTLEMENT = f"{_TRANSACTION}/ram:ApplicableHeaderTradeSettlement"


def specification(root: Node) -> Node | None:
    """BT-24's element."""
    return root.first(f"{_CONTEXT}/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID", "BT-24")


def read(root: Node, specification_id: str | None) -> Invoice:
    currency_code = root.text(f"{_SETTLEMENT}/ram:InvoiceCurrencyCode", "BT-5")
    tax_currency_code = root.text(f"{_SETTLEMENT}/ram:TaxCurrencyCode", "BT-6")
    return Invoice(
        syntax="cii",
        number=root.text(f"{_DOCUMENT}/ram:ID", "BT-1"),
        issue_date=_date(root, f"{_DOCUMENT}/ram:IssueDateTime/udt:DateTimeString", "BT-2"),
        type_code=root.text(f"{_DOCUMENT}/ram:TypeCode", "BT-3"),
        currency_code=currency_code,
        tax_currency_code=tax_currency_code,
        due_date=_date(
            root,
            f"{_SETTLEMENT}/ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime/udt:DateTimeString",
            "BT-9",
        ),
        buyer_reference=root.text(f"{_AGREEMENT}/ram:BuyerReference", "BT-10"),
        business_process=root.text(
            f"{_CONTEXT}/ram:BusinessProcessSpecifiedDocumentContextParameter/ram:ID", "BT-23"
        ),
        specification_id=specification_id,
        notes=tuple(
            note
            for node in root.findall(f"{_DOCUMENT}/ram:IncludedNote")
            if (note := _note(node)) is not None
        ),
        seller=_party(
            root.group(f"{_AGREEMENT}/ram:SellerTradeParty", "BG-4"),
            ("BT-27", "BT-28", "BT-30", "BT-31", "BT-40"),
        ),
        buyer=_party(
            root.group(f"{_AGREEMENT}/ram:BuyerTradeParty", "BG-7"),
            ("BT-44", "BT-45", "BT-47", "BT-48", "BT-55"),
        ),
        totals=_totals(
            root.group(
                f"{_SETTLEMENT}/ram:SpecifiedTradeSettlementHeaderMonetarySummation", "BG-22"
            ),
            currency_code,
            tax_currency_code,
        ),
        vat_breakdown=tuple(
            _vat_breakdown(node) for node in root.findall(f"{_SETTLEMENT}/ram:ApplicableTradeTax")
        ),
        lines=tuple(
            _line(node)
            for node in root.findall(f"{_TRANSACTION}/ram:IncludedSupplyChainTradeLineItem")
        ),
    )


def _date(parent: Node, path: str, term: str) -> date | None:
    """A date as `udt:DateTimeString` with `format="102"`."""
    node = parent.first(path, term)
    if node is None or node.value is None:
        return None
    if node.attribute("format") != "102":
        node.malformed(term, 'a date with format="102"', node.value)
        return None
    return node.as_date(term, _DATE_102, "YYYYMMDD")


def _note(node: Node) -> Note | None:
    note = Note(
        subject_code=node.text("ram:SubjectCode", "BT-21"),
        text=node.text("ram:Content", "BT-22"),
    )
    return None if note == Note() else note


def _party(party: Node | None, terms: tuple[str, str, str, str, str]) -> Party | None:
    if party is None:
        return None
    name, trading_name, registration, vat, country = terms
    vat_ids = [
        node
        for node in party.findall("ram:SpecifiedTaxRegistration/ram:ID")
        if node.attribute("schemeID") == "VA" and node.value is not None
    ]
    for node in vat_ids[1:]:
        node.drop(f"{vat} appears more than once; this one is left out: {node.value!r}")
    return Party(
        name=party.text("ram:Name", name),
        trading_name=party.text(
            "ram:SpecifiedLegalOrganization/ram:TradingBusinessName", trading_name
        ),
        legal_registration_id=party.text("ram:SpecifiedLegalOrganization/ram:ID", registration),
        vat_id=vat_ids[0].value if vat_ids else None,
        country_code=party.text("ram:PostalTradeAddress/ram:CountryID", country),
    )


def _totals(
    summation: Node | None, currency_code: str | None, tax_currency_code: str | None
) -> Totals | None:
    if summation is None:
        return None
    amounts = summation.findall("ram:TaxTotalAmount")
    vat_total, vat_total_in_tax_currency = choose_vat_totals(
        [(amount, amount) for amount in amounts], currency_code, tax_currency_code
    )
    return Totals(
        line_net_total=summation.decimal("ram:LineTotalAmount", "BT-106"),
        allowance_total=summation.decimal("ram:AllowanceTotalAmount", "BT-107"),
        charge_total=summation.decimal("ram:ChargeTotalAmount", "BT-108"),
        total_without_vat=summation.decimal("ram:TaxBasisTotalAmount", "BT-109"),
        vat_total=None if vat_total is None else vat_total.as_decimal("BT-110"),
        vat_total_in_tax_currency=(
            None
            if vat_total_in_tax_currency is None
            else vat_total_in_tax_currency.as_decimal("BT-111")
        ),
        total_with_vat=summation.decimal("ram:GrandTotalAmount", "BT-112"),
        prepaid_amount=summation.decimal("ram:TotalPrepaidAmount", "BT-113"),
        rounding_amount=summation.decimal("ram:RoundingAmount", "BT-114"),
        amount_due=summation.decimal("ram:DuePayableAmount", "BT-115"),
    )


def _vat_breakdown(tax: Node) -> VatBreakdown:
    return VatBreakdown(
        taxable_amount=tax.decimal("ram:BasisAmount", "BT-116"),
        tax_amount=tax.decimal("ram:CalculatedAmount", "BT-117"),
        category_code=tax.text("ram:CategoryCode", "BT-118"),
        rate=tax.decimal("ram:RateApplicablePercent", "BT-119"),
        exemption_reason=tax.text("ram:ExemptionReason", "BT-120"),
        exemption_reason_code=tax.text("ram:ExemptionReasonCode", "BT-121"),
    )


def _line(line: Node) -> InvoiceLine:
    quantity = line.first("ram:SpecifiedLineTradeDelivery/ram:BilledQuantity", "BT-129")
    settlement = "ram:SpecifiedLineTradeSettlement"
    return InvoiceLine(
        id=line.text("ram:AssociatedDocumentLineDocument/ram:LineID", "BT-126"),
        quantity=None if quantity is None else quantity.as_decimal("BT-129"),
        unit_code=None if quantity is None else quantity.attribute("unitCode"),
        net_amount=line.decimal(
            f"{settlement}/ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount",
            "BT-131",
        ),
        net_price=line.decimal(
            "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount",
            "BT-146",
        ),
        vat_category_code=line.text(
            f"{settlement}/ram:ApplicableTradeTax/ram:CategoryCode", "BT-151"
        ),
        vat_rate=line.decimal(
            f"{settlement}/ram:ApplicableTradeTax/ram:RateApplicablePercent", "BT-152"
        ),
        item_name=line.text("ram:SpecifiedTradeProduct/ram:Name", "BT-153"),
    )


# Writing (REQ-004-PRS-F003). Each value is checked as it is written, and refused naming its
# business term (REQ-004-PRS-F001). Elements are created in the order of the CII D16B XML Schema;
# those left empty are removed at the end, except the ones the schema requires.

_REQUIRED = frozenset(
    {
        "ram:ApplicableHeaderTradeAgreement",
        "ram:ApplicableHeaderTradeDelivery",
        "ram:ApplicableHeaderTradeSettlement",
        "ram:AssociatedDocumentLineDocument",
        "ram:SpecifiedLineTradeSettlement",
    }
)
# The characters XML 1.0 allows.
_NOT_XML = re.compile("[^\t\n\r\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


def write(invoice: Invoice) -> bytes:
    """The model as CII D16B, UTF-8 with an XML declaration."""
    root = Element(f"rsm:{ROOT}", {f"xmlns:{prefix}": uri for prefix, uri in NAMESPACES.items()})
    context = SubElement(root, "rsm:ExchangedDocumentContext")
    _put_text(
        context,
        "ram:BusinessProcessSpecifiedDocumentContextParameter/ram:ID",
        invoice.business_process,
        "BT-23",
    )
    _put_text(
        context,
        "ram:GuidelineSpecifiedDocumentContextParameter/ram:ID",
        invoice.specification_id,
        "BT-24",
    )

    document = SubElement(root, "rsm:ExchangedDocument")
    _put_text(document, "ram:ID", invoice.number, "BT-1")
    _put_text(document, "ram:TypeCode", invoice.type_code, "BT-3")
    _put_date(document, "ram:IssueDateTime", invoice.issue_date, "BT-2")
    for note in _group(invoice.notes, Note, "BG-1"):
        included = SubElement(document, "ram:IncludedNote")
        _put_text(included, "ram:Content", note.text, "BT-22")
        _put_text(included, "ram:SubjectCode", note.subject_code, "BT-21")

    transaction = SubElement(root, "rsm:SupplyChainTradeTransaction")
    for line in _group(invoice.lines, InvoiceLine, "BG-25"):
        _write_line(SubElement(transaction, "ram:IncludedSupplyChainTradeLineItem"), line)
    agreement = SubElement(transaction, "ram:ApplicableHeaderTradeAgreement")
    _put_text(agreement, "ram:BuyerReference", invoice.buyer_reference, "BT-10")
    _write_party(
        agreement,
        "ram:SellerTradeParty",
        invoice.seller,
        "BG-4",
        ("BT-27", "BT-28", "BT-30", "BT-31", "BT-40"),
    )
    _write_party(
        agreement,
        "ram:BuyerTradeParty",
        invoice.buyer,
        "BG-7",
        ("BT-44", "BT-45", "BT-47", "BT-48", "BT-55"),
    )
    SubElement(transaction, "ram:ApplicableHeaderTradeDelivery")
    settlement = SubElement(transaction, "ram:ApplicableHeaderTradeSettlement")
    _put_text(settlement, "ram:TaxCurrencyCode", invoice.tax_currency_code, "BT-6")
    _put_text(settlement, "ram:InvoiceCurrencyCode", invoice.currency_code, "BT-5")
    for vat in _group(invoice.vat_breakdown, VatBreakdown, "BG-23"):
        tax = SubElement(settlement, "ram:ApplicableTradeTax")
        _put_amount(tax, "ram:CalculatedAmount", vat.tax_amount, "BT-117")
        SubElement(tax, "ram:TypeCode").text = "VAT"
        _put_text(tax, "ram:ExemptionReason", vat.exemption_reason, "BT-120")
        _put_amount(tax, "ram:BasisAmount", vat.taxable_amount, "BT-116")
        _put_text(tax, "ram:CategoryCode", vat.category_code, "BT-118")
        _put_text(tax, "ram:ExemptionReasonCode", vat.exemption_reason_code, "BT-121")
        _put_amount(tax, "ram:RateApplicablePercent", vat.rate, "BT-119")
    _put_date(
        settlement, "ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime", invoice.due_date, "BT-9"
    )
    _write_totals(settlement, invoice)

    _remove_empty(root)
    # ElementTree writes a carriage return in text as it is, and XML parsers turn it into a line
    # feed; as a character reference it reads back unchanged. Text is the only place one can be.
    body = tostring(root, encoding="UTF-8", xml_declaration=False).replace(b"\r", b"&#13;")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + body


def _write_party(
    parent: Element,
    tag: str,
    party: object,
    group: str,
    terms: tuple[str, str, str, str, str],
) -> None:
    if party is None:
        return
    if not isinstance(party, Party):
        raise InvoiceWriteError(f"{group} is not a Party: {party!r}")
    name, trading_name, registration, vat_id, country = terms
    element = SubElement(parent, tag)
    _put_text(element, "ram:Name", party.name, name)
    organization = SubElement(element, "ram:SpecifiedLegalOrganization")
    _put_text(organization, "ram:ID", party.legal_registration_id, registration)
    _put_text(organization, "ram:TradingBusinessName", party.trading_name, trading_name)
    _put_text(element, "ram:PostalTradeAddress/ram:CountryID", party.country_code, country)
    _put_text(element, "ram:SpecifiedTaxRegistration/ram:ID", party.vat_id, vat_id, schemeID="VA")


def _write_totals(settlement: Element, invoice: Invoice) -> None:
    totals = cast(object, invoice.totals)
    if totals is None:
        return
    if not isinstance(totals, Totals):
        raise InvoiceWriteError(f"BG-22 is not a Totals: {totals!r}")
    if totals.vat_total_in_tax_currency is not None and invoice.tax_currency_code is None:
        raise InvoiceWriteError(
            "BT-111 needs the VAT accounting currency code (BT-6), which is missing"
        )
    summation = SubElement(settlement, "ram:SpecifiedTradeSettlementHeaderMonetarySummation")
    _put_amount(summation, "ram:LineTotalAmount", totals.line_net_total, "BT-106")
    _put_amount(summation, "ram:ChargeTotalAmount", totals.charge_total, "BT-108")
    _put_amount(summation, "ram:AllowanceTotalAmount", totals.allowance_total, "BT-107")
    _put_amount(summation, "ram:TaxBasisTotalAmount", totals.total_without_vat, "BT-109")
    _put_amount(
        summation,
        "ram:TaxTotalAmount",
        totals.vat_total,
        "BT-110",
        currencyID=invoice.currency_code,
    )
    _put_amount(
        summation,
        "ram:TaxTotalAmount",
        totals.vat_total_in_tax_currency,
        "BT-111",
        currencyID=invoice.tax_currency_code,
    )
    _put_amount(summation, "ram:RoundingAmount", totals.rounding_amount, "BT-114")
    _put_amount(summation, "ram:GrandTotalAmount", totals.total_with_vat, "BT-112")
    _put_amount(summation, "ram:TotalPrepaidAmount", totals.prepaid_amount, "BT-113")
    _put_amount(summation, "ram:DuePayableAmount", totals.amount_due, "BT-115")


def _write_line(item: Element, line: InvoiceLine) -> None:
    _put_text(item, "ram:AssociatedDocumentLineDocument/ram:LineID", line.id, "BT-126")
    _put_text(item, "ram:SpecifiedTradeProduct/ram:Name", line.item_name, "BT-153")
    _put_amount(
        item,
        "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount",
        line.net_price,
        "BT-146",
    )
    if line.unit_code is not None and line.quantity is None:
        raise InvoiceWriteError("BT-130 needs the invoiced quantity (BT-129), which is missing")
    _put_amount(
        item,
        "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity",
        line.quantity,
        "BT-129",
        unitCode=_checked_text(line.unit_code, "BT-130"),
    )
    settlement = SubElement(item, "ram:SpecifiedLineTradeSettlement")
    if line.vat_category_code is not None or line.vat_rate is not None:
        tax = SubElement(settlement, "ram:ApplicableTradeTax")
        SubElement(tax, "ram:TypeCode").text = "VAT"
        _put_text(tax, "ram:CategoryCode", line.vat_category_code, "BT-151")
        _put_amount(tax, "ram:RateApplicablePercent", line.vat_rate, "BT-152")
    _put_amount(
        settlement,
        "ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount",
        line.net_amount,
        "BT-131",
    )


def _group[T](values: object, kind: type[T], group: str) -> list[T]:
    """The model's static types aren't checked at run time; a caller may pass anything."""
    if not isinstance(values, tuple):
        raise InvoiceWriteError(f"{group} is not a tuple of {kind.__name__}: {values!r}")
    items: list[T] = []
    for value in cast(tuple[object, ...], values):
        if not isinstance(value, kind):
            raise InvoiceWriteError(
                f"{group} holds something other than {kind.__name__}: {value!r}"
            )
        items.append(value)
    return items


def _checked_text(value: object, term: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvoiceWriteError(f"{term} is not a str: {value!r}")
    if not value:
        raise InvoiceWriteError(f"{term} is empty; a missing term is None")
    if value != value.strip(XML_WHITESPACE):
        raise InvoiceWriteError(f"{term} has whitespace around it: {value!r}")
    if (character := _NOT_XML.search(value)) is not None:
        raise InvoiceWriteError(
            f"{term} holds a character XML doesn't allow, {character[0]!r}: {value!r}"
        )
    return value


def _put_text(
    parent: Element, path: str, value: object, term: str, **attributes: str | None
) -> None:
    _leaf(parent, path, _checked_text(value, term), attributes)


def _put_amount(
    parent: Element, path: str, value: object, term: str, **attributes: str | None
) -> None:
    """A number in plain notation with the digits the model holds: 1E+2 is 100, 10.50 stays
    10.50."""
    if value is None:
        return
    if not isinstance(value, Decimal) or not value.is_finite():
        raise InvoiceWriteError(f"{term} is not a finite Decimal: {value!r}")
    _leaf(parent, path, format(value, "f"), attributes)


def _put_date(parent: Element, path: str, value: object, term: str) -> None:
    if value is None:
        return
    if not isinstance(value, date) or isinstance(value, datetime):
        raise InvoiceWriteError(f"{term} is not a date: {value!r}")
    text = f"{value.year:04}{value.month:02}{value.day:02}"
    _leaf(parent, f"{path}/udt:DateTimeString", text, {"format": "102"})


def _leaf(parent: Element, path: str, text: str | None, attributes: dict[str, str | None]) -> None:
    if text is None:
        return
    element = parent
    for tag in path.split("/"):
        element = SubElement(element, tag)
    element.text = text
    for name, value in attributes.items():
        if value is not None:
            element.set(name, value)


def _remove_empty(element: Element) -> None:
    for child in list(element):
        _remove_empty(child)
        if child.tag not in _REQUIRED and len(child) == 0 and child.text is None:
            element.remove(child)

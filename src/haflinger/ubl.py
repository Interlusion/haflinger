"""UBL invoices and credit notes into the model, by the elements EN 16931-3-2 assigns
(REQ-003-PRS-F002)."""

import re
from datetime import date

from haflinger._xml import Node, choose_vat_totals
from haflinger.model import Invoice, InvoiceLine, Note, Party, Totals, VatBreakdown

INVOICE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CREDIT_NOTE = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
INVOICE_TAG = f"{{{INVOICE}}}Invoice"
CREDIT_NOTE_TAG = f"{{{CREDIT_NOTE}}}CreditNote"
NAMESPACES = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

_ISO_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
# BT-21 at the start of a note, the convention of XRechnung and Peppol.
_SUBJECT_CODE = re.compile(r"#([A-Z]{3})#(.*)", re.DOTALL)


def specification(root: Node) -> Node | None:
    """BT-24's element."""
    return root.first("cbc:CustomizationID", "BT-24")


def read(root: Node, specification_id: str | None, *, credit_note: bool) -> Invoice:
    currency_code = root.text("cbc:DocumentCurrencyCode", "BT-5")
    tax_currency_code = root.text("cbc:TaxCurrencyCode", "BT-6")
    tax_totals = [
        (tax_total, amount)
        for tax_total in root.findall("cac:TaxTotal")
        if (amount := tax_total.find("cbc:TaxAmount")) is not None
    ]
    vat_total, vat_total_in_tax_currency = choose_vat_totals(
        tax_totals, currency_code, tax_currency_code
    )
    line, quantity = (
        ("cac:CreditNoteLine", "cbc:CreditedQuantity")
        if credit_note
        else ("cac:InvoiceLine", "cbc:InvoicedQuantity")
    )
    return Invoice(
        syntax="ubl",
        number=root.text("cbc:ID", "BT-1"),
        issue_date=_date(root, "cbc:IssueDate", "BT-2"),
        type_code=root.text(
            "cbc:CreditNoteTypeCode" if credit_note else "cbc:InvoiceTypeCode", "BT-3"
        ),
        currency_code=currency_code,
        tax_currency_code=tax_currency_code,
        due_date=_date(
            root, "cac:PaymentMeans/cbc:PaymentDueDate" if credit_note else "cbc:DueDate", "BT-9"
        ),
        buyer_reference=root.text("cbc:BuyerReference", "BT-10"),
        business_process=root.text("cbc:ProfileID", "BT-23"),
        specification_id=specification_id,
        notes=tuple(note for node in root.findall("cbc:Note") if (note := _note(node)) is not None),
        seller=_party(
            root.find("cac:AccountingSupplierParty/cac:Party"),
            ("BT-27", "BT-28", "BT-30", "BT-31", "BT-40"),
        ),
        buyer=_party(
            root.find("cac:AccountingCustomerParty/cac:Party"),
            ("BT-44", "BT-45", "BT-47", "BT-48", "BT-55"),
        ),
        totals=_totals(
            root.find("cac:LegalMonetaryTotal"),
            vat_total.find("cbc:TaxAmount") if vat_total else None,
            vat_total_in_tax_currency.find("cbc:TaxAmount") if vat_total_in_tax_currency else None,
        ),
        vat_breakdown=tuple(
            _vat_breakdown(subtotal)
            for subtotal in (vat_total.findall("cac:TaxSubtotal") if vat_total else [])
        ),
        lines=tuple(_line(node, quantity) for node in root.findall(line)),
    )


def _date(parent: Node, path: str, term: str) -> date | None:
    node = parent.first(path, term)
    return None if node is None else node.as_date(term, _ISO_DATE, "YYYY-MM-DD")


def _note(node: Node) -> Note | None:
    value = node.value
    if value is None:
        return None
    match = _SUBJECT_CODE.fullmatch(value)
    if match is None:
        return Note(text=value)
    return Note(subject_code=match[1], text=match[2].strip(" \t\r\n") or None)


def _party(party: Node | None, terms: tuple[str, str, str, str, str]) -> Party | None:
    if party is None:
        return None
    name, trading_name, registration, vat, country = terms
    vat_ids = [
        node
        for scheme in party.findall("cac:PartyTaxScheme")
        if (scheme_id := scheme.find("cac:TaxScheme/cbc:ID")) is not None
        and scheme_id.value == "VAT"
        and (node := scheme.find("cbc:CompanyID")) is not None
        and node.value is not None
    ]
    for node in vat_ids[1:]:
        node.drop(f"{vat} appears more than once; this one is left out: {node.value!r}")
    return Party(
        name=party.text("cac:PartyLegalEntity/cbc:RegistrationName", name),
        trading_name=party.text("cac:PartyName/cbc:Name", trading_name),
        legal_registration_id=party.text("cac:PartyLegalEntity/cbc:CompanyID", registration),
        vat_id=vat_ids[0].value if vat_ids else None,
        country_code=party.text("cac:PostalAddress/cac:Country/cbc:IdentificationCode", country),
    )


def _totals(
    total: Node | None, vat_total: Node | None, vat_total_in_tax_currency: Node | None
) -> Totals | None:
    if total is None:
        return None
    return Totals(
        line_net_total=total.decimal("cbc:LineExtensionAmount", "BT-106"),
        allowance_total=total.decimal("cbc:AllowanceTotalAmount", "BT-107"),
        charge_total=total.decimal("cbc:ChargeTotalAmount", "BT-108"),
        total_without_vat=total.decimal("cbc:TaxExclusiveAmount", "BT-109"),
        vat_total=None if vat_total is None else vat_total.as_decimal("BT-110"),
        vat_total_in_tax_currency=(
            None
            if vat_total_in_tax_currency is None
            else vat_total_in_tax_currency.as_decimal("BT-111")
        ),
        total_with_vat=total.decimal("cbc:TaxInclusiveAmount", "BT-112"),
        prepaid_amount=total.decimal("cbc:PrepaidAmount", "BT-113"),
        rounding_amount=total.decimal("cbc:PayableRoundingAmount", "BT-114"),
        amount_due=total.decimal("cbc:PayableAmount", "BT-115"),
    )


def _vat_breakdown(subtotal: Node) -> VatBreakdown:
    return VatBreakdown(
        taxable_amount=subtotal.decimal("cbc:TaxableAmount", "BT-116"),
        tax_amount=subtotal.decimal("cbc:TaxAmount", "BT-117"),
        category_code=subtotal.text("cac:TaxCategory/cbc:ID", "BT-118"),
        rate=subtotal.decimal("cac:TaxCategory/cbc:Percent", "BT-119"),
        exemption_reason=subtotal.text("cac:TaxCategory/cbc:TaxExemptionReason", "BT-120"),
        exemption_reason_code=subtotal.text("cac:TaxCategory/cbc:TaxExemptionReasonCode", "BT-121"),
    )


def _line(line: Node, quantity_path: str) -> InvoiceLine:
    quantity = line.first(quantity_path, "BT-129")
    return InvoiceLine(
        id=line.text("cbc:ID", "BT-126"),
        quantity=None if quantity is None else quantity.as_decimal("BT-129"),
        unit_code=None if quantity is None else quantity.attribute("unitCode"),
        net_amount=line.decimal("cbc:LineExtensionAmount", "BT-131"),
        net_price=line.decimal("cac:Price/cbc:PriceAmount", "BT-146"),
        vat_category_code=line.text("cac:Item/cac:ClassifiedTaxCategory/cbc:ID", "BT-151"),
        vat_rate=line.decimal("cac:Item/cac:ClassifiedTaxCategory/cbc:Percent", "BT-152"),
        item_name=line.text("cac:Item/cbc:Name", "BT-153"),
    )

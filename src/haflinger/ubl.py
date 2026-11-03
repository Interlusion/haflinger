"""UBL invoices and credit notes into the model, by the elements EN 16931-3-2 assigns
(REQ-003-PRS-F002)."""

import re
from datetime import date

from haflinger._parties import BUYER, SELLER, PartyTerms, contact, identifier, identifiers
from haflinger._payments import one_value, payment_means
from haflinger._xml import (
    XML_WHITESPACE,
    Node,
    choose_vat_totals,
    first_group,
    first_of,
    none_if_empty,
)
from haflinger.model import (
    CreditTransfer,
    DirectDebit,
    Invoice,
    InvoiceLine,
    Note,
    Party,
    PaymentCard,
    PaymentInstructions,
    Totals,
    VatBreakdown,
)

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
    tax_totals = root.findall("cac:TaxTotal")
    vat_total, vat_total_in_tax_currency = choose_vat_totals(
        [
            (tax_total, amount)
            for tax_total in tax_totals
            if (amount := tax_total.first("cbc:TaxAmount", "BT-110 or BT-111")) is not None
        ],
        currency_code,
        tax_currency_code,
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
        payment_terms=root.text("cac:PaymentTerms/cbc:Note", "BT-20"),
        business_process=root.text("cbc:ProfileID", "BT-23"),
        specification_id=specification_id,
        notes=tuple(note for node in root.findall("cbc:Note") if (note := _note(node)) is not None),
        seller=_party(root.group("cac:AccountingSupplierParty/cac:Party", "BG-4"), SELLER),
        buyer=_party(root.group("cac:AccountingCustomerParty/cac:Party", "BG-7"), BUYER),
        payment_instructions=_payment_instructions(root),
        totals=_totals(
            root.group("cac:LegalMonetaryTotal", "BG-22"),
            _tax_amount(vat_total),
            _tax_amount(vat_total_in_tax_currency),
        ),
        vat_breakdown=tuple(_vat_breakdown(node) for node in _subtotals(tax_totals, vat_total)),
        lines=tuple(_line(node, quantity) for node in root.findall(line) if node.holds_value()),
    )


def _tax_amount(tax_total: Node | None) -> Node | None:
    """The first `cbc:TaxAmount` holding a value, which `choose_vat_totals` chose by."""
    if tax_total is None:
        return None
    return next((a for a in tax_total.findall("cbc:TaxAmount") if a.value is not None), None)


def _subtotals(tax_totals: list[Node], vat_total: Node | None) -> list[Node]:
    """The VAT breakdown: the subtotals of the `cac:TaxTotal` that gives BT-110 or, without one,
    of the first holding any; those of every other `cac:TaxTotal` are left out with a finding."""
    source = vat_total or next((t for t in tax_totals if t.find("cac:TaxSubtotal")), None)
    for tax_total in tax_totals:
        if source is not None and tax_total.element is source.element:
            continue
        for subtotal in tax_total.findall("cac:TaxSubtotal"):
            if subtotal.holds_value():
                subtotal.drop(
                    "BG-23 of a cac:TaxTotal other than the one giving the VAT breakdown"
                    " is left out"
                )
    return (
        [] if source is None else [s for s in source.findall("cac:TaxSubtotal") if s.holds_value()]
    )


def _date(parent: Node, path: str, term: str) -> date | None:
    node = parent.first(path, term)
    return None if node is None else node.as_date(term, _ISO_DATE, "YYYY-MM-DD")


def _note(node: Node) -> Note | None:
    value = node.plain("BT-22")
    if value is None:
        return None
    match = _SUBJECT_CODE.fullmatch(value)
    if match is None:
        return Note(text=value)
    return Note(subject_code=match[1], text=match[2].strip(XML_WHITESPACE) or None)


def _party(party: Node | None, terms: PartyTerms) -> Party | None:
    if party is None:
        return None
    # The terms of one legal entity, one address and one contact come from one element each.
    entity = party.group(
        "cac:PartyLegalEntity",
        f"{terms.name}, {terms.legal_registration_id} (cac:PartyLegalEntity)",
    )
    address = party.group("cac:PostalAddress", terms.address)
    contact_element = party.group("cac:Contact", terms.contact, *_CONTACT)
    # A tax scheme `VAT` gives the VAT identifier, another the seller's tax registration
    # identifier, which the buyer lacks.
    taxes = ", ".join(term for term in (terms.vat_id, terms.tax_registration) if term)
    vat_ids: list[Node] = []
    tax_ids: list[Node] = []
    for scheme in party.findall("cac:PartyTaxScheme"):
        kind = scheme.text("cac:TaxScheme/cbc:ID", f"{taxes} (cac:TaxScheme)")
        if kind == "VAT":
            vat_ids += scheme.holding(terms.vat_id, "cbc:CompanyID")
        elif kind is not None and terms.tax_registration is not None:
            tax_ids += scheme.holding(terms.tax_registration, "cbc:CompanyID")
    vat_id = first_of(vat_ids, terms.vat_id)
    tax_id = None if terms.tax_registration is None else first_of(tax_ids, terms.tax_registration)
    # The seller's identifier with scheme SEPA is the bank assigned creditor identifier (BT-90).
    ids = [
        node
        for node in party.findall("cac:PartyIdentification/cbc:ID")
        if not (terms.creditor_identifier and node.attribute("schemeID") == "SEPA")
        and node.plain(terms.identifier) is not None
    ]
    point, telephone, email = _CONTACT
    return Party(
        name=_text(entity, "cbc:RegistrationName", terms.name),
        trading_name=party.text("cac:PartyName/cbc:Name", terms.trading_name),
        identifiers=identifiers(ids, terms),
        legal_registration_id=_text(entity, "cbc:CompanyID", terms.legal_registration_id),
        vat_id=None if vat_id is None else vat_id.value,
        tax_registration_id=None if tax_id is None else tax_id.value,
        electronic_address=identifier(party.first("cbc:EndpointID", terms.electronic_address)),
        address_line_1=_text(address, "cbc:StreetName", terms.address_line_1),
        address_line_2=_text(address, "cbc:AdditionalStreetName", terms.address_line_2),
        address_line_3=_text(address, "cac:AddressLine/cbc:Line", terms.address_line_3),
        city=_text(address, "cbc:CityName", terms.city),
        post_code=_text(address, "cbc:PostalZone", terms.post_code),
        country_subdivision=_text(address, "cbc:CountrySubentity", terms.country_subdivision),
        country_code=_text(address, "cac:Country/cbc:IdentificationCode", terms.country_code),
        contact=None
        if contact_element is None
        else contact(
            point=contact_element.text(point, terms.contact_point),
            telephone=contact_element.text(telephone, terms.telephone),
            email=contact_element.text(email, terms.email),
        ),
    )


# The elements of a contact's terms, which make a cac:Contact the contact.
_CONTACT = ("cbc:Name", "cbc:Telephone", "cbc:ElectronicMail")


def _payment_instructions(root: Node) -> PaymentInstructions | None:
    """BG-16 from the payment means, repeated for each account (REQ-003-PRS-F002)."""
    means, code = payment_means(
        root.findall("cac:PaymentMeans"), lambda node: node.text("cbc:PaymentMeansCode", "BT-81")
    )
    texts = [
        (node, name)
        for m in means
        for node in m.findall("cbc:PaymentMeansCode")
        if (name := node.attribute("name")) is not None
    ]
    remittances = [(n, n.value or "") for m in means for n in m.holding("BT-83", "cbc:PaymentID")]
    transfers = [
        CreditTransfer(
            account_id=account.text("cbc:ID", "BT-84"),
            account_name=account.text("cbc:Name", "BT-85"),
            provider_id=account.text("cac:FinancialInstitutionBranch/cbc:ID", "BT-86"),
        )
        for node in means
        for account in node.findall("cac:PayeeFinancialAccount")
        if account.holds_value()
    ]
    card = first_group([c for node in means for c in node.findall("cac:CardAccount")], "BG-18")
    mandate = first_group(
        [m for node in means for m in node.findall("cac:PaymentMandate")], "BG-19"
    )
    return none_if_empty(
        PaymentInstructions(
            means_code=code,
            means_text=one_value(texts, "BT-82"),
            remittance_information=one_value(remittances, "BT-83"),
            credit_transfers=tuple(transfers),
            card=None
            if card is None
            else PaymentCard(
                account_number=card.text("cbc:PrimaryAccountNumberID", "BT-87"),
                holder_name=card.text("cbc:HolderName", "BT-88"),
            ),
            direct_debit=_direct_debit(root, mandate),
        )
    )


def _direct_debit(root: Node, mandate: Node | None) -> DirectDebit | None:
    """BG-19 from the mandate and the creditor identifier: the payee's, or else the seller's,
    identifier with scheme SEPA, which without a mandate is no direct debit's
    (REQ-003-PRS-F002)."""
    creditors = [
        node
        for party in ("cac:PayeeParty", "cac:AccountingSupplierParty/cac:Party")
        for node in root.findall(f"{party}/cac:PartyIdentification/cbc:ID")
        if node.attribute("schemeID") == "SEPA" and node.plain("BT-90") is not None
    ]
    if mandate is None:
        for node in creditors:
            node.drop(
                f"BT-90 without a direct debit (cac:PaymentMandate) is left out: {node.value!r}"
            )
        return None
    creditor = first_of(creditors, "BT-90")
    return none_if_empty(
        DirectDebit(
            mandate_reference=mandate.text("cbc:ID", "BT-89"),
            creditor_id=None if creditor is None else creditor.value,
            debited_account_id=mandate.text("cac:PayerFinancialAccount/cbc:ID", "BT-91"),
        )
    )


def _totals(
    total: Node | None, vat_total: Node | None, vat_total_in_tax_currency: Node | None
) -> Totals | None:
    if total is None:
        if vat_total is None and vat_total_in_tax_currency is None:
            return None
        # BT-110 and BT-111 lie outside cac:LegalMonetaryTotal: read them without it.
        return Totals(
            vat_total=None if vat_total is None else vat_total.as_decimal("BT-110"),
            vat_total_in_tax_currency=(
                None
                if vat_total_in_tax_currency is None
                else vat_total_in_tax_currency.as_decimal("BT-111")
            ),
        )
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
    category = subtotal.group("cac:TaxCategory", "BT-118 to BT-121 (cac:TaxCategory)")
    return VatBreakdown(
        taxable_amount=subtotal.decimal("cbc:TaxableAmount", "BT-116"),
        tax_amount=subtotal.decimal("cbc:TaxAmount", "BT-117"),
        category_code=_text(category, "cbc:ID", "BT-118"),
        rate=None if category is None else category.decimal("cbc:Percent", "BT-119"),
        exemption_reason=_text(category, "cbc:TaxExemptionReason", "BT-120"),
        exemption_reason_code=_text(category, "cbc:TaxExemptionReasonCode", "BT-121"),
    )


def _line(line: Node, quantity_path: str) -> InvoiceLine:
    quantity = line.first(quantity_path, "BT-129")
    # BT-130 is an attribute: read also where the quantity's element is empty.
    unit = quantity or line.find(quantity_path)
    item = line.group("cac:Item", "BG-31")
    tax = None if item is None else item.group("cac:ClassifiedTaxCategory", "BG-30")
    return InvoiceLine(
        id=line.text("cbc:ID", "BT-126"),
        quantity=None if quantity is None else quantity.as_decimal("BT-129"),
        unit_code=None if unit is None else unit.attribute("unitCode"),
        net_amount=line.decimal("cbc:LineExtensionAmount", "BT-131"),
        net_price=line.decimal("cac:Price/cbc:PriceAmount", "BT-146"),
        vat_category_code=_text(tax, "cbc:ID", "BT-151"),
        vat_rate=None if tax is None else tax.decimal("cbc:Percent", "BT-152"),
        item_name=_text(item, "cbc:Name", "BT-153"),
    )


def _text(node: Node | None, path: str, term: str) -> str | None:
    return None if node is None else node.text(path, term)

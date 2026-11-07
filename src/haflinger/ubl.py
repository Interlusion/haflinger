"""UBL invoices and credit notes into the model, by the elements EN 16931-3-2 assigns
(REQ-003-PRS-F002)."""

import re
from datetime import date

from haflinger._allowances import AllowanceChargeTerms, allowances_and_charges, price_allowance
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
from haflinger._payments import one_value, payment_means
from haflinger._periods import INVOICING_PERIOD, LINE_PERIOD, PeriodTerms
from haflinger._xml import (
    XML_WHITESPACE,
    Node,
    by_code,
    choose_vat_totals,
    first_group,
    first_of,
    first_reference,
    identifier_only,
    none_if_empty,
    of_code,
    vat_only,
)
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
    TaxRepresentative,
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
# The tax a UBL tax category belongs to.
_TAX_SCHEME = "cac:TaxScheme/cbc:ID"


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
    allowances, charges = allowances_and_charges(
        root.findall("cac:AllowanceCharge"), "cbc:ChargeIndicator", _allowance_charge
    )
    line, quantity = (
        ("cac:CreditNoteLine", "cbc:CreditedQuantity")
        if credit_note
        else ("cac:InvoiceLine", "cbc:InvoicedQuantity")
    )
    # BT-18 is the additional document of the type code 130, and in a credit note, which has no
    # cac:ProjectReference, BT-11 the one of 50; the others are supporting documents (BG-24),
    # whatever their type code.
    additional = root.findall("cac:AdditionalDocumentReference")
    documents = by_code(
        additional,
        "cbc:DocumentTypeCode",
        f"BG-24{', BT-11' if credit_note else ''}, BT-18 (cbc:DocumentTypeCode)",
    )
    invoiced_objects = documents.pop("130", [])
    identifier_only(
        invoiced_objects, _SUPPORTING_ONLY, "BT-18's additional document (type code 130)"
    )
    invoiced = first_reference(invoiced_objects, "cbc:ID", "BT-18")
    projects: list[Node] = []
    if credit_note:
        projects = documents.pop("50", [])
        identifier_only(projects, _SUPPORTING_ONLY, "BT-11's additional document (type code 50)")
        project = _text(first_reference(projects, "cbc:ID", "BT-11"), "cbc:ID", "BT-11")
    else:
        project = root.text("cac:ProjectReference/cbc:ID", "BT-11")
    references = {node.element for node in invoiced_objects + projects}
    seller = root.group("cac:AccountingSupplierParty/cac:Party", "BG-4")
    payee = root.group("cac:PayeeParty", "BG-10")
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
        project_reference=project,
        contract_reference=root.text("cac:ContractDocumentReference/cbc:ID", "BT-12"),
        purchase_order_reference=root.text("cac:OrderReference/cbc:ID", "BT-13"),
        sales_order_reference=root.text("cac:OrderReference/cbc:SalesOrderID", "BT-14"),
        receiving_advice_reference=root.text("cac:ReceiptDocumentReference/cbc:ID", "BT-15"),
        despatch_advice_reference=root.text("cac:DespatchDocumentReference/cbc:ID", "BT-16"),
        tender_or_lot_reference=root.text("cac:OriginatorDocumentReference/cbc:ID", "BT-17"),
        invoiced_object_id=None
        if invoiced is None
        else identifier(invoiced.first("cbc:ID", "BT-18")),
        buyer_accounting_reference=root.text("cbc:AccountingCost", "BT-19"),
        payment_terms=root.text("cac:PaymentTerms/cbc:Note", "BT-20"),
        business_process=root.text("cbc:ProfileID", "BT-23"),
        specification_id=specification_id,
        notes=tuple(note for node in root.findall("cbc:Note") if (note := _note(node)) is not None),
        preceding_invoices=tuple(
            reference
            for node in root.findall("cac:BillingReference/cac:InvoiceDocumentReference")
            if (
                reference := none_if_empty(
                    PrecedingInvoice(
                        number=node.text("cbc:ID", "BT-25"),
                        issue_date=_date(node, "cbc:IssueDate", "BT-26"),
                    )
                )
            )
            is not None
        ),
        seller=_party(seller, SELLER),
        buyer=_party(root.group("cac:AccountingCustomerParty/cac:Party", "BG-7"), BUYER),
        payee=_payee(payee),
        tax_representative=_tax_representative(root.group("cac:TaxRepresentativeParty", "BG-11")),
        delivery=_delivery(root.group("cac:Delivery", "BG-13", *_DELIVERY)),
        invoicing_period=_period(root, INVOICING_PERIOD),
        payment_instructions=_payment_instructions(root, payee, seller),
        allowances=allowances,
        charges=charges,
        totals=_totals(
            root.group("cac:LegalMonetaryTotal", "BG-22"),
            _tax_amount(vat_total),
            _tax_amount(vat_total_in_tax_currency),
        ),
        vat_breakdown=tuple(_vat_breakdown(node) for node in _subtotals(tax_totals, vat_total)),
        supporting_documents=tuple(
            document
            for node in additional
            if node.element not in references
            and (document := _supporting_document(node)) is not None
        ),
        lines=tuple(_line(node, quantity) for node in root.findall(line) if node.holds_value()),
    )


# The terms of a supporting document an additional document of BT-11 or BT-18 doesn't hold.
_SUPPORTING_ONLY = (
    ("cbc:DocumentDescription", "BT-123"),
    ("cac:Attachment/cac:ExternalReference/cbc:URI", "BT-124"),
)


def _supporting_document(node: Node) -> SupportingDocument | None:
    return none_if_empty(
        SupportingDocument(
            reference=node.text("cbc:ID", "BT-122"),
            description=node.text("cbc:DocumentDescription", "BT-123"),
            external_location=node.text("cac:Attachment/cac:ExternalReference/cbc:URI", "BT-124"),
        )
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
    entity_terms = (terms.name, terms.legal_registration_id, terms.additional_legal_information)
    entity = party.group(
        "cac:PartyLegalEntity",
        f"{', '.join(term for term in entity_terms if term)} (cac:PartyLegalEntity)",
    )
    address = party.group("cac:PostalAddress", terms.address.group)
    contact_element = party.group("cac:Contact", terms.contact, *_CONTACT)
    vat_id, tax_id = _tax_identifiers(party, terms.vat_id, terms.tax_registration)
    ids = (
        _identifier_nodes(party, terms.identifier, creditor=False)
        if terms.creditor_identifier
        else party.holding(terms.identifier, _IDENTIFIER)
    )
    point, telephone, email = _CONTACT
    return Party(
        name=_text(entity, "cbc:RegistrationName", terms.name),
        trading_name=party.text("cac:PartyName/cbc:Name", terms.trading_name),
        identifiers=identifiers(ids, terms.identifier, one=terms.one_identifier),
        legal_registration_id=_legal_registration(entity, terms.legal_registration_id),
        vat_id=vat_id,
        tax_registration_id=tax_id,
        additional_legal_information=None
        if terms.additional_legal_information is None
        else _text(entity, "cbc:CompanyLegalForm", terms.additional_legal_information),
        electronic_address=identifier(party.first("cbc:EndpointID", terms.electronic_address)),
        **_address(address, terms.address),
        contact=None
        if contact_element is None
        else contact(
            point=contact_element.text(point, terms.contact_point),
            telephone=contact_element.text(telephone, terms.telephone),
            email=contact_element.text(email, terms.email),
        ),
    )


def _identifier_nodes(party: Node | None, term: str, *, creditor: bool) -> list[Node]:
    """The seller's or the payee's identifiers holding a value: with `creditor`, those with scheme
    SEPA, which are the bank assigned creditor identifier (BT-90), else the others, of `term`."""
    if party is None:
        return []
    return [
        node
        for node in party.findall(_IDENTIFIER)
        if (node.attribute("schemeID") == "SEPA") == creditor and node.plain(term) is not None
    ]


def _legal_registration(entity: Node | None, term: str) -> Identifier | None:
    """The legal registration identifier (BT-30, BT-47, BT-61) of a cac:PartyLegalEntity, with
    its scheme."""
    return None if entity is None else identifier(entity.first("cbc:CompanyID", term))


def _tax_identifiers(
    party: Node, vat_term: str, tax_term: str | None
) -> tuple[str | None, str | None]:
    """The party's VAT identifier, of tax scheme `VAT`, and, where `tax_term` names one, its tax
    registration identifier, of another tax scheme."""
    taxes = ", ".join(term for term in (vat_term, tax_term) if term)
    vat_ids: list[Node] = []
    tax_ids: list[Node] = []
    for scheme in party.findall("cac:PartyTaxScheme"):
        kind = scheme.text(_TAX_SCHEME, f"{taxes} (cac:TaxScheme)")
        if kind == "VAT":
            vat_ids += scheme.holding(vat_term, "cbc:CompanyID")
        elif kind is not None and tax_term is not None:
            tax_ids += scheme.holding(tax_term, "cbc:CompanyID")
    vat_id = first_of(vat_ids, vat_term)
    tax_id = None if tax_term is None else first_of(tax_ids, tax_term)
    return (None if vat_id is None else vat_id.value), (None if tax_id is None else tax_id.value)


def _payee(payee: Node | None) -> Payee | None:
    """BG-10; its identifier with scheme SEPA is the creditor identifier (BT-90), read with the
    direct debit."""
    if payee is None:
        return None
    entity = payee.group("cac:PartyLegalEntity", "BT-61 (cac:PartyLegalEntity)")
    return none_if_empty(
        Payee(
            name=payee.text("cac:PartyName/cbc:Name", "BT-59"),
            identifier=one_identifier(
                _identifier_nodes(payee, PAYEE_IDENTIFIER, creditor=False), PAYEE_IDENTIFIER
            ),
            legal_registration_id=_legal_registration(entity, "BT-61"),
        )
    )


def _tax_representative(party: Node | None) -> TaxRepresentative | None:
    if party is None:
        return None
    address = party.group("cac:PostalAddress", TAX_REPRESENTATIVE_ADDRESS.group)
    vat_id, _ = _tax_identifiers(party, "BT-63", None)
    return none_if_empty(
        TaxRepresentative(
            name=party.text("cac:PartyName/cbc:Name", "BT-62"),
            vat_id=vat_id,
            **_address(address, TAX_REPRESENTATIVE_ADDRESS),
        )
    )


def _address(address: Node | None, terms: AddressTerms) -> Address:
    return Address(
        address_line_1=_text(address, "cbc:StreetName", terms.address_line_1),
        address_line_2=_text(address, "cbc:AdditionalStreetName", terms.address_line_2),
        address_line_3=_text(address, "cac:AddressLine/cbc:Line", terms.address_line_3),
        city=_text(address, "cbc:CityName", terms.city),
        post_code=_text(address, "cbc:PostalZone", terms.post_code),
        country_subdivision=_text(address, "cbc:CountrySubentity", terms.country_subdivision),
        country_code=_text(address, "cac:Country/cbc:IdentificationCode", terms.country_code),
    )


# The elements of BG-13's terms and of BG-14's or BG-26's, which make a cac:Delivery or a
# cac:InvoicePeriod the group (REQ-003-PRS-F002).
_DELIVERY = (
    "cac:DeliveryParty/cac:PartyName/cbc:Name",
    "cac:DeliveryLocation/cbc:ID",
    "cbc:ActualDeliveryDate",
    *(
        f"cac:DeliveryLocation/cac:Address/{path}"
        for path in (
            "cbc:StreetName",
            "cbc:AdditionalStreetName",
            "cac:AddressLine/cbc:Line",
            "cbc:CityName",
            "cbc:PostalZone",
            "cbc:CountrySubentity",
            "cac:Country/cbc:IdentificationCode",
        )
    ),
)
_PERIOD = ("cbc:StartDate", "cbc:EndDate")


def _delivery(delivery: Node | None) -> Delivery | None:
    if delivery is None:
        return None
    address = delivery.group("cac:DeliveryLocation/cac:Address", DELIVER_TO.group)
    return none_if_empty(
        Delivery(
            party_name=delivery.text("cac:DeliveryParty/cac:PartyName/cbc:Name", "BT-70"),
            location=one_identifier(
                delivery.holding(LOCATION, "cac:DeliveryLocation/cbc:ID"), LOCATION
            ),
            date=_date(delivery, "cbc:ActualDeliveryDate", "BT-72"),
            **_address(address, DELIVER_TO),
        )
    )


def _period(parent: Node, terms: PeriodTerms) -> Period | None:
    """BG-14 or BG-26, from the parent's first cac:InvoicePeriod holding a date."""
    period = parent.group("cac:InvoicePeriod", terms.group, *_PERIOD)
    if period is None:
        return None
    return none_if_empty(
        Period(
            start=_date(period, "cbc:StartDate", terms.start),
            end=_date(period, "cbc:EndDate", terms.end),
        )
    )


# A party's identifiers.
_IDENTIFIER = "cac:PartyIdentification/cbc:ID"
# The elements of a contact's terms, which make a cac:Contact the contact.
_CONTACT = ("cbc:Name", "cbc:Telephone", "cbc:ElectronicMail")


def _payment_instructions(
    root: Node, payee: Node | None, seller: Node | None
) -> PaymentInstructions | None:
    """BG-16 from the payment means, repeated for each account, and the creditor identifier of
    the payee and the seller read (REQ-003-PRS-F002)."""
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
            direct_debit=_direct_debit(mandate, payee, seller),
        )
    )


def _direct_debit(
    mandate: Node | None, payee: Node | None, seller: Node | None
) -> DirectDebit | None:
    """BG-19 from the mandate and the creditor identifier: the payee's, or else the seller's,
    identifier with scheme SEPA, which without a mandate is no direct debit's
    (REQ-003-PRS-F002)."""
    creditors = [
        node
        for party in (payee, seller)
        for node in _identifier_nodes(party, "BT-90", creditor=True)
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


def _allowance_charge(node: Node, terms: AllowanceChargeTerms) -> AllowanceCharge:
    label = f"{terms.vat} (cac:TaxCategory)"
    category = first_group(vat_only(node.findall("cac:TaxCategory"), _TAX_SCHEME, label), label)
    return AllowanceCharge(
        amount=node.decimal("cbc:Amount", terms.amount),
        base_amount=node.decimal("cbc:BaseAmount", terms.base_amount),
        percentage=node.decimal("cbc:MultiplierFactorNumeric", terms.percentage),
        vat_category_code=_text(category, "cbc:ID", terms.vat_category_code),
        vat_rate=None if category is None else category.decimal("cbc:Percent", terms.vat_rate),
        reason=node.text("cbc:AllowanceChargeReason", terms.reason),
        reason_code=node.text("cbc:AllowanceChargeReasonCode", terms.reason_code),
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
    # BT-130 and BT-150 are attributes: read also where the quantity's element is empty.
    unit = quantity or line.find(quantity_path)
    price = line.group("cac:Price", "BG-29")
    base_quantity = None if price is None else price.first("cbc:BaseQuantity", "BT-149")
    base_unit = base_quantity or (None if price is None else price.find("cbc:BaseQuantity"))
    discount = (
        None
        if price is None
        else price_allowance(
            price.findall("cac:AllowanceCharge"),
            "cbc:ChargeIndicator",
            ("cbc:Amount", "cbc:BaseAmount"),
            "BT-147, BT-148 (cac:AllowanceCharge)",
        )
    )
    item = line.group("cac:Item", "BG-31")
    tax = None if item is None else item.group("cac:ClassifiedTaxCategory", "BG-30")
    documents = by_code(
        line.findall("cac:DocumentReference"),
        "cbc:DocumentTypeCode",
        "BT-128 (cbc:DocumentTypeCode)",
    )
    line_object = first_reference(
        of_code(documents, "130", ("cbc:ID",), "BT-128"), "cbc:ID", "BT-128"
    )
    return InvoiceLine(
        id=line.text("cbc:ID", "BT-126"),
        note=line.text("cbc:Note", "BT-127"),
        object_id=None
        if line_object is None
        else identifier(line_object.first("cbc:ID", "BT-128")),
        quantity=None if quantity is None else quantity.as_decimal("BT-129"),
        unit_code=None if unit is None else unit.attribute("unitCode"),
        net_amount=line.decimal("cbc:LineExtensionAmount", "BT-131"),
        purchase_order_line_reference=line.text("cac:OrderLineReference/cbc:LineID", "BT-132"),
        buyer_accounting_reference=line.text("cbc:AccountingCost", "BT-133"),
        period=_period(line, LINE_PERIOD),
        net_price=None if price is None else price.decimal("cbc:PriceAmount", "BT-146"),
        price_discount=None if discount is None else discount.decimal("cbc:Amount", "BT-147"),
        gross_price=None if discount is None else discount.decimal("cbc:BaseAmount", "BT-148"),
        base_quantity=None if base_quantity is None else base_quantity.as_decimal("BT-149"),
        base_quantity_unit_code=None if base_unit is None else base_unit.attribute("unitCode"),
        vat_category_code=_text(tax, "cbc:ID", "BT-151"),
        vat_rate=None if tax is None else tax.decimal("cbc:Percent", "BT-152"),
        item_name=_text(item, "cbc:Name", "BT-153"),
        item_description=_text(item, "cbc:Description", "BT-154"),
        seller_item_id=_text(item, "cac:SellersItemIdentification/cbc:ID", "BT-155"),
        buyer_item_id=_text(item, "cac:BuyersItemIdentification/cbc:ID", "BT-156"),
        standard_item_id=None
        if item is None
        else identifier(item.first("cac:StandardItemIdentification/cbc:ID", "BT-157")),
    )


def _text(node: Node | None, path: str, term: str) -> str | None:
    return None if node is None else node.text(path, term)

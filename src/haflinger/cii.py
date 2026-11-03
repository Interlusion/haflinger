"""CII into the model and the model into CII, by the elements EN 16931-3-3 assigns
(REQ-003-PRS-F002, REQ-004-PRS-F003)."""

import re
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import cast
from xml.etree.ElementTree import Element, SubElement, tostring

from haflinger._parties import (
    BUYER,
    DELIVER_TO,
    LOCATION,
    SELLER,
    TAX_REGISTRATION,
    Address,
    AddressTerms,
    PartyTerms,
    contact,
    identifier,
    identifiers,
    location,
)
from haflinger._payments import one_value, payment_means
from haflinger._xml import (
    XML_WHITESPACE,
    Node,
    choose_vat_totals,
    first_group,
    first_of,
    none_if_empty,
)
from haflinger.errors import InvoiceWriteError
from haflinger.model import (
    Contact,
    CreditTransfer,
    Delivery,
    DirectDebit,
    Identifier,
    Invoice,
    InvoiceLine,
    Note,
    Party,
    PaymentCard,
    PaymentInstructions,
    Period,
    PrecedingInvoice,
    Totals,
    VatBreakdown,
)

NAMESPACE = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
NAMESPACES = {
    "rsm": NAMESPACE,
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    "qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
}
ROOT = "CrossIndustryInvoice"
TAG = f"{{{NAMESPACE}}}{ROOT}"

_DATE_102 = re.compile(r"([0-9]{4})([0-9]{2})([0-9]{2})")

_CONTEXT = "rsm:ExchangedDocumentContext"
_DOCUMENT = "rsm:ExchangedDocument"
_TRANSACTION = "rsm:SupplyChainTradeTransaction"
_AGREEMENT = f"{_TRANSACTION}/ram:ApplicableHeaderTradeAgreement"
_SETTLEMENT = f"{_TRANSACTION}/ram:ApplicableHeaderTradeSettlement"
_DELIVERY = f"{_TRANSACTION}/ram:ApplicableHeaderTradeDelivery"


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
        payment_terms=root.text(
            f"{_SETTLEMENT}/ram:SpecifiedTradePaymentTerms/ram:Description", "BT-20"
        ),
        business_process=root.text(
            f"{_CONTEXT}/ram:BusinessProcessSpecifiedDocumentContextParameter/ram:ID", "BT-23"
        ),
        specification_id=specification_id,
        notes=tuple(
            note
            for node in root.findall(f"{_DOCUMENT}/ram:IncludedNote")
            if (note := _note(node)) is not None
        ),
        preceding_invoices=tuple(
            reference
            for node in root.findall(f"{_SETTLEMENT}/ram:InvoiceReferencedDocument")
            if (reference := _preceding_invoice_of(node)) is not None
        ),
        seller=_party(root.group(f"{_AGREEMENT}/ram:SellerTradeParty", "BG-4"), SELLER),
        buyer=_party(root.group(f"{_AGREEMENT}/ram:BuyerTradeParty", "BG-7"), BUYER),
        delivery=_delivery(root),
        invoicing_period=_period(root.group(f"{_SETTLEMENT}/ram:BillingSpecifiedPeriod", "BG-14")),
        payment_instructions=_payment_instructions(root),
        totals=_totals(
            root.group(
                f"{_SETTLEMENT}/ram:SpecifiedTradeSettlementHeaderMonetarySummation", "BG-22"
            ),
            currency_code,
            tax_currency_code,
        ),
        vat_breakdown=tuple(
            _vat_breakdown(node)
            for node in _vat_taxes(root, f"{_SETTLEMENT}/ram:ApplicableTradeTax", "BG-23")
        ),
        lines=tuple(
            _line(node)
            for node in root.findall(f"{_TRANSACTION}/ram:IncludedSupplyChainTradeLineItem")
            if node.holds_value()
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
    return none_if_empty(note)


def _party(party: Node | None, terms: PartyTerms) -> Party | None:
    if party is None:
        return None
    # The terms of one legal organisation, one address and one contact come from one element
    # each.
    organization = party.group(
        "ram:SpecifiedLegalOrganization",
        f"{terms.legal_registration_id}, {terms.trading_name} (ram:SpecifiedLegalOrganization)",
    )
    address = party.group("ram:PostalTradeAddress", terms.address.group)
    contact_element = party.group("ram:DefinedTradeContact", terms.contact, *_CONTACT)
    registrations = party.findall("ram:SpecifiedTaxRegistration/ram:ID")
    return Party(
        name=party.text("ram:Name", terms.name),
        trading_name=_text(organization, "ram:TradingBusinessName", terms.trading_name),
        identifiers=identifiers(
            _identifier_nodes(party, terms.identifier),
            terms.identifier,
            one=terms.one_identifier,
        ),
        legal_registration_id=_text(organization, "ram:ID", terms.legal_registration_id),
        vat_id=_registration(registrations, "VA", terms.vat_id),
        tax_registration_id=(
            None
            if terms.tax_registration is None
            else _registration(registrations, "FC", terms.tax_registration)
        ),
        electronic_address=identifier(
            party.first("ram:URIUniversalCommunication/ram:URIID", terms.electronic_address)
        ),
        **_address(address, terms.address),
        contact=None if contact_element is None else _contact(contact_element, terms),
    )


def _identifier_nodes(party: Node, term: str) -> list[Node]:
    """A party's identifiers: each ram:ID, and each ram:GlobalID with its scheme, without which it
    identifies nothing and is left out with a finding (REQ-003-PRS-F002)."""
    nodes = party.holding(term, "ram:ID")
    for node in party.holding(term, "ram:GlobalID"):
        if node.attribute("schemeID") is None:
            node.drop(f"{term} in a ram:GlobalID without schemeID is left out: {node.value!r}")
        else:
            nodes.append(node)
    return nodes


def _address(address: Node | None, terms: AddressTerms) -> Address:
    return Address(
        address_line_1=_text(address, "ram:LineOne", terms.address_line_1),
        address_line_2=_text(address, "ram:LineTwo", terms.address_line_2),
        address_line_3=_text(address, "ram:LineThree", terms.address_line_3),
        city=_text(address, "ram:CityName", terms.city),
        post_code=_text(address, "ram:PostcodeCode", terms.post_code),
        country_subdivision=_text(address, "ram:CountrySubDivisionName", terms.country_subdivision),
        country_code=_text(address, "ram:CountryID", terms.country_code),
    )


def _preceding_invoice_of(node: Node) -> PrecedingInvoice | None:
    return none_if_empty(
        PrecedingInvoice(
            number=node.text("ram:IssuerAssignedID", "BT-25"),
            issue_date=_date(node, "ram:FormattedIssueDateTime/qdt:DateTimeString", "BT-26"),
        )
    )


def _delivery(root: Node) -> Delivery | None:
    """BG-13 from the deliver to party and the delivery event (REQ-003-PRS-F002)."""
    ship_to = root.group(f"{_DELIVERY}/ram:ShipToTradeParty", "BT-70, BT-71, BG-15")
    address = None if ship_to is None else ship_to.group("ram:PostalTradeAddress", DELIVER_TO.group)
    return none_if_empty(
        Delivery(
            party_name=_text(ship_to, "ram:Name", "BT-70"),
            location=None if ship_to is None else location(_identifier_nodes(ship_to, LOCATION)),
            date=_date(
                root,
                f"{_DELIVERY}/ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime/udt:DateTimeString",
                "BT-72",
            ),
            **_address(address, DELIVER_TO),
        )
    )


def _period(period: Node | None) -> Period | None:
    if period is None:
        return None
    return none_if_empty(
        Period(
            start=_date(period, "ram:StartDateTime/udt:DateTimeString", "BT-73"),
            end=_date(period, "ram:EndDateTime/udt:DateTimeString", "BT-74"),
        )
    )


# The elements of a contact's terms, which make a ram:DefinedTradeContact the contact.
_CONTACT = (
    "ram:PersonName",
    "ram:DepartmentName",
    "ram:TelephoneUniversalCommunication/ram:CompleteNumber",
    "ram:EmailURIUniversalCommunication/ram:URIID",
)


def _registration(registrations: list[Node], scheme: str, term: str) -> str | None:
    """The tax registration with `scheme`: `VA` for the VAT identifier, `FC` for BT-32."""
    nodes = [
        node
        for node in registrations
        if node.attribute("schemeID") == scheme and node.plain(term) is not None
    ]
    node = first_of(nodes, term)
    return None if node is None else node.value


def _contact(element: Node, terms: PartyTerms) -> Contact | None:
    """A person name, or else a department name, is the contact point (REQ-003-PRS-F002)."""
    person, department, telephone, email = _CONTACT
    return contact(
        point=element.text(person, terms.contact_point, department),
        telephone=element.text(telephone, terms.telephone),
        email=element.text(email, terms.email),
    )


def _payment_instructions(root: Node) -> PaymentInstructions | None:
    """BG-16 from the payment means, repeated for each account, and from the settlement and its
    payment terms (REQ-003-PRS-F002)."""
    means, code = payment_means(
        root.findall(f"{_SETTLEMENT}/ram:SpecifiedTradeSettlementPaymentMeans"),
        lambda node: node.text("ram:TypeCode", "BT-81"),
    )
    texts = [(n, n.value or "") for m in means for n in m.holding("BT-82", "ram:Information")]
    transfers: list[CreditTransfer] = []
    for node in means:
        accounts = [
            account
            for account in node.findall("ram:PayeePartyCreditorFinancialAccount")
            if account.holds_value()
        ]
        bic = node.first("ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID", "BT-86")
        if bic is not None and not accounts:
            bic.drop(f"BT-86 without an account (BT-84) is left out: {bic.value!r}")
        transfers += [
            CreditTransfer(
                account_id=account.text("ram:IBANID", "BT-84", "ram:ProprietaryID"),
                account_name=account.text("ram:AccountName", "BT-85"),
                provider_id=None if bic is None else bic.value,
            )
            for account in accounts
        ]
    card = first_group(
        [
            card
            for node in means
            for card in node.findall("ram:ApplicableTradeSettlementFinancialCard")
        ],
        "BG-18",
    )
    debited = first_of(
        [
            account
            for node in means
            for account in node.holding("BT-91", "ram:PayerPartyDebtorFinancialAccount/ram:IBANID")
        ],
        "BT-91",
    )
    return none_if_empty(
        PaymentInstructions(
            means_code=code,
            means_text=one_value(texts, "BT-82"),
            remittance_information=root.text(f"{_SETTLEMENT}/ram:PaymentReference", "BT-83"),
            credit_transfers=tuple(transfers),
            card=None
            if card is None
            else PaymentCard(
                account_number=card.text("ram:ID", "BT-87"),
                holder_name=card.text("ram:CardholderName", "BT-88"),
            ),
            direct_debit=none_if_empty(
                DirectDebit(
                    mandate_reference=root.text(
                        f"{_SETTLEMENT}/ram:SpecifiedTradePaymentTerms/ram:DirectDebitMandateID",
                        "BT-89",
                    ),
                    creditor_id=root.text(f"{_SETTLEMENT}/ram:CreditorReferenceID", "BT-90"),
                    debited_account_id=None if debited is None else debited.value,
                )
            ),
        )
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
    quantity_path = "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity"
    quantity = line.first(quantity_path, "BT-129")
    # BT-130 is an attribute: read also where the quantity's element is empty.
    unit = quantity or line.find(quantity_path)
    settlement = "ram:SpecifiedLineTradeSettlement"
    taxes = _vat_taxes(line, f"{settlement}/ram:ApplicableTradeTax", "BG-30")
    for node in taxes[1:]:
        node.drop("BG-30 appears more than once; this one is left out")
    tax = taxes[0] if taxes else None
    return InvoiceLine(
        id=line.text("ram:AssociatedDocumentLineDocument/ram:LineID", "BT-126"),
        quantity=None if quantity is None else quantity.as_decimal("BT-129"),
        unit_code=None if unit is None else unit.attribute("unitCode"),
        net_amount=line.decimal(
            f"{settlement}/ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount",
            "BT-131",
        ),
        net_price=line.decimal(
            "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount",
            "BT-146",
        ),
        vat_category_code=_text(tax, "ram:CategoryCode", "BT-151"),
        vat_rate=None if tax is None else tax.decimal("ram:RateApplicablePercent", "BT-152"),
        item_name=line.text("ram:SpecifiedTradeProduct/ram:Name", "BT-153"),
    )


def _vat_taxes(parent: Node, path: str, group: str) -> list[Node]:
    """The elements at `path` holding a value that are VAT: of type code `VAT`, or of none. Another
    tax, which Factur-X EXTENDED allows, is left out with a finding (REQ-003-PRS-F002)."""
    taxes: list[Node] = []
    for node in parent.findall(path):
        if not node.holds_value():
            continue
        type_code = node.find("ram:TypeCode")
        kind = None if type_code is None else type_code.value
        if kind in (None, "VAT"):
            taxes.append(node)
        else:
            node.drop(f"{group} of a tax other than VAT ({kind}) is left out")
    return taxes


def _text(node: Node | None, path: str, term: str) -> str | None:
    return None if node is None else node.text(path, term)


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
# The longest number written, in digits of plain notation (REQ-004-PRS-F001).
_MAX_DIGITS = 1000
# The characters XML 1.0 allows.
_NOT_XML = re.compile("[^\t\n\r\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")
# The form of an IBAN, which a credit transfer's account is written as ram:IBANID with
# (REQ-004-PRS-F003).
_IBAN = re.compile("[A-Z]{2}[0-9]{2}[A-Za-z0-9]{1,30}")
# A `#…#` run within one line, as BR-DE-18 finds them.
_HASH_RUN = re.compile("#.+#")


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
        if note.text is None and note.subject_code is None:
            raise InvoiceWriteError("BG-1 holds a note with neither subject code nor text")
        included = SubElement(document, "ram:IncludedNote")
        _put_text(included, "ram:Content", note.text, "BT-22")
        _put_text(included, "ram:SubjectCode", note.subject_code, "BT-21")

    transaction = SubElement(root, "rsm:SupplyChainTradeTransaction")
    for line in _group(invoice.lines, InvoiceLine, "BG-25"):
        _write_line(SubElement(transaction, "ram:IncludedSupplyChainTradeLineItem"), line)
    agreement = SubElement(transaction, "ram:ApplicableHeaderTradeAgreement")
    _put_text(agreement, "ram:BuyerReference", invoice.buyer_reference, "BT-10")
    _write_party(agreement, "ram:SellerTradeParty", invoice.seller, SELLER)
    _write_party(agreement, "ram:BuyerTradeParty", invoice.buyer, BUYER)
    _write_delivery(SubElement(transaction, "ram:ApplicableHeaderTradeDelivery"), invoice.delivery)
    payment = _checked_instructions(invoice.payment_instructions)
    preceding = _preceding_invoice(invoice)
    debit = None if payment is None else payment.direct_debit
    settlement = SubElement(transaction, "ram:ApplicableHeaderTradeSettlement")
    _put_text(
        settlement,
        "ram:CreditorReferenceID",
        None if debit is None else debit.creditor_id,
        "BT-90",
    )
    _put_text(
        settlement,
        "ram:PaymentReference",
        None if payment is None else payment.remittance_information,
        "BT-83",
    )
    _put_text(settlement, "ram:TaxCurrencyCode", invoice.tax_currency_code, "BT-6")
    _put_text(settlement, "ram:InvoiceCurrencyCode", invoice.currency_code, "BT-5")
    if payment is not None:
        _write_payment_means(settlement, payment)
    for vat in _group(invoice.vat_breakdown, VatBreakdown, "BG-23"):
        tax = SubElement(settlement, "ram:ApplicableTradeTax")
        _put_amount(tax, "ram:CalculatedAmount", vat.tax_amount, "BT-117")
        SubElement(tax, "ram:TypeCode").text = "VAT"
        _put_text(tax, "ram:ExemptionReason", vat.exemption_reason, "BT-120")
        _put_amount(tax, "ram:BasisAmount", vat.taxable_amount, "BT-116")
        _put_text(tax, "ram:CategoryCode", vat.category_code, "BT-118")
        _put_text(tax, "ram:ExemptionReasonCode", vat.exemption_reason_code, "BT-121")
        _put_amount(tax, "ram:RateApplicablePercent", vat.rate, "BT-119")
    _write_period(settlement, invoice.invoicing_period)
    terms = SubElement(settlement, "ram:SpecifiedTradePaymentTerms")
    payment_terms = _checked_text(invoice.payment_terms, "BT-20")
    if payment_terms is not None and _ends_with_discount_terms(payment_terms):
        payment_terms += "\n"
    _leaf(terms, "ram:Description", payment_terms, {})
    _put_date(terms, "ram:DueDateDateTime", invoice.due_date, "BT-9")
    _put_text(
        terms,
        "ram:DirectDebitMandateID",
        None if debit is None else debit.mandate_reference,
        "BT-89",
    )
    _write_totals(settlement, invoice)
    if preceding is not None:
        reference = SubElement(settlement, "ram:InvoiceReferencedDocument")
        _put_text(reference, "ram:IssuerAssignedID", preceding.number, "BT-25")
        _put_date(reference, "ram:FormattedIssueDateTime", preceding.issue_date, "BT-26", "qdt")

    _remove_empty(root)
    # ElementTree writes a carriage return in text as it is, and XML parsers turn it into a line
    # feed; as a character reference it reads back unchanged. Text is the only place one can be.
    body = tostring(root, encoding="UTF-8", xml_declaration=False).replace(b"\r", b"&#13;")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + body


def _write_party(parent: Element, tag: str, party: object, terms: PartyTerms) -> None:
    if party is None:
        return
    if not isinstance(party, Party):
        raise InvoiceWriteError(f"{terms.party} is not a Party: {party!r}")
    ids = _group(party.identifiers, Identifier, terms.identifier)
    if terms.one_identifier and len(ids) > 1:
        raise InvoiceWriteError(
            f"{terms.party} holds more than one identifier ({terms.identifier})"
        )
    if terms.tax_registration is None and party.tax_registration_id is not None:
        raise InvoiceWriteError(
            f"{TAX_REGISTRATION} is the seller's alone; the buyer ({terms.party}) has none"
        )
    element = SubElement(parent, tag)
    _write_identifiers(element, ids, terms.party, terms.identifier)
    _put_text(element, "ram:Name", party.name, terms.name)
    organization = SubElement(element, "ram:SpecifiedLegalOrganization")
    _put_text(organization, "ram:ID", party.legal_registration_id, terms.legal_registration_id)
    _put_text(organization, "ram:TradingBusinessName", party.trading_name, terms.trading_name)
    _write_contact(element, party.contact, terms)
    _write_address(element, party, terms.address)
    electronic_address = cast(object, party.electronic_address)
    if electronic_address is not None:
        if not isinstance(electronic_address, Identifier):
            raise InvoiceWriteError(
                f"{terms.electronic_address} is not an Identifier: {electronic_address!r}"
            )
        value, scheme = _identifier_parts(
            electronic_address,
            terms.party,
            "an electronic address",
            terms.electronic_address,
            scheme_required=True,
        )
        _put_text(
            element,
            "ram:URIUniversalCommunication/ram:URIID",
            value,
            terms.electronic_address,
            schemeID=scheme,
        )
    _put_text(
        element, "ram:SpecifiedTaxRegistration/ram:ID", party.vat_id, terms.vat_id, schemeID="VA"
    )
    if terms.tax_registration is not None:
        _put_text(
            element,
            "ram:SpecifiedTaxRegistration/ram:ID",
            party.tax_registration_id,
            terms.tax_registration,
            schemeID="FC",
        )


def _identifier_parts(
    identifier: Identifier,
    group: str,
    kind: str,
    term: str,
    *,
    scheme_required: bool = False,
) -> tuple[str, str | None]:
    """The identifier's value and scheme, checked as texts; refused without a value, or without
    a scheme where the group requires one (REQ-001-PRS-F001)."""
    value = _checked_text(identifier.value, term)
    if value is None:
        raise InvoiceWriteError(f"{group} holds {kind} without its value ({term})")
    scheme = _checked_text(identifier.scheme, f"{term}-1")
    if scheme is None and scheme_required:
        raise InvoiceWriteError(f"{group} holds {kind} without its scheme ({term}-1)")
    return value, scheme


def _write_identifiers(
    element: Element, identifiers: list[Identifier], group: str, term: str
) -> None:
    """Each identifier with a scheme as ram:GlobalID, one without as ram:ID; the XML Schema wants
    every ram:ID before the first ram:GlobalID (REQ-004-PRS-F003)."""
    for each in sorted(identifiers, key=lambda each: each.scheme is not None):
        value, scheme = _identifier_parts(each, group, "an identifier", term)
        _put_text(
            element, "ram:ID" if scheme is None else "ram:GlobalID", value, term, schemeID=scheme
        )


def _write_address(element: Element, holder: Party | Delivery, terms: AddressTerms) -> None:
    address = SubElement(element, "ram:PostalTradeAddress")
    _put_text(address, "ram:PostcodeCode", holder.post_code, terms.post_code)
    _put_text(address, "ram:LineOne", holder.address_line_1, terms.address_line_1)
    _put_text(address, "ram:LineTwo", holder.address_line_2, terms.address_line_2)
    _put_text(address, "ram:LineThree", holder.address_line_3, terms.address_line_3)
    _put_text(address, "ram:CityName", holder.city, terms.city)
    _put_text(address, "ram:CountryID", holder.country_code, terms.country_code)
    _put_text(
        address, "ram:CountrySubDivisionName", holder.country_subdivision, terms.country_subdivision
    )


def _write_delivery(element: Element, delivery: object) -> None:
    """BG-13 in ram:ApplicableHeaderTradeDelivery (REQ-004-PRS-F003)."""
    if delivery is None:
        return
    if not isinstance(delivery, Delivery):
        raise InvoiceWriteError(f"BG-13 is not a Delivery: {delivery!r}")
    if delivery == Delivery():
        raise InvoiceWriteError("BG-13 holds delivery information without any term")
    location = cast(object, delivery.location)
    if location is not None and not isinstance(location, Identifier):
        raise InvoiceWriteError(f"{LOCATION} is not an Identifier: {location!r}")
    ship_to = SubElement(element, "ram:ShipToTradeParty")
    if location is not None:
        _write_identifiers(ship_to, [location], "BG-13", LOCATION)
    _put_text(ship_to, "ram:Name", delivery.party_name, "BT-70")
    _write_address(ship_to, delivery, DELIVER_TO)
    _put_date(
        element, "ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime", delivery.date, "BT-72"
    )


def _write_period(settlement: Element, period: object) -> None:
    if period is None:
        return
    if not isinstance(period, Period):
        raise InvoiceWriteError(f"BG-14 is not a Period: {period!r}")
    if period == Period():
        raise InvoiceWriteError("BG-14 holds a period without any term")
    element = SubElement(settlement, "ram:BillingSpecifiedPeriod")
    _put_date(element, "ram:StartDateTime", period.start, "BT-73")
    _put_date(element, "ram:EndDateTime", period.end, "BT-74")


def _preceding_invoice(invoice: Invoice) -> PrecedingInvoice | None:
    """BG-3, of which CII D16B holds one (REQ-004-PRS-F001)."""
    references = _group(invoice.preceding_invoices, PrecedingInvoice, "BG-3")
    if len(references) > 1:
        raise InvoiceWriteError(
            "BG-3 holds more preceding invoices than CII D16B can, which is one"
        )
    if references and references[0] == PrecedingInvoice():
        raise InvoiceWriteError("BG-3 holds a preceding invoice without any term")
    return references[0] if references else None


def with_one_preceding_invoice(invoice: Invoice) -> Invoice:
    """The model with its first preceding invoice where it holds more than CII D16B can, as the
    round trip and the benchmark write a model read from UBL (REQ-004-PRS-F006)."""
    return replace(invoice, preceding_invoices=invoice.preceding_invoices[:1])


def _write_contact(party: Element, contact: object, terms: PartyTerms) -> None:
    if contact is None:
        return
    if not isinstance(contact, Contact):
        raise InvoiceWriteError(f"{terms.contact} is not a Contact: {contact!r}")
    if contact == Contact():
        raise InvoiceWriteError(f"{terms.contact} holds a contact without any term")
    element = SubElement(party, "ram:DefinedTradeContact")
    _put_text(element, "ram:PersonName", contact.point, terms.contact_point)
    _put_text(
        element,
        "ram:TelephoneUniversalCommunication/ram:CompleteNumber",
        contact.telephone,
        terms.telephone,
    )
    _put_text(element, "ram:EmailURIUniversalCommunication/ram:URIID", contact.email, terms.email)


def _ends_with_discount_terms(payment_terms: str) -> bool:
    """Whether a line starts with `#`, as XRechnung's discount terms do, and the text ends with a
    `#…#` run, after which BR-DE-18 then wants a line feed (REQ-004-PRS-F003)."""
    lines = payment_terms.split("\n")
    if not any(line.lstrip(XML_WHITESPACE).startswith("#") for line in lines):
        return False
    runs = list(_HASH_RUN.finditer(payment_terms))
    return bool(runs) and runs[-1].end() == len(payment_terms)


def _checked_instructions(payment: object) -> PaymentInstructions | None:
    """BG-16, with the groups in it of their classes, none of them empty, and the card with its
    number (BT-87)."""
    if payment is None:
        return None
    if not isinstance(payment, PaymentInstructions):
        raise InvoiceWriteError(f"BG-16 is not a PaymentInstructions: {payment!r}")
    if payment == PaymentInstructions():
        raise InvoiceWriteError("BG-16 holds payment instructions without any term")
    for transfer in _group(payment.credit_transfers, CreditTransfer, "BG-17"):
        if transfer == CreditTransfer():
            raise InvoiceWriteError("BG-17 holds a credit transfer without any term")
    card = cast(object, payment.card)
    if card is not None:
        if not isinstance(card, PaymentCard):
            raise InvoiceWriteError(f"BG-18 is not a PaymentCard: {card!r}")
        # EN 16931 requires BT-87 in BG-18, and no official rule checks it in CII D16B.
        if card.account_number is None:
            raise InvoiceWriteError("BG-18 holds a card without its account number (BT-87)")
    debit = cast(object, payment.direct_debit)
    if debit is not None:
        if not isinstance(debit, DirectDebit):
            raise InvoiceWriteError(f"BG-19 is not a DirectDebit: {debit!r}")
        if debit == DirectDebit():
            raise InvoiceWriteError("BG-19 holds a direct debit without any term")
    return payment


def _write_payment_means(settlement: Element, payment: PaymentInstructions) -> None:
    """One payment means for each credit transfer, or one without any; the card and the
    debited account in the first (REQ-004-PRS-F003)."""
    transfers: tuple[CreditTransfer | None, ...] = payment.credit_transfers or (None,)
    for index, transfer in enumerate(transfers):
        means = SubElement(settlement, "ram:SpecifiedTradeSettlementPaymentMeans")
        _put_text(means, "ram:TypeCode", payment.means_code, "BT-81")
        _put_text(means, "ram:Information", payment.means_text, "BT-82")
        if index == 0:
            card = payment.card
            if card is not None:
                element = SubElement(means, "ram:ApplicableTradeSettlementFinancialCard")
                _put_text(element, "ram:ID", card.account_number, "BT-87")
                _put_text(element, "ram:CardholderName", card.holder_name, "BT-88")
            debit = payment.direct_debit
            _put_text(
                means,
                "ram:PayerPartyDebtorFinancialAccount/ram:IBANID",
                None if debit is None else debit.debited_account_id,
                "BT-91",
            )
        if transfer is not None:
            account = SubElement(means, "ram:PayeePartyCreditorFinancialAccount")
            account_id = _checked_text(transfer.account_id, "BT-84")
            iban = account_id is not None and _IBAN.fullmatch(account_id) is not None
            if iban:
                _put_text(account, "ram:IBANID", account_id, "BT-84")
            _put_text(account, "ram:AccountName", transfer.account_name, "BT-85")
            if not iban:
                _put_text(account, "ram:ProprietaryID", account_id, "BT-84")
            _put_text(
                means,
                "ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID",
                transfer.provider_id,
                "BT-86",
            )


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
    digits, exponent = len(value.as_tuple().digits), int(value.as_tuple().exponent)
    if value.is_zero():
        digits, exponent = 1, min(exponent, 0)  # 0E+2000 is written 0
    if max(digits + exponent, digits, -exponent) > _MAX_DIGITS:
        raise InvoiceWriteError(
            f"{term} has more than {_MAX_DIGITS:,} digits in plain notation: {value!r}"
        )
    _leaf(parent, path, format(value, "f"), attributes)


def _put_date(parent: Element, path: str, value: object, term: str, data_type: str = "udt") -> None:
    """A date as `DateTimeString` with `format="102"`, of the unqualified data type or, where
    the XML Schema wants it, the qualified one (`qdt`)."""
    if value is None:
        return
    if not isinstance(value, date) or isinstance(value, datetime):
        raise InvoiceWriteError(f"{term} is not a date: {value!r}")
    text = f"{value.year:04}{value.month:02}{value.day:02}"
    _leaf(parent, f"{path}/{data_type}:DateTimeString", text, {"format": "102"})


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

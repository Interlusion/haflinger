"""CII into the model, by the elements EN 16931-3-3 assigns (REQ-003-PRS-F002)."""

import re
from datetime import date

from haflinger._xml import Node, choose_vat_totals
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


def specification_id(root: Node) -> str | None:
    return root.text(f"{_CONTEXT}/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID", "BT-24")


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
            root.find(f"{_AGREEMENT}/ram:SellerTradeParty"),
            ("BT-27", "BT-28", "BT-30", "BT-31", "BT-40"),
        ),
        buyer=_party(
            root.find(f"{_AGREEMENT}/ram:BuyerTradeParty"),
            ("BT-44", "BT-45", "BT-47", "BT-48", "BT-55"),
        ),
        totals=_totals(
            root.find(f"{_SETTLEMENT}/ram:SpecifiedTradeSettlementHeaderMonetarySummation"),
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

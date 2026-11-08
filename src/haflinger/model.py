"""The model of EN 16931 business terms: one invoice, whatever syntax it came in (REQ-001).

Each field holds the business term REQ-001-PRS-F001 names for it. A missing term is `None`, a
missing repeated group an empty tuple; whether a term is required is checked by reading and
writing, not here.
"""

import datetime
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

type Syntax = Literal["cii", "ubl"]

# A BT-24 of this form names the year as its edition (REQ-001, term Edition).
_EN16931 = re.compile(r"urn:cen\.eu:en16931:([0-9]{4})(?![0-9])")
# The profiles of REQ-002-PRS-F003 whose BT-24 doesn't start with `urn:cen.eu:en16931:`.
_NAMES_2017 = frozenset(
    {
        "urn:factur-x.eu:1p0:minimum",
        "urn:factur-x.eu:1p0:basicwl",
        "urn:zugferd.de:2p0:minimum",
        "urn:zugferd.de:2p0:basicwl",
    }
)


@dataclass(frozen=True, kw_only=True)
class Note:
    """BG-1."""

    subject_code: str | None = None  # BT-21
    text: str | None = None  # BT-22


@dataclass(frozen=True, kw_only=True)
class PrecedingInvoice:
    """BG-3."""

    number: str | None = None  # BT-25
    issue_date: date | None = None  # BT-26


@dataclass(frozen=True, kw_only=True)
class Identifier:
    """An identifier with the scheme it belongs to: BT-18, BT-29, BT-30, BT-34, BT-46, BT-47,
    BT-49, BT-60, BT-61, BT-71, BT-128 and BT-157, each with its scheme (BT-18-1 and so on)."""

    value: str | None = None
    scheme: str | None = None


@dataclass(frozen=True, kw_only=True)
class ItemClassification:
    """An item classification identifier (BT-158) with the scheme it belongs to (BT-158-1) and
    the scheme's version (BT-158-2)."""

    value: str | None = None  # BT-158
    scheme: str | None = None  # BT-158-1
    scheme_version: str | None = None  # BT-158-2


@dataclass(frozen=True, kw_only=True)
class Contact:
    """BG-6 seller contact or BG-9 buyer contact."""

    point: str | None = None  # BT-41, BT-56
    telephone: str | None = None  # BT-42, BT-57
    email: str | None = None  # BT-43, BT-58


@dataclass(frozen=True, kw_only=True)
class Party:
    """BG-4 seller or BG-7 buyer, with its postal address (BG-5, BG-8). BT-32 and BT-33 are the
    seller's alone, and the buyer has at most one identifier (BT-46)."""

    name: str | None = None  # BT-27, BT-44
    trading_name: str | None = None  # BT-28, BT-45
    identifiers: tuple[Identifier, ...] = ()  # BT-29, BT-46
    legal_registration_id: Identifier | None = None  # BT-30, BT-47
    vat_id: str | None = None  # BT-31, BT-48
    tax_registration_id: str | None = None  # BT-32
    additional_legal_information: str | None = None  # BT-33
    electronic_address: Identifier | None = None  # BT-34, BT-49
    address_line_1: str | None = None  # BT-35, BT-50
    address_line_2: str | None = None  # BT-36, BT-51
    address_line_3: str | None = None  # BT-162, BT-163
    city: str | None = None  # BT-37, BT-52
    post_code: str | None = None  # BT-38, BT-53
    country_subdivision: str | None = None  # BT-39, BT-54
    country_code: str | None = None  # BT-40, BT-55
    contact: Contact | None = None  # BG-6, BG-9


@dataclass(frozen=True, kw_only=True)
class Payee:
    """BG-10, where the payee isn't the seller."""

    name: str | None = None  # BT-59
    identifier: Identifier | None = None  # BT-60
    legal_registration_id: Identifier | None = None  # BT-61


@dataclass(frozen=True, kw_only=True)
class TaxRepresentative:
    """BG-11, with its postal address (BG-12)."""

    name: str | None = None  # BT-62
    vat_id: str | None = None  # BT-63
    address_line_1: str | None = None  # BT-64
    address_line_2: str | None = None  # BT-65
    address_line_3: str | None = None  # BT-164
    city: str | None = None  # BT-66
    post_code: str | None = None  # BT-67
    country_subdivision: str | None = None  # BT-68
    country_code: str | None = None  # BT-69


@dataclass(frozen=True, kw_only=True)
class Delivery:
    """BG-13, with the deliver to address (BG-15)."""

    party_name: str | None = None  # BT-70
    location: Identifier | None = None  # BT-71
    # `datetime.date`, since the field's name hides `date` within the class.
    date: datetime.date | None = None  # BT-72
    address_line_1: str | None = None  # BT-75
    address_line_2: str | None = None  # BT-76
    address_line_3: str | None = None  # BT-165
    city: str | None = None  # BT-77
    post_code: str | None = None  # BT-78
    country_subdivision: str | None = None  # BT-79
    country_code: str | None = None  # BT-80


@dataclass(frozen=True, kw_only=True)
class Period:
    """BG-14 invoicing period or BG-26 invoice line period."""

    start: date | None = None  # BT-73, BT-134
    end: date | None = None  # BT-74, BT-135


@dataclass(frozen=True, kw_only=True)
class CreditTransfer:
    """BG-17."""

    account_id: str | None = None  # BT-84
    account_name: str | None = None  # BT-85
    provider_id: str | None = None  # BT-86


@dataclass(frozen=True, kw_only=True)
class PaymentCard:
    """BG-18."""

    account_number: str | None = None  # BT-87
    holder_name: str | None = None  # BT-88


@dataclass(frozen=True, kw_only=True)
class DirectDebit:
    """BG-19."""

    mandate_reference: str | None = None  # BT-89
    creditor_id: str | None = None  # BT-90
    debited_account_id: str | None = None  # BT-91


@dataclass(frozen=True, kw_only=True)
class PaymentInstructions:
    """BG-16."""

    means_code: str | None = None  # BT-81
    means_text: str | None = None  # BT-82
    remittance_information: str | None = None  # BT-83
    credit_transfers: tuple[CreditTransfer, ...] = ()  # BG-17
    card: PaymentCard | None = None  # BG-18
    direct_debit: DirectDebit | None = None  # BG-19


@dataclass(frozen=True, kw_only=True)
class AllowanceCharge:
    """BG-20 document level allowance or BG-21 document level charge; or, of a line, BG-27
    invoice line allowance or BG-28 invoice line charge, which have no VAT category."""

    amount: Decimal | None = None  # BT-92, BT-99, BT-136, BT-141
    base_amount: Decimal | None = None  # BT-93, BT-100, BT-137, BT-142
    percentage: Decimal | None = None  # BT-94, BT-101, BT-138, BT-143
    vat_category_code: str | None = None  # BT-95, BT-102
    vat_rate: Decimal | None = None  # BT-96, BT-103
    reason: str | None = None  # BT-97, BT-104, BT-139, BT-144
    reason_code: str | None = None  # BT-98, BT-105, BT-140, BT-145


@dataclass(frozen=True, kw_only=True)
class Totals:
    """BG-22."""

    line_net_total: Decimal | None = None  # BT-106
    allowance_total: Decimal | None = None  # BT-107
    charge_total: Decimal | None = None  # BT-108
    total_without_vat: Decimal | None = None  # BT-109
    vat_total: Decimal | None = None  # BT-110
    vat_total_in_tax_currency: Decimal | None = None  # BT-111
    total_with_vat: Decimal | None = None  # BT-112
    prepaid_amount: Decimal | None = None  # BT-113
    rounding_amount: Decimal | None = None  # BT-114
    amount_due: Decimal | None = None  # BT-115


@dataclass(frozen=True, kw_only=True)
class VatBreakdown:
    """BG-23."""

    taxable_amount: Decimal | None = None  # BT-116
    tax_amount: Decimal | None = None  # BT-117
    category_code: str | None = None  # BT-118
    rate: Decimal | None = None  # BT-119
    exemption_reason: str | None = None  # BT-120
    exemption_reason_code: str | None = None  # BT-121


@dataclass(frozen=True, kw_only=True)
class SupportingDocument:
    """BG-24, without the attached document (BT-125), which the model doesn't hold."""

    reference: str | None = None  # BT-122
    description: str | None = None  # BT-123
    external_location: str | None = None  # BT-124


@dataclass(frozen=True, kw_only=True)
class InvoiceLine:
    """BG-25, with its period (BG-26), its allowances and charges (BG-27, BG-28), the price
    details (BG-29), the VAT information (BG-30) and the item (BG-31)."""

    id: str | None = None  # BT-126
    note: str | None = None  # BT-127
    object_id: Identifier | None = None  # BT-128
    quantity: Decimal | None = None  # BT-129
    unit_code: str | None = None  # BT-130
    net_amount: Decimal | None = None  # BT-131
    purchase_order_line_reference: str | None = None  # BT-132
    buyer_accounting_reference: str | None = None  # BT-133
    period: Period | None = None  # BG-26
    allowances: tuple[AllowanceCharge, ...] = ()  # BG-27
    charges: tuple[AllowanceCharge, ...] = ()  # BG-28
    net_price: Decimal | None = None  # BT-146
    price_discount: Decimal | None = None  # BT-147
    gross_price: Decimal | None = None  # BT-148
    base_quantity: Decimal | None = None  # BT-149
    base_quantity_unit_code: str | None = None  # BT-150
    vat_category_code: str | None = None  # BT-151
    vat_rate: Decimal | None = None  # BT-152
    item_name: str | None = None  # BT-153
    item_description: str | None = None  # BT-154
    seller_item_id: str | None = None  # BT-155
    buyer_item_id: str | None = None  # BT-156
    standard_item_id: Identifier | None = None  # BT-157
    item_classifications: tuple[ItemClassification, ...] = ()  # BT-158
    item_country_of_origin: str | None = None  # BT-159


@dataclass(frozen=True, kw_only=True)
class Invoice:
    """An invoice as EN 16931 defines it.

    `syntax` records where it was read from and takes no part in comparing two invoices
    (REQ-001-PRS-F002); `edition` follows from BT-24 (REQ-001-PRS-F003).
    """

    number: str | None = None  # BT-1
    issue_date: date | None = None  # BT-2
    type_code: str | None = None  # BT-3
    currency_code: str | None = None  # BT-5
    tax_currency_code: str | None = None  # BT-6
    vat_point_date: date | None = None  # BT-7
    vat_point_date_code: str | None = None  # BT-8, EN 16931's code (REQ-001-URS-NF001)
    due_date: date | None = None  # BT-9
    buyer_reference: str | None = None  # BT-10
    project_reference: str | None = None  # BT-11
    contract_reference: str | None = None  # BT-12
    purchase_order_reference: str | None = None  # BT-13
    sales_order_reference: str | None = None  # BT-14
    receiving_advice_reference: str | None = None  # BT-15
    despatch_advice_reference: str | None = None  # BT-16
    tender_or_lot_reference: str | None = None  # BT-17
    invoiced_object_id: Identifier | None = None  # BT-18
    buyer_accounting_reference: str | None = None  # BT-19
    payment_terms: str | None = None  # BT-20
    business_process: str | None = None  # BT-23
    specification_id: str | None = None  # BT-24
    notes: tuple[Note, ...] = ()  # BG-1
    preceding_invoices: tuple[PrecedingInvoice, ...] = ()  # BG-3
    seller: Party | None = None  # BG-4
    buyer: Party | None = None  # BG-7
    payee: Payee | None = None  # BG-10
    tax_representative: TaxRepresentative | None = None  # BG-11
    delivery: Delivery | None = None  # BG-13
    invoicing_period: Period | None = None  # BG-14
    payment_instructions: PaymentInstructions | None = None  # BG-16
    allowances: tuple[AllowanceCharge, ...] = ()  # BG-20
    charges: tuple[AllowanceCharge, ...] = ()  # BG-21
    totals: Totals | None = None  # BG-22
    vat_breakdown: tuple[VatBreakdown, ...] = ()  # BG-23
    supporting_documents: tuple[SupportingDocument, ...] = ()  # BG-24
    lines: tuple[InvoiceLine, ...] = ()  # BG-25
    syntax: Syntax | None = field(default=None, compare=False)

    @property
    def edition(self) -> str | None:
        """The EN 16931 edition BT-24 names, such as `"2017"`, or `None`."""
        if self.specification_id is None:
            return None
        if self.specification_id in _NAMES_2017:
            return "2017"
        match = _EN16931.match(self.specification_id)
        return match.group(1) if match else None

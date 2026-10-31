"""The model of EN 16931 business terms: one invoice, whatever syntax it came in (REQ-001).

Each field holds the business term REQ-001-PRS-F001 names for it. A missing term is `None`, a
missing repeated group an empty tuple; whether a term is required is checked by reading and
writing, not here.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

type Syntax = Literal["cii", "ubl"]

# A BT-24 of this form names the year as its edition (REQ-001, term Edition).
_EN16931 = re.compile(r"urn:cen\.eu:en16931:([0-9]{4})(?:[#:].*)?", re.DOTALL)
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
class Party:
    """BG-4 seller or BG-7 buyer."""

    name: str | None = None  # BT-27, BT-44
    trading_name: str | None = None  # BT-28, BT-45
    legal_registration_id: str | None = None  # BT-30, BT-47
    vat_id: str | None = None  # BT-31, BT-48
    country_code: str | None = None  # BT-40, BT-55


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
class InvoiceLine:
    """BG-25."""

    id: str | None = None  # BT-126
    quantity: Decimal | None = None  # BT-129
    unit_code: str | None = None  # BT-130
    net_amount: Decimal | None = None  # BT-131
    net_price: Decimal | None = None  # BT-146
    vat_category_code: str | None = None  # BT-151
    vat_rate: Decimal | None = None  # BT-152
    item_name: str | None = None  # BT-153


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
    due_date: date | None = None  # BT-9
    buyer_reference: str | None = None  # BT-10
    business_process: str | None = None  # BT-23
    specification_id: str | None = None  # BT-24
    notes: tuple[Note, ...] = ()  # BG-1
    seller: Party | None = None  # BG-4
    buyer: Party | None = None  # BG-7
    totals: Totals | None = None  # BG-22
    vat_breakdown: tuple[VatBreakdown, ...] = ()  # BG-23
    lines: tuple[InvoiceLine, ...] = ()  # BG-25
    syntax: Syntax | None = field(default=None, compare=False)

    @property
    def edition(self) -> str | None:
        """The EN 16931 edition BT-24 names, such as `"2017"`, or `None`."""
        if self.specification_id is None:
            return None
        if self.specification_id in _NAMES_2017:
            return "2017"
        match = _EN16931.fullmatch(self.specification_id)
        return match.group(1) if match else None

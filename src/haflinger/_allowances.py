"""Document level allowances and charges: the business term IDs of their fields, which reading,
writing and findings name (REQ-001-PRS-F001), and how reading tells them apart across the
syntaxes (REQ-003-PRS-F002)."""

from collections.abc import Callable
from dataclasses import dataclass

from haflinger._xml import Node, none_if_empty
from haflinger.model import AllowanceCharge


@dataclass(frozen=True, kw_only=True)
class AllowanceChargeTerms:
    """The IDs of an allowance's or a charge's group and of the terms each `AllowanceCharge`
    field holds for it, and its charge indicator as written."""

    group: str
    kind: str
    indicator: str
    amount: str
    base_amount: str
    percentage: str
    vat_category_code: str
    vat_rate: str
    reason: str
    reason_code: str

    @property
    def vat(self) -> str:
        """The VAT category's terms, as findings name the element holding them."""
        return f"{self.vat_category_code} and {self.vat_rate}"


ALLOWANCE = AllowanceChargeTerms(
    group="BG-20",
    kind="an allowance",
    indicator="false",
    amount="BT-92",
    base_amount="BT-93",
    percentage="BT-94",
    vat_category_code="BT-95",
    vat_rate="BT-96",
    reason="BT-97",
    reason_code="BT-98",
)
CHARGE = AllowanceChargeTerms(
    group="BG-21",
    kind="a charge",
    indicator="true",
    amount="BT-99",
    base_amount="BT-100",
    percentage="BT-101",
    vat_category_code="BT-102",
    vat_rate="BT-103",
    reason="BT-104",
    reason_code="BT-105",
)
# The values of xs:boolean, in which the syntaxes write the charge indicator.
_INDICATORS = {"false": ALLOWANCE, "0": ALLOWANCE, "true": CHARGE, "1": CHARGE}
# Both groups, as findings name them; the charge indicator has no business term of its own.
_EITHER = f"{ALLOWANCE.group}/{CHARGE.group}"


def allowances_and_charges(
    nodes: list[Node],
    indicator: str,
    read: Callable[[Node, AllowanceChargeTerms], AllowanceCharge],
) -> tuple[tuple[AllowanceCharge, ...], tuple[AllowanceCharge, ...]]:
    """The allowances and the charges `nodes` hold, in document order, each told apart by its
    charge indicator at the path `indicator`. One whose indicator is neither true nor false is
    left out with a finding; one holding no term is missing."""
    allowances: list[AllowanceCharge] = []
    charges: list[AllowanceCharge] = []
    for node in nodes:
        if not node.holds_value():
            continue
        value = node.text(indicator, f"{_EITHER} charge indicator")
        terms = None if value is None else _INDICATORS.get(value)
        if terms is None:
            node.drop(
                f"{_EITHER} whose charge indicator is neither true nor false ({value!r})"
                " is left out"
            )
            continue
        group = none_if_empty(read(node, terms))
        if group is not None:
            (allowances if terms is ALLOWANCE else charges).append(group)
    return tuple(allowances), tuple(charges)

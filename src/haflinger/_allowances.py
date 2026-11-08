"""Allowances and charges, document level and of a line: the business term IDs of their fields,
which reading, writing and findings name (REQ-001-PRS-F001), and how reading tells them apart
across the syntaxes (REQ-003-PRS-F002); and the allowance on a line's price, which gives its
discount."""

from collections.abc import Callable
from dataclasses import dataclass

from haflinger._xml import Node, first_group, none_if_empty
from haflinger.model import AllowanceCharge


@dataclass(frozen=True, kw_only=True)
class VatTerms:
    """The IDs of a document level allowance's or charge's VAT category code and rate."""

    category_code: str
    rate: str

    def __str__(self) -> str:
        """Both, as findings name the element holding them."""
        return f"{self.category_code} and {self.rate}"


@dataclass(frozen=True, kw_only=True)
class AllowanceChargeTerms:
    """The IDs of an allowance's or a charge's group and of the terms each `AllowanceCharge`
    field holds for it, and its charge indicator as written. A line's has no VAT category: its
    `vat` is None."""

    group: str
    kind: str
    indicator: str
    amount: str
    base_amount: str
    percentage: str
    vat: VatTerms | None
    reason: str
    reason_code: str


ALLOWANCE = AllowanceChargeTerms(
    group="BG-20",
    kind="an allowance",
    indicator="false",
    amount="BT-92",
    base_amount="BT-93",
    percentage="BT-94",
    vat=VatTerms(category_code="BT-95", rate="BT-96"),
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
    vat=VatTerms(category_code="BT-102", rate="BT-103"),
    reason="BT-104",
    reason_code="BT-105",
)
LINE_ALLOWANCE = AllowanceChargeTerms(
    group="BG-27",
    kind="a line allowance",
    indicator="false",
    amount="BT-136",
    base_amount="BT-137",
    percentage="BT-138",
    vat=None,
    reason="BT-139",
    reason_code="BT-140",
)
LINE_CHARGE = AllowanceChargeTerms(
    group="BG-28",
    kind="a line charge",
    indicator="true",
    amount="BT-141",
    base_amount="BT-142",
    percentage="BT-143",
    vat=None,
    reason="BT-144",
    reason_code="BT-145",
)
# The values of xs:boolean, in which the syntaxes write the charge indicator: whether it is a
# charge.
_INDICATORS = {"false": False, "0": False, "true": True, "1": True}


def allowances_and_charges(
    nodes: list[Node],
    indicator: str,
    read: Callable[[Node, AllowanceChargeTerms], AllowanceCharge],
    kinds: tuple[AllowanceChargeTerms, AllowanceChargeTerms] = (ALLOWANCE, CHARGE),
) -> tuple[tuple[AllowanceCharge, ...], tuple[AllowanceCharge, ...]]:
    """The allowances and the charges `nodes` hold, in document order, each told apart by its
    charge indicator at the path `indicator`, of the document or, with `kinds`, of a line. One
    whose indicator is neither true nor false is left out with a finding; one holding no term is
    missing."""
    allowance, charge = kinds
    # Both groups, as findings name them; the charge indicator has no business term of its own.
    either = f"{allowance.group}/{charge.group}"
    allowances: list[AllowanceCharge] = []
    charges: list[AllowanceCharge] = []
    for node in nodes:
        if not node.holds_value():
            continue
        is_charge, value = _indicated(node, indicator, either)
        if is_charge is None:
            node.drop(
                f"{either} whose charge indicator is neither true nor false ({value!r}) is left out"
            )
            continue
        group = none_if_empty(read(node, charge if is_charge else allowance))
        if group is not None:
            (charges if is_charge else allowances).append(group)
    return tuple(allowances), tuple(charges)


def price_allowance(
    nodes: list[Node], indicator: str, amounts: tuple[str, ...], label: str
) -> Node | None:
    """The allowance on a line's price that gives the item price discount (BT-147): the first of
    `nodes` holding a value at one of the paths `amounts` whose charge indicator at the path
    `indicator` is false, or that has no charge indicator, since EN 16931 has no charge on a
    price. A charge, one whose indicator is neither, empty included, and a further allowance are
    left out with a finding naming `label` (REQ-003-PRS-F002)."""
    allowances: list[Node] = []
    for node in nodes:
        if not any(amount.holds_value() for path in amounts for amount in node.findall(path)):
            continue
        if node.find(indicator.split("/")[0]) is None:
            allowances.append(node)
            continue
        is_charge, value = _indicated(node, indicator, label)
        if is_charge is False:
            allowances.append(node)
        else:
            node.drop(f"{label} that isn't an allowance ({value!r}) is left out")
    return first_group(allowances, label)


def _indicated(node: Node, indicator: str, label: str) -> tuple[bool | None, str | None]:
    """Whether the charge indicator at the path `indicator` makes a charge, None where it is
    neither true nor false, with its value as written."""
    value = node.text(indicator, f"{label} charge indicator")
    return (None if value is None else _INDICATORS.get(value)), value

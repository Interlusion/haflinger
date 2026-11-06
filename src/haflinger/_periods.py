"""The invoicing period and the invoice line period: the business term IDs of their fields, which
reading, writing and findings name (REQ-001-PRS-F001)."""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class PeriodTerms:
    """The IDs of a period's group and of the terms each `Period` field holds for it."""

    group: str
    start: str
    end: str


INVOICING_PERIOD = PeriodTerms(group="BG-14", start="BT-73", end="BT-74")
LINE_PERIOD = PeriodTerms(group="BG-26", start="BT-134", end="BT-135")

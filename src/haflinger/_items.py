"""The item of an invoice line (BG-31): what reading it shares across the syntaxes and with the
tests' second reader (REQ-003-PRS-F002, REQ-003-PRS-F005)."""

from haflinger._xml import Node
from haflinger.model import ItemClassification


def classifications(
    codes: list[Node], scheme: str = "listID", version: str = "listVersionID"
) -> tuple[ItemClassification, ...]:
    """The item classification identifiers (BT-158) `codes` hold, each with its scheme (BT-158-1)
    and the scheme's version (BT-158-2) in the attributes `scheme` and `version`: by default
    `listID` and `listVersionID`, which CII and UBL share."""
    return tuple(
        ItemClassification(
            value=code.value,
            scheme=code.attribute(scheme),
            scheme_version=code.attribute(version),
        )
        for code in codes
    )

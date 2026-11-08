"""The item of an invoice line (BG-31): what reading it shares across the syntaxes and with the
tests' second reader (REQ-003-PRS-F002, REQ-003-PRS-F005)."""

from haflinger._xml import Node, none_if_empty
from haflinger.model import ItemAttribute, ItemClassification


def attributes(
    nodes: list[Node], name: str, value: str, others: tuple[tuple[str, str], ...] = ()
) -> tuple[ItemAttribute, ...]:
    """The item attributes (BG-32) `nodes` hold, each with its name (BT-160) at the path `name`
    and its value (BT-161) at the path `value`; one holding neither is missing. A value at one of
    the paths of `others`, each with the term it gives in another form, such as Factur-X
    EXTENDED's, is left out with a finding (REQ-003-PRS-F002)."""
    for node in nodes:
        for path, term in others:
            for other in node.holding(term, path):
                other.drop(
                    f"{term} as {path}, which only Factur-X EXTENDED allows, is left out:"
                    f" {other.value!r}"
                )
    return tuple(
        attribute
        for node in nodes
        if (
            attribute := none_if_empty(
                ItemAttribute(name=node.text(name, "BT-160"), value=node.text(value, "BT-161"))
            )
        )
        is not None
    )


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

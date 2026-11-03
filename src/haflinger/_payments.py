"""What reading the payment instructions (BG-16) shares across the syntaxes
(REQ-003-PRS-F002)."""

from collections.abc import Callable

from haflinger._xml import Node


def payment_means(
    means: list[Node], code_of: Callable[[Node], str | None]
) -> tuple[list[Node], str | None]:
    """The elements of the invoice's one payment means, which the syntaxes repeat for each
    account, and its means code (BT-81), the first one given. An element with another code is
    left out, with the accounts, card and mandate it holds, with a finding."""
    kept: list[Node] = []
    first: str | None = None
    for node in means:
        if not node.holds_value():
            continue
        code = code_of(node)
        if first is not None and code is not None and code != first:
            node.drop(
                "BG-16 appears again with another means code (BT-81); this one is left out with"
                " the accounts, card and mandate it holds"
            )
            continue
        first = first or code
        kept.append(node)
    return kept, first


def one_value(values: list[tuple[Node, str]], term: str) -> str | None:
    """The first of `values`, each with the element it comes from, which the payment means repeat;
    another value is left out with a finding."""
    first = values[0][1] if values else None
    for node, value in values[1:]:
        if value != first:
            node.drop(f"{term} appears again with another value; this one is left out: {value!r}")
    return first

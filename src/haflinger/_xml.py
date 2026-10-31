"""Outside XML: checked and parsed safely, then read by business term (REQ-001, REQ-003).

A value that can't be read as its term requires is missing, with a `HAFL-VALUE` finding; a
further value of a term the model holds once is left out, with a `HAFL-DROPPED` finding
(REQ-003-PRS-F002).
"""

import re
from datetime import date
from decimal import Decimal
from xml.etree.ElementTree import Element, ParseError

import defusedxml.ElementTree
from defusedxml import DefusedXmlException

from haflinger.errors import InvoiceReadError
from haflinger.findings import Finding, Flag

MAX_SIZE = 100 * 1024 * 1024  # REQ-001-PRS-NF003

# The lexical form of xs:decimal: REQ-001's term Value as written.
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")
XML_WHITESPACE = " \t\r\n"


def check_size(data: bytes, max_size: int) -> None:
    if len(data) > max_size:
        raise InvoiceReadError(
            f"the input is {len(data):,} bytes, larger than max_size ({max_size:,} bytes)"
        )


def parse(data: bytes) -> Element:
    """Parse XML from outside: no DTDs, no entities, nothing fetched (REQ-001-PRS-NF001)."""
    try:
        return defusedxml.ElementTree.fromstring(data, forbid_dtd=True)
    except DefusedXmlException:
        raise InvoiceReadError(
            "the input contains a document type declaration (DTD) or an entity declaration,"
            " which outside input may not contain"
        ) from None
    except (ParseError, LookupError, ValueError) as error:
        raise InvoiceReadError(f"the input is not well-formed XML: {error}") from None


def choose_vat_totals[T](
    candidates: list[tuple[T, Node]], currency_code: str | None, tax_currency_code: str | None
) -> tuple[T | None, T | None]:
    """The candidates for BT-110 and BT-111, by the currency of their amount: the first in the
    invoice currency (BT-5) and the first in the VAT accounting currency (BT-6); where the two
    currencies are the same, the first and the second in it. An amount without `currencyID` is in
    the invoice currency. Every other amount is left out with a finding (REQ-003-PRS-F002)."""
    chosen: dict[str, T] = {}
    for candidate, amount in candidates:
        if amount.value is None:
            continue
        currency = amount.attribute("currencyID") or currency_code
        terms = [
            term
            for term, code in (("BT-110", currency_code), ("BT-111", tax_currency_code))
            if currency is not None and currency == code
        ]
        if not terms:
            amount.drop(
                f"BT-110 or BT-111: a VAT total in {currency or 'no currency'}, neither the"
                f" invoice currency ({currency_code or 'none'}) nor the VAT accounting currency"
                f" ({tax_currency_code or 'none'}), is left out: {amount.value!r}"
            )
            continue
        free = [term for term in terms if term not in chosen]
        if free:
            chosen[free[0]] = candidate
        else:
            amount.drop(
                f"{terms[-1]} appears more than once; this one is left out: {amount.value!r}"
            )
    return chosen.get("BT-110"), chosen.get("BT-111")


def local_name(tag: str) -> str:
    return tag.rpartition("}")[2]


class Reading:
    """The state of reading one document: its prefixes and the findings so far."""

    def __init__(self, root: Element, namespaces: dict[str, str], root_name: str) -> None:
        self.root = Node(self, root, f"/{root_name}")
        self.namespaces = namespaces
        self._findings: list[tuple[Element, Finding]] = []

    def report(self, node: Node, rule: str, flag: Flag, text: str) -> None:
        self._findings.append(
            (node.element, Finding(rule=rule, flag=flag, location=node.path, text=text))
        )

    def findings(self) -> tuple[Finding, ...]:
        """The findings in document order."""
        if not self._findings:
            return ()
        order = {id(element): index for index, element in enumerate(self.root.element.iter())}
        ranked = sorted(self._findings, key=lambda item: order[id(item[0])])
        return tuple(finding for _, finding in ranked)


class Node:
    """An element with its location, read by the paths of its syntax."""

    def __init__(self, reading: Reading, element: Element, path: str) -> None:
        self.reading = reading
        self.element = element
        self.path = path

    def find(self, path: str) -> Node | None:
        nodes = self.findall(path)
        return nodes[0] if nodes else None

    def findall(self, path: str) -> list[Node]:
        """The elements at `path`, in document order. A location indexes each step at which a
        parent has more than one match, so that it is an XPath to that element."""
        found = [(self.element, self.path)]
        for step in path.split("/"):
            following: list[tuple[Element, str]] = []
            for parent, location in found:
                children = parent.findall(step, self.reading.namespaces)
                for index, child in enumerate(children, start=1):
                    suffix = f"[{index}]" if len(children) > 1 else ""
                    following.append((child, f"{location}/{step}{suffix}"))
            found = following
        return [Node(self.reading, element, location) for element, location in found]

    def holds_value(self) -> bool:
        """Whether the element or one below it holds text."""
        return any(_stripped(element.text) is not None for element in self.element.iter())

    def group(self, path: str, group: str) -> Node | None:
        """The first element at `path` that holds a value, for a group the model holds once; each
        further one holding a value is left out with a finding."""
        nodes = [node for node in self.findall(path) if node.holds_value()]
        for node in nodes[1:]:
            node.drop(f"{group} appears more than once; this one is left out")
        return nodes[0] if nodes else None

    def attribute(self, name: str) -> str | None:
        return _stripped(self.element.get(name))

    @property
    def value(self) -> str | None:
        """The text without surrounding whitespace; `None` when nothing is left."""
        return _stripped(self.element.text)

    def first(self, path: str, term: str) -> Node | None:
        """The first element at `path` that holds a value; each further one is left out with a
        finding, since the model holds the term once."""
        nodes = [node for node in self.findall(path) if node.value is not None]
        for node in nodes[1:]:
            node.drop(f"{term} appears more than once; this one is left out: {node.value!r}")
        return nodes[0] if nodes else None

    def drop(self, text: str) -> None:
        self.reading.report(self, "HAFL-DROPPED", "warning", text)

    def text(self, path: str, term: str) -> str | None:
        node = self.first(path, term)
        return None if node is None else node.value

    def decimal(self, path: str, term: str) -> Decimal | None:
        node = self.first(path, term)
        return None if node is None else node.as_decimal(term)

    def as_decimal(self, term: str) -> Decimal | None:
        value = self.value
        if value is None:
            return None
        if _DECIMAL.fullmatch(value) is None:
            self.malformed(term, "a number", value)
            return None
        return Decimal(value)

    def as_date(self, term: str, pattern: re.Pattern[str], form: str) -> date | None:
        """The value as a date in `pattern`, whose groups are year, month and day."""
        value = self.value
        if value is None:
            return None
        match = pattern.fullmatch(value)
        if match is not None:
            try:
                return date(*(int(group) for group in match.groups()))
            except ValueError:
                pass
        self.malformed(term, f"a date as {form}", value)
        return None

    def malformed(self, term: str, kind: str, value: str) -> None:
        self.reading.report(
            self,
            "HAFL-VALUE",
            "error",
            f"{term} is not written as {kind}: {value!r}; read as missing",
        )


def _stripped(text: str | None) -> str | None:
    text = (text or "").strip(XML_WHITESPACE)
    return text or None

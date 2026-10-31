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
_XML_WHITESPACE = " \t\r\n"


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
    invoice currency (BT-5) and the first in the VAT accounting currency (BT-6); an amount without
    `currencyID` is in the invoice currency. Every other amount is left out with a finding
    (REQ-003-PRS-F002)."""
    chosen: dict[str, T] = {}
    for candidate, amount in candidates:
        if amount.value is None:
            continue
        currency = amount.attribute("currencyID") or currency_code
        if currency is not None and currency == currency_code:
            term = "BT-110"
        elif currency is not None and currency == tax_currency_code:
            term = "BT-111"
        else:
            amount.drop(
                f"BT-110 or BT-111: a VAT total in {currency or 'no currency'}, neither the"
                f" invoice currency ({currency_code or 'none'}) nor the VAT accounting currency"
                f" ({tax_currency_code or 'none'}), is left out: {amount.value!r}"
            )
            continue
        if term in chosen:
            amount.drop(f"{term} appears more than once; this one is left out: {amount.value!r}")
        else:
            chosen[term] = candidate
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
        element = self.element.find(path, self.reading.namespaces)
        return None if element is None else Node(self.reading, element, f"{self.path}/{path}")

    def findall(self, path: str) -> list[Node]:
        elements = self.element.findall(path, self.reading.namespaces)
        if len(elements) == 1:
            return [Node(self.reading, elements[0], f"{self.path}/{path}")]
        return [
            Node(self.reading, element, f"{self.path}/{path}[{index}]")
            for index, element in enumerate(elements, start=1)
        ]

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
    text = (text or "").strip(_XML_WHITESPACE)
    return text or None

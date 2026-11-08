"""Outside XML: checked and parsed safely, then read by business term (REQ-001, REQ-003).

A value that can't be read as its term requires is missing, with a `HAFL-VALUE` finding; a
further value of a term the model holds once is left out, with a `HAFL-DROPPED` finding
(REQ-003-PRS-F002).
"""

import codecs
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


def check_bytes(data: object) -> None:
    """Outside input comes as `bytes` (REQ-002-PRS-F001, REQ-003-PRS-F006)."""
    if not isinstance(data, bytes):
        raise InvoiceReadError(f"the input is not bytes but {type(data).__name__}")


def check_size(data: bytes, max_size: int) -> None:
    if len(data) > max_size:
        raise InvoiceReadError(
            f"the input is {len(data):,} bytes, larger than max_size ({max_size:,} bytes)"
        )


def parse(data: bytes) -> Element:
    """Parse XML from outside: no DTDs, no entities, nothing fetched (REQ-001-PRS-NF001)."""
    _check_byte_order_mark(data)
    try:
        return defusedxml.ElementTree.fromstring(data, forbid_dtd=True)
    except DefusedXmlException:
        raise InvoiceReadError(
            "the input contains a document type declaration (DTD) or an entity declaration,"
            " which outside input may not contain"
        ) from None
    except (ParseError, LookupError, ValueError) as error:
        raise InvoiceReadError(f"the input is not well-formed XML: {error}") from None


_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32-le", {"utf-32", "utf-32-le"}),
    (codecs.BOM_UTF32_BE, "utf-32-be", {"utf-32", "utf-32-be"}),
    (codecs.BOM_UTF8, "utf-8", {"utf-8"}),
    (codecs.BOM_UTF16_LE, "utf-16-le", {"utf-16", "utf-16-le"}),
    (codecs.BOM_UTF16_BE, "utf-16-be", {"utf-16", "utf-16-be"}),
)
_DECLARED = re.compile(rb"""<\?xml[^>]*?encoding\s*=\s*["']([A-Za-z][A-Za-z0-9._-]*)["']""")


def decode(data: bytes) -> str:
    """The text of an XML document, as the XML parser reads it: by its byte order mark, else by
    the encoding its declaration names, else UTF-8 (UTF-16 recognised by its first bytes). Saxon
    and the XML Schema check of `validate` get this text, so that they see the characters the
    reader sees (REQ-002-PRS-F011)."""
    for bom, encoding, _ in _BOMS:
        if data.startswith(bom):
            return _decode(data[len(bom) :], encoding)
    if data.startswith(b"<\x00?\x00"):
        return _decode(data, "utf-16-le")
    if data.startswith(b"\x00<\x00?"):
        return _decode(data, "utf-16-be")
    declared = _DECLARED.match(data)
    return _decode(data, declared[1].decode("ascii") if declared else "utf-8")


def _decode(data: bytes, encoding: str) -> str:
    try:
        return data.decode(encoding)
    except (LookupError, UnicodeDecodeError) as error:
        raise InvoiceReadError(f"the input can't be decoded as {encoding}: {error}") from None


def _check_byte_order_mark(data: bytes) -> None:
    """Refuse a byte order mark that contradicts the declared encoding, which XML 1.0 makes a
    fatal error: the parser would read by one and Saxon by the other."""
    for bom, encoding, agreeing in _BOMS:
        if not data.startswith(bom):
            continue
        declared = _DECLARED.match(data, len(bom))
        if declared is None:
            return
        name = declared[1].decode("ascii")
        try:
            agrees = codecs.lookup(name).name in agreeing
        except LookupError:
            agrees = False
        if not agrees:
            raise InvoiceReadError(
                f"the input's byte order mark ({encoding}) contradicts its encoding declaration"
                f" ({name})"
            )
        return


def choose_vat_totals[T](
    candidates: list[tuple[T, Node]], currency_code: str | None, tax_currency_code: str | None
) -> tuple[T | None, T | None]:
    """The candidates for BT-110 and BT-111, by the currency of their amount: the first in the
    invoice currency (BT-5) and the first in the VAT accounting currency (BT-6); where the two
    currencies are the same, the first and the second in it. An amount without `currencyID` is in
    the invoice currency. Every other amount is left out with a finding (REQ-003-PRS-F002)."""
    chosen: dict[str, T] = {}
    for candidate, amount in candidates:
        if amount.plain("BT-110 or BT-111") is None:
            continue
        declared = amount.attribute("currencyID")
        currency = declared or currency_code
        terms = [
            term
            for term, code in (("BT-110", currency_code), ("BT-111", tax_currency_code))
            if currency is not None and currency == code
        ]
        if declared is None and not terms:
            terms = ["BT-110"]  # without `currencyID` it is BT-110, also without BT-5
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

    def holds_value(self, *paths: str) -> bool:
        """Whether the element or one below it holds text; with `paths`, one at any of them."""
        if paths:
            return any(node.holds_value() for path in paths for node in self.findall(path))
        return any(_stripped(element.text) is not None for element in self.element.iter())

    def group(self, path: str, group: str, *terms: str) -> Node | None:
        """The first element at `path` that holds a value, for a group the model holds once; each
        further one holding a value is left out with a finding. Where `terms` gives the paths of
        the group's terms, only an element holding a value at one of them counts."""
        return first_group(
            [node for node in self.findall(path) if not terms or node.holds_value(*terms)],
            group,
        )

    def attribute(self, name: str) -> str | None:
        return _stripped(self.element.get(name))

    @property
    def value(self) -> str | None:
        """The text without surrounding whitespace; `None` when nothing is left. Read a term's
        value with `plain`, which checks that the element holds only text."""
        return _stripped(self.element.text)

    def plain(self, term: str) -> str | None:
        """The value of `term`; missing, with a finding, when the element holds elements
        (REQ-003-PRS-F002)."""
        if len(self.element):
            text = "".join(self.element.itertext()).strip(XML_WHITESPACE)
            self.malformed(term, "text alone, without elements", text)
            return None
        return self.value

    def holding(self, term: str, *paths: str) -> list[Node]:
        """The elements at each of `paths` in turn that hold a value of `term`."""
        return [
            node for path in paths for node in self.findall(path) if node.plain(term) is not None
        ]

    def first(self, path: str, term: str, *also: str) -> Node | None:
        """The first element at `path`, or else at the paths `also`, that holds a value; each
        further one is left out with a finding, since the model holds the term once."""
        return first_of(self.holding(term, path, *also), term)

    def drop(self, text: str) -> None:
        self.reading.report(self, "HAFL-DROPPED", "warning", text)

    def text(self, path: str, term: str, *also: str) -> str | None:
        node = self.first(path, term, *also)
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


def none_if_empty[T](group: T) -> T | None:
    """A group read from the document, or None where it holds no term (REQ-001-PRS-F001)."""
    return None if group == type(group)() else group


def first_group(nodes: list[Node], group: str) -> Node | None:
    """The first of `nodes` that holds a value, for a group the model holds once; each further one
    holding a value is left out with a finding."""
    nodes = [node for node in nodes if node.holds_value()]
    for node in nodes[1:]:
        node.drop(f"{group} appears more than once; this one is left out")
    return nodes[0] if nodes else None


def vat_only(nodes: list[Node], kind: str, group: str) -> list[Node]:
    """Those of `nodes` holding a value that are VAT: whose first element at `kind` holding a
    value holds `VAT` in any case, as CEN's rules compare it, or that have none. Another tax,
    which Factur-X EXTENDED allows, is left out with a finding (REQ-003-PRS-F002)."""
    taxes: list[Node] = []
    for node in nodes:
        if not node.holds_value():
            continue
        value = node.text(kind, f"{group} ({kind})")
        if value is None or value.upper() == "VAT":
            taxes.append(node)
        else:
            node.drop(f"{group} of a tax other than VAT ({value}) is left out")
    return taxes


def by_code(nodes: list[Node], path: str, label: str) -> dict[str | None, list[Node]]:
    """Those of `nodes` holding a value by the code at `path`, such as a referenced document's
    type code, each code's in document order; those without a code under None."""
    found: dict[str | None, list[Node]] = {}
    for node in nodes:
        if node.holds_value():
            found.setdefault(node.text(path, label), []).append(node)
    return found


def identifier_only(documents: list[Node], terms: tuple[tuple[str, str], ...], label: str) -> None:
    """`documents` are the additional documents of a reference, such as BT-18's, which hold only
    its identifier: each value at the paths of `terms`, the paths and IDs of the terms only a
    supporting document holds, is left out with a finding naming its term and `label`
    (REQ-003-PRS-F002)."""
    for document in documents:
        for path, term in terms:
            for node in document.holding(term, path):
                node.drop(f"{term} in {label} is left out: {node.value!r}")


def of_code(
    documents: dict[str | None, list[Node]], code: str, paths: tuple[str, ...], label: str
) -> list[Node]:
    """The documents of the type code `code`, to which EN 16931 binds what `label` names (BG-24,
    BT-128); each other one holding a value at one of `paths` is left out with a finding
    (REQ-003-PRS-F002)."""
    for other, nodes in documents.items():
        if other == code:
            continue
        for node in nodes:
            if node.holds_value(*paths):
                node.drop(
                    f"{label} without a type code is left out"
                    if other is None
                    else f"{label} of the type code {other!r}, not {code}, is left out"
                )
    return documents.get(code, [])


def first_reference(
    documents: list[Node], path: str, term: str, scheme: str | None = None
) -> Node | None:
    """The first of `documents` holding a value at `path`, the identifier of a document
    reference the model holds once (BT-11, BT-17, BT-18, BT-128); each further one is left out
    with a finding naming `term` and its identifier, and so is one that holds only the
    identifier's scheme at `scheme`."""
    found: list[Node] = []
    for document in documents:
        if document.holds_value(path):
            found.append(document)
        elif scheme is not None and document.holds_value(scheme):
            document.drop(f"{term}-1 without its identifier ({term}) is left out")
    for document in found[1:]:
        value = next((node.value for node in document.findall(path) if node.holds_value()), None)
        document.drop(f"{term} appears more than once; this one is left out: {value!r}")
    return found[0] if found else None


def first_of(nodes: list[Node], term: str) -> Node | None:
    """The first of `nodes`, which hold values of `term`; each further one is left out with a
    finding."""
    for node in nodes[1:]:
        node.drop(f"{term} appears more than once; this one is left out: {node.value!r}")
    return nodes[0] if nodes else None


def one_value(values: list[tuple[Node, str]], term: str) -> str | None:
    """The first of `values`, each with the element it comes from, of a term the syntax repeats
    with the same value, such as the payment means' text (BT-82) or CII's VAT point date code
    (BT-8) in each VAT entry; another value is left out with a finding."""
    first = values[0][1] if values else None
    for node, value in values[1:]:
        if value != first:
            node.drop(f"{term} appears again with another value; this one is left out: {value!r}")
    return first


def _stripped(text: str | None) -> str | None:
    text = (text or "").strip(XML_WHITESPACE)
    return text or None

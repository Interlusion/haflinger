"""XML Schema checks with lxml, of written invoices (REQ-004-PRS-F004) and of incoming ones before
the rules (REQ-002-PRS-F011); ADR-006."""

import re
import threading
from collections import Counter
from pathlib import Path
from typing import cast

from lxml import etree

# lxml's element type, which its stubs name only privately.
from lxml.etree import _Element  # pyright: ignore[reportPrivateUsage]

from haflinger._findings import Finding
from haflinger._xml import local_name, step

_ARTEFACTS = Path(__file__).parent / "artefacts"
_UBL = "kosit-validator-xrechnung/resources/ubl/2.1/xsd/maindoc"
_FERD = "ferd-zugferd/Schema"
# The schemas, by their path below `artefacts/`, with the name a finding gives.
SCHEMAS = {
    "kosit-validator-xrechnung/resources/cii/16b/xsd/CrossIndustryInvoice_100pD16B.xsd": (
        "CII D16B XML Schema"
    ),
    f"{_UBL}/UBL-Invoice-2.1.xsd": "UBL 2.1 Invoice XML Schema",
    f"{_UBL}/UBL-CreditNote-2.1.xsd": "UBL 2.1 CreditNote XML Schema",
    f"{_FERD}/0_Factur-X_1.09.2_MINIMUM/Factur-X_1.09.2_MINIMUM.xsd": "Factur-X MINIMUM XML Schema",
    f"{_FERD}/1_Factur-X_1.09.2_BASICWL/Factur-X_1.09.2_BASICWL.xsd": (
        "Factur-X BASIC WL XML Schema"
    ),
    f"{_FERD}/2_Factur-X_1.09.2_BASIC/Factur-X_1.09.2_BASIC.xsd": "Factur-X BASIC XML Schema",
    f"{_FERD}/3_Factur-X_1.09.2_EN16931/Factur-X_1.09.2_EN16931.xsd": (
        "Factur-X EN 16931 XML Schema"
    ),
    f"{_FERD}/4_Factur-X_1.09.2_EXTENDED/Factur-X_1.09.2_EXTENDED.xsd": (
        "Factur-X EXTENDED XML Schema"
    ),
}
CII = "kosit-validator-xrechnung/resources/cii/16b/xsd/CrossIndustryInvoice_100pD16B.xsd"
FACTUR_X_EN16931 = f"{_FERD}/3_Factur-X_1.09.2_EN16931/Factur-X_1.09.2_EN16931.xsd"
# What lxml parses has passed `defusedxml` first or was written by Haflinger: entities, DTDs and
# the network stay off, and libxml2's limits on the size of a text don't apply (an embedded
# attachment can be larger than 10 MB).
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=True)
# An XML declaration, which lxml refuses in a text it gets already decoded.
_DECLARATION = re.compile(r"<\?xml[^>]*\?>")
# Each thread compiles the schemas it uses, once: a schema's error log belongs to its last
# validation, whichever thread ran it, and a lock around it could be left held by an exception
# that a signal handler raises, such as RQ's job timeout (REQ-002-PRS-NF005).
_COMPILED = threading.local()
_MAX_TEXT = 500  # characters of a finding's text that a long one keeps
# The bytes of a prefixed name that libxml2's paths keep: `xmlGetNodePath` writes it into a buffer
# of 100 bytes, less one for its end and one it leaves out.
_NAME_BYTES = 98


def _schema(path: str) -> etree.XMLSchema:
    schemas: dict[str, etree.XMLSchema] | None = getattr(_COMPILED, "schemas", None)
    if schemas is None:
        schemas = _COMPILED.schemas = {}
    schema = schemas.get(path)
    if schema is None:
        schema = schemas[path] = etree.XMLSchema(etree.parse(_ARTEFACTS / path, _PARSER))
    return schema


def check(document: bytes | str, *schemas: str) -> list[Finding]:
    """`HAFL-XSD` findings for each violation of each schema, by its path below `artefacts/`, or
    for a document the check can't parse. A written invoice comes as bytes, which libxml2 decodes
    as a recipient's parser would; an incoming one as the text Saxon gets (REQ-002-PRS-F011).
    libxml2 stops at a depth of its own (2,048 elements), also with `huge_tree`: a deeper
    document is a finding, not a crash."""
    if isinstance(document, str):
        document = (
            _DECLARATION.sub("", document, count=1) if document.startswith("<?xml") else document
        )
    try:
        tree = etree.fromstring(document, _PARSER)
    except etree.XMLSyntaxError as error:
        location, text = f"line {error.lineno}", f"the document can't be parsed: {error}"
        return [_finding(SCHEMAS[schemas[0]], location, text)]
    findings: list[Finding] = []
    locations = Locations(tree)
    for path in schemas:
        schema = _schema(path)
        errors = [] if schema.validate(tree) else list(schema.error_log)
        findings.extend(
            _finding(
                SCHEMAS[path], locations.of(_path(error)) or f"line {error.line}", error.message
            )
            for error in errors
        )
    return findings


def _path(error: etree._LogEntry) -> str | None:  # pyright: ignore[reportPrivateUsage]
    """libxml2's path of the error; `None` where its cut of a long name splits a character,
    which lxml can't decode."""
    try:
        return error.path
    except UnicodeDecodeError:
        return None


class Locations:
    """libxml2's paths, such as `/ubl:Invoice/cbc:Note[2]` or `/*/*[3]`, as a finding's location
    gives them (REQ-002-PRS-F002). Each parent's children are indexed once, by libxml2's names,
    so that many errors among many siblings take linear time."""

    def __init__(self, root: _Element) -> None:
        self._root = root
        # By parent: each child by its libxml2 step, and its location; `None` for a step that
        # names more than one.
        self._children: dict[_Element, dict[str, tuple[_Element, str] | None]] = {}

    def of(self, path: str | None) -> str | None:
        """The location of the element at `path`, which for an attribute's error names its
        element; `None` where libxml2 gives no path or one that names no element of the tree."""
        if not path:
            return None
        first, *rest = path.split("/")[1:] if path.startswith("/") else ("", "")
        root, tag = self._root, cast(str, self._root.tag)
        if first != _cut(_libxml2_name(root, tag)):
            return None
        element, location = root, step(tag, 1)
        for part in rest:
            found = self._index(element, location).get(part)
            if found is None:
                return None
            element, location = found
        return location

    def _index(self, parent: _Element, at: str) -> dict[str, tuple[_Element, str] | None]:
        """libxml2's `xmlGetNodePath` counts a named element among its siblings of the same
        name and prefix, and one of the default namespace, `*`, among all its sibling elements;
        a step gives the position only where there is more than one. It cuts a long prefixed
        name, so that two siblings may share a step, which then names neither."""
        index = self._children.get(parent)
        if index is None:
            elements = [(child, child.tag) for child in parent if isinstance(child.tag, str)]
            names = [_libxml2_name(child, tag) for child, tag in elements]
            total = Counter(names)
            seen: dict[str, int] = {}
            tags: dict[str, int] = {}
            index = {}
            for position, ((child, tag), name) in enumerate(zip(elements, names, strict=True), 1):
                seen[name] = seen.get(name, 0) + 1
                tags[tag] = tags.get(tag, 0) + 1
                count, occurrence = (
                    (len(elements), position) if name == "*" else (total[name], seen[name])
                )
                key = _cut(name) + (f"[{occurrence}]" if count > 1 else "")
                index[key] = None if key in index else (child, at + step(tag, tags[tag]))
            self._children[parent] = index
        return index


def _libxml2_name(element: _Element, tag: str) -> str:
    """An element's name in libxml2's paths: with its prefix, `*` in the default namespace."""
    if element.prefix:
        return f"{element.prefix}:{local_name(tag)}"
    return "*" if tag.startswith("{") else tag


def _cut(name: str) -> str:
    """A name as libxml2's paths give it: a prefixed one of its first 98 bytes."""
    if ":" not in name or len(name) * 4 <= _NAME_BYTES:
        return name
    return name.encode()[:_NAME_BYTES].decode(errors="ignore")


def check_cii(document: bytes, *, factur_x_en16931: bool = False) -> list[Finding]:
    """A written invoice against the CII D16B XML Schema and, if asked, Factur-X's XML Schema of
    the EN 16931 profile."""
    return check(document, CII, *([FACTUR_X_EN16931] if factur_x_en16931 else []))


def _finding(schema: str, location: str, text: str) -> Finding:
    """libxml2 quotes the value it refuses, a large attachment's Base64 too: a long message keeps
    its start and its end (REQ-002-PRS-F011)."""
    if len(text) > _MAX_TEXT:
        start, end, left_out = (
            text[: _MAX_TEXT // 2],
            text[-_MAX_TEXT // 2 :],
            len(text) - _MAX_TEXT,
        )
        text = f"{start} … ({left_out:,} characters left out) … {end}"
    return Finding(rule="HAFL-XSD", flag="fatal", location=location, text=f"{schema}: {text}")

"""The XML Schema check of written invoices, with lxml (REQ-004-PRS-F004, ADR-006)."""

import threading
from functools import cache
from pathlib import Path

from lxml import etree

from haflinger.findings import Finding

_CII = (
    Path(__file__).parent
    / "artefacts/kosit-validator-xrechnung/resources/cii/16b/xsd/CrossIndustryInvoice_100pD16B.xsd"
)
# The documents are Haflinger's own or the caller's, never outside input: libxml2's limits on the
# size of a text don't apply to them; entities and the network stay off.
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=True)
# A schema's error log belongs to the last validation, whichever thread ran it.
_LOCK = threading.Lock()


@cache
def _cii_schema() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(_CII, _PARSER))


def check_cii(document: bytes) -> list[Finding]:
    """`HAFL-XSD` findings for each violation of the CII D16B XML Schema, or for a document the
    check can't parse."""
    try:
        tree = etree.fromstring(document, _PARSER)
    except etree.XMLSyntaxError as error:
        return [_finding(f"line {error.lineno}", f"the document can't be parsed: {error}")]
    with _LOCK:
        schema = _cii_schema()
        if schema.validate(tree):
            return []
        errors = list(schema.error_log)
    return [_finding(error.path or f"line {error.line}", error.message) for error in errors]


def _finding(location: str, text: str) -> Finding:
    return Finding(
        rule="HAFL-XSD", flag="fatal", location=location, text=f"CII D16B XML Schema: {text}"
    )

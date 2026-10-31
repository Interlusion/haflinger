"""The XML Schema check of written invoices, with lxml (REQ-004-PRS-F004, ADR-006)."""

from functools import cache
from pathlib import Path

from lxml import etree

from haflinger.findings import Finding

_CII = (
    Path(__file__).parent
    / "artefacts/kosit-validator-xrechnung/resources/cii/16b/xsd/CrossIndustryInvoice_100pD16B.xsd"
)
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)


@cache
def _cii_schema() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(_CII, _PARSER))


def check_cii(document: bytes) -> list[Finding]:
    """`HAFL-XSD` findings for each violation of the CII D16B XML Schema."""
    schema = _cii_schema()
    if schema.validate(etree.fromstring(document, _PARSER)):
        return []
    return [
        Finding(
            rule="HAFL-XSD",
            flag="fatal",
            location=error.path or f"line {error.line}",
            text=f"CII D16B XML Schema: {error.message}",
        )
        for error in schema.error_log
    ]

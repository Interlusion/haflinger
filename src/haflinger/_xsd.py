"""The XML Schema check of written invoices, with lxml (REQ-004-PRS-F004, ADR-006)."""

import threading
from functools import cache
from pathlib import Path

from lxml import etree

from haflinger.findings import Finding

_ARTEFACTS = Path(__file__).parent / "artefacts"
_CII = (
    _ARTEFACTS / "kosit-validator-xrechnung/resources/cii/16b/xsd/CrossIndustryInvoice_100pD16B.xsd"
)
_FACTUR_X_EN16931 = (
    _ARTEFACTS / "ferd-zugferd/Schema/3_Factur-X_1.09.2_EN16931/Factur-X_1.09.2_EN16931.xsd"
)
# The documents are Haflinger's own or the caller's, never outside input: libxml2's limits on the
# size of a text don't apply to them; entities and the network stay off.
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=True)
# A schema's error log belongs to the last validation, whichever thread ran it.
_LOCK = threading.Lock()


@cache
def _schema(path: Path) -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(path, _PARSER))


def check_cii(document: bytes, *, factur_x_en16931: bool = False) -> list[Finding]:
    """`HAFL-XSD` findings for each violation of the CII D16B XML Schema and, if asked, of
    Factur-X's XML Schema of the EN 16931 profile; or for a document the check can't parse."""
    try:
        tree = etree.fromstring(document, _PARSER)
    except etree.XMLSyntaxError as error:
        location, text = f"line {error.lineno}", f"the document can't be parsed: {error}"
        return [_finding("CII D16B XML Schema", location, text)]
    schemas = {"CII D16B XML Schema": _CII}
    if factur_x_en16931:
        schemas["Factur-X EN 16931 XML Schema"] = _FACTUR_X_EN16931
    findings: list[Finding] = []
    for name, path in schemas.items():
        with _LOCK:
            schema = _schema(path)
            errors = [] if schema.validate(tree) else list(schema.error_log)
        findings.extend(
            _finding(name, error.path or f"line {error.line}", error.message) for error in errors
        )
    return findings


def _finding(schema: str, location: str, text: str) -> Finding:
    return Finding(rule="HAFL-XSD", flag="fatal", location=location, text=f"{schema}: {text}")

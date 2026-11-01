"""XML Schema checks with lxml, of written invoices (REQ-004-PRS-F004) and of incoming ones before
the rules (REQ-002-PRS-F011); ADR-006."""

import threading
from functools import cache
from pathlib import Path

from lxml import etree

from haflinger.findings import Finding

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
# A schema's error log belongs to the last validation, whichever thread ran it.
_LOCK = threading.Lock()


@cache
def _schema(path: str) -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(_ARTEFACTS / path, _PARSER))


def check(document: bytes, *schemas: str) -> list[Finding]:
    """`HAFL-XSD` findings for each violation of each schema, by its path below `artefacts/`, or
    for a document the check can't parse."""
    try:
        tree = etree.fromstring(document, _PARSER)
    except etree.XMLSyntaxError as error:
        location, text = f"line {error.lineno}", f"the document can't be parsed: {error}"
        return [_finding(SCHEMAS[schemas[0]], location, text)]
    findings: list[Finding] = []
    for path in schemas:
        with _LOCK:
            schema = _schema(path)
            errors = [] if schema.validate(tree) else list(schema.error_log)
        findings.extend(
            _finding(SCHEMAS[path], error.path or f"line {error.line}", error.message)
            for error in errors
        )
    return findings


def check_cii(document: bytes, *, factur_x_en16931: bool = False) -> list[Finding]:
    """A written invoice against the CII D16B XML Schema and, if asked, Factur-X's XML Schema of
    the EN 16931 profile."""
    return check(document, CII, *([FACTUR_X_EN16931] if factur_x_en16931 else []))


def _finding(schema: str, location: str, text: str) -> Finding:
    return Finding(rule="HAFL-XSD", flag="fatal", location=location, text=f"{schema}: {text}")

"""Validation with the official rules, run unchanged with Saxon (REQ-002, ADR-006).

The rule sets of EN 16931 and XRechnung, with their levels, are those of KoSIT's validator
configuration: its scenario file names the stylesheets for each profile and lowers or raises the
levels of some rules. The Factur-X profiles have FeRD's Schematron, compiled with SchXslt.
"""

import re
from dataclasses import dataclass
from functools import cache
from xml.etree.ElementTree import Element

from haflinger import _saxon, _xsd
from haflinger._input import Document, Opened, open_invoice
from haflinger._xml import MAX_SIZE, XML_WHITESPACE, parse
from haflinger.errors import InvoiceReadError
from haflinger.findings import Finding, Flag

_CONFIGURATION = "kosit-validator-xrechnung"
_SCENARIOS_NAMESPACE = "{http://www.xoev.de/de/validator/framework/1/scenarios}"
_SVRL = "{http://purl.oclc.org/dsdl/svrl}"

_EN16931 = "urn:cen.eu:en16931:2017"
_XRECHNUNG = f"{_EN16931}#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
_EXTENSION = f"{_XRECHNUNG}#conformant#urn:xeinkauf.de:kosit:extension:xrechnung_3.0"
_CVD = f"{_XRECHNUNG}#compliant#urn:xeinkauf.de:kosit:xrechnung:cvd_0.9"

# REQ-002-PRS-F003: KoSIT's scenario for each document and BT-24. KoSIT has no scenario for the
# extension in a UBL credit note.
_RULE_SETS: dict[tuple[Document, str], str] = {
    ("cii", _EN16931): "EN16931 (CII)",
    ("cii", _XRECHNUNG): "EN16931 XRechnung (CII)",
    ("cii", _EXTENSION): "EN16931 XRechnung Extension (CII)",
    ("cii", _CVD): "EN16931 XRechnung CVD (CII)",
    ("ubl-invoice", _EN16931): "EN16931 (UBL Invoice)",
    ("ubl-invoice", _XRECHNUNG): "EN16931 XRechnung (UBL Invoice)",
    ("ubl-invoice", _EXTENSION): "EN16931 XRechnung Extension (UBL Invoice)",
    ("ubl-invoice", _CVD): "EN16931 XRechnung CVD (UBL Invoice)",
    ("ubl-credit-note", _EN16931): "EN16931 (UBL CreditNote)",
    ("ubl-credit-note", _XRECHNUNG): "EN16931 XRechnung (UBL CreditNote)",
    ("ubl-credit-note", _CVD): "EN16931 XRechnung CVD (UBL CreditNote)",
}
# REQ-002-PRS-F003: the Factur-X profiles, in CII only, by each BT-24 that names them (the
# alternative spellings included), with FeRD's Schematron for the profile.
_FERD = "ferd-zugferd/Schema"
_FACTUR_X: dict[str, tuple[str, tuple[str, ...]]] = {
    "Factur-X MINIMUM": (
        f"{_FERD}/0_Factur-X_1.09.2_MINIMUM/FACTUR-X_MINIMUM.sch",
        ("urn:factur-x.eu:1p0:minimum", "urn:zugferd.de:2p0:minimum"),
    ),
    "Factur-X BASIC WL": (
        f"{_FERD}/1_Factur-X_1.09.2_BASICWL/FACTUR-X_BASIC-WL.sch",
        ("urn:factur-x.eu:1p0:basicwl", "urn:zugferd.de:2p0:basicwl"),
    ),
    "Factur-X BASIC": (
        f"{_FERD}/2_Factur-X_1.09.2_BASIC/FACTUR-X_BASIC.sch",
        (
            f"{_EN16931}#compliant#urn:factur-x.eu:1p0:basic",
            f"{_EN16931}#compliant#urn:zugferd.de:2p0:basic",
            f"{_EN16931}:compliant:factur-x.eu:1p0:basic",
        ),
    ),
    "Factur-X EXTENDED": (
        f"{_FERD}/4_Factur-X_1.09.2_EXTENDED/FACTUR-X_EXTENDED.sch",
        (
            f"{_EN16931}#conformant#urn:factur-x.eu:1p0:extended",
            f"{_EN16931}#conformant#urn:zugferd.de:2p0:extended",
            f"{_EN16931}:compliant:factur-x.eu:1p0:extended",
        ),
    ),
}
# REQ-002-PRS-F011: FeRD's XML Schema of each Factur-X profile.
_FACTUR_X_SCHEMAS = {
    "Factur-X MINIMUM": f"{_FERD}/0_Factur-X_1.09.2_MINIMUM/Factur-X_1.09.2_MINIMUM.xsd",
    "Factur-X BASIC WL": f"{_FERD}/1_Factur-X_1.09.2_BASICWL/Factur-X_1.09.2_BASICWL.xsd",
    "Factur-X BASIC": f"{_FERD}/2_Factur-X_1.09.2_BASIC/Factur-X_1.09.2_BASIC.xsd",
    "Factur-X EXTENDED": f"{_FERD}/4_Factur-X_1.09.2_EXTENDED/Factur-X_1.09.2_EXTENDED.xsd",
}
_RULE_SETS.update(
    {
        ("cii", specification_id): name
        for name, (_, spellings) in _FACTUR_X.items()
        for specification_id in spellings
    }
)
# The limits of an invoice that is validated (REQ-002-PRS-F001): empty elements, the digits of a
# number, the characters of a telephone number.
_MAX_EMPTY = 1000
_MAX_DIGITS = 1000
_MAX_TELEPHONE = 100
_NUMBER = re.compile(r"[+-]?[0-9]*\.?[0-9]*")
_TELEPHONES = frozenset(
    {
        "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}"
        "CompleteNumber",
        "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Telephone",
    }
)
_DOCUMENTS: dict[Document, str] = {
    "cii": "a CII invoice",
    "ubl-invoice": "a UBL invoice",
    "ubl-credit-note": "a UBL credit note",
}
_FLAGS: dict[str, Flag] = {
    "fatal": "fatal",
    "error": "error",
    "warning": "warning",
    "information": "information",
}


@dataclass(frozen=True, kw_only=True)
class _Scenario:
    schema: str  # the XML Schema checked first (REQ-002-PRS-F011)
    stylesheets: tuple[str, ...]
    levels: dict[str, Flag]  # KoSIT's level by rule ID, where it sets one


def validate(data: bytes, *, max_size: int = MAX_SIZE) -> list[Finding]:
    """Validate a CII invoice or a UBL invoice or credit note with the rule set its syntax and
    BT-24 call for. Raises `InvoiceReadError` for input that can't be read
    (REQ-002-PRS-F001)."""
    opened = open_invoice(
        data,
        max_size,
        pdf="the input is a PDF; validate the XML that haflinger.pdf.extract_xml gives",
    )
    _refuse_costly(opened)
    name, no_profile = rule_set(opened)
    findings = [] if no_profile is None else [no_profile]
    schema = _xsd.check(data, _scenarios()[name].schema)
    if schema:
        return [*findings, *schema]
    return [*findings, *_rules(data, name)]


def _refuse_costly(opened: Opened) -> None:
    """Refuse the shapes on which the rules would take minutes (REQ-002-PRS-F001): more than
    `_MAX_EMPTY` empty elements, each failing PEPPOL-EN16931-R008 and located by counting its
    preceding siblings; a number of more than `_MAX_DIGITS` digits, whose arithmetic grows with the
    square of its length; a telephone number of more than `_MAX_TELEPHONE` characters, which
    XRechnung's BR-DE-27 checks with a pattern growing with the square of the length."""
    empty = 0
    for element in opened.reading.root.element.iter():
        text = (element.text or "").strip(XML_WHITESPACE)
        if len(element) == 0 and not text:
            empty += 1
        elif element.tag in _TELEPHONES and len(text) > _MAX_TELEPHONE:
            raise InvoiceReadError(
                f"the invoice holds a telephone number of {len(text):,} characters, more than"
                f" {_MAX_TELEPHONE}; Haflinger doesn't run the official rules on it, which would"
                " take minutes"
            )
        elif len(text) > _MAX_DIGITS and _NUMBER.fullmatch(text):
            digits = sum(character.isdigit() for character in text)
            if digits > _MAX_DIGITS:
                raise InvoiceReadError(
                    f"the invoice holds a number of {digits:,} digits, more than {_MAX_DIGITS:,};"
                    " Haflinger doesn't run the official rules on it, which would take minutes"
                )
    if empty > _MAX_EMPTY:
        raise InvoiceReadError(
            f"the invoice holds {empty:,} empty elements, more than {_MAX_EMPTY:,}; Haflinger"
            " doesn't run the official rules on it, which would take minutes"
        )


def check_rules(data: bytes) -> list[Finding]:
    """Like `validate`, without the XML Schema check: for fragments that aren't whole invoices,
    as in CEN's per-rule unit tests."""
    opened = open_invoice(data, MAX_SIZE, pdf="the input is a PDF")
    name, no_profile = rule_set(opened)
    return [*([] if no_profile is None else [no_profile]), *_rules(data, name)]


def _rules(data: bytes, name: str) -> list[Finding]:
    scenario = _scenarios()[name]
    findings: list[Finding] = []
    for report in _saxon.transform(data, *scenario.stylesheets):
        findings.extend(_findings(parse(report), scenario.levels))
    return findings


def rule_set(opened: Opened) -> tuple[str, Finding | None]:
    """The name of KoSIT's scenario for the invoice (REQ-002-PRS-F003) and, where its profile has
    none, CEN's rules with the `HAFL-PROFILE` finding (REQ-002-PRS-F004)."""
    name = _RULE_SETS.get((opened.document, _as_written(opened)))
    if name is None:
        return _RULE_SETS[opened.document, _EN16931], _no_profile(opened)
    return name, None


def _as_written(opened: Opened) -> str:
    """BT-24 exactly as written, as KoSIT's scenarios match it (REQ-002-PRS-F003)."""
    return "" if opened.specification is None else opened.specification.element.text or ""


def _no_profile(opened: Opened) -> Finding:
    """`HAFL-PROFILE` (REQ-002-PRS-F004, REQ-002-PRS-F010)."""
    document = _DOCUMENTS[opened.document]
    if opened.specification is None:
        location = opened.reading.root.path
        text = f"BT-24 is missing, so {document} names no profile"
    else:
        location = opened.specification.path
        text = (
            f"BT-24 {_as_written(opened)!r} names no profile Haflinger has rules for in {document}"
        )
    return Finding(
        rule="HAFL-PROFILE",
        flag="warning",
        location=location,
        text=f"{text}; checked with CEN's EN 16931 rules only, not the profile's own rules",
    )


def _findings(report: Element, levels: dict[str, Flag]) -> list[Finding]:
    """The failed assertions and successful reports of an SVRL report. KoSIT's level replaces a
    rule's flag; a flag Haflinger doesn't know counts as `error`, so that it still makes the
    invoice invalid."""
    findings: list[Finding] = []
    for element in report.iter():
        if element.tag not in (f"{_SVRL}failed-assert", f"{_SVRL}successful-report"):
            continue
        rule = element.get("id", "")
        findings.append(
            Finding(
                rule=rule,
                flag=levels.get(rule) or _FLAGS.get(element.get("flag", ""), "error"),
                location=element.get("location", ""),
                text=" ".join("".join(element.itertext()).split()),
            )
        )
    return findings


@cache
def _scenarios() -> dict[str, _Scenario]:
    """The rule sets by name: KoSIT's scenarios with their XML Schema, stylesheets and levels, and
    the Factur-X profiles with FeRD's XML Schema and Schematron."""
    n = _SCENARIOS_NAMESPACE
    root = parse((_saxon.ARTEFACTS / _CONFIGURATION / "scenarios.xml").read_bytes())
    factur_x = {
        name: _Scenario(schema=_FACTUR_X_SCHEMAS[name], stylesheets=(schematron,), levels={})
        for name, (schematron, _) in _FACTUR_X.items()
    }
    return factur_x | {
        scenario.findtext(f"{n}name", ""): _Scenario(
            schema=f"{_CONFIGURATION}/"
            + scenario.findtext(f"{n}validateWithXmlSchema/{n}resource/{n}location", ""),
            stylesheets=tuple(
                f"{_CONFIGURATION}/{location.text}"
                for location in scenario.findall(
                    f"{n}validateWithSchematron/{n}resource/{n}location"
                )
            ),
            levels={
                rule: _FLAGS[level.get("level", "")]
                for level in scenario.iter(f"{n}customLevel")
                for rule in (level.text or "").split()
            },
        )
        for scenario in root.findall(f"{n}scenario")
    }

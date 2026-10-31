"""Validation with the official rules, run unchanged with Saxon (REQ-002, ADR-006).

The rule sets and their levels are those of KoSIT's validator configuration: its scenario file
names the stylesheets for each profile and lowers or raises the levels of some rules.
"""

from dataclasses import dataclass
from functools import cache
from xml.etree.ElementTree import Element

from haflinger import _saxon
from haflinger._input import Document, Opened, open_invoice
from haflinger._xml import MAX_SIZE, parse
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
    findings: list[Finding] = []
    name = _RULE_SETS.get((opened.document, opened.specification_id or ""))
    if name is None:
        name = _RULE_SETS[opened.document, _EN16931]
        findings.append(_no_profile(opened))
    scenario = _scenarios()[name]
    for report in _saxon.transform(data, *scenario.stylesheets):
        findings.extend(_findings(parse(report), scenario.levels))
    return findings


def _no_profile(opened: Opened) -> Finding:
    """`HAFL-PROFILE` (REQ-002-PRS-F004, REQ-002-PRS-F010)."""
    document = _DOCUMENTS[opened.document]
    if opened.specification is None:
        location = opened.reading.root.path
        text = f"BT-24 is missing, so {document} names no profile"
    else:
        location = opened.specification.path
        text = (
            f"BT-24 {opened.specification_id!r} names no profile Haflinger has rules for in"
            f" {document}"
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
    """KoSIT's scenarios by name: their stylesheets and levels."""
    n = _SCENARIOS_NAMESPACE
    root = parse((_saxon.ARTEFACTS / _CONFIGURATION / "scenarios.xml").read_bytes())
    return {
        scenario.findtext(f"{n}name", ""): _Scenario(
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

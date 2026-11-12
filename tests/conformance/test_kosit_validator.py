"""KoSIT's validator, the official tool, over the KoSIT suite and the invoices the round trip
writes from it, as XRechnung and as EN 16931, and over invoices that fail: copies of the suite's
files with one error each, and the ZUGFeRD corpus's broken invoices. It gives the same verdict and
the same findings as `validate`, and accepts every invoice `write_cii` hands out
(REQ-002-PRS-F007, REQ-004-PRS-F005). It is Java, so it runs where HAFLINGER_KOSIT_VALIDATOR
names it, as in CI (`scripts/kosit-validator.sh`)."""

import os
import re
import subprocess
from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from defusedxml.ElementTree import parse
from test_write_kosit import EN16931, FILES, ROOT, XRECHNUNG, write

from haflinger import InvoiceReadError, is_valid, read_invoice, validate
from haflinger.pdf import extract_xml

VALIDATOR = os.environ.get("HAFLINGER_KOSIT_VALIDATOR")
REPORT = "{http://www.xoev.de/de/validator/varl/1}"
SCENARIOS = "{http://www.xoev.de/de/validator/framework/1/scenarios}"
FAIL = ROOT / "tests/data/zugferd-corpus/ZUGFeRDv2/fail"

type Findings = list[tuple[str, str, str]]

# The written documents' names, by target profile.
PROFILES = {"written": XRECHNUNG, "written-en16931": EN16931}

# One error each, made in a copy of every file of the suite: the first match of the UBL pattern
# or the CII one, replaced. Each must fail; which rules it fails is KoSIT's verdict.
BREAKS = {
    "amount-due": (
        (rb"(<cbc:PayableAmount\b[^>]*>)[^<]*", rb"\g<1>999999.99"),
        (rb"(<ram:DuePayableAmount\b[^>]*>)[^<]*", rb"\g<1>999999.99"),
    ),
    "type-code": (
        (rb"(<cbc:(?:Invoice|CreditNote)TypeCode\b[^>]*>)[^<]*", rb"\g<1>999"),
        (rb"(<rsm:ExchangedDocument>.*?<ram:TypeCode>)[^<]*", rb"\g<1>999"),
    ),
    "vat-category": (
        (rb"(<cac:TaxSubtotal>.*?<cac:TaxCategory>\s*<cbc:ID\b[^>]*>)[^<]*", rb"\g<1>Q"),
        (
            rb"(<ram:ApplicableHeaderTradeSettlement>.*?<ram:ApplicableTradeTax>.*?"
            rb"<ram:CategoryCode>)[^<]*",
            rb"\g<1>Q",
        ),
    ),
    "buyer-reference": (
        (rb"\s*<cbc:BuyerReference>[^<]*</cbc:BuyerReference>", b""),
        (rb"\s*<ram:BuyerReference>[^<]*</ram:BuyerReference>", b""),
    ),
    "decimals": (
        (rb"(<cbc:TaxExclusiveAmount\b[^>]*>)[^<]*", rb"\g<1>0.001"),
        (rb"(<ram:TaxBasisTotalAmount\b[^>]*>)[^<]*", rb"\g<1>0.001"),
    ),
    "schema": (
        (rb"<cbc:IssueDate>", b"<cbc:Unknown>x</cbc:Unknown><cbc:IssueDate>"),
        (rb"<ram:IssueDateTime>", b"<ram:Unknown>x</ram:Unknown><ram:IssueDateTime>"),
    ),
}


def kosit_has_rules_for(path: Path) -> bool:
    """Whether the PDF's invoice reads, and follows EN 16931 or XRechnung, for which KoSIT's
    configuration has rules; not the other Factur-X profiles."""
    try:
        invoice = read_invoice(path.read_bytes()).invoice
    except InvoiceReadError:
        return False
    return invoice.specification_id in (EN16931, XRECHNUNG)


# The broken invoices of the corpus selection that KoSIT's validator has rules for.
BROKEN = [path for path in sorted(FAIL.rglob("*.pdf")) if kosit_has_rules_for(path)]


def documents(path: Path) -> dict[str, bytes]:
    """The suite's file as received and the documents the round trip writes from it."""
    written = {
        f"{path.stem}-{name}.xml": write(path, profile)[1] for name, profile in PROFILES.items()
    }
    return {f"{path.stem}.xml": path.read_bytes(), **written}


def broken(path: Path) -> dict[str, bytes]:
    """A copy of the suite's file for each break, otherwise byte for byte."""
    data, copies = path.read_bytes(), dict[str, bytes]()
    for name, syntaxes in BREAKS.items():
        pattern, replacement = syntaxes[path.stem.endswith("uncefact")]
        copy, count = re.subn(pattern, replacement, data, count=1, flags=re.DOTALL)
        assert count == 1, (name, path.name)
        copies[f"{path.stem}-{name}.xml"] = copy
    return copies


def received(path: Path) -> dict[str, bytes]:
    """The corpus's invoice, taken out of its PDF."""
    return {f"{path.stem}.xml": extract_xml(path.read_bytes())}


def needs_validator() -> str:
    """Skips before any document is made, where no validator is named."""
    if not VALIDATOR:
        pytest.skip("HAFLINGER_KOSIT_VALIDATOR names no KoSIT validator")
    return VALIDATOR


def run(directory: Path, every: dict[str, bytes]) -> dict[str, Element]:
    """KoSIT's report on each document, from one call: Java starts once."""
    invoices, reports = directory / "invoices", directory / "reports"
    invoices.mkdir()
    reports.mkdir()
    for name, document in every.items():
        (invoices / name).write_bytes(document)
    command = [needs_validator(), str(invoices), str(reports)]
    # Its exit status counts the rejected documents, so a report per document shows it ran; 137
    # is the kernel's kill, when it ran out of memory.
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=240)  # noqa: S603
    found = {path.name.removesuffix("-report.xml") + ".xml": path for path in reports.iterdir()}
    assert sorted(found) == sorted(every), (
        f"exit {result.returncode}\n{result.stdout}{result.stderr}"
    )
    return {name: root(path) for name, path in found.items()}


@pytest.fixture(scope="module")
def reports(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Element]:
    needs_validator()
    every = {name: document for path in FILES for name, document in documents(path).items()}
    # Named by file name alone: two files of one name in different folders would clash.
    assert len(every) == (1 + len(PROFILES)) * len(FILES)
    return run(tmp_path_factory.mktemp("kosit"), every)


@pytest.fixture(scope="module")
def failing(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Element]:
    """A call of its own, as the validator's memory grows with each document."""
    needs_validator()
    every = {name: document for path in FILES for name, document in broken(path).items()}
    every |= {name: document for path in BROKEN for name, document in received(path).items()}
    assert len(every) == len(BREAKS) * len(FILES) + len(BROKEN)
    return run(tmp_path_factory.mktemp("kosit-failing"), every)


def root(path: Path) -> Element:
    element = parse(path).getroot()
    assert element is not None, path
    return element


def kosit(report: Element) -> Findings:
    """KoSIT's findings, each with its level after the scenario's levels (REQ-002-PRS-F005).

    The report's messages keep the stylesheets' own levels, and only KoSIT's assessment applies
    the scenario's, so here they are applied from the scenario the report embeds, as Haflinger
    applies them; KoSIT's verdict, compared beside, follows from its own."""
    levels = {
        code: level.get("level", "")
        for level in report.iter(f"{SCENARIOS}customLevel")
        for code in (level.text or "").split()
    }
    return sorted(
        (code, levels.get(code, message.get("level", "")), message.get("xpathLocation", ""))
        for message in report.iter(f"{REPORT}message")
        if (code := message.get("code", ""))
    )


def accepted(report: Element) -> bool:
    return report.find(f"{REPORT}assessment/{REPORT}accept") is not None


def steps(report: Element) -> dict[str, bool]:
    """Each step of KoSIT's validation, `val-xsd` the XML Schema and `val-sch.*` the rules, and
    whether it passed."""
    return {
        step.get("id", ""): step.get("valid") == "true"
        for step in report.iter(f"{REPORT}validationStepResult")
    }


def assert_same(name: str, document: bytes, report: Element) -> None:
    findings = validate(document)
    if "HAFL-XSD" in {finding.rule for finding in findings}:
        # Both stop at the XML Schema, whose errors their parsers word and count differently.
        assert {finding.rule for finding in findings} == {"HAFL-XSD"}, name
        assert steps(report).get("val-xsd") is False, name
        assert not [step for step in steps(report) if step.startswith("val-sch")], name
        assert (accepted(report), is_valid(findings)) == (False, False), name
        return
    # KoSIT's reports know no `fatal`: CEN's fatal rules show as `error`.
    ours = sorted(
        (finding.rule, "error" if finding.flag == "fatal" else finding.flag, finding.location)
        for finding in findings
    )
    assert (kosit(report), accepted(report)) == (ours, is_valid(findings)), name


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_kosit_finds_what_validate_finds(reports: dict[str, Element], path: Path) -> None:
    for name, document in documents(path).items():
        assert_same(name, document, reports[name])


def test_kosit_accepts_every_invoice_write_cii_hands_out(reports: dict[str, Element]) -> None:
    """Those it refuses fail rules the round trip lists (REQ-004-PRS-F005). The comparison above
    implies it; it stays as REQ-004-PRS-F005's own test."""
    handed_out = [
        f"{path.stem}-{name}.xml"
        for path in FILES
        for name, profile in PROFILES.items()
        if not write(path, profile)[2]
    ]
    assert len(handed_out) > len(FILES)
    assert [name for name in handed_out if not accepted(reports[name])] == []


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_every_broken_copy_fails(path: Path) -> None:
    """Without KoSIT's validator too: each break applies, and makes the copy fail."""
    assert [name for name, copy in broken(path).items() if is_valid(validate(copy))] == []


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_kosit_finds_what_validate_finds_in_broken_copies(
    failing: dict[str, Element], path: Path
) -> None:
    for name, document in broken(path).items():
        assert_same(name, document, failing[name])


def test_the_corpuss_broken_invoices_are_there() -> None:
    """FNFE-MPE's five of EN 16931, FeRD's ZUGFeRD 2.0 sample and Mustang's 507a and 507b."""
    assert len(BROKEN) == 8


@pytest.mark.parametrize("path", BROKEN, ids=lambda path: path.name)
def test_kosit_finds_what_validate_finds_in_the_corpuss_broken_invoices(
    failing: dict[str, Element], path: Path
) -> None:
    for name, document in received(path).items():
        assert_same(name, document, failing[name])
        assert not accepted(failing[name]), name

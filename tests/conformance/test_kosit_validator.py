"""KoSIT's validator, the official tool, over the KoSIT suite and the invoices the round trip
writes from it, as XRechnung and as EN 16931, and over invoices that fail: copies of the suite's
files with one error each, and the ZUGFeRD corpus's broken invoices. It gives the same verdict and
the same findings as `validate`, and accepts every invoice `write_cii` hands out
(REQ-002-PRS-F007, REQ-004-PRS-F005). Over copies whose BT-24 is split or given twice, it
chooses the scenario `validate` chooses (REQ-002-PRS-F003). It is Java, so it runs where
HAFLINGER_KOSIT_VALIDATOR names it, as in CI (`scripts/kosit-validator.sh`). Over UBL copies
with an extension at Saxon's limits in `validate`, it finds what `validate` finds within them,
rejects the copy beyond the limit of attributes, as `validate` does, and accepts the copy beyond
the XML Schema check's depth, which `validate` stops at (REQ-002-PRS-F011)."""

import os
import re
import subprocess
from collections.abc import Callable
from functools import cache
from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from defusedxml.ElementTree import parse
from test_write_kosit import EN16931, FILES, ROOT, XRECHNUNG, write

from haflinger import InvoiceReadError, is_valid, read_invoice, validate
from haflinger._input import open_invoice
from haflinger._xml import MAX_SIZE, decode
from haflinger.pdf import extract_xml

VALIDATOR = os.environ.get("HAFLINGER_KOSIT_VALIDATOR")
REPORT = "{http://www.xoev.de/de/validator/varl/1}"
SCENARIOS = "{http://www.xoev.de/de/validator/framework/1/scenarios}"
FAIL = ROOT / "tests/data/zugferd-corpus/ZUGFeRDv2/fail"
CREDIT_NOTE = ROOT / "tests/data/cen-en16931/ubl/examples/ubl-tc434-creditnote1.xml"

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

# BT-24 written with a comment, a processing instruction or CDATA, in the copies of SPLIT_FROM
# (REQ-002-PRS-F003); in each syntax, also with an element inside and a second BT-24.
REST = XRECHNUNG.removeprefix(EN16931)
SPLITS = {
    "comment-at-the-start": f"<!--x-->{XRECHNUNG}",
    "comment-at-the-end": f"{XRECHNUNG}<!--x-->",
    "comment-in-the-middle": f"{EN16931}<!--x-->{REST}",
    "instruction-in-the-middle": f"{EN16931}<?x y?>{REST}",
    "cdata": f"{EN16931}<![CDATA[{REST}]]>",
    "two-profiles": f"{EN16931}<!--x-->{XRECHNUNG}",
    "no-profile": "urn:cen.eu:<!--x-->en16931:2017",
}
CII_SECOND = (
    "</ram:ID></ram:GuidelineSpecifiedDocumentContextParameter>"
    "<ram:GuidelineSpecifiedDocumentContextParameter><ram:ID>"
)
UBL_SECOND = "</cbc:CustomizationID><cbc:CustomizationID>"
UBL_OWN = {
    "element-in-the-middle": f"{EN16931}<cbc:X/>{REST}",
    "second-bt-24": f"{XRECHNUNG}{UBL_SECOND}{EN16931}",
}
SPLIT_FROM: dict[str, tuple[Path, str, dict[str, str]]] = {
    "cii": (
        ROOT / "tests/data/kosit-testsuite/instances/standard/01.01a-INVOICE_uncefact.xml",
        XRECHNUNG,
        {
            "element-in-the-middle": f"{EN16931}<ram:X/>{REST}",
            "second-bt-24-of-a-profile": f"urn:example{CII_SECOND}{EN16931}",
            "second-bt-24-of-another-profile": f"{XRECHNUNG}{CII_SECOND}{EN16931}",
            "second-bt-24-of-the-same-profile": f"{XRECHNUNG}{CII_SECOND}{XRECHNUNG}",
            "xrechnung-and-factur-x": f"{XRECHNUNG}<!--x-->urn:factur-x.eu:1p0:minimum",
        },
    ),
    "ubl": (
        ROOT / "tests/data/kosit-testsuite/instances/standard/01.01a-INVOICE_ubl.xml",
        XRECHNUNG,
        UBL_OWN,
    ),
    "credit-note": (CREDIT_NOTE, EN16931, UBL_OWN),
}

# The extensions at Saxon's limits in `validate` (REQ-002-PRS-F011): the deepest level libxml2
# parses, and so the XML Schema check, and Java's limit of attributes; and one beyond each.
AT_THE_LIMITS = {"nested-2048": {"levels": 2048}, "attributes-10000": {"attributes": 10_000}}
BEYOND = {"nested-2049": {"levels": 2049}, "attributes-10001": {"attributes": 10_001}}


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


@cache
def split() -> dict[str, bytes]:
    """The copies of SPLIT_FROM with each BT-24 of SPLITS and of their own."""
    copies = dict[str, bytes]()
    for syntax, (path, written, own) in SPLIT_FROM.items():
        data = path.read_bytes()
        assert data.count(f">{written}<".encode()) == 1, path
        for name, new in (SPLITS | own).items():
            copies[f"{syntax}-{name}.xml"] = data.replace(
                f">{written}<".encode(), f">{new}<".encode()
            )
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


@pytest.fixture(scope="module")
def extensions(extended: Callable[..., bytes]) -> dict[str, bytes]:
    """KoSIT's 01.01a UBL file with each extension of AT_THE_LIMITS and BEYOND."""
    return {f"{name}.xml": extended(**shape) for name, shape in (AT_THE_LIMITS | BEYOND).items()}


@pytest.fixture(scope="module")
def copies(
    tmp_path_factory: pytest.TempPathFactory, extensions: dict[str, bytes]
) -> dict[str, Element]:
    """The split copies and the extensions, in one call: Java starts once."""
    needs_validator()
    return run(tmp_path_factory.mktemp("kosit-copies"), split() | extensions)


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


def scenario(report: Element) -> str | None:
    """The name of the scenario KoSIT's validator chose, `None` where it chose none."""
    return report.findtext(f"{REPORT}scenarioMatched/{SCENARIOS}scenario/{SCENARIOS}name")


def chosen(document: bytes) -> str | None:
    """The rule set `validate` chooses, `None` where it names no profile (`HAFL-PROFILE`)."""
    from haflinger._validation import rule_set
    from haflinger._xsd import tree

    opened = open_invoice(document, MAX_SIZE, pdf="the input is a PDF")
    name, no_profile = rule_set(opened, tree(decode(document)))
    return None if no_profile else name


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


def test_the_split_copies_are_there() -> None:
    assert len(split()) == 3 * len(SPLITS) + 9


@pytest.mark.parametrize("name", sorted(split()))
def test_kosit_chooses_the_scenario_validate_chooses_for_bt_24_in_pieces(
    copies: dict[str, Element], name: str
) -> None:
    """Some match a scenario, some none, some more than one, which KoSIT's validator counts as
    none (REQ-002-PRS-F003, REQ-002-PRS-F004); KoSIT's has no Factur-X scenario."""
    assert scenario(copies[name]) == chosen(split()[name])


@pytest.mark.parametrize("name", AT_THE_LIMITS)
def test_kosit_finds_what_validate_finds_in_extensions_at_saxons_limits(
    copies: dict[str, Element], extensions: dict[str, bytes], name: str
) -> None:
    """Beyond SaxonC's own limits, 100 levels and 200 attributes (REQ-002-PRS-F011)."""
    assert_same(name, extensions[f"{name}.xml"], copies[f"{name}.xml"])


def test_kosit_rejects_what_validate_rejects_beyond_the_limit_of_attributes(
    copies: dict[str, Element], extensions: dict[str, bytes]
) -> None:
    """Both parsers stop: `validate` with `HAFL-RULES`, KoSIT's validator with a processing
    error, before any scenario."""
    findings = validate(extensions["attributes-10001.xml"])
    assert [finding.rule for finding in findings] == ["HAFL-RULES"]
    report = copies["attributes-10001.xml"]
    assert (steps(report), scenario(report), accepted(report)) == ({"val-xml": False}, None, False)


def test_kosit_accepts_what_validate_stops_at_the_xml_schema_beyond_its_depth(
    copies: dict[str, Element], extensions: dict[str, bytes]
) -> None:
    """The known difference: libxml2 parses no deeper than 2,048 levels, KoSIT's parser does."""
    findings = validate(extensions["nested-2049.xml"])
    assert [finding.rule for finding in findings] == ["HAFL-XSD"]
    assert accepted(copies["nested-2049.xml"])

"""Validation with the official rules (REQ-002), on edited copies of official files."""

import re
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from xml.etree.ElementTree import Element, tostring

import defusedxml.ElementTree
import pytest
from lxml import etree

from haflinger import (
    Finding,
    Flag,
    InvoiceReadError,
    is_valid,
    read_invoice,
    validate,
)
from haflinger._input import open_invoice
from haflinger._validation import check_rules, rule_set
from haflinger._xml import MAX_SIZE, decode
from haflinger._xsd import Locations, check_cii, tree
from haflinger.pdf import extract_xml

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/data/kosit-testsuite/instances"
CII = SUITE / "standard/01.01a-INVOICE_uncefact.xml"
UBL = SUITE / "standard/01.01a-INVOICE_ubl.xml"
CREDIT_NOTE = ROOT / "tests/data/cen-en16931/ubl/examples/ubl-tc434-creditnote1.xml"
SCENARIOS = ROOT / "src/haflinger/artefacts/kosit-validator-xrechnung/scenarios.xml"

EN16931 = "urn:cen.eu:en16931:2017"
XRECHNUNG = f"{EN16931}#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
EXTENSION = f"{XRECHNUNG}#conformant#urn:xeinkauf.de:kosit:extension:xrechnung_3.0"
CVD = f"{XRECHNUNG}#compliant#urn:xeinkauf.de:kosit:xrechnung:cvd_0.9"
OTHER_EDITION = "urn:cen.eu:en16931:2026"
# What closes BT-24 and opens a second one.
SECOND_BT_24 = {
    CII: "</ram:ID></ram:GuidelineSpecifiedDocumentContextParameter>"
    "<ram:GuidelineSpecifiedDocumentContextParameter><ram:ID>",
    UBL: "</cbc:CustomizationID><cbc:CustomizationID>",
}
# Prefixed, as `xpath` spells them in the form findings give.
CII_BT_24 = "/rsm:CrossIndustryInvoice/rsm:ExchangedDocumentContext/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID"  # noqa: E501

# The edits, in each syntax of KoSIT case 01.01a.
WRONG_TOTAL = {
    CII: ("<ram:GrandTotalAmount>336.9<", "<ram:GrandTotalAmount>336.91<"),
    UBL: (
        '<cbc:TaxInclusiveAmount currencyID="EUR">336.9<',
        '<cbc:TaxInclusiveAmount currencyID="EUR">336.91<',
    ),
}
NO_BUYER_REFERENCE = {
    CII: ("<ram:BuyerReference>04011000-12345-03</ram:BuyerReference>", ""),
    UBL: ("<cbc:BuyerReference>04011000-12345-03</cbc:BuyerReference>", ""),
}
NO_SPECIFICATION_ID = {
    CII: ("<ram:ID>" + XRECHNUNG + "</ram:ID>", ""),
    UBL: ("<cbc:CustomizationID>" + XRECHNUNG + "</cbc:CustomizationID>", ""),
}


def edited(path: Path, *edits: tuple[str, str]) -> bytes:
    text = path.read_text(encoding="utf-8")
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text.encode()


def with_specification_id(path: Path, specification_id: str, *edits: tuple[str, str]) -> bytes:
    """A copy with BT-24 changed from XRechnung 3.0 to `specification_id`."""
    return edited(path, (f">{XRECHNUNG}<", f">{specification_id}<"), *edits)


def rules(findings: Sequence[Finding]) -> set[tuple[str, str]]:
    return {(finding.rule, finding.flag) for finding in findings}


def invalid(findings: Sequence[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.flag in ("fatal", "error")]


PROFILE_END = "; checked with CEN's EN 16931 rules only, not the profile's own rules"


def profile_findings(findings: Sequence[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.rule == "HAFL-PROFILE"]


def xrechnung_rules(findings: Sequence[Finding]) -> set[str]:
    return {finding.rule for finding in findings if finding.rule.startswith("BR-DE-")}


# REQ-002-PRS-F001


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
def test_validates_cii_and_ubl(path: Path) -> None:
    findings = validate(path.read_bytes())
    assert isinstance(findings, tuple)
    assert invalid(findings) == []
    assert is_valid(findings)


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"<Invoice>", "not well-formed"),
        (b"%PDF-1.7\n", "validate the XML that haflinger.pdf.extract_xml gives"),
        (b'<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>', "document type declaration"),
        (b"<Order/>", "neither a CII invoice nor a UBL invoice"),
        (with_specification_id(CII, OTHER_EDITION), "EN 16931-1:2026"),
        (with_specification_id(UBL, OTHER_EDITION), "EN 16931-1:2026"),
        (with_specification_id(CII, f"{XRECHNUNG}{SECOND_BT_24[CII]}{OTHER_EDITION}"), "2026"),
        (with_specification_id(UBL, f"{XRECHNUNG}{SECOND_BT_24[UBL]}{OTHER_EDITION}"), "2026"),
        (with_specification_id(CII, f"{OTHER_EDITION}<ram:X/>"), "2026"),
        (with_specification_id(UBL, f"{OTHER_EDITION}<cbc:X/>"), "2026"),
        (with_specification_id(CII, "urn:cen.eu:en16931:<ram:X>2026</ram:X>"), "2026"),
        (with_specification_id(CII, f"{XRECHNUNG}<!--x-->{OTHER_EDITION}"), "2026"),
        (with_specification_id(UBL, f"{XRECHNUNG}<!--x-->{OTHER_EDITION}"), "2026"),
    ],
    ids=[
        "not-xml",
        "pdf",
        "dtd",
        "other-root",
        "2026-cii",
        "2026-ubl",
        "2026-second-cii",
        "2026-second-ubl",
        "2026-before-an-element-cii",
        "2026-before-an-element-ubl",
        "2026-within-an-element-cii",
        "2026-after-a-comment-cii",
        "2026-after-a-comment-ubl",
    ],
)
def test_refusals(data: bytes, reason: str) -> None:
    """REQ-002-PRS-F001 and, for 2026, REQ-002-PRS-F009: in any BT-24, anywhere in its whole
    text, also where reading leaves it out."""
    with pytest.raises(InvoiceReadError, match=re.escape(reason)):
        validate(data)


def test_refuses_more_than_max_size() -> None:
    with pytest.raises(InvoiceReadError, match="larger than max_size"):
        validate(CII.read_bytes(), max_size=1000)


# REQ-002-PRS-F002


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
def test_a_total_one_cent_off_fails_br_co_15_and_br_co_16(path: Path) -> None:
    findings = validate(edited(path, WRONG_TOTAL[path]))
    failed = {finding.rule: finding for finding in invalid(findings)}
    assert set(failed) == {"BR-CO-15", "BR-CO-16"}
    for rule, finding in failed.items():
        assert finding.flag == "fatal"
        assert finding.location.startswith("/")
        assert finding.text.startswith(f"[{rule}]")
    assert not is_valid(findings)


def finding(flag: Flag) -> Finding:
    return Finding(rule="BR-01", flag=flag, location="/", text="[BR-01] A rule.")


@pytest.mark.parametrize(
    ("flags", "valid"),
    [
        ((), True),
        (("warning", "information"), True),
        (("warning", "fatal"), False),
        (("information", "error"), False),
    ],
)
def test_is_valid_applies_the_rule(flags: tuple[Flag, ...], valid: bool) -> None:
    findings = [finding(flag) for flag in flags]
    assert is_valid(tuple(findings)) is valid
    assert is_valid(findings) is valid
    assert is_valid(finding for finding in findings) is valid


# REQ-002-PRS-F003: each row's rule set ran.


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
def test_xrechnung_runs_kosits_rules(path: Path) -> None:
    findings = validate(edited(path, NO_BUYER_REFERENCE[path]))
    assert ("BR-DE-15", "fatal") in rules(findings)
    assert profile_findings(findings) == []


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
def test_en16931_runs_cens_rules_only(path: Path) -> None:
    data = with_specification_id(path, EN16931, NO_BUYER_REFERENCE[path], WRONG_TOTAL[path])
    findings = validate(data)
    assert ("BR-CO-15", "fatal") in rules(findings)
    assert xrechnung_rules(findings) == set()
    assert profile_findings(findings) == []


def test_en16931_credit_note() -> None:
    assert validate(CREDIT_NOTE.read_bytes()) == ()


@pytest.mark.parametrize(
    ("path", "finding"),
    [
        (SUITE / "extension/04.05a-INVOICE_uncefact.xml", ("BR-CL-10", "information")),
        (SUITE / "extension/05.01a-INVOICE_ubl.xml", ("BR-CO-16", "information")),
    ],
    ids=["cii", "ubl"],
)
def test_the_extension_runs_its_scenario(path: Path, finding: tuple[str, str]) -> None:
    """The scenario of the extension lowers these rules to `information`."""
    findings = validate(path.read_bytes())
    assert finding in rules(findings)
    assert profile_findings(findings) == []


@pytest.mark.parametrize(
    "path",
    [
        SUITE / "technical-cases/cvd/02.01a-cvd_INVOICE_uncefact.xml",
        SUITE / "technical-cases/cvd/02.01a-cvd_INVOICE_ubl.xml",
    ],
    ids=["cii", "ubl"],
)
def test_cvd_runs_its_scenario(path: Path) -> None:
    """The scenario of CVD lowers BR-CL-13 to `information`."""
    findings = validate(path.read_bytes())
    assert ("BR-CL-13", "information") in rules(findings)
    assert invalid(findings) == []


# A rule of FeRD's for each Factur-X profile that a type code outside its code list fails.
WRONG_TYPE_CODE = ("<ram:TypeCode>380<", "<ram:TypeCode>999<")
FACTUR_X = [
    ("urn:factur-x.eu:1p0:minimum", "FX-SCH-A-000023"),
    ("urn:zugferd.de:2p0:minimum", "FX-SCH-A-000023"),
    ("urn:factur-x.eu:1p0:basicwl", "FX-SCH-A-000417"),
    ("urn:zugferd.de:2p0:basicwl", "FX-SCH-A-000417"),
    (f"{EN16931}#compliant#urn:factur-x.eu:1p0:basic", "FX-SCH-A-000492"),
    (f"{EN16931}#compliant#urn:zugferd.de:2p0:basic", "FX-SCH-A-000492"),
    (f"{EN16931}:compliant:factur-x.eu:1p0:basic", "FX-SCH-A-000492"),
    (f"{EN16931}#conformant#urn:factur-x.eu:1p0:extended", "FX-SCH-A-000635"),
    (f"{EN16931}#conformant#urn:zugferd.de:2p0:extended", "FX-SCH-A-000635"),
    (f"{EN16931}:compliant:factur-x.eu:1p0:extended", "FX-SCH-A-000635"),
]


@pytest.mark.parametrize(("specification_id", "rule"), FACTUR_X)
def test_factur_x_runs_ferds_rules_for_its_profile(
    specification_id: str, rule: str, factur_x: Callable[..., bytes]
) -> None:
    """Each spelling of REQ-002-PRS-F003's Factur-X rows runs FeRD's rules for its profile."""
    findings = validate(factur_x(specification_id, WRONG_TYPE_CODE))
    assert (rule, "error") in rules(findings)
    assert profile_findings(findings) == []
    assert xrechnung_rules(findings) == set()


def test_a_factur_x_bt_24_is_compared_by_each_piece(factur_x: Callable[..., bytes]) -> None:
    """As KoSIT's scenarios compare CII's (REQ-002-PRS-F003): a comment beside the identifier
    leaves it naming its profile, one inside it names none."""
    minimum = "urn:factur-x.eu:1p0:minimum"
    beside = validate(factur_x(minimum, WRONG_TYPE_CODE, (f">{minimum}<", f">{minimum}<!--x--><")))
    assert ("FX-SCH-A-000023", "error") in rules(beside)
    assert profile_findings(beside) == []
    inside = validate(factur_x(minimum, (f">{minimum}<", ">urn:factur-x.eu:<!--x-->1p0:minimum<")))
    assert [finding.text.removesuffix(PROFILE_END) for finding in profile_findings(inside)] == [
        "BT-24 'urn:factur-x.eu:1p0:minimum', in pieces 'urn:factur-x.eu:' and '1p0:minimum',"
        " names no profile Haflinger has rules for in a CII invoice"
    ]


@pytest.mark.parametrize(
    ("specification_id", "rule"),
    [
        (f"{EN16931}:compliant:factur-x.eu:1p0:basic", "FX-SCH-A-000493"),
        (f"{EN16931}:compliant:factur-x.eu:1p0:extended", "FX-SCH-A-000636"),
    ],
)
def test_ferds_rules_judge_a_colon_spelling(
    specification_id: str, rule: str, factur_x: Callable[..., bytes]
) -> None:
    """The colon spellings select their profile's rules, whose code list for BT-24 lacks them:
    the official verdict, reported as such."""
    findings = validate(factur_x(specification_id))
    assert (rule, "error") in rules(findings)


def test_an_official_extended_invoice_gets_the_extended_schema() -> None:
    """Mustang's EXTENDED PDF, filed as failing, fails FeRD's EXTENDED XML Schema."""
    pdf = ROOT / (
        "tests/data/zugferd-corpus/ZUGFeRDv2/fail/Mustangproject/"
        "MustangGnuaccountingBeispielRE-20171118_506.pdf"
    )
    findings = validate(extract_xml(pdf.read_bytes()))
    assert profile_findings(findings) == []
    assert findings
    assert all(f.rule == "HAFL-XSD" for f in findings)
    assert findings[0].text.startswith("Factur-X EXTENDED XML Schema: ")


def test_a_rule_without_an_id(factur_x: Callable[..., bytes]) -> None:
    """FeRD reports an element its profile doesn't use without a rule ID or flag: an `error`
    with an empty rule (REQ-002-PRS-F002). MINIMUM doesn't use the buyer's address."""
    findings = validate(factur_x("urn:factur-x.eu:1p0:minimum", buyer_country=True))
    unnamed = [finding for finding in findings if finding.rule == ""]
    assert unnamed
    assert all(finding.flag == "error" for finding in unnamed)
    assert any("is marked as not used in the given context" in f.text for f in unnamed)


def test_the_factur_x_spellings_are_those_of_the_spec() -> None:
    """The BT-24 values of REQ-002-PRS-F003's Factur-X rows, alternative spellings included."""
    from haflinger._validation import _FACTUR_X  # pyright: ignore[reportPrivateUsage]

    table = (ROOT / "docs/specs/req-002-conformance.md").read_text(encoding="utf-8")
    rows = [line for line in table.splitlines() if line.startswith("| Factur-X / ZUGFeRD ")]
    in_spec = {
        value
        for row in rows
        if "| CII |" in row and "The Factur-X rules" in row
        for value in re.findall(r"`([^`]+)`", row)
    }
    in_code = {value for _, spellings in _FACTUR_X.values() for value in spellings}
    assert in_spec == in_code


def scenario_matches() -> dict[str | None, str]:
    """KoSIT's match expression of each scenario, by the scenario's name."""
    namespace = "{http://www.xoev.de/de/validator/framework/1/scenarios}"
    return {
        scenario.findtext(f"{namespace}name"): scenario.findtext(f"{namespace}match") or ""
        for scenario in defusedxml.ElementTree.fromstring(SCENARIOS.read_bytes()).iter(
            f"{namespace}scenario"
        )
    }


def test_each_rule_set_is_kosits_scenario_for_its_document_and_bt_24() -> None:
    """The rule sets of REQ-002-PRS-F003 other than Factur-X's, by syntax and BT-24, are the
    scenarios whose match expressions name the same root element and BT-24; every scenario is
    used."""
    from haflinger._validation import _FACTUR_X, _RULE_SETS  # pyright: ignore[reportPrivateUsage]

    matches = scenario_matches()
    roots = {
        "cii": "/rsm:CrossIndustryInvoice",
        "ubl-invoice": "/invoice:Invoice",
        "ubl-credit-note": "/creditnote:CreditNote",
    }
    kosit = {key: name for key, name in _RULE_SETS.items() if name not in _FACTUR_X}
    for (document, specification_id), name in kosit.items():
        assert roots[document] in matches[name], name
        assert re.findall(r"'([^']*)'", matches[name]) == [specification_id], name
    assert set(kosit.values()) == set(matches)


def test_each_row_is_compared_as_its_scenario_compares_bt_24() -> None:
    """By BT-24's string value, `.`, or by each of its text nodes, `text()` (REQ-002-PRS-F003)."""
    from haflinger._validation import (
        _BY_WHOLE_TEXT,  # pyright: ignore[reportPrivateUsage]
        _FACTUR_X,  # pyright: ignore[reportPrivateUsage]
        _RULE_SETS,  # pyright: ignore[reportPrivateUsage]
    )

    matches = scenario_matches()
    whole = set[tuple[str, str]]()
    for key, name in _RULE_SETS.items():
        if name in _FACTUR_X:
            continue
        by_value = re.search(r"\[\s*\.\s*=", matches[name]) is not None
        assert by_value != ("/text() =" in matches[name]), name
        if by_value:
            whole.add(key)
    assert whole == _BY_WHOLE_TEXT
    assert len(whole) == 3


# REQ-002-PRS-F004, REQ-002-PRS-F010


@pytest.mark.parametrize(
    ("data", "location", "text"),
    [
        (
            with_specification_id(
                UBL, f"{EN16931}#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
            ),
            "/ubl:Invoice/cbc:CustomizationID",
            "BT-24 'urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0'"
            " names no profile Haflinger has rules for in a UBL invoice",
        ),
        (
            with_specification_id(
                CII, f"{EN16931}#compliant#urn:xoev-de:kosit:standard:xrechnung_2.1"
            ),
            CII_BT_24,
            "BT-24 'urn:cen.eu:en16931:2017#compliant#urn:xoev-de:kosit:standard:xrechnung_2.1'"
            " names no profile Haflinger has rules for in a CII invoice",
        ),
        (
            with_specification_id(UBL, f"{EN16931}#compliant#urn:factur-x.eu:1p0:basic"),
            "/ubl:Invoice/cbc:CustomizationID",
            "BT-24 'urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic' names no"
            " profile Haflinger has rules for in a UBL invoice",
        ),
        (
            edited(CREDIT_NOTE, (f">{EN16931}<", f">{EXTENSION}<")),
            "/cn:CreditNote/cbc:CustomizationID",
            f"BT-24 '{EXTENSION}' names no profile Haflinger has rules for in a UBL credit note",
        ),
        (
            edited(CII, NO_SPECIFICATION_ID[CII]),
            "/rsm:CrossIndustryInvoice",
            "BT-24 is missing, so a CII invoice names no profile",
        ),
        (
            edited(UBL, NO_SPECIFICATION_ID[UBL]),
            "/ubl:Invoice",
            "BT-24 is missing, so a UBL invoice names no profile",
        ),
    ],
    ids=[
        "peppol",
        "xrechnung-2.1",
        "ubl-factur-x",
        "credit-note-extension",
        "none-cii",
        "none-ubl",
    ],
)
def test_other_profiles_get_cens_rules_and_hafl_profile(
    data: bytes, location: str, text: str, xpath: Callable[[str], str]
) -> None:
    findings = validate(data)
    assert profile_findings(findings) == [
        Finding(
            rule="HAFL-PROFILE",
            flag="warning",
            location=xpath(location),
            text=f"{text}; checked with CEN's EN 16931 rules only, not the profile's own rules",
        )
    ]
    assert xrechnung_rules(findings) == set()


# REQ-002-PRS-F002: each location selects its element, with no prefixes declared; the location
# prefixed, as `xpath` spells it.
LOCATED = {
    "cii-rule": (
        edited(CII, WRONG_TOTAL[CII]),
        "BR-CO-16",
        "/rsm:CrossIndustryInvoice/rsm:SupplyChainTradeTransaction"
        "/ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementHeaderMonetarySummation",
    ),
    "ubl-rule": (
        edited(UBL, WRONG_TOTAL[UBL]),
        "BR-CO-16",
        "/ubl:Invoice/cac:LegalMonetaryTotal",
    ),
    "cii-profile": (
        with_specification_id(CII, f"{EN16931}#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"),
        "HAFL-PROFILE",
        CII_BT_24,
    ),
    "ubl-profile": (
        with_specification_id(UBL, f"{EN16931}#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"),
        "HAFL-PROFILE",
        "/ubl:Invoice/cbc:CustomizationID",
    ),
    "ubl-no-profile": (edited(UBL, NO_SPECIFICATION_ID[UBL]), "HAFL-PROFILE", "/ubl:Invoice"),
    "cii-schema": (
        edited(CII, ("<ram:IssueDateTime>", "<ram:Unknown/><ram:IssueDateTime>")),
        "HAFL-XSD",
        "/rsm:CrossIndustryInvoice/rsm:ExchangedDocument/ram:Unknown",
    ),
    "ubl-schema": (
        edited(UBL, ("<cbc:IssueDate>", "<cbc:Unknown/><cbc:IssueDate>")),
        "HAFL-XSD",
        "/ubl:Invoice/cbc:Unknown",
    ),
    # Its root's namespace is the default one, for which libxml2's path gives `*[n]`.
    "credit-note-schema": (
        edited(CREDIT_NOTE, ("<cbc:IssueDate>", "<Unknown/><Unknown/><cbc:IssueDate>")),
        "HAFL-XSD",
        "/cn:CreditNote/cn:Unknown",
    ),
    "cii-hafl-rules": (
        edited(
            CII,
            (
                "<ram:LineTotalAmount>314.86</ram:LineTotalAmount>",
                "<ram:LineTotalAmount>314.86</ram:LineTotalAmount>" * 2,
            ),
        ),
        "HAFL-RULES",
        "/rsm:CrossIndustryInvoice",
    ),
    "ubl-reading": (
        edited(
            UBL,
            (
                "<cbc:ID>Porto + Versandkosten</cbc:ID>",
                "<cbc:ID>Porto + Versandkosten</cbc:ID>"
                "<cbc:Note>a</cbc:Note><cbc:Note>b</cbc:Note>",
            ),
        ),
        "HAFL-DROPPED",
        "/ubl:Invoice/cac:InvoiceLine[2]/cbc:Note[2]",
    ),
}


@pytest.mark.parametrize("case", list(LOCATED), ids=list(LOCATED))
def test_every_location_selects_its_element(
    case: str, selects: Callable[[bytes, str], Element], xpath: Callable[[str], str]
) -> None:
    data, rule, location = LOCATED[case]
    findings = [*validate(data), *read_invoice(data).findings]
    for finding in findings:
        selects(data, finding.location)
    assert xpath(location) in {finding.location for finding in findings if finding.rule == rule}


def test_a_path_that_names_no_element_has_no_location(xpath: Callable[[str], str]) -> None:
    """The XML Schema check's finding then gives the line (REQ-002-PRS-F010)."""
    locations = Locations(etree.fromstring(CII.read_bytes()))
    assert locations.of("/rsm:CrossIndustryInvoice") == xpath("/rsm:CrossIndustryInvoice")
    for path in (None, "", "rsm:CrossIndustryInvoice", "/rsm:Other", "/rsm:CrossIndustryInvoice/x"):
        assert locations.of(path) is None, path


LONG = "n" * 120  # a name longer than libxml2's paths keep, with its prefix


@pytest.mark.parametrize(
    ("name", "tag"),
    [(LONG, f"{{urn:example}}{LONG}"), ("n" * 95 + "é" * 5, None)],
    ids=["long-name", "cut-within-a-character"],
)
def test_the_schema_check_locates_a_long_name_libxml2_cuts(
    name: str, tag: str | None, selects: Callable[[bytes, str], Element]
) -> None:
    """libxml2's path cuts a prefixed name to 98 bytes: the location is still the element's,
    or, where the cut splits a character, the line (REQ-002-PRS-F010)."""
    data = edited(
        CII, ("<ram:IssueDateTime>", f'<x:{name} xmlns:x="urn:example"/><ram:IssueDateTime>')
    )
    (finding,) = [finding for finding in validate(data) if finding.rule == "HAFL-XSD"]
    if tag is None:
        assert re.fullmatch("line [0-9]+", finding.location), finding.location
    else:
        assert selects(data, finding.location).tag == tag


def test_a_path_two_cut_names_share_has_no_location() -> None:
    """Two siblings whose names libxml2 cuts to the same text share its path, which names
    neither."""
    data = edited(
        CII,
        (
            "<ram:IssueDateTime>",
            f'<x:{LONG}a xmlns:x="urn:example"/><x:{LONG}b xmlns:x="urn:example"/>'
            "<ram:IssueDateTime>",
        ),
    )
    locations = Locations(etree.fromstring(data))
    cut = f"x:{LONG}"[:98]
    assert locations.of(f"/rsm:CrossIndustryInvoice/rsm:ExchangedDocument/{cut}") is None
    assert locations.of("/rsm:CrossIndustryInvoice/rsm:ExchangedDocument/ram:ID") is not None


# REQ-002-PRS-F005


def test_kosits_levels_apply() -> None:
    """CII-SR-475's context is wrong in CEN's rules 1.3.16; KoSIT lowers it to `information` for
    XRechnung. Plain EN 16931 has no levels, so the stylesheet's own flag stays."""
    path = SUITE / "standard/03.03a-INVOICE_uncefact.xml"
    assert ("CII-SR-475", "information") in rules(validate(path.read_bytes()))
    assert ("CII-SR-475", "warning") in rules(validate(with_specification_id(path, EN16931)))


# REQ-002-PRS-F006


def test_the_rules_judge_the_document_as_received() -> None:
    """PEPPOL-EN16931-R008 exempts the empty `ram:ApplicableHeaderTradeDelivery` by its prefixed
    name; the same document written out again with other prefixes fails it."""
    data = CII.read_bytes()
    assert b"<ram:ApplicableHeaderTradeDelivery/>" in data
    assert "PEPPOL-EN16931-R008" not in {finding.rule for finding in validate(data)}
    written_again = tostring(defusedxml.ElementTree.fromstring(data))
    assert "PEPPOL-EN16931-R008" in {finding.rule for finding in validate(written_again)}


# REQ-002-PRS-F003: BT-24 exactly as written


def test_bt_24_with_whitespace_names_no_profile() -> None:
    """KoSIT's scenarios match BT-24's exact text; padded, it matches none."""
    data = edited(UBL, (f">{XRECHNUNG}<", f"> {XRECHNUNG} <"), NO_BUYER_REFERENCE[UBL])
    findings = validate(data)
    assert len(profile_findings(findings)) == 1
    assert xrechnung_rules(findings) == set()


# REQ-002-PRS-F003: BT-24 split by a comment, a processing instruction or an element, or given
# twice. The rule set is the one KoSIT's validator chooses for the same copy, or none, with
# `HAFL-PROFILE` (tests/conformance/test_kosit_validator.py).

XRECHNUNG_REST = "#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
BT_24_LOCATIONS = {
    CII: CII_BT_24,
    UBL: "/ubl:Invoice/cbc:CustomizationID",
    CREDIT_NOTE: "/cn:CreditNote/cbc:CustomizationID",
}
SYNTAXES = {CII: "a CII invoice", UBL: "a UBL invoice", CREDIT_NOTE: "a UBL credit note"}
NAMES = {CII: "CII", UBL: "UBL Invoice", CREDIT_NOTE: "UBL CreditNote"}


def with_bt_24(path: Path, written: str) -> bytes:
    """A copy whose BT-24 is `written`, markup included, and, but for the credit note, without
    its buyer reference, so that XRechnung's rules fail (BR-DE-15) where they run."""
    if path == CREDIT_NOTE:
        return edited(path, (f">{EN16931}<", f">{written}<"))
    return with_specification_id(path, written, NO_BUYER_REFERENCE[path])


def in_pieces(*pieces: str) -> str:
    """One BT-24 split into `pieces`, as `HAFL-PROFILE` names it."""
    listed = " and ".join(repr(piece) for piece in pieces)
    return f"BT-24 {''.join(pieces)!r}, in pieces {listed},"


def twice(first: str, second: str) -> str:
    """Two BT-24, as `HAFL-PROFILE` names them."""
    return f"BT-24, given 2 times, as {first!r} and {second!r},"


def several(path: Path) -> str:
    """The rule sets of EN 16931 and XRechnung 3.0, as `HAFL-PROFILE` names them."""
    return (
        f"names more than one profile Haflinger has rules for in {SYNTAXES[path]}, with the rule"
        f" sets 'EN16931 ({NAMES[path]})' and 'EN16931 XRechnung ({NAMES[path]})'"
    )


def no_profile(path: Path) -> str:
    return f"names no profile Haflinger has rules for in {SYNTAXES[path]}"


@pytest.mark.parametrize(
    ("path", "written", "xrechnung", "profile"),
    [
        (CII, f"<!--x-->{XRECHNUNG}", True, None),
        (CII, f"{XRECHNUNG}<!--x-->", True, None),
        (CII, f"{EN16931}<!--x-->{XRECHNUNG_REST}", False, None),
        (CII, f"{EN16931}<?x y?>{XRECHNUNG_REST}", False, None),
        (CII, f"{EN16931}<ram:X/>{XRECHNUNG_REST}", False, None),
        (
            CII,
            f"{EN16931}<!--x-->{XRECHNUNG}",
            False,
            f"{in_pieces(EN16931, XRECHNUNG)} {several(CII)}",
        ),
        (
            CII,
            "urn:cen.eu:<!--x-->en16931:2017",
            False,
            f"{in_pieces('urn:cen.eu:', 'en16931:2017')} {no_profile(CII)}",
        ),
        (CII, f"urn:example{SECOND_BT_24[CII]}{EN16931}", False, None),
        (CII, f"{XRECHNUNG}<!--x-->urn:factur-x.eu:1p0:minimum", True, None),
        (
            CII,
            f"{XRECHNUNG}{SECOND_BT_24[CII]}{EN16931}",
            False,
            f"{twice(XRECHNUNG, EN16931)} {several(CII)}",
        ),
        (UBL, f"<!--x-->{XRECHNUNG}", True, None),
        (UBL, f"{XRECHNUNG}<!--x-->", True, None),
        (
            UBL,
            f"{EN16931}<!--x-->{XRECHNUNG_REST}",
            False,
            f"{in_pieces(EN16931, XRECHNUNG_REST)} {several(UBL)}",
        ),
        (
            UBL,
            f"{EN16931}<?x y?>{XRECHNUNG_REST}",
            False,
            f"{in_pieces(EN16931, XRECHNUNG_REST)} {several(UBL)}",
        ),
        (
            UBL,
            f"{EN16931}<cbc:X/>{XRECHNUNG_REST}",
            False,
            f"{in_pieces(EN16931, XRECHNUNG_REST)} {several(UBL)}",
        ),
        (UBL, f"{EN16931}<!--x-->{XRECHNUNG}", False, None),
        (
            UBL,
            "urn:cen.eu:<!--x-->en16931:2017",
            False,
            f"{in_pieces('urn:cen.eu:', 'en16931:2017')} {no_profile(UBL)}",
        ),
        (
            UBL,
            f"{XRECHNUNG}{SECOND_BT_24[UBL]}{EN16931}",
            False,
            f"{twice(XRECHNUNG, EN16931)} {several(UBL)}",
        ),
        (CREDIT_NOTE, f"<!--x-->{XRECHNUNG}", True, None),
        (CREDIT_NOTE, f"{XRECHNUNG}<!--x-->", True, None),
        (CREDIT_NOTE, f"{EN16931}<!--x-->{XRECHNUNG_REST}", False, None),
        (CREDIT_NOTE, f"{EN16931}<?x y?>{XRECHNUNG_REST}", False, None),
        (CREDIT_NOTE, f"{EN16931}<cbc:X/>{XRECHNUNG_REST}", False, None),
        (
            CREDIT_NOTE,
            f"{EN16931}<!--x-->{XRECHNUNG}",
            False,
            f"{in_pieces(EN16931, XRECHNUNG)} {several(CREDIT_NOTE)}",
        ),
        (
            CREDIT_NOTE,
            f"{XRECHNUNG}{SECOND_BT_24[UBL]}{EN16931}",
            False,
            f"{twice(XRECHNUNG, EN16931)} {several(CREDIT_NOTE)}",
        ),
    ],
    ids=[
        "cii-comment-at-the-start",
        "cii-comment-at-the-end",
        "cii-comment-in-the-middle",
        "cii-instruction-in-the-middle",
        "cii-element-in-the-middle",
        "cii-two-profiles",
        "cii-no-profile",
        "cii-second-bt-24-of-a-profile",
        "cii-second-bt-24-of-another-profile",
        "cii-xrechnung-and-factur-x",
        "ubl-comment-at-the-start",
        "ubl-comment-at-the-end",
        "ubl-comment-in-the-middle",
        "ubl-instruction-in-the-middle",
        "ubl-element-in-the-middle",
        "ubl-two-profiles",
        "ubl-no-profile",
        "ubl-second-bt-24",
        "credit-note-comment-at-the-start",
        "credit-note-comment-at-the-end",
        "credit-note-comment-in-the-middle",
        "credit-note-instruction-in-the-middle",
        "credit-note-element-in-the-middle",
        "credit-note-two-profiles",
        "credit-note-second-bt-24",
    ],
)
def test_bt_24_in_pieces_is_compared_as_kosits_scenarios_compare_it(
    path: Path, written: str, xrechnung: bool, profile: str | None, xpath: Callable[[str], str]
) -> None:
    """By the whole text for XRechnung in a UBL invoice, by each piece otherwise, every BT-24
    element counted; matching more than one row names no profile (REQ-002-PRS-F003,
    REQ-002-PRS-F004, REQ-002-PRS-F010); a row of KoSIT's before Factur-X's. An element inside
    BT-24, and a second one in UBL, fail the XML Schema, so that no rules run, and the rule set is
    checked as chosen; two in CII make CEN's rules fail (`HAFL-RULES`)."""
    data = with_bt_24(path, written)
    name, _ = rule_set(open_invoice(data, MAX_SIZE, pdf="a PDF"), tree(decode(data)))
    assert name == f"EN16931{' XRechnung' if xrechnung else ''} ({NAMES[path]})"
    findings = validate(data)
    assert bool(xrechnung_rules(findings)) == xrechnung
    expected = [] if profile is None else [profile]
    assert [finding.text.removesuffix(PROFILE_END) for finding in profile_findings(findings)] == (
        expected
    )
    assert [finding.location for finding in profile_findings(findings)] == [
        xpath(BT_24_LOCATIONS[path]) for _ in expected
    ]


def test_bt_24_inside_an_element_is_named_not_missing(xpath: Callable[[str], str]) -> None:
    """Its text, all inside a child element, is no text node of BT-24's own (REQ-002-PRS-F003);
    `HAFL-PROFILE` names it (REQ-002-PRS-F010)."""
    findings = validate(with_bt_24(UBL, f"<cbc:X>{EN16931}</cbc:X>"))
    assert [finding.text.removesuffix(PROFILE_END) for finding in profile_findings(findings)] == [
        f"BT-24 {EN16931!r}, all of it inside an element, {no_profile(UBL)}"
    ]
    assert [finding.location for finding in profile_findings(findings)] == [
        xpath(BT_24_LOCATIONS[UBL])
    ]


def test_hafl_profile_names_the_first_pieces_of_many() -> None:
    """Split into 1,000 pieces, BT-24 is named shortened, and the first five pieces and how many
    more (REQ-002-PRS-F010)."""
    findings = validate(with_bt_24(CII, "<!--x-->".join(["urn:example"] * 1000)))
    (finding,) = profile_findings(findings)
    assert "'urn:example', 'urn:example', 'urn:example', 'urn:example', 'urn:example' and" in (
        finding.text
    )
    assert " and 995 more, names no profile" in finding.text
    assert len(finding.text) < 800


# Validation and writing from several threads at once


def test_validation_from_several_threads() -> None:
    inputs = [
        CII.read_bytes(),
        edited(CII, WRONG_TOTAL[CII]),
        UBL.read_bytes(),
        edited(UBL, WRONG_TOTAL[UBL]),
    ]
    expected = [validate(data) for data in inputs]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(validate, inputs * 10))
    assert results == expected * 10


def test_schema_checks_from_several_threads() -> None:
    valid = CII.read_bytes()
    invalid = valid.replace(b"<ram:TypeCode>380</ram:TypeCode>", b"<ram:Unknown/>", 1)
    inputs = [valid, invalid]
    expected = [check_cii(data) for data in inputs]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check_cii, inputs * 50))
    assert results == expected * 50


# REQ-002-PRS-F004: other profiles get CEN's rules


@pytest.mark.parametrize(
    ("path", "specification_id"),
    [
        (UBL, f"{EN16931}#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"),
        (CII, f"{EN16931}#compliant#urn:xoev-de:kosit:standard:xrechnung_2.1"),
        (UBL, f"{EN16931}<!--x-->{XRECHNUNG_REST}"),
    ],
    ids=["peppol", "xrechnung-2.1", "ubl-en16931-and-xrechnung"],
)
def test_other_profiles_run_cens_rules(path: Path, specification_id: str) -> None:
    findings = validate(with_specification_id(path, specification_id, WRONG_TOTAL[path]))
    assert ("BR-CO-15", "fatal") in rules(findings)


# REQ-002-PRS-F011: the XML Schema first


@pytest.mark.parametrize(
    ("path", "edit"),
    [
        (CII, ("<ram:ID>123456XX</ram:ID>", "<ram:ID>123456XX</ram:ID><ram:Bogus>x</ram:Bogus>")),
        (UBL, ("<cbc:ID>123456XX</cbc:ID>", "<cbc:ID>123456XX</cbc:ID><cbc:Bogus>x</cbc:Bogus>")),
        (CII, ("<ram:GrandTotalAmount>336.9<", "<ram:GrandTotalAmount>1,00<")),
        (
            UBL,
            (
                '<cbc:TaxInclusiveAmount currencyID="EUR">336.9<',
                '<cbc:TaxInclusiveAmount currencyID="EUR">1,00<',
            ),
        ),
    ],
    ids=["cii-unknown-element", "ubl-unknown-element", "cii-comma-amount", "ubl-comma-amount"],
)
def test_the_schema_comes_before_the_rules(path: Path, edit: tuple[str, str]) -> None:
    findings = validate(edited(path, edit))
    assert findings
    assert {finding.rule for finding in findings} == {"HAFL-XSD"}
    assert all(finding.flag == "fatal" for finding in findings)


def test_a_factur_x_invoice_gets_its_profiles_schema() -> None:
    """KoSIT case 01.01a holds lines, which MINIMUM's XML Schema doesn't allow."""
    findings = validate(with_specification_id(CII, "urn:factur-x.eu:1p0:minimum"))
    assert findings
    assert {finding.rule for finding in findings} == {"HAFL-XSD"}
    assert findings[0].text.startswith("Factur-X MINIMUM XML Schema: ")


# REQ-001-PRS-NF001: validation writes nothing to the file system


def test_validation_writes_no_file(
    monkeypatch: pytest.MonkeyPatch, factur_x: Callable[..., bytes]
) -> None:
    """Nothing asks for a temporary file or directory while validating."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("validation asked for a temporary file")

    for name in ("mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryDirectory"):
        monkeypatch.setattr(f"tempfile.{name}", refuse)
    validate(CII.read_bytes())
    validate(factur_x(f"{EN16931}#conformant#urn:factur-x.eu:1p0:extended"))


def test_factur_x_rules_under_a_path_with_hash_and_percent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, factur_x: Callable[..., bytes]
) -> None:
    """The compiled Schematron reads its code lists relative to a file URI, not a raw path."""
    import shutil

    from haflinger import _saxon

    artefacts = tmp_path / "odd#path%20name"
    shutil.copytree(_saxon.ARTEFACTS, artefacts)
    monkeypatch.setattr(_saxon, "ARTEFACTS", artefacts)
    _saxon.clear_caches()
    try:
        findings = validate(factur_x("urn:factur-x.eu:1p0:minimum", WRONG_TYPE_CODE))
    finally:
        monkeypatch.undo()
        _saxon.clear_caches()
    assert ("FX-SCH-A-000023", "error") in rules(findings)


# REQ-002-PRS-F001: thousands of empty elements, on which the rules would take minutes


def with_empty_notes(total: int) -> bytes:
    """KoSIT case 01.01a in CII with as many empty notes as make `total` empty elements."""
    data = CII.read_bytes()
    root = defusedxml.ElementTree.fromstring(data)
    present = sum(1 for e in root.iter() if len(e) == 0 and not (e.text or "").strip())
    note = b"<ram:IncludedNote/>" * (total - present)
    return data.replace(b"</ram:IncludedNote>", b"</ram:IncludedNote>" + note, 1)


def test_thousands_of_empty_elements_are_refused_at_once() -> None:
    start = time.monotonic()
    with pytest.raises(InvoiceReadError, match=r"25,000 empty elements"):
        validate(with_empty_notes(25_000))
    assert time.monotonic() - start < 1


def test_a_thousand_empty_elements_are_validated() -> None:
    findings = validate(with_empty_notes(1_000))
    assert "PEPPOL-EN16931-R008" in {finding.rule for finding in findings}
    with pytest.raises(InvoiceReadError, match=r"1,001 empty elements"):
        validate(with_empty_notes(1_001))


def test_empty_elements_whose_locations_take_ten_million_characters_are_validated(
    extended: Callable[..., bytes],
) -> None:
    """Each step of a location names the namespace, so the locations of a few hundred elements
    nested 2,048 levels deep take millions of characters."""
    findings = validate(extended(levels=2048, empty="<x:b/>" * 255))
    empty = [finding for finding in findings if finding.rule == "PEPPOL-EN16931-R008"]
    assert sum(len(finding.location) for finding in empty) == 9_991_812
    with pytest.raises(InvoiceReadError, match=r"total 10,030,996 characters"):
        validate(extended(levels=2048, empty="<x:b/>" * 256))
    start = time.monotonic()
    with pytest.raises(InvoiceReadError, match=r"more than 10,000,000"):
        validate(extended(levels=2048, empty="<x:b/>" * 1_000))
    assert time.monotonic() - start < 1


# REQ-002-PRS-F001: numbers and telephone numbers too long for the rules

TELEPHONE = {
    CII: "<ram:CompleteNumber>+49 1234-5678</ram:CompleteNumber>",
    UBL: "<cbc:Telephone>+49 1234-5678</cbc:Telephone>",
}


def with_telephone(path: Path, number: str) -> bytes:
    element = TELEPHONE[path].replace("+49 1234-5678", number)
    return edited(path, (TELEPHONE[path], element))


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
def test_a_long_telephone_number_is_refused_at_once(path: Path) -> None:
    assert invalid(validate(with_telephone(path, "+49 " + "1" * 96))) == []
    with pytest.raises(InvoiceReadError, match="101 characters"):
        validate(with_telephone(path, "+49 " + "1" * 97))
    start = time.monotonic()
    with pytest.raises(InvoiceReadError, match="telephone number"):
        validate(with_telephone(path, "a" * 8000 + "1"))
    assert time.monotonic() - start < 1


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
def test_a_long_number_is_refused_at_once(path: Path) -> None:
    old, new = WRONG_TOTAL[path]
    for digits, refused in ((1000, False), (1001, True)):
        data = edited(path, (old, new.replace("336.91", "3" * (digits - 1) + ".9")))
        if refused:
            with pytest.raises(InvoiceReadError, match="1,001 digits"):
                validate(data)
        else:
            assert ("BR-CO-15", "fatal") in rules(validate(data))
    start = time.monotonic()
    with pytest.raises(InvoiceReadError, match="digits"):
        validate(edited(path, (old, new.replace("336.91", "3" * 200_000))))
    assert time.monotonic() - start < 1


# The third review of 2026-11-01

DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
LINE_TOTAL = "<ram:LineTotalAmount>314.86</ram:LineTotalAmount>"


@pytest.mark.parametrize(
    "data",
    ["text", memoryview(b"<x/>"), bytearray(b"<x/>"), None],
    ids=["str", "memoryview", "bytearray", "none"],
)
def test_refuses_input_that_is_not_bytes(data: object) -> None:
    with pytest.raises(InvoiceReadError, match="not bytes"):
        validate(data)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    ("doctype", "seller"),
    [
        ("<!DOCTYPE rsm:CrossIndustryInvoice [<!ELEMENT rsm:CrossIndustryInvoice ANY>]>", None),
        (
            '<!DOCTYPE rsm:CrossIndustryInvoice [<!ENTITY seller SYSTEM "file:///etc/passwd">]>',
            "&seller;",
        ),
    ],
    ids=["internal DTD", "external entity"],
)
def test_refuses_dtds_and_external_entities(doctype: str, seller: str | None) -> None:
    """REQ-001-PRS-NF001, from validation."""
    edits = [(DECLARATION, DECLARATION + doctype)]
    if seller is not None:
        edits.append(("<ram:Name>[Seller name]</ram:Name>", f"<ram:Name>{seller}</ram:Name>"))
    with pytest.raises(InvoiceReadError, match="DTD"):
        validate(edited(CII, *edits))


def test_refuses_a_byte_order_mark_that_contradicts_the_declaration() -> None:
    data = b"\xef\xbb\xbf" + edited(CII, (DECLARATION, DECLARATION.replace("UTF-8", "ISO-8859-1")))
    with pytest.raises(InvoiceReadError, match="byte order mark"):
        validate(data)


def test_validates_input_as_large_as_max_size() -> None:
    """REQ-001-PRS-NF003: just below the limit, for validate."""
    data = CII.read_bytes()
    assert invalid(validate(data, max_size=len(data))) == []


@pytest.mark.parametrize(
    ("path", "edit"),
    [
        (CII, (LINE_TOTAL, LINE_TOTAL * 2)),
        (
            UBL,
            (
                "<cac:PartyLegalEntity>\n                <cbc:RegistrationName>[Seller name]",
                "<cac:PartyLegalEntity><cbc:RegistrationName>[Seller name]</cbc:RegistrationName>"
                "</cac:PartyLegalEntity><cac:PartyLegalEntity>"
                "<cbc:RegistrationName>[Seller name]",
            ),
        ),
    ],
    ids=["cii-bt-106-twice", "ubl-two-legal-entities"],
)
def test_rules_that_fail_on_a_schema_valid_invoice_are_hafl_rules(
    path: Path, edit: tuple[str, str], xpath: Callable[[str], str]
) -> None:
    """REQ-002-PRS-F010: as KoSIT's processing error, a fatal finding, not a refusal."""
    findings = validate(edited(path, edit))
    assert [(f.rule, f.flag) for f in findings] == [("HAFL-RULES", "fatal")]
    assert findings[0].location == xpath(
        "/rsm:CrossIndustryInvoice" if path == CII else "/ubl:Invoice"
    )
    assert "EN16931 XRechnung" in findings[0].text


def test_hafl_profile_also_when_the_schema_fails() -> None:
    """REQ-002-PRS-F004: one HAFL-PROFILE each, whatever the schema finds."""
    data = with_specification_id(
        CII,
        "urn:cen.eu:en16931:2017#compliant#urn:xoev-de:kosit:standard:xrechnung_2.1",
        ("<ram:ID>123456XX</ram:ID>", "<ram:ID>123456XX</ram:ID><ram:Bogus>x</ram:Bogus>"),
    )
    assert {f.rule for f in validate(data)} == {"HAFL-PROFILE", "HAFL-XSD"}
    assert len(profile_findings(validate(data))) == 1


def test_the_schema_reads_the_text_the_rules_read() -> None:
    """REQ-002-PRS-F011: an encoding Python knows and libxml2 doesn't."""
    text = CII.read_text(encoding="utf-8")
    data = text.replace(DECLARATION, DECLARATION.replace("UTF-8", "mac-roman")).encode("mac-roman")
    assert invalid(validate(data)) == []


def test_deeply_nested_xml_is_a_schema_finding() -> None:
    """libxml2 stops at a depth of its own; the result is a finding, not a crash."""
    nested = "<ram:Bogus>" * 50_000 + "x" + "</ram:Bogus>" * 50_000
    data = edited(CII, ("<ram:ID>123456XX</ram:ID>", "<ram:ID>123456XX</ram:ID>" + nested))
    findings = validate(data)
    assert {f.rule for f in findings} == {"HAFL-XSD"}


@pytest.mark.parametrize(
    "declaration",
    ['<?xml version="1.0" encoding="UTF-8"?>', '<?xml version="1.0"\n  encoding="UTF-8"?>'],
    ids=["one-line", "two-lines"],
)
def test_a_schema_finding_located_at_a_line_names_the_inputs_line(declaration: str) -> None:
    """REQ-002-PRS-F010: the line is the input's, also where its XML declaration, which the
    schema check leaves out, spans lines."""
    nested = "\n" + "<ram:Bogus>" * 3_000 + "x" + "</ram:Bogus>" * 3_000
    data = edited(
        CII,
        ('<?xml version="1.0" encoding="UTF-8"?>', declaration),
        ("<ram:ID>123456XX</ram:ID>", "<ram:ID>123456XX</ram:ID>" + nested),
    )
    line = data.decode().split("\n").index(nested.strip()) + 1
    (finding,) = [finding for finding in validate(data) if finding.rule == "HAFL-XSD"]
    assert finding.location == f"line {line}"


@pytest.mark.parametrize("levels", [100, 101, 2048])
def test_an_extension_as_deep_as_the_schema_check_parses_gets_the_rules(
    extended: Callable[..., bytes], levels: int
) -> None:
    """REQ-002-PRS-F011: Saxon parses it, beyond SaxonC's limit of 100 levels, as KoSIT's
    validator does; CEN's `UBL-CR-001` reports the extension."""
    findings = validate(extended(levels=levels))
    assert [finding for finding in findings if finding.rule.startswith("HAFL-")] == []
    assert "UBL-CR-001" in {finding.rule for finding in findings}
    assert invalid(findings) == []


def test_an_extension_deeper_than_the_schema_check_parses_is_a_schema_finding(
    extended: Callable[..., bytes],
) -> None:
    """REQ-002-PRS-F011: libxml2 parses no deeper than 2,048 levels, and Saxon no deeper either,
    where the rules run without the XML Schema check."""
    (finding,) = validate(extended(levels=2049))
    assert finding.rule == "HAFL-XSD"
    assert "depth" in finding.text
    assert [finding.rule for finding in check_rules(extended(levels=2049))] == ["HAFL-RULES"]


@pytest.mark.parametrize("attributes", [201, 10_000])
def test_an_element_of_ten_thousand_attributes_gets_the_rules(
    extended: Callable[..., bytes], attributes: int
) -> None:
    """REQ-002-PRS-F011: Saxon parses it, beyond SaxonC's limit of 200, as KoSIT's validator
    does."""
    findings = validate(extended(attributes=attributes))
    assert [finding for finding in findings if finding.rule.startswith("HAFL-")] == []
    assert invalid(findings) == []


def test_an_element_of_more_than_ten_thousand_attributes_fails_the_rules(
    extended: Callable[..., bytes],
) -> None:
    """REQ-002-PRS-F011: KoSIT's validator rejects it with a processing error."""
    (finding,) = validate(extended(attributes=10_001))
    assert (finding.rule, finding.flag) == ("HAFL-RULES", "fatal")
    assert "10,000" in finding.text


def test_a_text_over_ten_megabytes_passes_the_schema() -> None:
    """REQ-002-PRS-F011: libxml2's limit on a text doesn't apply (`huge_tree`)."""
    content = "<ram:Content>Es gelten"
    data = edited(CII, (content, "<ram:Content>" + "A" * 11_000_000 + " Es gelten"))
    assert "HAFL-XSD" not in {f.rule for f in validate(data)}

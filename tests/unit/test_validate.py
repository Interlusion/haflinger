"""Validation with the official rules (REQ-002), on edited copies of official files."""

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from xml.etree.ElementTree import tostring

import defusedxml.ElementTree
import pytest

from haflinger import Finding, InvoiceReadError, validate
from haflinger._xsd import check_cii

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


def rules(findings: list[Finding]) -> set[tuple[str, str]]:
    return {(finding.rule, finding.flag) for finding in findings}


def invalid(findings: list[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.flag in ("fatal", "error")]


def profile_findings(findings: list[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.rule == "HAFL-PROFILE"]


def xrechnung_rules(findings: list[Finding]) -> set[str]:
    return {finding.rule for finding in findings if finding.rule.startswith("BR-DE-")}


# REQ-002-PRS-F001


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
def test_validates_cii_and_ubl(path: Path) -> None:
    assert invalid(validate(path.read_bytes())) == []


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"<Invoice>", "not well-formed"),
        (b"%PDF-1.7\n", "validate the XML that haflinger.pdf.extract_xml gives"),
        (b'<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>', "document type declaration"),
        (b"<Order/>", "neither a CII invoice nor a UBL invoice"),
        (with_specification_id(CII, "urn:cen.eu:en16931:2026"), "EN 16931-1:2026"),
        (with_specification_id(UBL, "urn:cen.eu:en16931:2026"), "EN 16931-1:2026"),
    ],
    ids=["not-xml", "pdf", "dtd", "other-root", "2026-cii", "2026-ubl"],
)
def test_refusals(data: bytes, reason: str) -> None:
    """REQ-002-PRS-F001 and, for 2026, REQ-002-PRS-F009."""
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
    assert validate(CREDIT_NOTE.read_bytes()) == []


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


@pytest.mark.parametrize(
    "specification_id",
    [
        "urn:factur-x.eu:1p0:minimum",
        "urn:zugferd.de:2p0:minimum",
        "urn:factur-x.eu:1p0:basicwl",
        "urn:zugferd.de:2p0:basicwl",
        f"{EN16931}#compliant#urn:factur-x.eu:1p0:basic",
        f"{EN16931}#compliant#urn:zugferd.de:2p0:basic",
        f"{EN16931}:compliant:factur-x.eu:1p0:basic",
        f"{EN16931}#conformant#urn:factur-x.eu:1p0:extended",
        f"{EN16931}#conformant#urn:zugferd.de:2p0:extended",
        f"{EN16931}:compliant:factur-x.eu:1p0:extended",
    ],
)
def test_factur_x_gets_cens_rules_until_its_own_are_vendored(specification_id: str) -> None:
    """REQ-002's open question: until FeRD's licence covers the Factur-X rules, the Factur-X
    profiles are checked as REQ-002-PRS-F004 says."""
    findings = validate(with_specification_id(CII, specification_id, WRONG_TOTAL[CII]))
    assert ("BR-CO-15", "fatal") in rules(findings)
    assert xrechnung_rules(findings) == set()
    assert len(profile_findings(findings)) == 1


def test_each_rule_set_is_kosits_scenario_for_its_document_and_bt_24() -> None:
    """The rule sets of REQ-002-PRS-F003, by syntax and BT-24, are the scenarios whose match
    expressions name the same root element and BT-24; every scenario is used."""
    from haflinger.validation import _RULE_SETS  # pyright: ignore[reportPrivateUsage]

    namespace = "{http://www.xoev.de/de/validator/framework/1/scenarios}"
    matches = {
        scenario.findtext(f"{namespace}name"): scenario.findtext(f"{namespace}match") or ""
        for scenario in defusedxml.ElementTree.fromstring(SCENARIOS.read_bytes()).iter(
            f"{namespace}scenario"
        )
    }
    roots = {
        "cii": "/rsm:CrossIndustryInvoice",
        "ubl-invoice": "/invoice:Invoice",
        "ubl-credit-note": "/creditnote:CreditNote",
    }
    for (document, specification_id), name in _RULE_SETS.items():
        assert roots[document] in matches[name], name
        assert re.findall(r"'([^']*)'", matches[name]) == [specification_id], name
    assert set(_RULE_SETS.values()) == set(matches)


# REQ-002-PRS-F004, REQ-002-PRS-F010


@pytest.mark.parametrize(
    ("data", "location", "text"),
    [
        (
            with_specification_id(
                UBL, f"{EN16931}#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
            ),
            "/Invoice/cbc:CustomizationID",
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
            "/Invoice/cbc:CustomizationID",
            "BT-24 'urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic' names no"
            " profile Haflinger has rules for in a UBL invoice",
        ),
        (
            edited(CREDIT_NOTE, (f">{EN16931}<", f">{EXTENSION}<")),
            "/CreditNote/cbc:CustomizationID",
            f"BT-24 '{EXTENSION}' names no profile Haflinger has rules for in a UBL credit note",
        ),
        (
            edited(CII, NO_SPECIFICATION_ID[CII]),
            "/rsm:CrossIndustryInvoice",
            "BT-24 is missing, so a CII invoice names no profile",
        ),
        (
            edited(UBL, NO_SPECIFICATION_ID[UBL]),
            "/Invoice",
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
    data: bytes, location: str, text: str
) -> None:
    findings = validate(data)
    assert profile_findings(findings) == [
        Finding(
            rule="HAFL-PROFILE",
            flag="warning",
            location=location,
            text=f"{text}; checked with CEN's EN 16931 rules only, not the profile's own rules",
        )
    ]
    assert xrechnung_rules(findings) == set()


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

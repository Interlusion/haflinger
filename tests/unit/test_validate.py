"""Validation with the official rules (REQ-002), on edited copies of official files."""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from xml.etree.ElementTree import tostring

import defusedxml.ElementTree
import pytest

from haflinger import Finding, Invoice, InvoiceReadError, Totals, cii, read_invoice, validate
from haflinger._xsd import check_cii
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
MODEL = read_invoice(CII.read_bytes()).invoice
assert MODEL.totals is not None
assert MODEL.seller is not None
assert MODEL.buyer is not None
# KoSIT case 01.01a's model reduced to what MINIMUM and BASIC WL hold, so that the invoice passes
# their XML Schemas (REQ-002-PRS-F011); BASIC and EXTENDED take the whole model.
WITHOUT_LINES = replace(
    MODEL,
    notes=(),
    lines=(),
    buyer_reference=None,
    seller=replace(MODEL.seller, trading_name=None),
    totals=Totals(
        total_without_vat=MODEL.totals.total_without_vat,
        vat_total=MODEL.totals.vat_total,
        total_with_vat=MODEL.totals.total_with_vat,
        amount_due=MODEL.totals.amount_due,
    ),
)
MINIMUM = replace(WITHOUT_LINES, vat_breakdown=(), buyer=replace(MODEL.buyer, country_code=None))
BASIC_WL = replace(
    WITHOUT_LINES,
    totals=replace(WITHOUT_LINES.totals, line_net_total=MODEL.totals.line_net_total),  # type: ignore[arg-type]
)


def factur_x(specification_id: str, *edits: tuple[str, str], model: Invoice | None = None) -> bytes:
    """An invoice of the Factur-X profile `specification_id` names that passes its XML Schema."""
    if model is None:
        model = (
            MINIMUM
            if "minimum" in specification_id
            else (BASIC_WL if "basicwl" in specification_id else MODEL)
        )
    text = cii.write(replace(model, specification_id=specification_id)).decode()
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text.encode()


@pytest.mark.parametrize(("specification_id", "rule"), FACTUR_X)
def test_factur_x_runs_ferds_rules_for_its_profile(specification_id: str, rule: str) -> None:
    """Each spelling of REQ-002-PRS-F003's Factur-X rows runs FeRD's rules for its profile."""
    findings = validate(factur_x(specification_id, WRONG_TYPE_CODE))
    assert (rule, "error") in rules(findings)
    assert profile_findings(findings) == []
    assert xrechnung_rules(findings) == set()


@pytest.mark.parametrize(
    ("specification_id", "rule"),
    [
        (f"{EN16931}:compliant:factur-x.eu:1p0:basic", "FX-SCH-A-000493"),
        (f"{EN16931}:compliant:factur-x.eu:1p0:extended", "FX-SCH-A-000636"),
    ],
)
def test_ferds_rules_judge_a_colon_spelling(specification_id: str, rule: str) -> None:
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


def test_a_rule_without_an_id() -> None:
    """FeRD reports an element its profile doesn't use without a rule ID or flag: an `error`
    with an empty rule (REQ-002-PRS-F002). MINIMUM doesn't use the buyer's address."""
    findings = validate(
        factur_x("urn:factur-x.eu:1p0:minimum", model=replace(MINIMUM, buyer=MODEL.buyer))
    )
    unnamed = [finding for finding in findings if finding.rule == ""]
    assert unnamed
    assert all(finding.flag == "error" for finding in unnamed)
    assert any("is marked as not used in the given context" in f.text for f in unnamed)


def test_the_factur_x_spellings_are_those_of_the_spec() -> None:
    """The BT-24 values of REQ-002-PRS-F003's Factur-X rows, alternative spellings included."""
    from haflinger.validation import _FACTUR_X  # pyright: ignore[reportPrivateUsage]

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


def test_each_rule_set_is_kosits_scenario_for_its_document_and_bt_24() -> None:
    """The rule sets of REQ-002-PRS-F003 other than Factur-X's, by syntax and BT-24, are the
    scenarios whose match expressions name the same root element and BT-24; every scenario is
    used."""
    from haflinger.validation import _FACTUR_X, _RULE_SETS  # pyright: ignore[reportPrivateUsage]

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
    kosit = {key: name for key, name in _RULE_SETS.items() if name not in _FACTUR_X}
    for (document, specification_id), name in kosit.items():
        assert roots[document] in matches[name], name
        assert re.findall(r"'([^']*)'", matches[name]) == [specification_id], name
    assert set(kosit.values()) == set(matches)


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


# REQ-002-PRS-F004: other profiles get CEN's rules


@pytest.mark.parametrize(
    ("path", "specification_id"),
    [
        (UBL, f"{EN16931}#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"),
        (CII, f"{EN16931}#compliant#urn:xoev-de:kosit:standard:xrechnung_2.1"),
    ],
    ids=["peppol", "xrechnung-2.1"],
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


def test_validation_writes_no_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing asks for a temporary file or directory while validating."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("validation asked for a temporary file")

    for name in ("mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryDirectory"):
        monkeypatch.setattr(f"tempfile.{name}", refuse)
    validate(CII.read_bytes())
    validate(factur_x(f"{EN16931}#conformant#urn:factur-x.eu:1p0:extended"))


def test_factur_x_rules_under_a_path_with_hash_and_percent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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

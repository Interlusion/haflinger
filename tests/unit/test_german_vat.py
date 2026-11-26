"""The German VAT check: what §14(4) UStG asks of an invoice beyond its profile's rules
(REQ-002-PRS-F012 to REQ-002-PRS-F014, ADR-014), on edited copies of official files."""

import re
from collections.abc import Callable, Sequence
from pathlib import Path

import defusedxml.ElementTree
import pytest

from haflinger import Finding, InvoiceReadError, check_german_vat, validate
from haflinger.pdf import extract_xml

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/data/kosit-testsuite/instances"
CII = SUITE / "standard/01.01a-INVOICE_uncefact.xml"
UBL = SUITE / "standard/01.01a-INVOICE_ubl.xml"
CREDIT_NOTE = ROOT / "tests/data/cen-en16931/ubl/examples/ubl-tc434-creditnote1.xml"
MUSTANG = ROOT / "tests/data/zugferd-corpus/ZUGFeRDv2/correct/Mustangproject"
STYLESHEETS = ROOT / "src/haflinger/artefacts/kosit-validator-xrechnung/resources/xrechnung"

EN16931 = "urn:cen.eu:en16931:2017"
XRECHNUNG = f"{EN16931}#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
MINIMUM = ("urn:factur-x.eu:1p0:minimum", "urn:zugferd.de:2p0:minimum")
BASIC_WL = ("urn:factur-x.eu:1p0:basicwl", "urn:zugferd.de:2p0:basicwl")
# REQ-002-PRS-F013: the rules the check keeps.
RULES = {"BR-DE-TMP-32", "BR-DE-3", "BR-DE-4", "BR-DE-8", "BR-DE-9"}
CII_BT_24 = "/rsm:CrossIndustryInvoice/rsm:ExchangedDocumentContext/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID"  # noqa: E501
SECOND_BT_24 = (
    "</ram:ID></ram:GuidelineSpecifiedDocumentContextParameter>"
    "<ram:GuidelineSpecifiedDocumentContextParameter><ram:ID>"
)
# The parties' elements and the address terms the rules ask for, in each syntax.
PARTIES = {
    "cii": {"seller": "ram:SellerTradeParty", "buyer": "ram:BuyerTradeParty"},
    "ubl": {"seller": "cac:AccountingSupplierParty", "buyer": "cac:AccountingCustomerParty"},
}
ADDRESS = {"cii": r"ram:(?:CityName|PostcodeCode)", "ubl": r"cbc:(?:CityName|PostalZone)"}
# The edits, in each syntax of KoSIT case 01.01a, which states no time of supply: its second line
# has no period, and it has neither a delivery date nor an invoicing period.
TOTAL = {
    CII: "<ram:GrandTotalAmount>336.9</ram:GrandTotalAmount>",
    UBL: '<cbc:TaxInclusiveAmount currencyID="EUR">336.9</cbc:TaxInclusiveAmount>',
}
CURRENCY = {
    CII: "<ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>",
    UBL: "<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>",
}
TYPE = {
    CII: "<ram:TypeCode>380</ram:TypeCode>",
    UBL: "<cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>",
}
BREAKDOWN_CATEGORY = {
    CII: "<ram:BasisAmount>314.86</ram:BasisAmount>\n                <ram:CategoryCode>S<",
    UBL: "<cac:TaxCategory>\n                <cbc:ID>S<",
}
LINE_CATEGORY = {
    CII: "<ram:CategoryCode>S</ram:CategoryCode>\n                    <ram:RateApplicablePercent>7<"
    "/ram:RateApplicablePercent>\n                </ram:ApplicableTradeTax>\n"
    "                <ram:SpecifiedTradeSettlementLineMonetarySummation>",
    UBL: "<cbc:Name>Porto + Versandkosten</cbc:Name>\n            <cac:ClassifiedTaxCategory>\n"
    "                <cbc:ID>S<",
}


def syntax(path: Path) -> str:
    return "cii" if path == CII else "ubl"


def edited(path: Path, *edits: tuple[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text


def plain(path: Path, *edits: tuple[str, str]) -> str:
    """A copy whose BT-24 names EN 16931, not XRechnung: an invoice between businesses."""
    return edited(path, (f">{XRECHNUNG}<", f">{EN16931}<"), *edits)


def without_address(text: str, syntax: str, party: str) -> str:
    """The party's city and post code left out."""
    element = PARTIES[syntax][party]
    start, end = text.index(f"<{element}>"), text.index(f"</{element}>")
    part = re.sub(rf"<({ADDRESS[syntax]})>[^<]*</\1>", "", text[start:end])
    assert part != text[start:end], party
    return text[:start] + part + text[end:]


def rules(findings: Sequence[Finding]) -> set[str]:
    return {finding.rule for finding in findings}


# REQ-002-PRS-F012: the entry point


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
def test_checks_cii_and_ubl(path: Path) -> None:
    findings = check_german_vat(path.read_bytes())
    assert isinstance(findings, tuple)
    assert rules(findings) == {"BR-DE-TMP-32"}


def test_the_kosit_suite_gets_only_the_time_of_supply() -> None:
    """KoSIT's accepted files hold city and post code for both parties; many state no time of
    supply (REQ-002's assumptions)."""
    for path in sorted(SUITE.rglob("*.xml")):
        assert rules(check_german_vat(path.read_bytes())) <= {"BR-DE-TMP-32"}, path.name


DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
TELEPHONE = "<ram:CompleteNumber>+49 1234-5678</ram:CompleteNumber>"


def with_empty_notes(total: int) -> bytes:
    """KoSIT case 01.01a in CII with as many empty notes as make `total` empty elements."""
    data = CII.read_bytes()
    root = defusedxml.ElementTree.fromstring(data)
    present = sum(1 for e in root.iter() if len(e) == 0 and not (e.text or "").strip())
    note = b"<ram:IncludedNote/>" * (total - present)
    return data.replace(b"</ram:IncludedNote>", b"</ram:IncludedNote>" + note, 1)


REFUSED = {
    "str": "text",
    "not-xml": b"<Invoice>",
    "byte-order-mark": b"\xef\xbb\xbf"
    + edited(CII, (DECLARATION, DECLARATION.replace("UTF-8", "ISO-8859-1"))).encode(),
    "dtd": b'<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>',
    "other-root": b"<Order/>",
    "2026": edited(CII, (f">{XRECHNUNG}<", ">urn:cen.eu:en16931:2026<")).encode(),
    "empty-elements": with_empty_notes(1_001),
    "digits": edited(CII, (TOTAL[CII], TOTAL[CII].replace("336.9", "3" * 1_000 + ".9"))).encode(),
    "telephone": edited(CII, (TELEPHONE, TELEPHONE.replace("1234-5678", "1" * 97))).encode(),
}


@pytest.mark.parametrize("data", REFUSED.values(), ids=REFUSED.keys())
def test_refuses_what_validate_refuses(data: object) -> None:
    """REQ-002-PRS-F001's refusals, with `validate`'s reasons."""
    with pytest.raises(InvoiceReadError) as refused:
        validate(data)  # pyright: ignore[reportArgumentType]
    with pytest.raises(InvoiceReadError, match=re.escape(str(refused.value))):
        check_german_vat(data)  # pyright: ignore[reportArgumentType]


def test_refuses_more_than_max_size() -> None:
    with pytest.raises(InvoiceReadError, match="larger than max_size"):
        check_german_vat(CII.read_bytes(), max_size=1000)


def test_refuses_empty_elements_whose_locations_take_ten_million_characters(
    extended: Callable[..., bytes],
) -> None:
    with pytest.raises(InvoiceReadError, match=r"total 10,030,996 characters"):
        check_german_vat(extended(levels=2048, empty="<x:b/>" * 256))


def test_refuses_a_pdf() -> None:
    with pytest.raises(InvoiceReadError, match=r"check the XML that haflinger\.pdf\.extract_xml"):
        check_german_vat(b"%PDF-1.7\n")


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
def test_the_schema_comes_first(path: Path) -> None:
    opening = "<rsm:ExchangedDocumentContext>" if path == CII else "<cbc:CustomizationID>"
    findings = check_german_vat(
        edited(path, (opening, "<x:Unknown xmlns:x='urn:x'/>" + opening)).encode()
    )
    assert findings
    assert rules(findings) == {"HAFL-XSD"}


@pytest.mark.parametrize("specification_id", MINIMUM + BASIC_WL)
def test_minimum_and_basic_wl_are_no_e_invoices(
    specification_id: str, factur_x: Callable[..., bytes], xpath: Callable[[str], str]
) -> None:
    findings = check_german_vat(factur_x(specification_id))
    assert len(findings) == 1
    (finding,) = findings
    assert (finding.rule, finding.flag, finding.location) == (
        "HAFL-DE-PROFILE",
        "error",
        xpath(CII_BT_24),
    )
    profile = "Factur-X MINIMUM" if specification_id in MINIMUM else "Factur-X BASIC WL"
    assert finding.text.startswith(f"{profile} is no e-invoice under §14(1) UStG")
    assert "§14(4) UStG" in finding.text
    assert "weren't run" in finding.text


def test_a_minimum_invoice_that_fails_its_schema() -> None:
    """KoSIT case 01.01a holds lines, which MINIMUM's XML Schema doesn't allow."""
    findings = check_german_vat(edited(CII, (f">{XRECHNUNG}<", f">{MINIMUM[0]}<")).encode())
    assert findings
    assert rules(findings) == {"HAFL-XSD"}


def test_xrechnung_and_minimum_in_bt_24_get_the_rules() -> None:
    """REQ-002-PRS-F003 chooses XRechnung's rules where BT-24 names both."""
    data = edited(CII, (f">{XRECHNUNG}<", f">{XRECHNUNG}{SECOND_BT_24}{MINIMUM[0]}<"))
    assert rules(check_german_vat(data.encode())) == {"BR-DE-TMP-32"}


def test_a_bt_24_naming_no_profile_is_checked() -> None:
    data = edited(CII, (f">{XRECHNUNG}<", ">urn:example:other<")).encode()
    assert check_german_vat(data) == check_german_vat(plain(CII).encode())


# REQ-002-PRS-F013: the rules


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
def test_the_time_of_supply(path: Path) -> None:
    (finding,) = check_german_vat(plain(path).encode())
    assert (finding.rule, finding.flag) == ("BR-DE-TMP-32", "information")


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
@pytest.mark.parametrize(
    ("party", "found"), [("seller", {"BR-DE-3", "BR-DE-4"}), ("buyer", {"BR-DE-8", "BR-DE-9"})]
)
def test_the_addresses(
    path: Path, party: str, found: set[str], selects: Callable[[bytes, str], object]
) -> None:
    data = without_address(plain(path), syntax(path), party).encode()
    findings = [f for f in check_german_vat(data) if f.rule != "BR-DE-TMP-32"]
    assert rules(findings) == found
    for finding in findings:
        assert finding.flag == "fatal"
        selects(data, finding.location)


def test_the_addresses_of_a_credit_note(selects: Callable[[bytes, str], object]) -> None:
    """CEN's credit note, above the limit for small invoices; a credit note keeps no time of
    supply (REQ-002-PRS-F014)."""
    text = edited(
        CREDIT_NOTE,
        (
            '<cbc:TaxInclusiveAmount currencyID="EUR">100.11<',
            '<cbc:TaxInclusiveAmount currencyID="EUR">1000.11<',
        ),
    )
    text = without_address(without_address(text, "ubl", "seller"), "ubl", "buyer")
    data = text.encode()
    findings = check_german_vat(data)
    assert rules(findings) == {"BR-DE-3", "BR-DE-4", "BR-DE-8", "BR-DE-9"}
    for finding in findings:
        selects(data, finding.location)


@pytest.mark.parametrize("pdf", sorted(MUSTANG.glob("*.pdf")), ids=lambda path: path.name)
def test_zugferd_invoices_between_businesses(pdf: Path) -> None:
    """The corpus's correct EN 16931 invoices fail some of XRechnung's own rules, which the check
    leaves out."""
    xml = extract_xml(pdf.read_bytes())
    assert check_german_vat(xml) == ()


def test_the_rules_failing_give_hafl_rules(extended: Callable[..., bytes]) -> None:
    """Saxon refuses an element of 10,001 attributes, which the XML Schema check passes
    (REQ-002-PRS-F011)."""
    (finding,) = check_german_vat(extended(attributes=10_001))
    assert (finding.rule, finding.flag) == ("HAFL-RULES", "fatal")
    assert "German VAT check" in finding.text


def test_the_rules_are_in_the_vendored_stylesheets() -> None:
    """A KoSIT release that drops or renames one of the rules fails here (ADR-014)."""
    for name in ("XRechnung-CII-validation.xsl", "XRechnung-UBL-validation.xsl"):
        (stylesheet,) = STYLESHEETS.rglob(name)
        text = stylesheet.read_text(encoding="utf-8")
        for rule in RULES:
            assert f'id="{rule}"' in text, (name, rule)


# REQ-002-PRS-F014: the exceptions


def small(path: Path, *edits: tuple[str, str]) -> bytes:
    """A copy without the time of supply and the buyer's city and post code."""
    return without_address(plain(path, *edits), syntax(path), "buyer").encode()


DROPPED = {"BR-DE-TMP-32", "BR-DE-8", "BR-DE-9"}


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
@pytest.mark.parametrize(
    ("total", "found"),
    [("250.00", set[str]()), ("-250.00", set[str]()), ("250.01", DROPPED), ("-250.01", DROPPED)],
)
def test_small_invoices(path: Path, total: str, found: set[str]) -> None:
    data = small(path, (TOTAL[path], TOTAL[path].replace("336.9", total)))
    assert rules(check_german_vat(data)) == found


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
@pytest.mark.parametrize(
    ("edited_codes", "old", "new"),
    [
        (CURRENCY, "EUR", "USD"),
        (BREAKDOWN_CATEGORY, "S<", "K<"),
        (BREAKDOWN_CATEGORY, "S<", "AE<"),
        (LINE_CATEGORY, "S<", "AE<"),
        (LINE_CATEGORY, "S<", "K<"),
        (LINE_CATEGORY, "S<", "<"),
    ],
    ids=[
        "usd",
        "intra-community",
        "reverse-charge",
        "reverse-charge-line",
        "intra-community-line",
        "line-category-not-read",
    ],
)
def test_no_small_invoice(path: Path, edited_codes: dict[Path, str], old: str, new: str) -> None:
    code = edited_codes[path]
    data = small(
        path, (TOTAL[path], TOTAL[path].replace("336.9", "100.00")), (code, code.replace(old, new))
    )
    assert rules(check_german_vat(data)) == DROPPED


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
def test_no_total_no_small_invoice(path: Path) -> None:
    assert rules(check_german_vat(small(path, (TOTAL[path], "")))) == DROPPED


def test_no_breakdown_no_small_invoice() -> None:
    """UBL's XML Schema allows an invoice without a VAT breakdown, CII's doesn't."""
    text = plain(UBL, (TOTAL[UBL], TOTAL[UBL].replace("336.9", "100.00")))
    text = re.sub(r"<cac:TaxSubtotal>.*</cac:TaxSubtotal>", "", text, count=1, flags=re.S)
    data = without_address(text, "ubl", "buyer").encode()
    assert rules(check_german_vat(data)) == DROPPED


@pytest.mark.parametrize("path", [CII, UBL], ids=["cii", "ubl"])
@pytest.mark.parametrize("code", ["381", "386"])
def test_credit_notes_and_advance_payments(path: Path, code: str) -> None:
    data = small(path, (TYPE[path], TYPE[path].replace("380", code)))
    assert rules(check_german_vat(data)) == {"BR-DE-8", "BR-DE-9"}


def test_a_ubl_credit_note() -> None:
    text = edited(
        CREDIT_NOTE,
        (
            '<cbc:TaxInclusiveAmount currencyID="EUR">100.11<',
            '<cbc:TaxInclusiveAmount currencyID="EUR">1000.11<',
        ),
    )
    text = re.sub(r"<cac:InvoicePeriod>.*?</cac:InvoicePeriod>", "", text, count=1, flags=re.S)
    data = without_address(text, "ubl", "buyer").encode()
    assert rules(check_german_vat(data)) == {"BR-DE-8", "BR-DE-9"}

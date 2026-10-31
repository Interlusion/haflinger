"""The model of EN 16931 business terms.

REQ-001-PRS-F001 to REQ-001-PRS-F003 and REQ-001-PRS-NF002.
"""

import dataclasses
import re
import sys
import typing
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

import pytest

from haflinger import model
from haflinger.model import Invoice, Party, Totals

ROOT = Path(__file__).resolve().parents[2]
REQ_001 = ROOT / "docs/specs/req-001-core.md"
REQ_002 = ROOT / "docs/specs/req-002-conformance.md"
KOSIT_SUITE = ROOT / "tests/data/kosit-testsuite/instances"

CII_BT_24 = (
    "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}ExchangedDocumentContext/"
    "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}"
    "GuidelineSpecifiedDocumentContextParameter/"
    "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ID"
)
UBL_BT_24 = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}CustomizationID"


def spec_section(path: Path, heading: str) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index(f"#### {heading}")
    end = text.index("\n#### ", start + 1)
    return text[start:end]


def spec_fields() -> dict[str, set[str]]:
    """The model's fields by class, as REQ-001-PRS-F001's table names them."""
    fields: dict[str, set[str]] = {}
    for row in spec_section(REQ_001, "REQ-001-PRS-F001").splitlines():
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        match = re.fullmatch(r"`(\w+)\.(\w+)`", cells[0]) if len(cells) == 4 else None
        if match is None:
            continue
        cls, name = match.groups()
        fields.setdefault(cls, set()).add(name)
        # A group whose terms the row names inline, such as BG-1's.
        inline = re.findall(r"`(\w+)`", cells[2])
        if inline:
            element = typing.get_args(typing.get_type_hints(getattr(model, cls))[name])[0]
            fields.setdefault(element.__name__, set()).update(inline)
    return fields


def specification_ids() -> list[str]:
    """Every BT-24 of REQ-002-PRS-F003's table, alternative spellings included."""
    ids: list[str] = []
    for row in spec_section(REQ_002, "REQ-002-PRS-F003").splitlines():
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) == 5 and cells[1].startswith("`"):
            ids += re.findall(r"`([^`]+)`", cells[1] + cells[2])
    return ids


def test_fields_match_req_001() -> None:
    expected = spec_fields()
    expected["Invoice"] |= {"syntax"}
    actual = {cls: {f.name for f in dataclasses.fields(getattr(model, cls))} for cls in expected}
    assert actual == expected


def test_missing_terms_are_none_and_missing_groups_empty() -> None:
    invoice = Invoice()
    assert invoice.number is None
    assert invoice.seller is None
    assert invoice.notes == ()
    assert invoice.lines == ()


def test_invoices_compare_equal_whatever_their_syntax() -> None:
    cii = Invoice(number="1", seller=Party(name="Example GmbH"), syntax="cii")
    ubl = Invoice(number="1", seller=Party(name="Example GmbH"), syntax="ubl")
    assert cii == ubl
    assert hash(cii) == hash(ubl)
    assert cii.syntax != ubl.syntax


def test_a_model_built_in_code_has_no_syntax() -> None:
    assert Invoice(number="1").syntax is None


def test_numbers_compare_by_value() -> None:
    a = Invoice(totals=Totals(amount_due=Decimal("10.50")))
    b = Invoice(totals=Totals(amount_due=Decimal("10.5")))
    assert a == b


@pytest.mark.parametrize("specification_id", specification_ids())
def test_every_supported_profile_names_2017(specification_id: str) -> None:
    assert Invoice(specification_id=specification_id).edition == "2017"


@pytest.mark.parametrize(
    ("specification_id", "edition"),
    [
        ("urn:cen.eu:en16931:2026", "2026"),
        ("urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0", "2017"),
        (None, None),
        ("urn:example:other", None),
        ("urn:cen.eu:en16931:", None),
        ("urn:cen.eu:en16931:20171", None),
        ("urn:cen.eu:en16931:٢٠١٧", None),
    ],
)
def test_edition_follows_from_bt_24(specification_id: str | None, edition: str | None) -> None:
    assert Invoice(specification_id=specification_id).edition == edition


def test_edition_is_not_set_on_its_own() -> None:
    invoice = Invoice()
    with pytest.raises(AttributeError):
        invoice.edition = "2017"  # pyright: ignore[reportAttributeAccessIssue]
    assert "edition" not in {f.name for f in dataclasses.fields(Invoice)}


@pytest.mark.parametrize("path", sorted(KOSIT_SUITE.rglob("*.xml")), ids=lambda path: path.name)
def test_every_kosit_test_file_names_2017(path: Path) -> None:
    root = ET.parse(path).getroot()  # noqa: S314 (a vendored official file, not outside input)
    element = root.find(CII_BT_24 if path.stem.endswith("uncefact") else UBL_BT_24)
    assert element is not None
    assert Invoice(specification_id=(element.text or "").strip()).edition == "2017"


def test_no_frappe_is_loaded() -> None:
    Invoice(number="1", seller=Party(name="Example GmbH"))
    loaded = {name.split(".")[0] for name in sys.modules}
    assert not loaded & {"frappe", "erpnext"}

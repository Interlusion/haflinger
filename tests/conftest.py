"""What every test shares."""

import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from xml.etree.ElementTree import Element

import defusedxml.ElementTree
import pytest

from haflinger import Party, Totals, _cii, _saxon, _ubl, read_invoice

# The prefixes the tests spell locations with.
PREFIXES = {**_cii.NAMESPACES, **_ubl.NAMESPACES, "ubl": _ubl.INVOICE, "cn": _ubl.CREDIT_NOTE}
# A location's step: XPath 3.0's `Q{namespace}name[position]` (REQ-002-PRS-F002).
_STEP = re.compile(r"/Q\{([^}]*)\}([^/\[\]{}]+)\[([1-9][0-9]*)\]")
_UBL = Path(__file__).parent / "data/kosit-testsuite/instances/standard/01.01a-INVOICE_ubl.xml"
_CII = Path(__file__).parent / "data/kosit-testsuite/instances/standard/01.01a-INVOICE_uncefact.xml"
_EXTENSIONS = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"


def pytest_sessionfinish() -> None:
    """Stop the rules' worker before pytest ends: under coverage, it writes its data only when
    it ends, which `coverage combine` reads right after (development guide, CI)."""
    _saxon.clear_caches()


def _xpath(prefixed: str) -> str:
    """A path such as `/rsm:CrossIndustryInvoice/ram:ID[2]` as a finding's location gives it:
    each step `Q{namespace}name[position]`, the position 1 where the path gives none."""

    def step(match: re.Match[str]) -> str:
        return f"Q{{{PREFIXES[match[1]]}}}{match[2]}[{match[3] or 1}]"

    return re.sub(r"(\w+):(\w+)(?:\[([0-9]+)\])?", step, prefixed)


def _selects(document: bytes, location: str) -> Element:
    """The one element `location` selects in `document`, each step in the form findings give."""
    steps = _STEP.findall(location)
    assert "".join(f"/Q{{{ns}}}{name}[{position}]" for ns, name, position in steps) == location
    element = defusedxml.ElementTree.fromstring(document)
    (ns, name, position), *below = steps
    assert (element.tag, position) == (f"{{{ns}}}{name}", "1"), location
    for ns, name, position in below:
        children = [child for child in element if child.tag == f"{{{ns}}}{name}"]
        assert len(children) >= int(position), location
        element = children[int(position) - 1]
    return element


@pytest.fixture
def xpath() -> Callable[[str], str]:
    return _xpath


@pytest.fixture
def selects() -> Callable[[bytes, str], Element]:
    return _selects


def _extended(*, levels: int = 5, attributes: int = 0, empty: str = "") -> bytes:
    """KoSIT's 01.01a UBL file with an extension whose deepest element lies at `levels`, the root
    at 1, and has `attributes` attributes and the text `x`, followed by `empty` (REQ-002-PRS-F011).
    UBL's extensions take any foreign element, so that the XML Schema passes it."""
    nested = levels - 4  # below the root, `ext:UBLExtensions`, `UBLExtension`, `ExtensionContent`
    deepest = "<x:a" + "".join(f' a{i}="v"' for i in range(attributes)) + ">x</x:a>"
    content = "<x:a>" * (nested - 1) + deepest + empty + "</x:a>" * (nested - 1)
    extension = (
        f'<ext:UBLExtensions xmlns:ext="{_EXTENSIONS}"><ext:UBLExtension>'
        f'<ext:ExtensionContent xmlns:x="urn:example">{content}</ext:ExtensionContent>'
        "</ext:UBLExtension></ext:UBLExtensions>"
    )
    data = _UBL.read_text(encoding="utf-8")
    assert data.count("<cbc:CustomizationID>") == 1, _UBL
    return data.replace("<cbc:CustomizationID>", f"{extension}<cbc:CustomizationID>").encode()


@pytest.fixture(scope="session")
def extended() -> Callable[..., bytes]:
    return _extended


_MODEL = read_invoice(_CII.read_bytes()).invoice
assert _MODEL.totals is not None
assert _MODEL.seller is not None
assert _MODEL.buyer is not None
# KoSIT case 01.01a's model reduced to what MINIMUM, BASIC WL and BASIC hold, so that the invoice
# passes their XML Schemas (REQ-002-PRS-F011); EN 16931 and EXTENDED take the whole model.
_WITHOUT_LINES = replace(
    _MODEL,
    # Neither MINIMUM nor BASIC WL has a VAT point date.
    vat_point_date=None,
    notes=(),
    lines=(),
    buyer_reference=None,
    supporting_documents=(),
    # The parties' terms that every profile's XML Schema allows.
    seller=Party(
        name=_MODEL.seller.name,
        legal_registration_id=_MODEL.seller.legal_registration_id,
        vat_id=_MODEL.seller.vat_id,
        country_code=_MODEL.seller.country_code,
    ),
    buyer=Party(name=_MODEL.buyer.name, country_code=_MODEL.buyer.country_code),
    totals=Totals(
        total_without_vat=_MODEL.totals.total_without_vat,
        vat_total=_MODEL.totals.vat_total,
        total_with_vat=_MODEL.totals.total_with_vat,
        amount_due=_MODEL.totals.amount_due,
    ),
)
_MINIMUM = replace(
    _WITHOUT_LINES,
    vat_point_date_code=None,
    vat_breakdown=(),
    buyer=Party(name=_MODEL.buyer.name),
    payee=None,
    tax_representative=None,
    payment_terms=None,
    payment_instructions=None,
)
# BASIC has no VAT point date, seller contact, additional legal information or supporting
# documents, no line references, and of an item only its standard identifier and its name.
_BASIC = replace(
    _MODEL,
    vat_point_date=None,
    supporting_documents=(),
    seller=replace(_MODEL.seller, contact=None, additional_legal_information=None),
    lines=tuple(
        replace(
            line,
            object_id=None,
            purchase_order_line_reference=None,
            buyer_accounting_reference=None,
            item_description=None,
            seller_item_id=None,
            buyer_item_id=None,
            item_classifications=(),
            item_country_of_origin=None,
            item_attributes=(),
        )
        for line in _MODEL.lines
    ),
)
_BASIC_WL = replace(
    _WITHOUT_LINES,
    totals=replace(_WITHOUT_LINES.totals, line_net_total=_MODEL.totals.line_net_total),  # type: ignore[arg-type]
)


def _factur_x(specification_id: str, *edits: tuple[str, str], buyer_country: bool = False) -> bytes:
    """An invoice of the Factur-X profile `specification_id` names that passes its XML Schema;
    with `buyer_country`, its buyer has only the terms every profile's XML Schema allows, the
    buyer's country among them, which MINIMUM's own buyer lacks."""
    model = (
        _MINIMUM
        if "minimum" in specification_id
        else _BASIC_WL
        if "basicwl" in specification_id
        else _BASIC
        if "basic" in specification_id
        else _MODEL
    )
    if buyer_country:
        model = replace(model, buyer=_WITHOUT_LINES.buyer)
    text = _cii.write(replace(model, specification_id=specification_id)).decode()
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text.encode()


@pytest.fixture(scope="session")
def factur_x() -> Callable[..., bytes]:
    return _factur_x

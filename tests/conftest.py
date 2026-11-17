"""What every test shares."""

import re
from collections.abc import Callable
from pathlib import Path
from xml.etree.ElementTree import Element

import defusedxml.ElementTree
import pytest

from haflinger import _cii, _saxon, _ubl

# The prefixes the tests spell locations with.
PREFIXES = {**_cii.NAMESPACES, **_ubl.NAMESPACES, "ubl": _ubl.INVOICE, "cn": _ubl.CREDIT_NOTE}
# A location's step: XPath 3.0's `Q{namespace}name[position]` (REQ-002-PRS-F002).
_STEP = re.compile(r"/Q\{([^}]*)\}([^/\[\]{}]+)\[([1-9][0-9]*)\]")
_UBL = Path(__file__).parent / "data/kosit-testsuite/instances/standard/01.01a-INVOICE_ubl.xml"
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

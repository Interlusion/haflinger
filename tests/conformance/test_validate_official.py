"""The official test files' verdicts, reproduced (REQ-002-PRS-F007)."""

from pathlib import Path
from xml.etree.ElementTree import Element, tostring

import defusedxml.ElementTree
import pytest

from haflinger import validate

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/data/kosit-testsuite/instances"
CEN_TESTS = ROOT / "tests/data/cen-en16931/test"
VEFA = "{http://difi.no/xsd/vefa/validator/1.0}"


@pytest.mark.parametrize("path", sorted(SUITE.rglob("*.xml")), ids=lambda path: path.name)
def test_every_kosit_file_is_valid(path: Path) -> None:
    findings = validate(path.read_bytes())
    assert [finding for finding in findings if finding.flag in ("fatal", "error")] == []


def cen_tests() -> list[tuple[str, Element]]:
    """CEN's unit tests, each a `<test>` with an `<assert>` and an invoice fragment."""
    tests: list[tuple[str, Element]] = []
    for path in sorted(CEN_TESTS.rglob("*.xml")):
        test_set = defusedxml.ElementTree.fromstring(path.read_bytes(), forbid_dtd=True)
        for number, test in enumerate(test_set.iter(f"{VEFA}test"), start=1):
            tests.append((f"{path.relative_to(CEN_TESTS)}#{number}", test))
    return tests


CEN = cen_tests()


def test_cens_tests_are_there() -> None:
    assert len(CEN) == 1140


@pytest.mark.parametrize("test", [test for _, test in CEN], ids=[name for name, _ in CEN])
def test_cens_expectations_are_met(test: Element) -> None:
    """Each rule an `<error>` or `<warning>` names fails, as often as its `number` says (once at
    least) and with that seriousness; each rule a `<success>` names doesn't fail. The fragment is
    written out by ElementTree; CEN's rules test no prefixes. Fragments without BT-24 get CEN's
    rules and `HAFL-PROFILE`."""
    expectations = test.find(f"{VEFA}assert")
    assert expectations is not None
    (fragment,) = [child for child in test if child.tag != f"{VEFA}assert"]
    findings = validate(tostring(fragment))
    checked = 0
    for expectation in expectations:
        kind, rule = expectation.tag.removeprefix(VEFA), (expectation.text or "").strip()
        flags = [finding.flag for finding in findings if finding.rule == rule]
        match kind:
            case "success":
                assert flags == [], rule
            case "error" | "warning":
                assert len(flags) == int(expectation.get("number", len(flags) or 1)), rule
                assert set(flags) <= ({"fatal", "error"} if kind == "error" else {"warning"}), rule
            case _:
                continue
        checked += 1
    assert checked > 0

"""KoSIT's validator, the official tool, over the KoSIT suite and the invoices the round trip
writes from it, as XRechnung and as EN 16931: it gives the same verdict and the same findings as
`validate`, and accepts every invoice `write_cii` hands out (REQ-002-PRS-F007, REQ-004-PRS-F005).
It is Java, so it runs where HAFLINGER_KOSIT_VALIDATOR names it, as in CI
(`scripts/kosit-validator.sh`)."""

import os
import subprocess
from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from defusedxml.ElementTree import parse
from test_write_kosit import EN16931, FILES, XRECHNUNG, write

from haflinger import is_valid, validate

VALIDATOR = os.environ.get("HAFLINGER_KOSIT_VALIDATOR")
REPORT = "{http://www.xoev.de/de/validator/varl/1}"
SCENARIOS = "{http://www.xoev.de/de/validator/framework/1/scenarios}"

pytestmark = pytest.mark.skipif(
    not VALIDATOR, reason="HAFLINGER_KOSIT_VALIDATOR names no KoSIT validator"
)

type Findings = list[tuple[str, str, str]]

# The written documents' names, by target profile.
PROFILES = {"written": XRECHNUNG, "written-en16931": EN16931}


def documents(path: Path) -> dict[str, bytes]:
    """The suite's file as received and the documents the round trip writes from it."""
    written = {
        f"{path.stem}-{name}.xml": write(path, profile)[1] for name, profile in PROFILES.items()
    }
    return {f"{path.stem}.xml": path.read_bytes(), **written}


@pytest.fixture(scope="module")
def reports(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Element]:
    """KoSIT's report on each document, from one call: Java starts once."""
    invoices, reports = tmp_path_factory.mktemp("invoices"), tmp_path_factory.mktemp("reports")
    every = {name: document for path in FILES for name, document in documents(path).items()}
    # Named by file name alone: two files of one name in different folders would clash.
    assert len(every) == (1 + len(PROFILES)) * len(FILES)
    for name, document in every.items():
        (invoices / name).write_bytes(document)
    command = [str(VALIDATOR), str(invoices), str(reports)]
    # Its exit status counts the rejected documents, so a report per document shows it ran; 137
    # is the kernel's kill, when it ran out of memory.
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=240)  # noqa: S603
    found = {path.name.removesuffix("-report.xml") + ".xml": path for path in reports.iterdir()}
    assert sorted(found) == sorted(every), (
        f"exit {result.returncode}\n{result.stdout}{result.stderr}"
    )
    return {name: root(path) for name, path in found.items()}


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


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_kosit_finds_what_validate_finds(reports: dict[str, Element], path: Path) -> None:
    for name, document in documents(path).items():
        findings = validate(document)
        # KoSIT's reports know no `fatal`: CEN's fatal rules show as `error`.
        ours = sorted(
            (finding.rule, "error" if finding.flag == "fatal" else finding.flag, finding.location)
            for finding in findings
        )
        assert (kosit(reports[name]), accepted(reports[name])) == (ours, is_valid(findings)), name


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

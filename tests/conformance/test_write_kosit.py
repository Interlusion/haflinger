"""The round trip over the KoSIT suite: every file's model written as CII, checked by the XML
Schema and the rules, and read back by both readers (REQ-004-PRS-F004 to REQ-004-PRS-F006)."""

from dataclasses import replace
from functools import cache
from pathlib import Path

import pytest

from haflinger import Finding, Invoice, InvoiceWriteError, _kosit, read_invoice, write_cii
from haflinger._cii import with_one_preceding_invoice

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/data/kosit-testsuite/instances"
FILES = sorted(SUITE.rglob("*.xml"))
XRECHNUNG = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"

# REQ-004-PRS-F005: the rules a written KoSIT file still fails, each with the business terms the
# model lacks for it (ADR-007). The list shrinks as the model grows.
MISSING_TERMS = {
    "BR-CO-16": "BG-DEX-09 third party payments of the XRechnung extension, which the extension"
    " allows into BT-115; outside the model by ADR-007, so the entry stays while the extension"
    " case is written as XRechnung",
}
# REQ-004-PRS-F005: the rules a written KoSIT file fails because the round trip writes it as
# XRechnung 3.0, not as XRechnung's extension or CVD, which aren't target profiles
# (REQ-004-PRS-F002), each with the code only its own profile allows. They stay while those
# cases are written as XRechnung.
OTHER_PROFILE = {
    "BR-CL-10": "BT-29-1, BT-46-1 and BT-60-1 with the schemes XR01 and XR03 for digital health"
    " apps, which only XRechnung's extension allows beside the ISO 6523 list",
    "BR-CL-13": "BT-158-1 with the scheme CVD of the Clean Vehicles Directive, which only"
    " XRechnung's CVD allows beside the UNTDID 7143 list",
}
# Rules listed above that may fail only on these files.
ONLY_ON = {
    "BR-CO-16": {"05.01a-INVOICE_ubl.xml"},
    "BR-CL-10": {"04.05a-INVOICE_uncefact.xml"},
    "BR-CL-13": {"02.01a-cvd_INVOICE_ubl.xml", "02.01a-cvd_INVOICE_uncefact.xml"},
}
EN16931 = "urn:cen.eu:en16931:2017"


@cache
def write(path: Path, profile: str = XRECHNUNG) -> tuple[Invoice, bytes, tuple[Finding, ...]]:
    """The file's model, the document written from it, and the findings of the refusal.

    The model's BT-24 becomes the target profile, XRechnung 3.0 unless another is given, as the
    suite's files also name XRechnung's extension and CVD, which aren't target profiles
    (REQ-004-PRS-F002); and its preceding invoices (BG-3) become the first where they are more
    than CII D16B can hold (REQ-004-PRS-F006)."""
    invoice = with_one_preceding_invoice(read_invoice(path.read_bytes()).invoice)
    if invoice.specification_id != profile:
        invoice = replace(invoice, specification_id=profile)
    try:
        return invoice, write_cii(invoice), ()
    except InvoiceWriteError as error:
        refusal = error
    assert refusal.document is not None, refusal
    return invoice, refusal.document, refusal.findings


def failed(findings: tuple[Finding, ...]) -> set[str]:
    return {finding.rule for finding in findings if finding.flag in ("fatal", "error")}


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_reads_back_with_haflinger(path: Path) -> None:
    invoice, document, _ = write(path)
    result = read_invoice(document)
    assert result.findings == ()
    assert result.invoice == invoice


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_reads_back_with_kosit(path: Path) -> None:
    invoice, document, _ = write(path)
    result = _kosit.read_invoice(document)
    assert result.findings == ()
    expected, read = _kosit.comparable(invoice, result.invoice)
    assert read == expected


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_fails_only_listed_rules(path: Path) -> None:
    """The document is schema-valid (no `HAFL-XSD`), and every rule it fails is listed."""
    _, _, findings = write(path)
    assert failed(findings) - set(MISSING_TERMS) - set(OTHER_PROFILE) == set()
    for rule, files in ONLY_ON.items():
        assert rule not in failed(findings) or path.name in files, rule


def test_every_listed_rule_still_fails() -> None:
    """Once no file fails a listed rule, its entry goes: a missing term's once the model holds
    it."""
    still = set[str]().union(*(failed(write(path)[2]) for path in FILES))
    assert set(MISSING_TERMS) - still == set()
    assert set(OTHER_PROFILE) - still == set()


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_written_as_en16931_passes_both_schemas_and_reads_back(path: Path) -> None:
    """REQ-004-PRS-F004: the EN 16931 target also passes Factur-X's XML Schema."""
    invoice, document, findings = write(path, EN16931)
    assert "HAFL-XSD" not in {finding.rule for finding in findings}
    assert read_invoice(document).invoice == invoice
    expected, read = _kosit.comparable(invoice, _kosit.read_invoice(document).invoice)
    assert read == expected

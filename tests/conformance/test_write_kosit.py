"""The round trip over the KoSIT suite: every file's model written as CII, checked by the XML
Schema and the rules, and read back by both readers (REQ-004-PRS-F004 to REQ-004-PRS-F006)."""

from dataclasses import replace
from functools import cache
from pathlib import Path

import pytest

from haflinger import Finding, Invoice, InvoiceWriteError, kosit, read_invoice, write_cii

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/data/kosit-testsuite/instances"
FILES = sorted(SUITE.rglob("*.xml"))
XRECHNUNG = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"

# REQ-004-PRS-F005: the rules a written KoSIT file still fails, each with the business terms the
# model lacks for it (ADR-007). The list shrinks as the model grows.
MISSING_TERMS = {
    "BR-DE-1": "BG-16 payment instructions",
    "BR-DE-2": "BG-6 seller contact",
    "BR-DE-3": "BT-37 seller city",
    "BR-DE-4": "BT-38 seller post code",
    "BR-DE-8": "BT-52 buyer city",
    "BR-DE-9": "BT-53 buyer post code",
    "PEPPOL-EN16931-R010": "BT-49 buyer electronic address",
    "PEPPOL-EN16931-R020": "BT-34 seller electronic address",
    "BR-CO-11": "BG-20 document level allowances",
    "BR-CO-12": "BG-21 document level charges",
    "BR-CO-26": "BT-29 seller identifier",
    "BR-AE-08": "BG-20 and BG-21, which enter the taxable amount (BT-116)",
    "BR-E-08": "BG-20 and BG-21, which enter the taxable amount (BT-116)",
    "BR-S-08": "BG-20 and BG-21, which enter the taxable amount (BT-116)",
    "BR-E-01": "BG-20 and BG-21, whose VAT category (BT-95, BT-102) the rule counts",
    "BR-CO-16": "BG-DEX-09 third party payments of the XRechnung extension, which the extension"
    " allows into BT-115; outside the model by ADR-007, so the entry stays while the extension"
    " case is written as XRechnung",
}
# Rules listed above that may fail only on these files.
ONLY_ON = {"BR-CO-16": {"05.01a-INVOICE_ubl.xml"}}
EN16931 = "urn:cen.eu:en16931:2017"


@cache
def write(path: Path) -> tuple[Invoice, bytes, tuple[Finding, ...]]:
    """The file's model, the document written from it, and the findings of the refusal.

    The model's BT-24 becomes XRechnung 3.0 where it names the extension or CVD, which aren't
    target profiles (REQ-004-PRS-F002)."""
    invoice = read_invoice(path.read_bytes()).invoice
    if invoice.specification_id != XRECHNUNG:
        invoice = replace(invoice, specification_id=XRECHNUNG)
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
    result = kosit.read_invoice(document)
    assert result.findings == ()
    assert result.invoice == invoice


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_fails_only_rules_that_need_missing_terms(path: Path) -> None:
    """The document is schema-valid (no `HAFL-XSD`), and every rule it fails is listed."""
    _, _, findings = write(path)
    assert failed(findings) - set(MISSING_TERMS) == set()
    for rule, files in ONLY_ON.items():
        assert rule not in failed(findings) or path.name in files, rule


def test_every_listed_rule_still_fails() -> None:
    """Once the model holds a rule's terms and no file fails it, its entry goes."""
    still = set[str]().union(*(failed(write(path)[2]) for path in FILES))
    assert set(MISSING_TERMS) - still == set()


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_written_as_en16931_passes_both_schemas_and_reads_back(path: Path) -> None:
    """REQ-004-PRS-F004: the EN 16931 target also passes Factur-X's XML Schema."""
    invoice = replace(read_invoice(path.read_bytes()).invoice, specification_id=EN16931)
    try:
        document, findings = write_cii(invoice), ()
    except InvoiceWriteError as error:
        document, findings = error.document, error.findings
    assert document is not None
    assert "HAFL-XSD" not in {finding.rule for finding in findings}
    assert read_invoice(document).invoice == invoice
    assert kosit.read_invoice(document).invoice == invoice

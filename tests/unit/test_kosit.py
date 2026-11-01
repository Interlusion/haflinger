"""The second reader through KoSIT's stylesheets (REQ-003-PRS-F005, ADR-005)."""

import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from haflinger import InvoiceReadError, kosit, read_invoice

ROOT = Path(__file__).resolve().parents[2]
CII = ROOT / "tests/data/kosit-testsuite/instances/standard/01.01a-INVOICE_uncefact.xml"


def test_reads_the_terms_by_their_id() -> None:
    invoice = kosit.read_invoice(CII.read_bytes()).invoice
    assert invoice.syntax == "cii"
    assert invoice.number == "123456XX"
    assert invoice.totals is not None
    assert invoice.totals.total_with_vat == Decimal("336.9")
    assert [line.item_name for line in invoice.lines] == [
        "Zeitschrift [...]",
        "Porto + Versandkosten",
    ]


def test_a_malformed_value_is_missing_with_a_finding() -> None:
    data = CII.read_bytes().replace(
        b">336.9</ram:GrandTotalAmount>", b">1E+2</ram:GrandTotalAmount>"
    )
    result = kosit.read_invoice(data)
    assert result.invoice.totals is not None
    assert result.invoice.totals.total_with_vat is None
    assert [(finding.rule, finding.text) for finding in result.findings] == [
        ("HAFL-VALUE", "BT-112 is not written as a number: '1E+2'; read as missing")
    ]


def test_reads_the_encoding_the_input_declares() -> None:
    text = CII.read_text(encoding="utf-8").replace("[Seller name]", "Exämple GmbH")
    data = text.replace('encoding="UTF-8"', 'encoding="windows-1252"', 1).encode("cp1252")
    invoice = kosit.read_invoice(data).invoice
    assert invoice.seller is not None
    assert invoice.seller.name == "Exämple GmbH"
    assert invoice == read_invoice(data).invoice


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"<Order/>", "neither a CII invoice nor a UBL invoice"),
        (b'<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>', "document type declaration"),
        (b"<x>", "not well-formed"),
    ],
)
def test_refuses_what_isnt_an_invoice(data: bytes, reason: str) -> None:
    with pytest.raises(InvoiceReadError, match=reason):
        kosit.read_invoice(data)


def test_read_invoice_runs_without_saxon() -> None:
    """KoSIT's stylesheet is not on the reading path, and importing Haflinger doesn't load Saxon
    (ADR-005)."""
    script = (
        "import sys, haflinger;"
        f"haflinger.read_invoice(open({str(CII)!r}, 'rb').read());"
        "assert 'saxonche' not in sys.modules, 'saxonche loaded'"
    )
    subprocess.run([sys.executable, "-c", script], check=True)  # noqa: S603

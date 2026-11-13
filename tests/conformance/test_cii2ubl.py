"""phax's converter `en16931-cii2ubl`, a mapping of its own from CII to UBL: the UBL copy it makes
of every invoice the round trip writes from the KoSIT suite, and of the corpus's CII invoices,
reads to the same model as the CII invoice (REQ-003-PRS-F009, ADR-005). It is Java, so it runs
where HAFLINGER_CII2UBL names it, as in CI (`scripts/cii2ubl.sh`)."""

import os
import subprocess
from dataclasses import replace
from decimal import Decimal
from functools import cache

import pytest
from test_read_kosit import term, without, zero_as_absent
from test_second_reader import PDFS
from test_write_kosit import FILES, write

from haflinger import Invoice, _xsd, read_invoice
from haflinger.pdf import extract_xml

CONVERTER = os.environ.get("HAFLINGER_CII2UBL")

# The CII invoices, by the name the converter gets: the round trip's from each file of the suite,
# and each corpus PDF's.
SOURCES = {f"written-{path.stem}.xml": path for path in FILES} | {
    f"{path.stem}.xml": path for path in PDFS
}

# The corpus invoices the converter refuses, as they fail the CII D16B XML Schema, with the reason.
FAILS_THE_SCHEMA = {
    f"MustangGnuaccountingBeispielRE-20190610_{n}.xml": "its ram:BuyerReference is in no namespace"
    for n in ("507a", "507b")
}
INVOICES = [name for name in SOURCES if name not in FAILS_THE_SCHEMA]

# REQ-003-PRS-F009: where the UBL copy reads differently from the CII invoice, by invoice and model
# path: the business term, the difference, and why: a limit of the converter's, or a known one of
# Haflinger's with its backlog item. The comparison leaves out only these terms.
PURCHASE_ORDER = {
    "purchase_order_reference": (
        "BT-13",
        "absent in CII, the text None in UBL",
        "the converter's: UBL's cac:OrderReference needs a cbc:ID beside BT-14's"
        " cbc:SalesOrderID, and the converter writes None",
    ),
}
SELLER_IDENTIFIERS = {
    "seller.identifiers": (
        "BT-29",
        "with and without a scheme in CII, in UBL only the one with a scheme",
        "the converter's: it takes CII's ram:GlobalID, not a ram:ID without a scheme",
    ),
}
WITHOUT_PAYMENT_MEANS = {
    "payment_instructions": (
        "BG-16",
        "only the remittance information (BT-83) in CII, absent in UBL",
        "the converter's: UBL holds BT-83 in cac:PaymentMeans, which needs a means code (BT-81),"
        " and the converter writes none where CII has no payment means",
    ),
}


def price_discounts(*lines: int) -> dict[str, tuple[str, str, str]]:
    return {
        f"lines.{line}.price_discount": (
            "BT-147",
            "absent in CII, 0 in UBL",
            "the converter's: it writes a price allowance of 0 where CII's gross price has none",
        )
        for line in lines
    }


KNOWN_DIFFERENCES: dict[str, dict[str, tuple[str, str, str]]] = {
    **{
        f"written-01.{n:02}a-INVOICE_uncefact.xml": PURCHASE_ORDER
        for n in (2, 8, 9, 10, 11, 12, 13)
    },
    **{
        f"written-{name}_uncefact.xml": SELLER_IDENTIFIERS
        for name in (
            "01.01_comprehensive_test",
            "02.01a-cvd_INVOICE",
            "03.07a-INVOICE",
            "04.05a-INVOICE",
        )
    },
    "written-01.05_minimal_test_uncefact.xml": {
        "totals.vat_total": (
            "BT-110",
            "absent in CII, 0 in UBL",
            "the converter's: UBL's cac:TaxTotal needs an amount where CII may leave it out",
        ),
    },
    "Avoir_FR_type380_EN16931.xml": WITHOUT_PAYMENT_MEANS | price_discounts(1),
    "Avoir_FR_type381_EN16931.xml": WITHOUT_PAYMENT_MEANS
    | price_discounts(1)
    | {
        "due_date": (
            "BT-9",
            "2017-11-16 in CII, absent in UBL",
            "the converter's: a UBL credit note holds BT-9 in cac:PaymentMeans, left out with"
            " BG-16",
        ),
    },
    **{f"Facture_{name}_EN16931.xml": price_discounts(1, 2) for name in ("DOM", "FR", "UE")},
    **{
        f"MustangGnuaccountingBeispielRE-{name}.xml": price_discounts(0, 1, 2)
        for name in ("20171118_506", "20190610_507", "20201121_508", "20201121_508_withBOM")
    },
    "ZUGFeRD_2.0_fully_compliant_complete.xml": {
        "seller.vat_id": (
            "BT-31",
            "absent as Haflinger reads CII, DE12345618938 in UBL",
            "Haflinger's: it leaves out a CII seller's tax registration with the scheme VAT, not"
            " VA, without a finding (the backlog's item on ram:SpecifiedTaxRegistration); the"
            " converter takes it",
        ),
    },
}

# REQ-003-PRS-F009: the converter writes amounts without trailing zeros, so the comparison takes
# them by value, as Decimal's == does; Haflinger's own tests check the digits as written.
TRAILING_ZEROS = (
    "written-03.06a-INVOICE_uncefact.xml",
    "totals.line_net_total",
    ("BT-106", "1500.00 in CII, 1500 in UBL", "the converter's: it writes amounts anew"),
)


@cache
def cii(name: str) -> bytes:
    path = SOURCES[name]
    return extract_xml(path.read_bytes()) if path.suffix == ".pdf" else write(path)[1]


def needs_converter() -> str:
    """Skips before any invoice is written, where no converter is named."""
    if not CONVERTER:
        pytest.skip("HAFLINGER_CII2UBL names no en16931-cii2ubl")
    return CONVERTER


@pytest.fixture(scope="module")
def copies(tmp_path_factory: pytest.TempPathFactory) -> dict[str, bytes]:
    """The converter's UBL copy of each invoice, from one call: Java starts once."""
    converter = needs_converter()
    directory = tmp_path_factory.mktemp("cii2ubl")
    invoices, output = directory / "invoices", directory / "output"
    invoices.mkdir()
    output.mkdir()
    for name in INVOICES:
        (invoices / name).write_bytes(cii(name))
    command = [converter, str(invoices), str(output)]
    # It exits with 0 even where it refuses an invoice, so a copy per invoice shows it converted.
    # The time to build its image comes before the converter's own limit of 120 s.
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=240)  # noqa: S603
    found = {path.name.removesuffix("-ubl.xml") + ".xml": path for path in output.iterdir()}
    assert sorted(found) == sorted(INVOICES), (
        f"exit {result.returncode}\n{result.stdout}{result.stderr}"
    )
    return {name: path.read_bytes() for name, path in found.items()}


def comparable(invoice: Invoice, name: str) -> Invoice:
    invoice = replace(invoice, syntax="cii")
    for path in KNOWN_DIFFERENCES.get(name, {}):
        invoice = without(invoice, path)
    return zero_as_absent(invoice)


def test_the_invoices_are_there() -> None:
    assert len(FILES) == 86
    assert len(INVOICES) == 86 + 10


def test_the_converter_gets_the_cii_invoices_that_pass_the_schema() -> None:
    assert {read_invoice(cii(name)).invoice.syntax for name in SOURCES} == {"cii"}
    assert {name for name in SOURCES if _xsd.check(cii(name), _xsd.CII)} == set(FAILS_THE_SCHEMA)


@pytest.mark.parametrize("name", INVOICES)
def test_the_ubl_copy_reads_as_the_cii_invoice(copies: dict[str, bytes], name: str) -> None:
    copy = read_invoice(copies[name])
    assert copy.findings == ()
    assert copy.invoice.syntax == "ubl"
    original = read_invoice(cii(name)).invoice
    assert comparable(copy.invoice, name) == comparable(original, name)


@pytest.mark.parametrize(
    ("name", "path"), [(name, path) for name, paths in KNOWN_DIFFERENCES.items() for path in paths]
)
def test_known_differences_are_still_there(copies: dict[str, bytes], name: str, path: str) -> None:
    """Once a new release of the converter, or Haflinger, removes a difference, its record goes."""
    original, copy = (read_invoice(document).invoice for document in (cii(name), copies[name]))
    assert term(original, path) != term(copy, path)


def test_the_converter_still_drops_trailing_zeros(copies: dict[str, bytes]) -> None:
    """Once a new release keeps an amount's digits, the comparison can take them as written."""
    name, path, _ = TRAILING_ZEROS
    original, copy = (read_invoice(document).invoice for document in (cii(name), copies[name]))
    assert (term(original, path), term(copy, path)) == (Decimal("1500.00"), Decimal("1500"))
    assert str(term(original, path)) != str(term(copy, path))


def test_the_copy_writes_dates_anew(copies: dict[str, bytes]) -> None:
    """Where it writes a value anew, the converter checks Haflinger's parsing too."""
    name = "written-01.01a-INVOICE_uncefact.xml"
    assert b'<udt:DateTimeString format="102">20160404</udt:DateTimeString>' in cii(name)
    assert b"<cbc:IssueDate>2016-04-04</cbc:IssueDate>" in copies[name]

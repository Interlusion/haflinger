"""Reading the KoSIT test suite and CEN's UBL credit note.

REQ-003-PRS-F001, REQ-003-PRS-F002 (VAT totals by currency), REQ-003-PRS-F004; REQ-001-PRS-F001;
REQ-002-PRS-F008 for the differences between the CII and UBL files of a business case.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from haflinger import (
    Contact,
    CreditTransfer,
    Identifier,
    Invoice,
    InvoiceLine,
    Note,
    Party,
    PaymentInstructions,
    Period,
    Totals,
    VatBreakdown,
    read_invoice,
)

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/data/kosit-testsuite/instances"
CREDIT_NOTE = ROOT / "tests/data/cen-en16931/ubl/examples/ubl-tc434-creditnote1.xml"

FILES = sorted(SUITE.rglob("*.xml"))
# A business case is a UBL file with its CII counterpart; the extension cases come in one syntax.
CASES = {
    str(path.relative_to(SUITE)).removesuffix("_ubl.xml"): (
        path.with_name(path.name.replace("_ubl.xml", "_uncefact.xml")),
        path,
    )
    for path in FILES
    if path.name.endswith("_ubl.xml")
    and path.with_name(path.name.replace("_ubl.xml", "_uncefact.xml")).exists()
}

# REQ-002-PRS-F008: where the CII and UBL file of a case differ, by case and model path: the
# business term, the difference, and the upstream report or why there is none. The comparison
# leaves out only these terms.
NOT_YET_REPORTED = "not reported yet (ITEM-006)"
PLACEHOLDERS = "none: different placeholder texts"
SELLER_IDENTIFIERS = {
    "seller.identifiers": (
        "BT-29",
        "three in CII, in UBL only the one with scheme 0088",
        NOT_YET_REPORTED,
    ),
}
CONTACT_POINT = {
    "seller.contact.point": (
        "BT-41",
        "the department name Testorganisation in CII, Tim Tester in UBL",
        NOT_YET_REPORTED,
    ),
}
PURCHASE_ORDER = {
    "purchase_order_reference": (
        "BT-13",
        "only the UBL file has one, Dummywert",
        "ask whether it is deliberate (ITEM-006)",
    ),
}
PAYEE_LEGAL_REGISTRATION = {
    "payee.legal_registration_id": ("BT-61", "only the CII file has one", NOT_YET_REPORTED),
}
SECOND_LINES_BASE_QUANTITY = {
    "lines.1.base_quantity": ("BT-149", "only the UBL file has one", NOT_YET_REPORTED),
    "lines.1.base_quantity_unit_code": ("BT-150", "only the UBL file has one", NOT_YET_REPORTED),
}
ONE_PRECEDING_INVOICE = {
    "preceding_invoices": (
        "BG-3",
        "two in UBL, one in CII",
        "none: CII D16B holds one preceding invoice reference",
    ),
}
KNOWN_DIFFERENCES: dict[str, dict[str, tuple[str, str, str]]] = {
    **{f"standard/01.{n:02}a-INVOICE": PURCHASE_ORDER for n in (2, 8, 9, 10, 11, 12, 13)},
    "standard/01.20a-INVOICE": {
        "seller.address_line_1": ("BT-35", "[Street] in CII, [Seller street] in UBL", PLACEHOLDERS),
        "seller.city": ("BT-37", "[City] in CII, [Seller city] in UBL", PLACEHOLDERS),
    },
    "standard/01.21a-INVOICE": {
        "seller.vat_id": ("BT-31", "DE152338654 in CII, DE 123456789 in UBL", NOT_YET_REPORTED),
        "payment_instructions.means_text": (
            "BT-82",
            "Rechnung in CII, Information in UBL",
            NOT_YET_REPORTED,
        ),
        "vat_breakdown.0.exemption_reason": (
            "BT-120",
            "different texts in CII and UBL",
            NOT_YET_REPORTED,
        ),
    },
    "standard/03.01a-INVOICE": {
        "buyer.trading_name": ("BT-45", "only the UBL file has one", NOT_YET_REPORTED),
    },
    "standard/03.06a-INVOICE": {
        path: (term, "the UBL file swaps city and post code", NOT_YET_REPORTED)
        for path, term in (
            ("seller.city", "BT-37"),
            ("seller.post_code", "BT-38"),
            ("buyer.city", "BT-52"),
            ("buyer.post_code", "BT-53"),
        )
    },
    "standard/03.07a-INVOICE": SELLER_IDENTIFIERS | PAYEE_LEGAL_REGISTRATION,
    "technical-cases/cvd/02.01a-cvd_INVOICE": SELLER_IDENTIFIERS
    | PAYEE_LEGAL_REGISTRATION
    | {
        "lines.0.item_description": (
            "BT-154",
            "Gruppe von Fahrzeugde XY in CII, Gruppe von Fahrzeug XY in UBL",
            NOT_YET_REPORTED,
        ),
    },
    **{
        f"technical-cases/cius/01.0{n}_comprehensive_test": {
            "buyer.name": (
                "BT-44",
                "the UBL file has the trading name's placeholder as the name",
                NOT_YET_REPORTED,
            ),
            "buyer.trading_name": (
                "BT-45",
                "the UBL file has the name's placeholder as the trading name",
                NOT_YET_REPORTED,
            ),
            **SECOND_LINES_BASE_QUANTITY,
            **PAYEE_LEGAL_REGISTRATION,
            **{
                1: SELLER_IDENTIFIERS | ONE_PRECEDING_INVOICE,
                3: CONTACT_POINT,
                4: CONTACT_POINT,
            }.get(n, {}),
        }
        for n in range(1, 5)
    },
    "technical-cases/cius/01.05_minimal_test": {
        "totals.vat_total": (
            "BT-110",
            "absent in CII, 0 in UBL",
            "none: the term is optional, and UBL's cac:TaxTotal needs an amount where CII may"
            " leave it out",
        ),
    },
}

# An optional sum one file gives as zero and the other leaves out counts as agreeing.
ZERO_OR_ABSENT = ("allowance_total", "charge_total", "prepaid_amount", "rounding_amount")


def without(value: Any, path: str) -> Any:
    """`value` with the term at the dotted `path` set to None."""
    head, _, rest = path.partition(".")
    if isinstance(value, tuple):
        items = list(cast(tuple[Any, ...], value))
        items[int(head)] = without(items[int(head)], rest)
        return tuple(items)
    return replace(value, **{head: without(getattr(value, head), rest) if rest else None})


def term(value: Any, path: str) -> Any:
    for part in path.split("."):
        value = cast(tuple[Any, ...], value)[int(part)] if part.isdigit() else getattr(value, part)
    return value


def comparable(invoice: Invoice, case: str) -> Invoice:
    for path in KNOWN_DIFFERENCES.get(case, {}):
        invoice = without(invoice, path)
    if invoice.totals is not None:
        zeros = {name: None for name in ZERO_OR_ABSENT if getattr(invoice.totals, name) == 0}
        invoice = replace(invoice, totals=replace(invoice.totals, **zeros))
    return invoice


def read(path: Path) -> Invoice:
    return read_invoice(path.read_bytes()).invoice


def test_the_suite_is_there() -> None:
    assert len(FILES) == 86
    assert len(CASES) == 40


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_every_file_reads_with_its_syntax_and_without_findings(path: Path) -> None:
    result = read_invoice(path.read_bytes())
    assert result.invoice.syntax == ("cii" if path.stem.endswith("uncefact") else "ubl")
    assert result.findings == ()


@pytest.mark.parametrize("case", CASES)
def test_cii_and_ubl_agree(case: str) -> None:
    cii, ubl = CASES[case]
    assert comparable(read(cii), case) == comparable(read(ubl), case)


@pytest.mark.parametrize(
    ("case", "path"), [(case, path) for case, paths in KNOWN_DIFFERENCES.items() for path in paths]
)
def test_known_differences_are_still_there(case: str, path: str) -> None:
    """Once a new release of the suite removes a difference, its record goes."""
    cii, ubl = CASES[case]
    assert term(read(cii), path) != term(read(ubl), path)


EXPECTED_01_01A = Invoice(
    number="123456XX",
    issue_date=date(2016, 4, 4),
    type_code="380",
    currency_code="EUR",
    buyer_reference="04011000-12345-03",
    business_process="urn:fdc:peppol.eu:2017:poacc:billing:01:1.0",
    specification_id="urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0",
    payment_terms="Zahlbar sofort ohne Abzug.",
    notes=(
        Note(
            subject_code="ADU",
            text="Es gelten unsere Allgem. Geschäftsbedingungen, die Sie unter […] finden.",
        ),
    ),
    seller=Party(
        name="[Seller name]",
        trading_name="[Seller trading name]",
        legal_registration_id=Identifier(value="[HRA-Eintrag]"),
        additional_legal_information="123/456/7890, HRA-Eintrag in […]",
        vat_id="DE 123456789",
        electronic_address=Identifier(value="seller@email.de", scheme="EM"),
        address_line_1="[Seller address line 1]",
        city="[Seller city]",
        post_code="12345",
        country_code="DE",
        contact=Contact(
            point="nicht vorhanden", telephone="+49 1234-5678", email="seller@email.de"
        ),
    ),
    buyer=Party(
        name="[Buyer name]",
        identifiers=(Identifier(value="[Buyer identifier]"),),
        electronic_address=Identifier(value="buyer@info.de", scheme="EM"),
        address_line_1="[Buyer address line 1]",
        city="[Buyer city]",
        post_code="12345",
        country_code="DE",
    ),
    payment_instructions=PaymentInstructions(
        means_code="58",
        credit_transfers=(CreditTransfer(account_id="DE79000000001234567890"),),
    ),
    totals=Totals(
        line_net_total=Decimal("314.86"),
        total_without_vat=Decimal("314.86"),
        vat_total=Decimal("22.04"),
        total_with_vat=Decimal("336.9"),
        amount_due=Decimal("336.9"),
    ),
    vat_breakdown=(
        VatBreakdown(
            taxable_amount=Decimal("314.86"),
            tax_amount=Decimal("22.04"),
            category_code="S",
            rate=Decimal(7),
        ),
    ),
    lines=(
        InvoiceLine(
            id="Zeitschrift [...]",
            note="Die letzte Lieferung im Rahmen des abgerechneten Abonnements erfolgt in 12/2016"
            " Lieferung erfolgt / erfolgte direkt vom Verlag",
            quantity=Decimal(1),
            unit_code="XPP",
            net_amount=Decimal("288.79"),
            period=Period(start=date(2016, 1, 1), end=date(2016, 12, 31)),
            net_price=Decimal("288.79"),
            vat_category_code="S",
            vat_rate=Decimal(7),
            item_name="Zeitschrift [...]",
            item_description="Zeitschrift Inland",
            seller_item_id="246",
        ),
        InvoiceLine(
            id="Porto + Versandkosten",
            quantity=Decimal(1),
            unit_code="XPP",
            net_amount=Decimal("26.07"),
            net_price=Decimal("26.07"),
            vat_category_code="S",
            vat_rate=Decimal(7),
            item_name="Porto + Versandkosten",
        ),
    ),
)


@pytest.mark.parametrize("syntax", ["cii", "ubl"])
def test_01_01a_reads_to_the_exact_model(syntax: str) -> None:
    cii, ubl = CASES["standard/01.01a-INVOICE"]
    assert read(cii if syntax == "cii" else ubl) == EXPECTED_01_01A


@pytest.mark.parametrize("syntax", ["cii", "ubl"])
def test_vat_totals_by_currency(syntax: str) -> None:
    cii, ubl = CASES["standard/02.01a-INVOICE"]
    invoice = read(cii if syntax == "cii" else ubl)
    assert (invoice.currency_code, invoice.tax_currency_code) == ("EUR", "GBP")
    assert invoice.totals is not None
    assert invoice.totals.vat_total == Decimal("2048.44")
    assert invoice.totals.vat_total_in_tax_currency == Decimal("2048.44")


def test_reads_a_ubl_credit_note() -> None:
    result = read_invoice(CREDIT_NOTE.read_bytes())
    assert result.invoice.syntax == "ubl"
    assert result.invoice.type_code == "381"
    assert len(result.invoice.lines) == 1
    assert result.invoice.lines[0].quantity is not None
    assert result.findings == ()

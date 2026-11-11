"""The public interface: two public modules and what their `__all__` lists (REQ-001-PRS-F006,
ADR-012)."""

import pkgutil

import haflinger
from haflinger import pdf

MODEL = {
    "AllowanceCharge",
    "Attachment",
    "Contact",
    "CreditTransfer",
    "Delivery",
    "DirectDebit",
    "Identifier",
    "Invoice",
    "InvoiceLine",
    "ItemAttribute",
    "ItemClassification",
    "Note",
    "Party",
    "Payee",
    "PaymentCard",
    "PaymentInstructions",
    "Period",
    "PrecedingInvoice",
    "SupportingDocument",
    "TaxRepresentative",
    "Totals",
    "VatBreakdown",
}
PUBLIC = MODEL | {
    "read_invoice",
    "validate",
    "write_cii",
    "Syntax",
    "ReadResult",
    "Finding",
    "Flag",
    "is_valid",
    "TARGET_PROFILES",
    "InvoiceReadError",
    "InvoiceWriteError",
}
ENTRY_POINTS = ("read_invoice", "validate", "write_cii", "extract_xml", "embed")


def test_every_module_but_the_package_and_pdf_is_private() -> None:
    public = [
        module.name
        for module in pkgutil.walk_packages(haflinger.__path__, "haflinger.")
        if not module.name.rpartition(".")[2].startswith("_")
    ]
    assert public == ["haflinger.pdf"]


def test_the_package_exports_exactly_its_api() -> None:
    assert sorted(haflinger.__all__) == sorted(PUBLIC)


def test_pdf_exports_extract_xml_and_embed() -> None:
    assert sorted(pdf.__all__) == ["embed", "extract_xml"]


def test_every_exported_name_resolves() -> None:
    for module in (haflinger, pdf):
        for name in module.__all__:
            assert hasattr(module, name), f"{module.__name__}.{name}"


def test_the_package_docstring_names_the_entry_points() -> None:
    assert haflinger.__doc__ is not None
    for name in ENTRY_POINTS:
        assert f"`{name}(" in haflinger.__doc__, name

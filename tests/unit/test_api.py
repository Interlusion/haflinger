"""The public interface: two public modules and what their `__all__` lists (REQ-001-PRS-F006,
ADR-012), and none of Frappe loaded by using it (REQ-001-PRS-NF002)."""

import json
import os
import pkgutil
import subprocess
import sys
from pathlib import Path

import haflinger
from haflinger import pdf

ROOT = Path(__file__).resolve().parents[2]
STANDARD = ROOT / "tests/data/kosit-testsuite/instances/standard"

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


USE = """
import importlib, importlib.util, json, pkgutil, sys
from dataclasses import replace
from pathlib import Path
import haflinger
from haflinger import _saxon, read_invoice, validate, write_cii
from haflinger.pdf import embed

for module in pkgutil.walk_packages(haflinger.__path__, "haflinger."):
    importlib.import_module(module.name)
cii, ubl, pdfa = (Path(path).read_bytes() for path in sys.argv[1:])
read_invoice(ubl)
findings = validate(cii)
invoice = replace(read_invoice(cii).invoice, specification_id="urn:cen.eu:en16931:2017")
read_invoice(embed(pdfa, write_cii(invoice)))
print(json.dumps({
    "stand-in": importlib.util.find_spec("frappe").origin,
    "rules": sorted({finding.rule for finding in findings}),
    "worker": _saxon.worker_pid() is not None,
    "loaded": sorted({name.split(".")[0] for name in sys.modules} & {"frappe", "erpnext"}),
}))
"""


def test_no_frappe_is_loaded(tmp_path: Path) -> None:
    """Where Frappe and ERPNext are importable, as in a bench: stand-ins on the import path that
    leave a mark when imported, also by the rules' worker process, which inherits the path. The
    library is imported whole and used in a fresh interpreter: reading CII, UBL and a ZUGFeRD
    PDF, validating with the rules' worker, writing and embedding."""
    marks = tmp_path / "marks"
    marks.mkdir()
    for name in ("frappe", "erpnext"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "__init__.py").write_text(
            f"from pathlib import Path\nPath({str(marks / name)!r}).touch()\n", encoding="utf-8"
        )
    pdfa = next((ROOT / "tests/data/verapdf-corpus").rglob("*.pdf"))
    files = [STANDARD / "01.01a-INVOICE_uncefact.xml", STANDARD / "01.01a-INVOICE_ubl.xml", pdfa]
    path = os.pathsep.join(filter(None, [str(tmp_path), os.environ.get("PYTHONPATH")]))
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", USE, *map(str, files)],
        env=os.environ | {"PYTHONPATH": path},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "stand-in": str(tmp_path / "frappe/__init__.py"),
        "rules": ["BR-DE-TMP-32"],
        "worker": True,
        "loaded": [],
    }
    assert not list(marks.iterdir())

"""Time and memory of reading, validating and writing, against the limits of REQ-002-PRS-NF002,
REQ-003-PRS-NF002 and REQ-004-PRS-NF001. Prints a Markdown table, with the machine it ran on, to
record with a release. The large invoices come from a clone of the ZUGFeRD corpus (development
guide); without it, their rows are skipped.

    uv run python scripts/benchmark.py [<ZUGFeRD corpus clone>]
"""

import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import replace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from haflinger import Party, Totals, cii, read_invoice, validate
from haflinger._input import open_invoice
from haflinger._xml import MAX_SIZE
from haflinger._xsd import check
from haflinger.validation import _RULE_SETS as RULE_SETS  # pyright: ignore[reportPrivateUsage]
from haflinger.validation import _scenarios, rule_set  # pyright: ignore[reportPrivateUsage]

ROOT = Path(__file__).resolve().parents[1]
SUITE = sorted((ROOT / "tests/data/kosit-testsuite/instances").rglob("*.xml"))
CREDIT_NOTE = ROOT / "tests/data/cen-en16931/ubl/examples/ubl-tc434-creditnote1.xml"
SUITE_CII = ROOT / "tests/data/kosit-testsuite/instances/standard/01.01a-INVOICE_uncefact.xml"
SUITE_UBL = ROOT / "tests/data/kosit-testsuite/instances/standard/01.01a-INVOICE_ubl.xml"
LARGE_1 = "PEPPOL/Valid/Qvalia/Large_Invoice_sample1.xml"  # 25.7 MB
LARGE_2 = "PEPPOL/Valid/Qvalia/Large_Invoice_sample2.xml"  # 61.1 MB

# Run in a fresh process: prints the seconds of the measured step and the peak memory in bytes.
MEASURE = """
import resource, sys, time
from pathlib import Path
step, path = sys.argv[1], Path(sys.argv[2])
start = time.perf_counter()
from haflinger import cii, read_invoice, validate
data = path.read_bytes()
if step == "write":
    invoice = cii.with_one_preceding_invoice(read_invoice(data).invoice)
    start = time.perf_counter()
    cii.write(invoice)
elif step == "read":
    start = time.perf_counter()
    read_invoice(data)
elif step == "validate-first":
    validate(data)
else:
    start = time.perf_counter()
    validate(data)
seconds = time.perf_counter() - start
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(seconds, peak if sys.platform == "darwin" else peak * 1024)
"""


def fresh(step: str, path: Path) -> tuple[float, int] | str:
    """Seconds and peak memory of `step` in a fresh process, or why it failed."""
    command = [sys.executable, "-c", MEASURE, step, str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        lines = result.stderr.strip().splitlines()
        return f"failed: {lines[-1] if lines else result.returncode}"
    seconds, peak = result.stdout.split()
    return float(seconds), int(peak)


def timed[T](action: Callable[[T], object], items: list[T]) -> list[float]:
    times: list[float] = []
    for item in items:
        start = time.perf_counter()
        action(item)
        times.append(time.perf_counter() - start)
    return times


def per_file(action: Callable[[bytes], object], paths: list[Path]) -> list[float]:
    return timed(action, [path.read_bytes() for path in paths])


def ms(times: list[float]) -> str:
    return f"max {max(times) * 1000:.1f} ms, median {statistics.median(times) * 1000:.1f} ms"


def processor() -> str:
    """The processor's model and its number of logical cores."""
    model = platform.processor() or platform.machine()
    try:
        lscpu = subprocess.run(["lscpu"], capture_output=True, text=True, check=True).stdout  # noqa: S607
    except OSError, subprocess.CalledProcessError:
        lscpu = ""
    fields = dict(line.split(":", 1) for line in lscpu.splitlines() if ":" in line)
    name, vendor = fields.get("Model name", "").strip(), fields.get("Vendor ID", "").strip()
    if name and name != "-":
        model = name
    elif vendor:
        model = f"{vendor} {platform.machine()}"
    return f"{model}, {os.cpu_count()} logical cores"


def rule_set_samples(directory: Path) -> dict[str, Path]:
    """One file per rule set, by the rule set's name: an official file where one is vendored,
    otherwise one written into `directory` that passes the rule set's XML Schema, so that its
    rules run: a copy with BT-24 changed, for Factur-X KoSIT case 01.01a's model written as CII
    and reduced to what MINIMUM and BASIC WL hold."""
    samples: dict[str, Path] = {}
    for path in [*SUITE, CREDIT_NOTE]:
        name, _ = rule_set(open_invoice(path.read_bytes(), MAX_SIZE, pdf="a PDF"))
        samples.setdefault(name, path)
    bases = {
        "cii": SUITE_CII.read_bytes(),
        "ubl-invoice": SUITE_UBL.read_bytes(),
        "ubl-credit-note": CREDIT_NOTE.read_bytes(),
    }
    for (document, specification_id), name in RULE_SETS.items():
        if name in samples:
            continue
        if name.startswith("Factur-X"):
            data = factur_x(specification_id)
            if check(data, _scenarios()[name].schema):
                raise SystemExit(f"the sample for {name} fails its XML Schema; its rules won't run")
        else:
            base = bases[document]
            current = re.search(rb"(?:CustomizationID|ram:ID)>(urn:cen\.eu:[^<]*)<", base)
            if current is None:
                raise SystemExit(f"no BT-24 to change in the sample for {name}")
            data = base.replace(current[1], specification_id.encode(), 1)
        samples[name] = directory / f"{len(samples)}.xml"
        samples[name].write_bytes(data)
    return samples


def factur_x(specification_id: str) -> bytes:
    model = read_invoice(SUITE_CII.read_bytes()).invoice
    totals, seller, buyer = model.totals, model.seller, model.buyer
    if totals is None or seller is None or buyer is None:
        raise SystemExit("KoSIT case 01.01a has changed")
    if "minimum" in specification_id or "basicwl" in specification_id:
        model = replace(
            model,
            notes=(),
            lines=(),
            buyer_reference=None,
            supporting_documents=(),
            # The parties' terms that every profile's XML Schema allows.
            seller=Party(
                name=seller.name,
                legal_registration_id=seller.legal_registration_id,
                vat_id=seller.vat_id,
                country_code=seller.country_code,
            ),
            buyer=Party(name=buyer.name, country_code=buyer.country_code),
            totals=Totals(
                line_net_total=None if "minimum" in specification_id else totals.line_net_total,
                total_without_vat=totals.total_without_vat,
                vat_total=totals.vat_total,
                total_with_vat=totals.total_with_vat,
                amount_due=totals.amount_due,
            ),
        )
    elif "basic" in specification_id:
        # BASIC has no seller contact, additional legal information or supporting documents, and
        # of an item only its standard identifier and its name.
        model = replace(
            model,
            supporting_documents=(),
            seller=replace(seller, contact=None, additional_legal_information=None),
            lines=tuple(
                replace(line, item_description=None, seller_item_id=None, buyer_item_id=None)
                for line in model.lines
            ),
        )
    if "minimum" in specification_id:
        model = replace(
            model,
            vat_breakdown=(),
            buyer=Party(name=buyer.name),
            payee=None,
            tax_representative=None,
            payment_terms=None,
            payment_instructions=None,
            preceding_invoices=(),
            delivery=None,
            invoicing_period=None,
            allowances=(),
            charges=(),
        )
    return cii.write(replace(model, specification_id=specification_id))


def installed(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not installed"


def main(arguments: list[str]) -> int:
    with tempfile.TemporaryDirectory(prefix="haflinger-benchmark-") as directory:
        return measure(Path(arguments[0]) if arguments else None, Path(directory))


def measure(corpus: Path | None, scratch: Path) -> int:
    rows: list[tuple[str, str, str, str]] = []

    models = [cii.with_one_preceding_invoice(read_invoice(p.read_bytes()).invoice) for p in SUITE]
    rows.append(
        ("REQ-003-PRS-NF002", "Read a KoSIT file", "20 ms", ms(per_file(read_invoice, SUITE)))
    )
    write_times = timed(cii.write, models)
    rows.append(
        (
            "REQ-004-PRS-NF001",
            "Write a KoSIT file's model, without checks",
            "10 ms",
            ms(write_times),
        )
    )
    for name, path in rule_set_samples(scratch).items():
        measured = fresh("validate-first", path)
        rows.append(
            (
                "REQ-002-PRS-NF002",
                f"First validation in a fresh process: {name}",
                "2 s",
                measured if isinstance(measured, str) else f"{measured[0]:.2f} s",
            )
        )
    per_file(validate, SUITE)  # every rule set compiled
    rows.append(
        ("REQ-002-PRS-NF002", "Validate a KoSIT file", "50 ms", ms(per_file(validate, SUITE)))
    )

    large = [
        ("REQ-003-PRS-NF002", "read", LARGE_1, "Read the 25.7 MB Peppol invoice", "-"),
        ("REQ-003-PRS-NF002", "read", LARGE_2, "Read the 61.1 MB Peppol invoice", "10 s"),
        ("REQ-002-PRS-NF002", "validate", LARGE_1, "Validate the 25.7 MB Peppol invoice", "30 s"),
        (
            "REQ-002-PRS-NF002",
            "validate",
            LARGE_2,
            "Validate the 61.1 MB Peppol invoice",
            "60 s",
        ),
        (
            "REQ-004-PRS-NF001",
            "write",
            LARGE_1,
            "Write the 25.7 MB invoice's model, without checks",
            "5 s",
        ),
    ]
    for requirement, step, name, what, limit in large:
        path = None if corpus is None else corpus / name
        if path is None or not path.is_file():
            rows.append((requirement, what, limit, "skipped: no corpus clone"))
            continue
        measured = fresh(step, path)
        if not isinstance(measured, str):
            seconds, peak = measured
            measured = f"{seconds:.1f} s, peak memory {peak / 2**20:.0f} MiB"
        rows.append((requirement, what, limit, measured))

    system = f"{platform.system()} {platform.machine()}, Python {platform.python_version()}"
    print(f"Machine: {processor()}; {system}")
    packages = ("haflinger", "saxonche", "lxml", "pypdf", "factur-x")
    print("Versions: " + ", ".join(f"{name} {installed(name)}" for name in packages))
    print()
    print("| Requirement | Measured step | Limit | Measured |")
    print("| :- | :- | :- | :- |")
    for row in rows:
        print("| " + " | ".join(row) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

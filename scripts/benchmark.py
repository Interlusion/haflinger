"""Time and memory of reading, validating and writing, against the limits of REQ-002-PRS-NF002,
REQ-003-PRS-NF002 and REQ-004-PRS-NF001. Prints a Markdown table, with the machine it ran on, to
record with a release. The large invoices come from a clone of the ZUGFeRD corpus (development
guide); without it, their rows are skipped.

    uv run python scripts/benchmark.py [<ZUGFeRD corpus clone>]
"""

import os
import platform
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

from haflinger import cii, read_invoice, validate

ROOT = Path(__file__).resolve().parents[1]
SUITE = sorted((ROOT / "tests/data/kosit-testsuite/instances").rglob("*.xml"))
CREDIT_NOTE = ROOT / "tests/data/cen-en16931/ubl/examples/ubl-tc434-creditnote1.xml"
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
    invoice = read_invoice(data).invoice
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


def fresh(step: str, path: Path) -> tuple[float, int]:
    command = [sys.executable, "-c", MEASURE, step, str(path)]
    output = subprocess.run(command, capture_output=True, text=True, check=True).stdout  # noqa: S603
    seconds, peak = output.split()
    return float(seconds), int(peak)


def per_file(action: Callable[[bytes], object], paths: list[Path]) -> list[float]:
    times: list[float] = []
    for path in paths:
        data = path.read_bytes()
        start = time.perf_counter()
        action(data)
        times.append(time.perf_counter() - start)
    return times


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


def rule_set_samples() -> list[Path]:
    """One file per rule set the official files exercise: by root element and BT-24."""
    samples: dict[tuple[str | None, bool, str | None], Path] = {}
    for path in [*SUITE, CREDIT_NOTE]:
        data = path.read_bytes()
        invoice = read_invoice(data).invoice
        key = (invoice.syntax, b"CreditNote-2" in data[:2000], invoice.specification_id)
        samples.setdefault(key, path)
    return list(samples.values())


def main(arguments: list[str]) -> int:
    corpus = Path(arguments[0]) if arguments else None
    rows: list[tuple[str, str, str, str]] = []

    models = [read_invoice(path.read_bytes()).invoice for path in SUITE]
    rows.append(
        ("REQ-003-PRS-NF002", "Read a KoSIT file", "20 ms", ms(per_file(read_invoice, SUITE)))
    )
    write_times: list[float] = []
    for invoice in models:
        start = time.perf_counter()
        cii.write(invoice)
        write_times.append(time.perf_counter() - start)
    rows.append(
        (
            "REQ-004-PRS-NF001",
            "Write a KoSIT file's model, without checks",
            "10 ms",
            ms(write_times),
        )
    )
    for path in rule_set_samples():
        seconds, _ = fresh("validate-first", path)
        name = path.relative_to(ROOT / "tests/data").as_posix()
        rows.append(
            (
                "REQ-002-PRS-NF002",
                f"First validation in a fresh process: `{name}`",
                "2 s",
                f"{seconds:.2f} s",
            )
        )
    per_file(validate, SUITE)  # every rule set compiled
    rows.append(
        ("REQ-002-PRS-NF002", "Validate a KoSIT file", "50 ms", ms(per_file(validate, SUITE)))
    )

    large = [
        ("REQ-003-PRS-NF002", "read", LARGE_2, "Read the 61.1 MB Peppol invoice", "10 s"),
        ("REQ-002-PRS-NF002", "validate", LARGE_1, "Validate the 25.7 MB Peppol invoice", "30 s"),
        (
            "REQ-002-PRS-NF002",
            "validate",
            LARGE_2,
            "Validate the 61.1 MB Peppol invoice",
            "to be set",
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
        seconds, peak = fresh(step, path)
        rows.append(
            (requirement, what, limit, f"{seconds:.1f} s, peak memory {peak / 2**20:.0f} MiB")
        )

    system = f"{platform.system()} {platform.machine()}, Python {platform.python_version()}"
    print(f"Machine: {processor()}; {system}")
    packages = ("haflinger", "saxonche", "lxml", "pypdf", "factur-x")
    print("Versions: " + ", ".join(f"{name} {version(name)}" for name in packages))
    print()
    print("| Requirement | Measured step | Limit | Measured |")
    print("| :- | :- | :- | :- |")
    for row in rows:
        print("| " + " | ".join(row) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

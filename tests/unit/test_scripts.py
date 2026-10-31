"""The scripts in `scripts/`, run on the vendored files: the corpus report and the benchmark
(development guide; REQ-002-PRS-NF002, REQ-003-PRS-NF002, REQ-004-PRS-NF001)."""

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def script(name: str, *arguments: str | Path) -> str:
    command = [sys.executable, str(ROOT / "scripts" / name), *map(str, arguments)]
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout  # noqa: S603


def report(directory: Path, tmp_path: Path) -> tuple[str, dict[str, dict[str, str]]]:
    tsv = tmp_path / "report.tsv"
    summary = script("corpus_report.py", directory, tsv)
    with tsv.open(encoding="utf-8", newline="") as file:
        rows = {row["path"]: row for row in csv.DictReader(file, delimiter="\t")}
    return summary, rows


def test_corpus_report_on_the_vendored_pdfs(tmp_path: Path) -> None:
    summary, rows = report(ROOT / "tests/data/zugferd-corpus", tmp_path)
    assert "8 files" in summary
    assert "crashes: 0" in summary
    fail = "ZUGFeRDv2/fail/Mustangproject/"
    assert rows[f"{fail}wrongFilename.pdf"]["extract"].startswith("refused: the PDF holds no")
    v1 = "ZUGFeRDv1/correct/Mustangproject/MustangGnuaccountingBeispielRE-20170509_505.pdf"
    assert "ZUGFeRD 1.0" in rows[v1]["read"]
    valid = rows["ZUGFeRDv2/correct/Mustangproject/MustangGnuaccountingBeispielRE-20201121_508.pdf"]
    assert (valid["read"], valid["kosit"], valid["agree"]) == ("ok", "ok", "yes")
    assert valid["specification_id"] == "urn:cen.eu:en16931:2017"


def test_corpus_report_on_the_kosit_suite(tmp_path: Path) -> None:
    summary, rows = report(ROOT / "tests/data/kosit-testsuite", tmp_path)
    assert len(rows) == 86
    assert {row["agree"] for row in rows.values()} == {"yes"}
    assert {row["validation"] for row in rows.values()} == {"valid"}
    assert "crashes: 0" in summary


def test_benchmark_without_the_corpus() -> None:
    output = script("benchmark.py")
    assert output.startswith("Machine: ")
    table = [line for line in output.splitlines() if line.startswith("| REQ-")]
    requirements = {line.split(" | ")[0].removeprefix("| ") for line in table}
    assert requirements == {"REQ-002-PRS-NF002", "REQ-003-PRS-NF002", "REQ-004-PRS-NF001"}
    assert sum("First validation in a fresh process" in line for line in table) == 7
    assert sum(line.endswith("| skipped: no corpus clone |") for line in table) == 4

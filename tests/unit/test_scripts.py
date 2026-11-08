"""The scripts in `scripts/`, run on the vendored files: the corpus report, the term report and
the benchmark (development guide; REQ-002-PRS-NF002, REQ-003-PRS-NF002, REQ-004-PRS-NF001)."""

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


def term_rows(output: str) -> dict[str, list[str]]:
    """The term report's rows by business term ID."""
    rows = [line.strip("|").split("|") for line in output.splitlines() if line.startswith("| B")]
    return {cells[0].strip(): [cell.strip() for cell in cells[1:]] for cells in rows}


def in_scripts(code: str, *arguments: str) -> str:
    """What Python `code` prints, run in `scripts/`, so that it can import the scripts."""
    command = [sys.executable, "-c", code, *arguments]
    result = subprocess.run(  # noqa: S603
        command, cwd=ROOT / "scripts", capture_output=True, text=True, check=True
    )
    return result.stdout


def held_by_the_model() -> set[str]:
    """The business terms the term report takes as the model's, by its own reading of REQ-001."""
    return set(in_scripts("import term_report; print(*sorted(term_report.held()))").split())


def test_term_report_lists_only_terms_the_model_doesnt_hold() -> None:
    output = script("term_report.py")
    assert "kosit-testsuite: 86 files, 86 read" in output
    rows = term_rows(output)
    held = held_by_the_model()
    assert {"BT-1", "BT-153", "BG-23", "BT-160"} <= held
    assert "BT-125" not in held
    assert rows
    assert not held & set(rows)
    assert rows["BT-125"] == ["Attached document", "BG-24", "32"]


def test_term_report_counts_a_column_per_directory() -> None:
    output = script("term_report.py", ROOT / "tests/data/zugferd-corpus")
    assert "zugferd-corpus: 8 files, " in output
    header = next(line for line in output.splitlines() if line.startswith("| Term"))
    assert header.split("|")[-3:-1] == [" kosit-testsuite ", " zugferd-corpus "]


def carried(directory: Path) -> set[str]:
    """The business terms the term report counts in the files below `directory`, held or not."""
    code = (
        "import sys, term_report; from pathlib import Path;"
        " print(*sorted(term_report.count(Path(sys.argv[1]), {}).carried))"
    )
    return set(in_scripts(code, str(directory)).split())


def test_term_report_leaves_out_xrechnungs_extension(tmp_path: Path) -> None:
    """KoSIT case 04.03a with an item attribute (BT-160) only in a sub-invoice line, a group of
    XRechnung's extension: not counted."""
    name = "04.03a-INVOICE_ubl.xml"
    source = ROOT / "tests/data/kosit-testsuite/instances/extension" / name
    item = b"<cbc:Name>Baustelle einrichten</cbc:Name>"
    attribute = (
        b"<cac:AdditionalItemProperty><cbc:Name>Farbe</cbc:Name><cbc:Value>Rot</cbc:Value>"
        b"</cac:AdditionalItemProperty>"
    )
    data = source.read_bytes()
    assert data.count(item) == 1
    (tmp_path / name).write_bytes(data.replace(item, item + attribute))
    found = carried(tmp_path)
    assert "BT-153" in found
    assert "BT-160" not in found


def test_term_report_counts_files_it_cant_read(tmp_path: Path) -> None:
    (tmp_path / "folder.xml").mkdir()
    (tmp_path / "empty.xml").write_bytes(b"")
    output = script("term_report.py", tmp_path)
    assert f"{tmp_path.name}: 1 files, 0 read, 1 refused" in output


def test_term_report_refuses_a_missing_directory(tmp_path: Path) -> None:
    command = [sys.executable, str(ROOT / "scripts/term_report.py"), str(tmp_path / "missing")]
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    assert result.returncode == 2
    assert f"{tmp_path / 'missing'} is not a directory" in result.stderr
    assert result.stdout == ""


def test_benchmark_without_the_corpus() -> None:
    output = script("benchmark.py")
    assert output.startswith("Machine: ")
    table = [line for line in output.splitlines() if line.startswith("| REQ-")]
    requirements = {line.split(" | ")[0].removeprefix("| ") for line in table}
    assert requirements == {"REQ-002-PRS-NF002", "REQ-003-PRS-NF002", "REQ-004-PRS-NF001"}
    assert sum("First validation in a fresh process" in line for line in table) == 15
    assert sum(line.endswith("| skipped: no corpus clone |") for line in table) == 5


def test_corpus_report_counts_crashes_by_outcome_only(tmp_path: Path) -> None:
    corpus = tmp_path / "CRASH"
    corpus.mkdir()
    source = ROOT / "tests/data/kosit-testsuite/instances/standard/01.01a-INVOICE_uncefact.xml"
    (corpus / "CRASH.xml").write_bytes(source.read_bytes())
    summary, _ = report(corpus, tmp_path)
    assert "crashes: 0" in summary

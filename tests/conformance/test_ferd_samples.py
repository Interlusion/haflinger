"""FeRD's sample invoices, from the maintainer's copy of the ZUGFeRD package: no terms name the
samples, so they aren't vendored (ITEM-002). Skipped unless HAFLINGER_FERD_PACKAGE names the
unpacked package (REQ-002-PRS-F007, REQ-003-PRS-F003, REQ-003-PRS-F007)."""

import os
from pathlib import Path

import pytest

from haflinger import read_invoice, validate
from haflinger.pdf import extract_xml

PACKAGE = Path(os.environ.get("HAFLINGER_FERD_PACKAGE", "/nonexistent"))
EXAMPLES = PACKAGE / "Examples"
PROFILES = ["0. MINIMUM", "1. BASIC WL", "2. BASIC", "3. EN16931", "4. EXTENDED"]
SAMPLES = sorted(path for profile in PROFILES for path in (EXAMPLES / profile).glob("*/*.xml"))

pytestmark = pytest.mark.skipif(
    not EXAMPLES.is_dir(), reason="HAFLINGER_FERD_PACKAGE names no unpacked ZUGFeRD package"
)


def name(path: Path) -> str:
    return f"{path.parent.parent.name}/{path.name}"


@pytest.mark.parametrize("path", SAMPLES, ids=name)
def test_every_sample_is_valid_with_its_profiles_rules(path: Path) -> None:
    findings = validate(path.read_bytes())
    assert [f for f in findings if f.flag in ("fatal", "error")] == []
    assert "HAFL-PROFILE" not in {finding.rule for finding in findings}


@pytest.mark.parametrize("path", SAMPLES, ids=name)
def test_every_sample_reads_like_its_pdf(path: Path) -> None:
    """The PDF next to each XML embeds it: the model read from the PDF is that of the XML."""
    pdfs = sorted(path.parent.glob("*.pdf"))
    xml = path.read_bytes()
    for pdf in pdfs:
        data = pdf.read_bytes()
        if extract_xml(data) == xml:
            assert read_invoice(data) == read_invoice(xml)
            return
    pytest.skip(f"no PDF next to {path.name} embeds it")


@pytest.mark.parametrize("profile", PROFILES[:2])
def test_minimum_and_basic_wl_read_without_lines(profile: str) -> None:
    """REQ-003-PRS-F003: what EN 16931 requires but the profile leaves out is missing, without a
    refusal or a finding."""
    for path in (EXAMPLES / profile).glob("*/*.xml"):
        result = read_invoice(path.read_bytes())
        assert result.invoice.lines == ()
        assert result.findings == ()
        assert result.invoice.totals is not None

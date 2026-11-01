"""Running stylesheets with Saxon: only local files are opened (REQ-001-PRS-NF001, ADR-006)."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from haflinger import InvoiceReadError, _saxon

LOCAL = """<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="3.0">
  <xsl:template match="/"><r><xsl:value-of select="count(doc('local.xml')/*)"/></r></xsl:template>
</xsl:stylesheet>"""
REMOTE = """<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="3.0">
  <xsl:template match="/"><r><xsl:copy-of select="doc('http://127.0.0.1:9/x.xml')"/></r></xsl:template>
</xsl:stylesheet>"""


@pytest.fixture
def artefacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Stylesheets of the test's own in place of the vendored artefacts."""
    (tmp_path / "local.xsl").write_text(LOCAL, encoding="utf-8")
    (tmp_path / "remote.xsl").write_text(REMOTE, encoding="utf-8")
    (tmp_path / "local.xml").write_text("<a/>", encoding="utf-8")
    monkeypatch.setattr(_saxon, "ARTEFACTS", tmp_path)
    _saxon.clear_caches()
    yield tmp_path
    monkeypatch.undo()
    _saxon.clear_caches()


def test_a_stylesheet_reads_local_files(artefacts: Path) -> None:
    (result,) = _saxon.transform(b"<x/>", "local.xsl")
    assert result.endswith(b"<r>1</r>")


def test_a_stylesheet_fetches_no_url(artefacts: Path) -> None:
    """Refused by Saxon before any connection, not failed by one."""
    with pytest.raises(InvoiceReadError, match="has been prohibited"):
        _saxon.transform(b"<x/>", "remote.xsl")

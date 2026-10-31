"""ZUGFeRD PDFs: extracting, reading and embedding (REQ-003-PRS-F006, REQ-003-PRS-F007,
REQ-003-PRS-NF001, REQ-003-PRS-NF003, REQ-004-PRS-F007)."""

import contextlib
import io
import os
import random
import re
import shutil
import subprocess
import sys
import time
import tracemalloc
import zlib
from dataclasses import replace
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from haflinger import InvoiceReadError, InvoiceWriteError, ReadResult, read_invoice, write_cii
from haflinger.pdf import embed, extract_xml

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/data/zugferd-corpus"
MUSTANG = CORPUS / "ZUGFeRDv2/correct/Mustangproject"
FAIL = CORPUS / "ZUGFeRDv2/fail"
PDFA = next((ROOT / "tests/data/verapdf-corpus").rglob("*.pdf")).read_bytes()
SUITE = ROOT / "tests/data/kosit-testsuite/instances/standard"
CII = (SUITE / "01.01a-INVOICE_uncefact.xml").read_bytes()
UBL = (SUITE / "01.01a-INVOICE_ubl.xml").read_bytes()
EN16931 = "urn:cen.eu:en16931:2017"
INVOICE = replace(read_invoice(CII).invoice, specification_id=EN16931)
XML = write_cii(INVOICE)

VALID = sorted(MUSTANG.glob("*.pdf"))


def attached(name: str, data: bytes, base: bytes = PDFA) -> bytes:
    """`base` with `data` embedded as `name`, by pypdf."""
    writer = PdfWriter(clone_from=io.BytesIO(base))
    writer.add_attachment(name, data)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def raw_pdf(*objects: bytes) -> bytes:
    """A PDF of the given objects, numbered from 1; object 1 is the catalogue."""
    body = b"%PDF-1.7\n"
    offsets: list[int] = []
    for number, content in enumerate(objects, start=1):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % number + content + b"\nendobj\n"
    xref = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    body += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    body += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return body


def with_embedded_stream(name: bytes, stream: bytes, dictionary: bytes = b"") -> bytes:
    """A PDF whose only embedded file is `name`, with the given stream data and entries."""
    return raw_pdf(
        b"<< /Type /Catalog /Pages 2 0 R /Names << /EmbeddedFiles 3 0 R >> >>",
        b"<< /Type /Pages /Kids [] /Count 0 >>",
        b"<< /Names [(" + name + b") 4 0 R] >>",
        b"<< /Type /Filespec /F (" + name + b") /UF (" + name + b") /EF << /F 5 0 R >> >>",
        b"<< /Type /EmbeddedFile /Length %d " % len(stream)
        + dictionary
        + b">>\nstream\n"
        + stream
        + b"\nendstream",
    )


# REQ-003-PRS-F007: extracting and reading


@pytest.mark.parametrize("path", VALID, ids=lambda path: path.name)
def test_extracts_the_embedded_invoice_byte_for_byte(path: Path) -> None:
    data = path.read_bytes()
    (embedded,) = [
        content
        for name, contents in PdfReader(path).attachments.items()
        for content in contents
        if name in ("factur-x.xml", "zugferd-invoice.xml")
    ]
    assert extract_xml(data) == embedded
    assert read_invoice(data) == read_invoice(embedded)


def test_keeps_a_byte_order_mark() -> None:
    data = (MUSTANG / "MustangGnuaccountingBeispielRE-20201121_508_withBOM.pdf").read_bytes()
    assert extract_xml(data).startswith(b"\xef\xbb\xbf<?xml")


def test_reads_ubl_embedded_as_xrechnung() -> None:
    result = read_invoice(attached("xrechnung.xml", UBL))
    assert result.invoice.syntax == "ubl"
    assert result == read_invoice(UBL)


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"%PDF-1.7\nnot a PDF", "the input isn't a readable PDF"),
        (
            (FAIL / "Mustangproject/wrongFilename.pdf").read_bytes(),
            "its embedded files: factur-y.xml",
        ),
        (
            (FAIL / "MustangRE-20171118_506_ZUGFeRD1and2.pdf").read_bytes(),
            "more than one invoice: ZUGFeRD-invoice.xml, factur-x.xml",
        ),
        (
            with_embedded_stream(b"factur-x.xml", XML.hex().encode(), b"/Filter /ASCIIHexDecode "),
            "encoded with /ASCIIHexDecode",
        ),
        (
            with_embedded_stream(
                b"factur-x.xml", zlib.compress(XML)[:-20], b"/Filter /FlateDecode "
            ),
            "cut off",
        ),
    ],
    ids=["unreadable", "no-invoice", "two-invoices", "other-filter", "cut-off"],
)
def test_extract_refusals(data: bytes, reason: str) -> None:
    with pytest.raises(InvoiceReadError, match=re.escape(reason)):
        extract_xml(data)


def test_extract_refuses_more_than_max_size() -> None:
    data = VALID[0].read_bytes()
    with pytest.raises(InvoiceReadError, match="larger than max_size"):
        extract_xml(data, max_size=len(data) - 1)


# REQ-003-PRS-F006: refusals of read_invoice for PDFs


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        (
            CORPUS
            / "ZUGFeRDv1/correct/Mustangproject/MustangGnuaccountingBeispielRE-20170509_505.pdf",
            "the PDF's embedded invoice: the input is a ZUGFeRD 1.0 invoice",
        ),
        (
            FAIL / "Mustangproject/factur-x-invalid-xml-encoding-attribute.pdf",
            "the PDF's embedded invoice: the input is not well-formed XML",
        ),
    ],
    ids=["zugferd-1.0", "not-xml"],
)
def test_read_refusals(path: Path, reason: str) -> None:
    with pytest.raises(InvoiceReadError, match=re.escape(reason)):
        read_invoice(path.read_bytes())


def test_without_the_extra() -> None:
    """`read_invoice` refuses a PDF, naming the extra; importing `haflinger.pdf` fails, naming
    it too."""
    script = f"""
import sys
sys.modules["pypdf"] = None
sys.modules["facturx"] = None
import haflinger
try:
    haflinger.read_invoice(open({str(VALID[0])!r}, "rb").read())
except haflinger.InvoiceReadError as error:
    assert "needs the extra 'pdf'" in str(error), error
else:
    raise AssertionError("read")
try:
    import haflinger.pdf
except ImportError as error:
    assert "needs the extra 'pdf'" in str(error), error
else:
    raise AssertionError("imported")
"""
    subprocess.run([sys.executable, "-c", script], check=True)  # noqa: S603


# REQ-003-PRS-NF001


def test_an_embedded_file_counts_against_max_size_as_it_is_inflated() -> None:
    """A PDF of a few kB whose embedded file inflates to 64 MiB is refused with max_size 1 MiB,
    without inflating more than that."""
    bomb = zlib.compressobj(9)
    stream = b"".join(bomb.compress(bytes(1024 * 1024)) for _ in range(64)) + bomb.flush()
    data = with_embedded_stream(b"factur-x.xml", stream, b"/Filter /FlateDecode ")
    assert len(data) < 1024 * 1024
    tracemalloc.start()
    try:
        with pytest.raises(InvoiceReadError, match="larger than max_size"):
            extract_xml(data, max_size=1024 * 1024)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 8 * 1024 * 1024


# REQ-003-PRS-NF003


@pytest.mark.parametrize("path", sorted(CORPUS.rglob("*.pdf")), ids=lambda path: path.name)
def test_every_corpus_pdf_reads_or_is_refused(path: Path) -> None:
    with contextlib.suppress(InvoiceReadError):
        read_invoice(path.read_bytes())


@pytest.mark.parametrize("cut", [0.1, 0.5, 0.99])
def test_a_truncated_pdf_is_refused(cut: float) -> None:
    data = VALID[0].read_bytes()
    with pytest.raises(InvoiceReadError):
        read_invoice(data[: int(len(data) * cut)])


def test_an_embedded_file_that_isnt_xml_is_refused() -> None:
    with pytest.raises(InvoiceReadError, match="not well-formed XML"):
        read_invoice(attached("factur-x.xml", b"%%not XML"))


@pytest.mark.parametrize(
    "data",
    [
        raw_pdf(
            b"<< /Type /Catalog /Names << /EmbeddedFiles 2 0 R >> >>",
            b"<< /Kids [" + b"[" * 100_000 + b"]" * 100_000 + b"] >>",
        ),
        raw_pdf(
            b"<< /Type /Catalog /Names << /EmbeddedFiles 2 0 R >> >>",
            *(b"<< /Kids [%d 0 R] >>" % (number + 1) for number in range(2, 200)),
            b"<< /Names [] >>",
        ),
    ],
    ids=["nested-arrays", "nested-name-tree"],
)
def test_deeply_nested_objects_are_refused(data: bytes) -> None:
    with pytest.raises(InvoiceReadError):
        read_invoice(data)


def test_mutated_pdfs_read_or_are_refused_in_time() -> None:
    """Random bytes changed in copies of the test PDFs: each read gives a result or
    `InvoiceReadError`, within 5 s."""
    generator = random.Random(20261031)  # noqa: S311 - a reproducible fuzz test
    bases = [path.read_bytes() for path in VALID] + [embed(PDFA, XML)]
    for _ in range(1000):
        data = bytearray(generator.choice(bases))
        for _ in range(generator.randint(1, 20)):
            data[generator.randrange(len(data))] = generator.randrange(256)
        start = time.monotonic()
        with contextlib.suppress(InvoiceReadError):
            assert isinstance(read_invoice(bytes(data)), ReadResult)
        assert time.monotonic() - start < 5


# REQ-004-PRS-F007: embedding


def test_embeds_an_invoice_into_a_pdfa_file() -> None:
    result = embed(PDFA, XML)
    assert extract_xml(result) == XML
    assert read_invoice(result).invoice == INVOICE
    reader, original = PdfReader(io.BytesIO(result)), PdfReader(io.BytesIO(PDFA))
    assert len(reader.pages) == len(original.pages)
    for page, before in zip(reader.pages, original.pages, strict=True):
        contents, original_contents = page.get_contents(), before.get_contents()
        assert contents is not None
        assert original_contents is not None
        assert contents.get_data() == original_contents.get_data()
    xmp = reader.xmp_metadata
    assert xmp is not None
    text = xmp.stream.get_data().decode()
    assert re.search(r"pdfaid:part(>|=\")3", text)
    assert re.search(r"fx:ConformanceLevel>EN 16931<|fx:ConformanceLevel=\"EN 16931\"", text)
    assert re.search(
        r"fx:DocumentFileName>factur-x.xml<|fx:DocumentFileName=\"factur-x.xml\"", text
    )


def verapdf() -> str | None:
    return os.environ.get("HAFLINGER_VERAPDF") or shutil.which("verapdf")


@pytest.mark.skipif(verapdf() is None, reason="veraPDF isn't installed")
def test_verapdf_finds_the_result_pdfa_3(tmp_path: Path) -> None:
    """veraPDF, the reference PDF/A validator, as the oracle; it runs where it is installed (on
    PATH, or named by HAFLINGER_VERAPDF)."""
    path = tmp_path / "invoice.pdf"
    path.write_bytes(embed(PDFA, XML))
    command = [str(verapdf()), "--flavour", "3b", "--format", "text", str(path)]
    output = subprocess.run(command, capture_output=True, text=True, check=False).stdout  # noqa: S603
    assert output.startswith("PASS"), output


@pytest.mark.parametrize(
    ("pdf", "xml", "reason"),
    [
        (b"%PDF-1.7\nnot a PDF", XML, "the PDF isn't readable"),
        (
            attached(
                "readme.txt",
                b"x",
                base=raw_pdf(
                    b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [] /Count 0 >>"
                ),
            ),
            XML,
            "the input must be PDF/A",
        ),
        (PDFA, CII, "embed writes only CII invoices with BT-24 urn:cen.eu:en16931:2017"),
        (PDFA, UBL, "this is ubl-invoice"),
        (PDFA, b"<Invoice", "the XML can't be read"),
    ],
    ids=["unreadable-pdf", "not-pdfa", "xrechnung", "ubl", "not-xml"],
)
def test_embed_refusals(pdf: bytes, xml: bytes, reason: str) -> None:
    with pytest.raises(InvoiceWriteError, match=re.escape(reason)):
        embed(pdf, xml)


def test_embed_refuses_an_invalid_invoice_with_its_findings() -> None:
    xml = XML.replace(b"<ram:GrandTotalAmount>336.9<", b"<ram:GrandTotalAmount>336.91<")
    with pytest.raises(InvoiceWriteError, match="BR-CO-15") as refusal:
        embed(PDFA, xml)
    assert "BR-CO-15" in {finding.rule for finding in refusal.value.findings}
    assert refusal.value.document == xml


def test_two_embedded_files_of_one_name_are_two_invoices() -> None:
    writer = PdfWriter(clone_from=io.BytesIO(PDFA))
    writer.add_attachment("factur-x.xml", XML)
    writer.add_attachment("factur-x.xml", b"<other/>")
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(
        InvoiceReadError, match=re.escape("more than one invoice: factur-x.xml, factur-x.xml")
    ):
        extract_xml(output.getvalue())


def test_embed_refuses_xml_the_schema_check_cant_parse() -> None:
    """lxml knows no encoding `latin_1`, which defusedxml accepts: a finding, not lxml's error."""
    xml = XML.replace(b'encoding="UTF-8"', b'encoding="latin_1"', 1)
    with pytest.raises(InvoiceWriteError) as refusal:
        embed(PDFA, xml)
    assert "HAFL-XSD" in {finding.rule for finding in refusal.value.findings}


def test_embed_checks_the_pdf_before_the_invoice() -> None:
    """A PDF that isn't PDF/A is refused without the seconds a validation can take."""
    plain = raw_pdf(b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [] /Count 0 >>")
    invalid = XML.replace(b"<ram:GrandTotalAmount>336.9<", b"<ram:GrandTotalAmount>336.91<")
    with pytest.raises(InvoiceWriteError, match="the input must be PDF/A"):
        embed(plain, invalid)

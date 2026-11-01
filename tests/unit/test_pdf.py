"""ZUGFeRD PDFs: extracting, reading and embedding (REQ-003-PRS-F006, REQ-003-PRS-F007,
REQ-003-PRS-NF001, REQ-003-PRS-NF003, REQ-004-PRS-F007)."""

import contextlib
import io
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import time
import tracemalloc
import zlib
from dataclasses import replace
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

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


# The second review of 2026-11-01


def incrementally_updated(base: bytes) -> bytes:
    """`base` with two incremental updates: a 200 kB stream added to the catalogue, then removed."""
    writer = PdfWriter(io.BytesIO(base), incremental=True)
    stream = DecodedStreamObject()
    stream.set_data(bytes(range(256)) * 800)
    writer._root_object[NameObject("/Junk")] = writer._add_object(stream)  # pyright: ignore[reportPrivateUsage]
    first = io.BytesIO()
    writer.write(first)
    writer = PdfWriter(io.BytesIO(first.getvalue()), incremental=True)
    del writer._root_object["/Junk"]  # pyright: ignore[reportPrivateUsage]
    second = io.BytesIO()
    writer.write(second)
    return second.getvalue()


def test_embed_into_an_incrementally_updated_pdf() -> None:
    """REQ-004-PRS-F007: the result is one PDF that a strict reader reads."""
    result = embed(incrementally_updated(PDFA), XML)
    assert result.count(b"%PDF-") == 1
    reader = PdfReader(io.BytesIO(result), strict=True)
    assert list(reader.attachments) == ["factur-x.xml"]
    assert extract_xml(result) == XML


@pytest.mark.parametrize(
    ("pdf", "reason"),
    [
        (attached("timesheet.csv", b"a;b"), "embedded files or named destinations"),
        (PDFA.replace(b'pdfaid:part="2"', b'pdfaid:part="4"'), "PDF/A-1, -2 or -3"),
    ],
    ids=["other-attachment", "pdfa-4"],
)
def test_embed_refuses_what_it_would_damage(pdf: bytes, reason: str) -> None:
    assert b'pdfaid:part="2"' in PDFA
    with pytest.raises(InvoiceWriteError, match=re.escape(reason)):
        embed(pdf, XML)


@pytest.mark.parametrize(
    ("pdf", "xml"), [(PDFA, None), (PDFA, XML.decode()), (None, XML), (bytearray(PDFA), XML)]
)
def test_embed_refuses_arguments_that_arent_bytes(pdf: object, xml: object) -> None:
    with pytest.raises(InvoiceWriteError, match="bytes"):
        embed(pdf, xml)  # type: ignore[arg-type]


@pytest.mark.parametrize("data", [None, "%PDF-1.7", bytearray(b"%PDF-1.7")])
def test_extract_refuses_arguments_that_arent_bytes(data: object) -> None:
    with pytest.raises(InvoiceReadError, match="bytes"):
        extract_xml(data)  # type: ignore[arg-type]


@pytest.mark.parametrize("parameters", [b"/DecodeParms null ", b"/DecodeParms << >> "])
def test_extract_takes_flate_with_empty_parameters(parameters: bytes) -> None:
    data = with_embedded_stream(
        b"factur-x.xml", zlib.compress(XML), b"/Filter /FlateDecode " + parameters
    )
    assert extract_xml(data) == XML


def object_stream_bomb(entries: int, size: int) -> bytes:
    """A PDF whose tree of embedded files has `entries` kids, each in an object stream of its own
    that inflates to `size` bytes."""
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Names 2 0 R >>",
        2: b"<< /EmbeddedFiles 3 0 R >>",
        3: b"<< /Kids [" + b" ".join(b"%d 0 R" % (100 + i) for i in range(entries)) + b"] >>",
    }
    in_streams: dict[int, int] = {}
    for i in range(entries):
        header = b"%d 0 " % (100 + i)
        payload = header + b"<< /Names [] >>"
        packed = zlib.compress(payload + b" " * (size - len(payload)), 9)
        objects[1000 + i] = (
            b"<< /Type /ObjStm /N 1 /First %d /Filter /FlateDecode /Length %d >>\nstream\n"
            % (len(header), len(packed))
            + packed
            + b"\nendstream"
        )
        in_streams[100 + i] = 1000 + i
    body = bytearray(b"%PDF-1.7\n")
    offsets: dict[int, int] = {}
    for number, content in objects.items():
        offsets[number] = len(body)
        body += b"%d 0 obj\n" % number + content + b"\nendobj\n"
    xref = 1000 + entries
    offsets[xref] = len(body)
    rows = {0: (0, 0, 65535)} | {n: (1, o, 0) for n, o in offsets.items()}
    rows |= {n: (2, s, 0) for n, s in in_streams.items()}
    numbers = sorted(rows)
    table = zlib.compress(b"".join(struct.pack(">BIH", *rows[n]) for n in numbers))
    index = b" ".join(b"%d 1" % n for n in numbers)
    body += (
        b"%d 0 obj\n<< /Type /XRef /Size %d /Root 1 0 R /W [1 4 2] /Index [%s] /Filter"
        b" /FlateDecode /Length %d >>\nstream\n"
        % (xref, max(numbers) + 1, index, len(table))
        + table
        + b"\nendstream\nendobj\nstartxref\n%d\n%%%%EOF\n" % offsets[xref]
    )
    return bytes(body)


def test_a_wide_tree_of_embedded_files_is_refused_in_bounds() -> None:
    """REQ-003-PRS-NF003: ten object streams of 20 MB each, behind a PDF of a few kB."""
    data = object_stream_bomb(10, 20_000_000)
    assert len(data) < 1024 * 1024
    tracemalloc.start()
    start = time.monotonic()
    try:
        with pytest.raises(InvoiceReadError):
            extract_xml(data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert time.monotonic() - start < 5
    assert peak < 100 * 1024 * 1024


def test_a_tree_with_thousands_of_entries_is_refused() -> None:
    data = raw_pdf(
        b"<< /Type /Catalog /Names << /EmbeddedFiles 2 0 R >> >>",
        b"<< /Names ["
        + b" ".join(b"(f%d.txt) << /F (f%d.txt) >>" % (i, i) for i in range(5000))
        + b"] >>",
    )
    with pytest.raises(InvoiceReadError, match="entries"):
        extract_xml(data)


def test_read_invoice_hands_max_size_to_the_pdf() -> None:
    """REQ-001-PRS-NF003: a PDF read with a lower max_size limits its embedded file to it."""
    bomb = zlib.compressobj(9)
    stream = b"".join(bomb.compress(bytes(1024 * 1024)) for _ in range(8)) + bomb.flush()
    data = with_embedded_stream(b"factur-x.xml", stream, b"/Filter /FlateDecode ")
    with pytest.raises(InvoiceReadError, match="larger than max_size"):
        read_invoice(data, max_size=1024 * 1024)


def test_fatturapa_inside_a_pdf_is_named() -> None:
    fattura = b'<?xml version="1.0"?><p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"/>'
    with pytest.raises(InvoiceReadError, match="FatturaPA"):
        read_invoice(attached("factur-x.xml", fattura))


def test_an_external_entity_inside_a_pdf_is_refused() -> None:
    """REQ-001-PRS-NF001: the embedded XML is checked before anything parses it."""
    xml = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/hostname">]><x>&e;</x>'
    with pytest.raises(InvoiceReadError, match="document type declaration"):
        read_invoice(attached("factur-x.xml", xml))


def test_a_file_specification_pointing_outside_isnt_opened(tmp_path: Path) -> None:
    """A file specification naming a file outside the PDF, without an embedded stream."""
    outside = tmp_path / "factur-x.xml"
    outside.write_bytes(XML)
    data = raw_pdf(
        b"<< /Type /Catalog /Names << /EmbeddedFiles 2 0 R >> >>",
        b"<< /Names [(factur-x.xml) 3 0 R] >>",
        b"<< /Type /Filespec /F (" + str(outside).encode() + b") /UF (factur-x.xml) >>",
    )
    with pytest.raises(InvoiceReadError, match="no embedded file stream"):
        extract_xml(data)
